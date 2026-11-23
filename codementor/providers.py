"""Hint providers, kept behind one small interface so the rest of the app is provider-neutral.

A provider takes a system prompt, messages and a JSON schema, and returns the
model's raw text. It does not validate, check policy or retry on bad content;
tutor.py does that.

This prototype connects NO live model, by design (no API costs). The model is
SIMULATED by ScriptedProvider, which replays fixed replies: from the automated
tests, or from a demo script (demo/*.json) in the app's simulated mode, which the
interface labels as scripted. Every simulated reply still goes through schema
validation and the policy checker. A real model could be added later as another
class with the same generate() method.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Protocol


class ProviderError(Exception):
    def __init__(self, message: str, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class ProviderReply:
    text: str
    model: str
    request_id: str | None = None
    usage: dict = field(default_factory=dict)


class HintProvider(Protocol):
    name: str
    model: str

    def generate(self, system: str, messages: list[dict], schema: dict) -> ProviderReply: ...


class ScriptedProvider:
    """Replies with queued strings, or raises queued ProviderErrors, in order."""

    name = "scripted"

    def __init__(self, replies: list[str | ProviderError], model: str = "scripted-model"):
        self.replies = deque(replies)
        self.model = model
        self.calls: list[dict] = []

    @classmethod
    def from_file(cls, path) -> "ScriptedProvider":
        """Load a demo script: a JSON list of hint replies, replayed in order."""
        import json
        from pathlib import Path
        replies = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(replies, list):
            raise ValueError("a demo script must be a JSON list of replies")
        return cls([r if isinstance(r, str) else json.dumps(r) for r in replies], model="scripted demo")

    def generate(self, system: str, messages: list[dict], schema: dict) -> ProviderReply:
        self.calls.append({"system": system, "messages": messages, "schema": schema})
        if not self.replies:
            raise ProviderError("No scripted reply left.", retryable=False)
        reply = self.replies.popleft()
        if isinstance(reply, ProviderError):
            raise reply
        return ProviderReply(text=reply, model=self.model)
