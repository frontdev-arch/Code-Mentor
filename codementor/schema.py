"""The structured response the model must return for a hint, and its validation.

The JSON schema is sent with the request (structured outputs), so the API
constrains the shape of the reply. validate_hint_response() still checks it
here, because a schema guarantees shape, not truth (Lecture 09), and because
the API cannot enforce things like a maximum length.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

MAX_HINT_CHARS = 900
MAX_FIELD_CHARS = 300

HINT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "hint": {
            "type": "string",
            "description": "The hint shown to the student. Plain text, under 80 words.",
        },
        "target_concept": {
            "type": "string",
            "description": "The programming idea the hint is about, in a few words.",
        },
        "level": {
            "type": "integer",
            "enum": [1, 2, 3],
            "description": "The assistance level this hint was written for. Must equal the level requested.",
        },
        "evidence_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "IDs of the test results (e.g. T3) or run problems (e.g. SYNTAX) the hint relies on.",
        },
        "has_unverified_interpretation": {
            "type": "boolean",
            "description": "True if the hint says anything about the cause that the test results don't show directly.",
        },
        "rationale": {
            "type": "string",
            "description": "One sentence on why this hint, for the developer's log. Never shown to the student.",
        },
    },
    "required": ["hint", "target_concept", "level", "evidence_ids",
                 "has_unverified_interpretation", "rationale"],
    "additionalProperties": False,
}


@dataclass
class HintResponse:
    hint: str
    target_concept: str
    level: int
    evidence_ids: list[str]
    has_unverified_interpretation: bool
    rationale: str = ""


@dataclass
class ValidationResult:
    response: HintResponse | None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.response is not None and not self.errors


def validate_hint_response(raw: str | dict) -> ValidationResult:
    """Parse the model's reply and check every field. Never raises on bad input."""
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except ValueError as exc:
            return ValidationResult(None, [f"reply is not valid JSON ({exc.msg})"])
    else:
        data = raw
    if not isinstance(data, dict):
        return ValidationResult(None, ["reply is not a JSON object"])

    errors = []
    expected = set(HINT_SCHEMA["required"])
    missing = expected - data.keys()
    extra = data.keys() - set(HINT_SCHEMA["properties"])
    if missing:
        errors.append(f"missing fields: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"unexpected fields: {', '.join(sorted(extra))}")
    if errors:
        return ValidationResult(None, errors)

    hint, concept, level = data["hint"], data["target_concept"], data["level"]
    evidence, unverified, rationale = data["evidence_ids"], data["has_unverified_interpretation"], data["rationale"]

    if not isinstance(hint, str) or not hint.strip():
        errors.append("hint must be a non-empty string")
    elif len(hint) > MAX_HINT_CHARS:
        errors.append(f"hint is longer than {MAX_HINT_CHARS} characters")
    if not isinstance(concept, str) or len(concept) > MAX_FIELD_CHARS:
        errors.append("target_concept must be a short string")
    if isinstance(level, bool) or level not in (1, 2, 3):
        errors.append("level must be 1, 2 or 3")
    if not isinstance(evidence, list) or not all(isinstance(e, str) for e in evidence):
        errors.append("evidence_ids must be a list of strings")
    if not isinstance(unverified, bool):
        errors.append("has_unverified_interpretation must be true or false")
    if not isinstance(rationale, str):
        errors.append("rationale must be a string")
    if errors:
        return ValidationResult(None, errors)

    return ValidationResult(HintResponse(
        hint=hint.strip(),
        target_concept=concept.strip(),
        level=level,
        evidence_ids=[e.strip() for e in evidence],
        has_unverified_interpretation=unverified,
        rationale=rationale.strip()[:MAX_FIELD_CHARS],
    ))
