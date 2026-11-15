"""Runs an exercise's predefined tests against student code, outside the app process.

The Streamlit process never executes student code. Each run goes through these layers:

1. Static check (this file). Parse the code without running it. Report syntax
   errors, and turn away imports and built-ins an introductory exercise doesn't
   need, with a message the student can act on. This layer is for the student,
   not for security: it can be bypassed.
2. Separate process. A fresh interpreter (`python -I -S -B`) in a new temporary
   folder, with an emptied environment (so no secrets), no stdin, and its own
   session so the whole process group can be killed.
3. Resource limits and timers (in _harness.py). CPU time, file size, open files,
   a timer per test and a wall-clock limit for the whole run.
4. Runtime audit hook (in _harness.py). Refuses process creation, sockets,
   native code loading and file access outside the run folder.
5. OS sandbox (macOS only). sandbox-exec denies network access, process creation,
   writes outside the run folder, and reads under /Users.

The expected values stay in this process. The child only reports what the
student's function returned, and comparison happens here.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codementor.exercises import Exercise

HARNESS = Path(__file__).with_name("_harness.py")
MAX_CODE_CHARS = 20_000
SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")

ALLOWED_IMPORTS = {
    "math", "string", "collections", "itertools", "functools", "typing", "re",
    "statistics", "dataclasses", "decimal", "fractions", "operator", "copy",
}
BLOCKED_NAMES = {
    "__import__", "eval", "exec", "compile", "open", "input", "globals", "locals",
    "vars", "breakpoint", "help", "exit", "quit", "getattr", "setattr", "delattr",
    "memoryview",
}

# Status values for a single test.
PASSED, FAILED, ERROR, TIMEOUT, NOT_RUN = "passed", "failed", "error", "timeout", "not_run"
# Status values for a whole run.
COMPLETED = "completed"
SYNTAX_ERROR = "syntax_error"
REJECTED = "rejected"
LOAD_ERROR = "load_error"
RUN_TIMEOUT = "timeout"
RUNNER_ERROR = "runner_error"


def code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]


@dataclass
class TestOutcome:
    __test__ = False  # stop pytest trying to collect this class

    test_id: str
    description: str
    call: str
    expected_repr: str
    status: str
    actual_repr: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    error_line: int | None = None
    output: str = ""

    @property
    def passed(self) -> bool:
        return self.status == PASSED

    def summary(self) -> str:
        """One factual sentence about this test. Used in prompts and on screen."""
        if self.status == PASSED:
            return f"{self.call} returned {self.actual_repr}, as expected."
        if self.status == FAILED:
            return f"{self.call} should return {self.expected_repr} but returned {self.actual_repr}."
        if self.status == ERROR:
            where = f" (line {self.error_line})" if self.error_line else ""
            return f"{self.call} raised {self.error_type}: {self.error_message}{where}."
        if self.status == TIMEOUT:
            return f"{self.call} did not finish within the time limit (possible infinite loop)."
        return f"{self.call} was not run."


@dataclass
class RunResult:
    code: str
    code_hash: str
    status: str
    outcomes: list[TestOutcome] = field(default_factory=list)
    message: str | None = None
    error_line: int | None = None
    isolation: str = ""
    duration_s: float = 0.0

    @property
    def passed_ids(self) -> set[str]:
        return {o.test_id for o in self.outcomes if o.passed}

    @property
    def failing_ids(self) -> frozenset[str]:
        """Tests that ran and did not pass. Empty when nothing ran."""
        return frozenset(o.test_id for o in self.outcomes if o.status in (FAILED, ERROR, TIMEOUT))

    @property
    def all_passed(self) -> bool:
        return self.status == COMPLETED and bool(self.outcomes) and all(o.passed for o in self.outcomes)

    @property
    def run_level_id(self) -> str | None:
        """Evidence id for a problem that stopped the tests running at all."""
        return {SYNTAX_ERROR: "SYNTAX", LOAD_ERROR: "LOAD", RUN_TIMEOUT: "TIMEOUT",
                REJECTED: "REJECTED"}.get(self.status)

    def evidence(self) -> dict[str, tuple[str, str]]:
        """Every observable fact from this run: evidence id -> (status, sentence)."""
        items: dict[str, tuple[str, str]] = {}
        if self.run_level_id:
            items[self.run_level_id] = (self.status, self.message or "")
        for o in self.outcomes:
            items[o.test_id] = (o.status, o.summary())
        return items

    def outcome(self, test_id: str) -> TestOutcome | None:
        return next((o for o in self.outcomes if o.test_id == test_id), None)


def values_match(expected: Any, actual: Any) -> bool:
    """Equality with a float tolerance, and strict about bool vs int (True is not 1)."""
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(expected) is type(actual) and expected == actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isclose(expected, actual, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(expected, list) and isinstance(actual, list):
        return len(expected) == len(actual) and all(values_match(e, a) for e, a in zip(expected, actual))
    if isinstance(expected, dict) and isinstance(actual, dict):
        return expected.keys() == actual.keys() and all(values_match(expected[k], actual[k]) for k in expected)
    return type(expected) is type(actual) and expected == actual


def _parse_value(text: str) -> tuple[bool, Any]:
    """Turn the child's repr() back into a value without executing anything."""
    try:
        return True, ast.literal_eval(text)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return False, None


