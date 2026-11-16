"""Every exercise is internally consistent: run against the real sandboxed runner."""

import pytest

from codementor.exercises import load_exercises
from codementor.policy import PolicyContext, check_hint
from codementor.schema import HintResponse

EXERCISES = load_exercises()
IDS = [e.id for e in EXERCISES]


def test_bank_size_and_categories():
    assert 8 <= len(EXERCISES) <= 12
    assert len({e.bug.category for e in EXERCISES}) >= 7


@pytest.mark.parametrize("exercise", EXERCISES, ids=IDS)
def test_starter_fails_exactly_the_expected_tests(exercise, runner):
    run = runner.run(exercise, exercise.starter_code)
    assert run.status == "completed"
    assert run.failing_ids == exercise.bug.expected_failing


@pytest.mark.parametrize("exercise", EXERCISES, ids=IDS)
def test_reference_solution_passes_every_test(exercise, runner):
    assert runner.run(exercise, exercise.solution_code).all_passed


@pytest.mark.parametrize("exercise", EXERCISES, ids=IDS)
def test_known_bug_is_detected_in_starter_only(exercise, runner):
    """Known bug = its lines are still there AND the failing tests are the ones it causes.
    Line presence alone is not enough: some fixes (ex03) add a guard and keep the line."""
    starter = PolicyContext(exercise, 1, exercise.starter_code, runner.run(exercise, exercise.starter_code))
    solution = PolicyContext(exercise, 1, exercise.solution_code, runner.run(exercise, exercise.solution_code))
    assert starter.known_bug
    assert not solution.known_bug


@pytest.mark.parametrize("exercise", EXERCISES, ids=IDS)
@pytest.mark.parametrize("level", [1, 2, 3])
def test_prewritten_hints_pass_the_policy_checker(exercise, level, runner):
    """The fallback hints must obey the same policy as generated ones."""
    run = runner.run(exercise, exercise.starter_code)
    text = exercise.authored_hint(level, exercise.starter_code)
    assert "{line}" not in text and "line ?" not in text
    response = HintResponse(text, "", level, sorted(run.failing_ids), False)
    decision = check_hint(response, PolicyContext(exercise, level, exercise.starter_code, run))
    assert decision.accepted, decision.reasons()


@pytest.mark.parametrize("exercise", EXERCISES, ids=IDS)
def test_reference_solution_would_be_caught(exercise, runner):
    """Pasting the solution's changed lines into a hint is always rejected."""
    run = runner.run(exercise, exercise.starter_code)
    leak = " ".join(f"`{line}`" for line in exercise.fix_lines()) or "x"
    response = HintResponse(f"Change it to {leak} and it works.", "", 3, sorted(run.failing_ids), False)
    decision = check_hint(response, PolicyContext(exercise, 3, exercise.starter_code, run))
    if exercise.fix_lines():
        assert not decision.accepted
