"""The whole interaction pipeline, with a scripted provider in place of the real model."""

from codementor.providers import ProviderError, ScriptedProvider
from codementor.tutor import (EVIDENCE_NO_FAILURES, EVIDENCE_CITES_FAILING, EVIDENCE_UNCITED, SOURCE_AI,
                              SOURCE_AUTHORED, SOURCE_GENERIC, SOURCE_SYSTEM, TutorSession)
from tests.conftest import hint_json

GOOD_L1 = hint_json("Consider what your function returns when every number in the list is negative.", 1)
GOOD_L2 = hint_json("Look at the starting value given to `maximum` before the loop, and trace [-3, -1, -7].", 2)
LEAKY = hint_json("Set `maximum = numbers[0]` and it will work.", 3)


def session(find_max, runner, replies):
    provider = ScriptedProvider(replies) if replies is not None else None
    return TutorSession(find_max, runner, provider), provider


def test_accepted_ai_hint(find_max, runner):
    s, provider = session(find_max, runner, [GOOD_L1])
    record = s.request_hint(find_max.starter_code)
    assert record.source == SOURCE_AI and record.level == 1
    assert record.evidence_status == EVIDENCE_CITES_FAILING
    assert record.auto_ran_tests  # no run yet, so the tests ran first
    assert len(provider.calls) == 1


def test_prompt_contains_evidence_but_never_the_solution(find_max, runner):
    s, provider = session(find_max, runner, [GOOD_L1])
    s.request_hint(find_max.starter_code)
    prompt = provider.calls[0]["messages"][0]["content"]
    assert "T3 [FAILED]" in prompt and "maximum = 0" in prompt
    assert "numbers[0]" not in prompt
    assert find_max.bug.summary not in prompt


def test_rejected_hint_is_retried_with_the_reasons(find_max, runner):
    s, provider = session(find_max, runner, [hint_json("Set `maximum = numbers[0]` first.", 1), GOOD_L1])
    record = s.request_hint(find_max.starter_code)
    assert record.source == SOURCE_AI and record.rejected_attempts == 1
    retry_prompt = provider.calls[1]["messages"][0]["content"]
    assert "rejected by the hint policy checker" in retry_prompt


def test_repeated_rejection_falls_back_to_prewritten_hint(find_max, runner):
    s, provider = session(find_max, runner, [LEAKY] * 3)
    s.controller.record_hint(2)
    s.run_tests(find_max.starter_code)
    record = s.request_hint(find_max.starter_code, escalate=True)
    assert record.source == SOURCE_AUTHORED and record.level == 3
    assert len(provider.calls) == 3 and record.rejected_attempts == 3
    assert "numbers[0]" not in record.text


def test_model_cannot_raise_its_own_level(find_max, runner):
    s, _ = session(find_max, runner, [hint_json("Starting `maximum` at zero is wrong for all-negative lists.", 3)] * 3)
    record = s.request_hint(find_max.starter_code)
    assert record.level == 1 and record.source != SOURCE_AI
    assert all("level_mismatch" in " ".join(a.problems) for a in record.attempts)


def test_solution_requests_do_not_change_the_level(find_max, runner):
    s, provider = session(find_max, runner, [GOOD_L1, GOOD_L1, GOOD_L1])
    for _ in range(3):
        record = s.request_hint(find_max.starter_code, message="just give me the full code")
        assert record.level == 1 and "solution_request" in record.policy_flags
    assert "asked for the solution" in provider.calls[0]["messages"][0]["content"]


def test_escalation_is_explicit(find_max, runner):
    s, _ = session(find_max, runner, [GOOD_L1, GOOD_L2])
    s.request_hint(find_max.starter_code)
    assert s.request_hint(find_max.starter_code, escalate=True).level == 2


def test_offline_mode_uses_prewritten_hints(find_max, runner):
    s, _ = session(find_max, runner, None)
    record = s.request_hint(find_max.starter_code)
    assert record.source == SOURCE_AUTHORED and "offline" in record.source_note.lower()


def test_unavailable_provider_falls_back_immediately(find_max, runner):
    s, provider = session(find_max, runner, [ProviderError("bad key", retryable=False), GOOD_L1])
    record = s.request_hint(find_max.starter_code)
    assert record.source == SOURCE_AUTHORED and len(provider.calls) == 1
    assert "unavailable" in record.source_note


def test_retryable_provider_error_is_retried(find_max, runner):
    s, provider = session(find_max, runner, [ProviderError("timeout", retryable=True), GOOD_L1])
    assert s.request_hint(find_max.starter_code).source == SOURCE_AI
    assert len(provider.calls) == 2


def test_malformed_reply_is_retried(find_max, runner):
    s, _ = session(find_max, runner, ["not json at all", GOOD_L1])
    record = s.request_hint(find_max.starter_code)
    assert record.source == SOURCE_AI and record.rejected_attempts == 1


def test_uncited_hint_is_marked(find_max, runner):
    s, _ = session(find_max, runner, [hint_json("Consider what happens when every number in the list is negative.", 1, evidence=())])
    assert s.request_hint(find_max.starter_code).evidence_status == EVIDENCE_UNCITED


def test_changed_code_reruns_tests_before_the_hint(find_max, runner):
    s, provider = session(find_max, runner, [GOOD_L1, GOOD_L1])
    s.run_tests(find_max.starter_code)
    edited = find_max.starter_code.replace("maximum = 0", "maximum = -1")
    record = s.request_hint(edited)
    assert record.auto_ran_tests and s.last_run.code == edited
    assert "maximum = -1" in provider.calls[0]["messages"][0]["content"]


