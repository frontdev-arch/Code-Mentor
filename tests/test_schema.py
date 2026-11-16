import json

from codementor.schema import HINT_SCHEMA, validate_hint_response
from tests.conftest import hint_json


def test_valid_reply_is_parsed():
    result = validate_hint_response(hint_json("Look at the starting value.", 2))
    assert result.ok and result.response.level == 2 and result.response.evidence_ids == ["T3"]


def test_invalid_json():
    assert not validate_hint_response("not json").ok


def test_missing_and_extra_fields():
    data = json.loads(hint_json("x y z", 1))
    del data["level"]
    data["confidence"] = 0.9
    result = validate_hint_response(data)
    assert not result.ok and any("missing" in e for e in result.errors) and any("unexpected" in e for e in result.errors)


def test_wrong_types():
    data = json.loads(hint_json("x y z", 1))
    data["level"] = True
    data["evidence_ids"] = "T3"
    assert len(validate_hint_response(data).errors) == 2


def test_schema_has_no_confidence_field():
    assert "confidence" not in HINT_SCHEMA["properties"]
    assert HINT_SCHEMA["additionalProperties"] is False
