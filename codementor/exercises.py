"""The exercise bank: loads and validates exercises from exercises/<id>/.

Each exercise folder holds three files:
  exercise.json  description, tests, bug metadata and pre-written hints
  starter.py     the buggy code the student starts from
  solution.py    a reference solution, used only for internal checks

The reference solution never goes into a model prompt. The policy checker uses
it locally to spot hints that give the fix away (see policy.py).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXERCISES_DIR = Path(__file__).resolve().parent.parent / "exercises"
HINT_LEVELS = (1, 2, 3)


def normalise_line(line: str) -> str:
    """Compare lines by content and indentation, ignoring runs of spaces and trailing space."""
    expanded = line.expandtabs(4).rstrip()
    stripped = expanded.lstrip(" ")
    indent = len(expanded) - len(stripped)
    return " " * indent + re.sub(r"\s+", " ", stripped)


def compact(text: str) -> str:
    """Remove all whitespace and lower-case, for loose substring matching of code."""
    return re.sub(r"\s+", "", text).lower()


@dataclass(frozen=True)
class TestCase:
    __test__ = False  # stop pytest trying to collect this class

    id: str
    args: tuple[Any, ...]
    expected: Any
    description: str

    def call(self, function_name: str) -> str:
        """The call this test makes, written as Python, e.g. find_max([-3, -1, -7])."""
        return f"{function_name}({', '.join(repr(a) for a in self.args)})"


@dataclass(frozen=True)
class BugInfo:
    category: str
    summary: str
    lines: tuple[str, ...]
    expected_failing: frozenset[str]
    location_patterns: tuple[str, ...]
    disclosure_patterns: tuple[str, ...]


@dataclass(frozen=True)
class Exercise:
    id: str
    order: int
    title: str
    function_name: str
    description: str
    expected_behaviour: str
    concepts: tuple[str, ...]
    starter_code: str
    solution_code: str
    tests: tuple[TestCase, ...]
    bug: BugInfo
    hints: dict[int, str]

    def test(self, test_id: str) -> TestCase | None:
        return next((t for t in self.tests if t.id == test_id), None)

    def fix_lines(self) -> list[str]:
        """Lines of the reference solution whose content does not appear in the starter code."""
        starter = {line.strip() for line in self.starter_code.splitlines()}
        return [
            line.strip()
            for line in self.solution_code.splitlines()
            if line.strip() and line.strip() not in starter
        ]

    def bug_line_numbers(self, code: str) -> list[int]:
        """Current line numbers of the known bug's lines, or [] if any of them has gone."""
        lines = [normalise_line(line) for line in code.splitlines()]
        numbers = []
        for bug_line in self.bug.lines:
            target = normalise_line(bug_line)
            if target not in lines:
                return []
            numbers.append(lines.index(target) + 1)
        return numbers

    def authored_hint(self, level: int, code: str) -> str:
        """The pre-written hint for a level, with {line} filled in for the current code."""
        numbers = self.bug_line_numbers(code)
        line = numbers[0] if numbers else "?"
        return self.hints[level].replace("{line}", str(line))


class ExerciseError(ValueError):
    pass


def _load_one(folder: Path) -> Exercise:
    data = json.loads((folder / "exercise.json").read_text(encoding="utf-8"))
    required = ["id", "order", "title", "function_name", "description",
                "expected_behaviour", "bug", "tests", "hints"]
    missing = [key for key in required if key not in data]
    if missing:
        raise ExerciseError(f"{folder.name}: missing {', '.join(missing)}")

    bug = data["bug"]
    for pattern in bug["location_patterns"] + bug["disclosure_patterns"]:
        re.compile(pattern)  # fail at load time, not mid-session

    tests = tuple(
        TestCase(id=t["id"], args=tuple(t["args"]), expected=t["expected"],
                 description=t.get("description", ""))
        for t in data["tests"]
    )
    if len({t.id for t in tests}) != len(tests):
        raise ExerciseError(f"{folder.name}: duplicate test ids")

    hints = {int(level): text for level, text in data["hints"].items()}
    if set(hints) != set(HINT_LEVELS):
        raise ExerciseError(f"{folder.name}: needs hints for levels 1, 2 and 3")

    return Exercise(
        id=data["id"],
        order=data["order"],
        title=data["title"],
        function_name=data["function_name"],
        description=data["description"],
        expected_behaviour=data["expected_behaviour"],
        concepts=tuple(data.get("concepts", [])),
        starter_code=(folder / "starter.py").read_text(encoding="utf-8"),
        solution_code=(folder / "solution.py").read_text(encoding="utf-8"),
        tests=tests,
        bug=BugInfo(
            category=bug["category"],
            summary=bug["summary"],
            lines=tuple(bug["lines"]),
            expected_failing=frozenset(bug["expected_failing"]),
            location_patterns=tuple(bug["location_patterns"]),
            disclosure_patterns=tuple(bug["disclosure_patterns"]),
        ),
        hints=hints,
    )


def load_exercises(directory: Path = EXERCISES_DIR) -> list[Exercise]:
    folders = sorted(p for p in directory.iterdir() if (p / "exercise.json").exists())
    exercises = [_load_one(folder) for folder in folders]
    return sorted(exercises, key=lambda e: e.order)
