import pytest

from codementor.hint_controller import MAX_LEVEL, HintController


def test_first_request_is_level_1_even_when_escalating():
    c = HintController()
    assert c.level_for_request(escalate=False) == 1
    assert c.level_for_request(escalate=True) == 1


def test_student_escalates_one_level_at_a_time_up_to_the_cap():
    c = HintController()
    for expected in (1, 2, 3, 3):
        level = c.level_for_request(escalate=True)
        assert level == expected
        c.record_hint(level)
    assert c.level == MAX_LEVEL and not c.can_escalate


def test_asking_again_keeps_the_level():
    c = HintController()
    c.record_hint(1)
    c.record_hint(c.level_for_request(escalate=True))
    assert c.level_for_request(escalate=False) == 2


def test_new_failing_tests_reset_the_level():
    c = HintController()
    c.update_focus(frozenset({"T3", "T4"}))
    c.record_hint(2)
    assert c.update_focus(frozenset({"T3", "T4"})) is False and c.level == 2
    assert c.update_focus(frozenset({"T5"})) is True and c.level == 0
    assert c.level_for_request(escalate=True) == 1


def test_invalid_levels_cannot_be_recorded():
    with pytest.raises(ValueError):
        HintController().record_hint(4)