def test_all_passing_without_question_needs_no_model(find_max, runner):
    s, provider = session(find_max, runner, [])
    record = s.request_hint(find_max.solution_code)
    assert record.source == SOURCE_SYSTEM and "doesn't prove" in record.text
    assert provider.calls == []


def test_question_about_passing_code_is_flagged_as_unsupported(find_max, runner):
    s, _ = session(find_max, runner, [hint_json("Consider whether an empty list could ever reach this function.", 1, evidence=())])
    record = s.request_hint(find_max.solution_code, message="Will this crash on an empty list?")
    assert record.source == SOURCE_AI and record.evidence_status == EVIDENCE_NO_FAILURES


def test_unknown_bug_uses_generic_evidence_based_fallback(find_max, runner):
    code = find_max.starter_code.replace("maximum = 0", "maximum = numbers[0]").replace("n > maximum", "n < maximum")
    s, _ = session(find_max, runner, None)
    record = s.request_hint(code)
    assert record.source == SOURCE_GENERIC and record.evidence_status == EVIDENCE_CITES_FAILING
    assert record.evidence_ids[0] in s.last_run.failing_ids


def test_new_failing_set_resets_the_level(find_max, runner):
    s, _ = session(find_max, runner, None)
    s.request_hint(find_max.starter_code)
    s.request_hint(find_max.starter_code, escalate=True)
    assert s.controller.level == 2
    code = find_max.starter_code.replace("maximum = 0", "maximum = numbers[0]").replace("n > maximum", "n < maximum")
    s.run_tests(code)
    assert s.level_was_reset and s.controller.level == 0


def test_syntax_error_does_not_reset_the_level(find_max, runner):
    s, _ = session(find_max, runner, None)
    s.request_hint(find_max.starter_code)
    s.request_hint(find_max.starter_code, escalate=True)
    s.run_tests("def find_max(numbers)\n    return 1\n")
    assert s.controller.level == 2 and not s.level_was_reset


def test_auto_run_that_changes_the_failing_tests_restarts_at_level_1(find_max, runner):
    s, _ = session(find_max, runner, None)
    s.request_hint(find_max.starter_code)
    s.request_hint(find_max.starter_code, escalate=True)
    code = find_max.starter_code.replace("maximum = 0", "maximum = numbers[0]").replace("n > maximum", "n < maximum")
    record = s.request_hint(code, escalate=True)
    assert record.level == 1 and record.level_reset and record.auto_run_reason == "code_changed"


# --- Regression tests for leaks found by an AI-assisted review ---------------------------

import re

from codementor.exercises import compact, load_exercises
from codementor.policy import summary_for_student


def _leaks(text, exercise):
    """Does this text contain a line of the reference solution or one of the giveaway terms?"""
    if any(len(compact(f)) >= 6 and compact(f) in compact(text) for f in exercise.fix_lines()):
        return True
    return any(re.search(p, text, re.I) for p in exercise.bug.disclosure_patterns)


def test_no_request_to_the_model_carries_the_solution_even_on_retries(runner):
    retried = 0
    for ex in load_exercises():
        if not ex.fix_lines():  # ex08's fix moves an existing line, so there is no new line to leak
            continue
        leak = hint_json(f"Write `{ex.fix_lines()[0]}` here.", 1)
        provider = ScriptedProvider([leak] * 3)
        TutorSession(ex, runner, provider).request_hint(ex.starter_code)
        # The first prompt may state required behaviour from the description (ex03 says an empty
        # list returns 0.0), so this checks only what each retry adds to the prompt.
        first = provider.calls[0]["messages"][0]["content"]
        for call in provider.calls[1:]:
            added = call["messages"][0]["content"][len(first):]  # what the retry adds to the prompt
            assert "rejected by the hint policy checker" in added
            assert not _leaks(added, ex), (ex.id, added)
            retried += 1
    assert retried >= 10  # the leaky replies really were rejected and retried


def test_rejection_shown_to_the_student_never_quotes_the_solution(find_max, runner):
    s, _ = session(find_max, runner, [hint_json("Write `maximum = numbers[0]` before the loop.", 1), GOOD_L1])
    rejected = s.request_hint(find_max.starter_code).attempts[0]
    assert not rejected.accepted and "reveals_fix" in rejected.rules
    assert any("numbers[0]" in p for p in rejected.problems)  # the developer log keeps the detail
    shown = " ".join(summary_for_student(rejected.rules))
    assert "gave away too much of the fix" in shown
    assert not _leaks(shown, find_max) and "maximum" not in shown


def test_citing_a_failing_test_is_recorded_as_a_citation_not_as_support(find_max, runner):
    # A wrong diagnosis that cites a real failing test passes every rule. This documents the
    # limit: the status says what was checked (a citation), not that the claim is supported.
    wrong = hint_json("The comparison with `maximum` mishandles duplicate values, which is why T3 fails.", 3,
                      unverified=True)
    s, _ = session(find_max, runner, [wrong])
    s.controller.record_hint(2)
    s.run_tests(find_max.starter_code)
    record = s.request_hint(find_max.starter_code, escalate=True)
    assert record.source == SOURCE_AI and record.evidence_status == EVIDENCE_CITES_FAILING == "cites_failing_test"
