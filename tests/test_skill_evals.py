"""Unit tests for tools/run_skill_evals.py: stream parsing (did the skill trigger?) and grading."""

import json

from tools.run_skill_evals import grade, parse_stream


def line(obj):
    return json.dumps(obj)


ASSISTANT_SKILL = line({"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Skill", "input": {"skill": "pre-registration"}}]}})
ASSISTANT_OTHER = line({"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Read", "input": {"file_path": "x"}}]}})
RESULT = line({"type": "result", "subtype": "success", "result": "Hypothesis: …"})


def test_parse_stream_detects_skill_and_result():
    invoked, text = parse_stream([ASSISTANT_SKILL, "not json", RESULT])
    assert invoked is True and text == "Hypothesis: …"


def test_parse_stream_other_tools_do_not_count():
    invoked, _ = parse_stream([ASSISTANT_OTHER, RESULT])
    assert invoked is False


def test_parse_stream_other_skill_does_not_count():
    other = line({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Skill", "input": {"skill": "something-else"}}]}})
    assert parse_stream([other, RESULT])[0] is False


def test_grade_trigger_and_terms():
    case = {"should_trigger": True, "expect_all": ["gate", "PASS"], "expect_any": [["commit", "freeze"]]}
    ok, why = grade(case, True, "Gates ... pass/fail ... freeze it")
    assert ok and why == []
    ok, why = grade(case, True, "gates only")
    assert not ok and "missing: PASS" in why and "missing one of: commit / freeze" in why
    ok, why = grade(case, False, "Gates PASS freeze")
    assert not ok and why[0].startswith("trigger")


def test_grade_negative_case_only_checks_trigger():
    case = {"should_trigger": False, "expect_all": [], "expect_any": []}
    assert grade(case, False, "anything") == (True, [])
    assert grade(case, True, "anything")[0] is False