def check_code(tree: ast.AST, function_name: str) -> list[str]:
    """Static check: problems that stop the code being run, phrased for the student."""
    problems = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", "?")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                if name.split(".")[0] not in ALLOWED_IMPORTS:
                    problems.append(f"Line {line}: importing '{name}' isn't allowed in these exercises.")
        elif isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            problems.append(f"Line {line}: '{node.id}' isn't available in these exercises.")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr.endswith("__"):
            problems.append(f"Line {line}: special attributes like '{node.attr}' aren't allowed.")
    defined = {n.name for n in getattr(tree, "body", []) if isinstance(n, ast.FunctionDef)}
    if function_name not in defined:
        problems.append(f"Your code needs to define a function called {function_name}.")
    return problems


class TestRunner:
    __test__ = False

    def __init__(self, per_test_timeout: float = 0.5, wall_timeout: float = 8.0,
                 cpu_seconds: int = 4, use_os_sandbox: bool | None = None):
        self.per_test_timeout = per_test_timeout
        self.wall_timeout = wall_timeout
        self.cpu_seconds = cpu_seconds
        if use_os_sandbox is None:
            use_os_sandbox = sys.platform == "darwin" and SANDBOX_EXEC.exists()
        self.use_os_sandbox = use_os_sandbox
        self.python = self._base_interpreter()

    @property
    def isolation(self) -> str:
        return "macOS sandbox + process limits" if self.use_os_sandbox else "process limits only"

    @staticmethod
    def _base_interpreter() -> str:
        # Outside the virtual environment, so the child sees only the standard library.
        candidate = getattr(sys, "_base_executable", None) or sys.executable
        return candidate if os.path.exists(candidate) else sys.executable

    def _sandbox_profile(self, workdir: str) -> str:
        prefixes = sorted({os.path.realpath(p) for p in (sys.base_prefix, sys.prefix,
                                                         os.path.dirname(self.python))})
        allow_exec = "\n".join(f'(allow process-exec (subpath "{p}"))' for p in prefixes)
        allow_read = "\n".join(f'(allow file-read* (subpath "{p}"))' for p in prefixes)
        return f"""(version 1)
(allow default)
(deny network*)
(deny process-fork)
(deny process-exec)
{allow_exec}
(deny file-write*)
(allow file-write* (subpath "{workdir}"))
(allow file-write-data (literal "/dev/null"))
(deny file-read* (subpath "/Users"))
{allow_read}
(allow file-read* (subpath "{workdir}"))
"""

    def run(self, exercise: Exercise, code: str, precheck: bool = True) -> RunResult:
        """Run every test. `precheck=False` exists only so tests can probe the deeper layers."""
        started = time.monotonic()
        result = RunResult(code=code, code_hash=code_hash(code), status=COMPLETED,
                           isolation=self.isolation)

        if len(code) > MAX_CODE_CHARS:
            result.status, result.message = REJECTED, f"The code is longer than {MAX_CODE_CHARS} characters."
            return result
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError) as exc:
            result.status = SYNTAX_ERROR
            result.error_line = getattr(exc, "lineno", None)
            where = f" on line {result.error_line}" if result.error_line else ""
            result.message = f"Python could not read the code: {getattr(exc, 'msg', str(exc))}{where}."
            return result
        if precheck:
            problems = check_code(tree, exercise.function_name)
            if problems:
                result.status, result.message = REJECTED, " ".join(problems)
                return result

        workdir = os.path.realpath(tempfile.mkdtemp(prefix="codementor-"))
        try:
            self._execute(exercise, code, workdir, result)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        result.duration_s = round(time.monotonic() - started, 3)
        return result

    def _execute(self, exercise: Exercise, code: str, workdir: str, result: RunResult) -> None:
        Path(workdir, "student.py").write_text(code, encoding="utf-8")
        shutil.copy(HARNESS, Path(workdir, "harness.py"))
        payload = {
            "function_name": exercise.function_name,
            "tests": [{"id": t.id, "args": list(t.args)} for t in exercise.tests],
            "per_test_timeout": self.per_test_timeout,
            "max_output_chars": 2000,
            "limits": {"cpu_seconds": self.cpu_seconds, "file_bytes": 2 * 1024 * 1024,
                       "memory_bytes": 512 * 1024 * 1024},
        }
        Path(workdir, "payload.json").write_text(json.dumps(payload), encoding="utf-8")

        command = [self.python, "-I", "-S", "-B", "harness.py"]
        if self.use_os_sandbox:
            command = [str(SANDBOX_EXEC), "-p", self._sandbox_profile(workdir), *command]
        env = {"PATH": "/usr/bin:/bin", "HOME": workdir, "LANG": "en_US.UTF-8"}

        timed_out = False
        with open(Path(workdir, "stderr.txt"), "wb") as stderr:
            proc = subprocess.Popen(command, cwd=workdir, env=env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=stderr,
                                    start_new_session=True)
            try:
                proc.wait(timeout=self.wall_timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()

        raw = self._read_result(workdir)
        if raw is None:
            result.status = RUN_TIMEOUT if timed_out or proc.returncode in (-signal.SIGXCPU, -signal.SIGKILL) else RUNNER_ERROR
            result.message = ("The code did not finish within the time limit."
                              if result.status == RUN_TIMEOUT else
                              "The test runner failed before any test ran.")
            result.outcomes = [self._outcome(exercise, t, None) for t in exercise.tests]
            return

        if raw["load_error"]:
            err = raw["load_error"]
            result.status = LOAD_ERROR
            result.error_line = err.get("line")
            where = f" (line {result.error_line})" if result.error_line else ""
            result.message = f"Running the file raised {err['type']}: {err['message']}{where}, before any test could run."
            result.outcomes = [self._outcome(exercise, t, None) for t in exercise.tests]
            return

        by_id = {entry["id"]: entry for entry in raw["results"]}
        stopped = timed_out or proc.returncode != 0
        first_missing = True
        for test in exercise.tests:
            entry = by_id.get(test.id)
            if entry is None and stopped and first_missing:
                entry, first_missing = {"status": "timeout"}, False  # the test that was running when killed
            result.outcomes.append(self._outcome(exercise, test, entry))
        if stopped:
            result.status = RUN_TIMEOUT
            result.message = "The run was stopped at the time limit; later tests did not run."

    @staticmethod
    def _read_result(workdir: str) -> dict | None:
        path = Path(workdir, "result.json")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    @staticmethod
    def _outcome(exercise: Exercise, test, entry: dict | None) -> TestOutcome:
        outcome = TestOutcome(test_id=test.id, description=test.description,
                              call=test.call(exercise.function_name),
                              expected_repr=repr(test.expected), status=NOT_RUN)
        if entry is None:
            return outcome
        outcome.output = entry.get("output", "")
        if entry["status"] == "timeout":
            outcome.status = TIMEOUT
        elif entry["status"] == "error":
            err = entry["error"]
            outcome.status = ERROR
            outcome.error_type, outcome.error_message, outcome.error_line = err["type"], err["message"], err["line"]
        else:
            outcome.actual_repr = entry["value"]
            parsed, value = _parse_value(entry["value"])
            outcome.status = PASSED if parsed and values_match(test.expected, value) else FAILED
        return outcome
