"""Child-side test harness. It runs inside the restricted process, never in the app.

runner.py copies this file into a fresh temporary folder next to student.py and
payload.json, then starts a separate Python interpreter on it. It uses only the
standard library and must not import anything from codementor.

What it does:
1. Sets resource limits (CPU time, file size, open files, memory where the OS allows).
2. Installs an audit hook that refuses process creation, network access, native
   code loading and file access outside this folder and the standard library.
3. Loads student.py, calls the function once per test with a per-test timer, and
   writes each result to result.json as it goes.

The expected values are never sent here. The parent process compares results,
so student code cannot read or change what counts as a pass.
"""

import builtins
import copy
import json
import os
import resource
import signal
import sys

RESULT_FILE = "result.json"
STUDENT_FILE = "student.py"
MAX_REPR = 1000
MAX_MESSAGE = 300


class TestTimeout(BaseException):
    """Raised by the per-test timer. A BaseException, so `except Exception` won't swallow it."""


class CappedWriter:
    """Stands in for stdout/stderr and keeps only the first `limit` characters printed."""

    def __init__(self, limit):
        self.limit = limit
        self.parts = []
        self.size = 0

    def write(self, text):
        text = str(text)
        room = self.limit - self.size
        if room > 0:
            self.parts.append(text[:room])
        self.size += len(text)
        return len(text)

    def flush(self):
        pass

    def take(self):
        value = "".join(self.parts)
        if self.size > self.limit:
            value += "\n[output truncated]"
        self.parts, self.size = [], 0
        return value


def set_limits(limits):
    def cap(kind, value):
        try:
            resource.setrlimit(kind, (value, value))
        except (ValueError, OSError):
            pass  # not every limit is enforceable on every OS (RLIMIT_AS on macOS)

    cap(resource.RLIMIT_CPU, limits["cpu_seconds"])
    cap(resource.RLIMIT_FSIZE, limits["file_bytes"])
    cap(resource.RLIMIT_NOFILE, 64)
    cap(resource.RLIMIT_AS, limits["memory_bytes"])


def install_audit_hook(workdir):
    """Refuse the operations student code has no reason to perform."""
    workdir = os.path.realpath(workdir)
    readable_roots = [workdir] + sorted(
        {os.path.realpath(p) for p in (sys.prefix, sys.base_prefix, sys.exec_prefix)}
    )
    blocked_events = {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
        "os.kill", "os.killpg", "subprocess.Popen", "socket.__new__", "socket.connect",
        "socket.bind", "socket.getaddrinfo", "ctypes.dlopen", "ctypes.dlsym",
        "builtins.input", "os.chdir", "sys.addaudithook",
    }
    path_events = {
        "os.remove", "os.rename", "os.rmdir", "os.mkdir", "os.chmod", "os.chown",
        "os.symlink", "os.link", "os.truncate", "shutil.rmtree", "shutil.copyfile",
        "shutil.move",
    }
    listing_events = {"os.listdir", "os.scandir"}  # the import system lists stdlib folders
    write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC

    def inside(path, roots):
        if isinstance(path, int):
            return True  # an already-open file descriptor
        if path is None:
            return True
        try:
            real = os.path.realpath(os.fsdecode(path))
        except (TypeError, ValueError):
            return False
        return any(real == root or real.startswith(root + os.sep) for root in roots)

    def hook(event, args):
        if event in blocked_events:
            raise PermissionError(f"{event} is not allowed in CodeMentor exercises")
        if event == "open":
            path, mode, flags = (list(args) + [None, None, None])[:3]
            writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                isinstance(flags, int) and flags & write_flags
            )
            roots = [workdir] if writing else readable_roots
            if not inside(path, roots) and path != "/dev/null":
                raise PermissionError("file access outside the exercise folder is not allowed")
        elif event in path_events:
            if args and not inside(args[0], [workdir]):
                raise PermissionError(f"{event} outside the exercise folder is not allowed")
        elif event in listing_events:
            if args and not inside(args[0], readable_roots):
                raise PermissionError(f"{event} outside the exercise folder is not allowed")

    sys.addaudithook(hook)


def error_line(exc):
    """Line number of the deepest traceback frame inside student.py, if any."""
    line = getattr(exc, "lineno", None) if isinstance(exc, SyntaxError) else None
    tb = exc.__traceback__
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == STUDENT_FILE:
            line = tb.tb_lineno
        tb = tb.tb_next
    return line


def describe(exc):
    return {
        "type": type(exc).__name__,
        "message": str(exc)[:MAX_MESSAGE],
        "line": error_line(exc),
    }


def safe_repr(value):
    try:
        text = repr(value)
    except BaseException as exc:  # a broken __repr__ in student code
        text = f"<unprintable {type(value).__name__}: {type(exc).__name__}>"
    if len(text) > MAX_REPR:
        text = text[:MAX_REPR] + "...[truncated]"
    return text


def write_result(result):
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f)


def on_alarm(signum, frame):
    raise TestTimeout()


def main():
    with open("payload.json", encoding="utf-8") as f:
        payload = json.load(f)
    with open(STUDENT_FILE, encoding="utf-8") as f:
        source = f.read()

    set_limits(payload["limits"])
    signal.signal(signal.SIGALRM, on_alarm)
    install_audit_hook(os.getcwd())

    result = {"load_error": None, "load_output": "", "results": []}
    output = CappedWriter(payload["max_output_chars"])
    real_stdout, real_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = output
    namespace = {"__name__": "student", "__builtins__": builtins}

    try:
        signal.setitimer(signal.ITIMER_REAL, payload["per_test_timeout"])
        exec(compile(source, STUDENT_FILE, "exec"), namespace)
        signal.setitimer(signal.ITIMER_REAL, 0)
    except TestTimeout:
        result["load_error"] = {"type": "TimeoutError", "line": None,
                                "message": "loading the file did not finish in time"}
    except BaseException as exc:
        signal.setitimer(signal.ITIMER_REAL, 0)
        result["load_error"] = describe(exc)
    result["load_output"] = output.take()

    func = namespace.get(payload["function_name"])
    if result["load_error"] is None and not callable(func):
        result["load_error"] = {
            "type": "NameError", "line": None,
            "message": f"no function called {payload['function_name']} was defined",
        }
    write_result(result)
    if result["load_error"] is not None:
        return

    for test in payload["tests"]:
        entry = {"id": test["id"], "status": "ok", "value": None, "type": None,
                 "error": None, "output": ""}
        try:
            args = copy.deepcopy(test["args"])
            signal.setitimer(signal.ITIMER_REAL, payload["per_test_timeout"])
            value = func(*args)
            signal.setitimer(signal.ITIMER_REAL, 0)
            entry["value"] = safe_repr(value)
            entry["type"] = type(value).__name__
        except TestTimeout:
            entry["status"] = "timeout"
        except BaseException as exc:  # includes SystemExit and RecursionError
            signal.setitimer(signal.ITIMER_REAL, 0)
            entry["status"] = "error"
            entry["error"] = describe(exc)
        entry["output"] = output.take()
        result["results"].append(entry)
        write_result(result)

    sys.stdout, sys.stderr = real_stdout, real_stderr


if __name__ == "__main__":
    main()
