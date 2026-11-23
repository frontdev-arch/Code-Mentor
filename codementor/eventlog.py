"""Append-only JSON Lines log of runs and hint requests, for the development record and evaluation."""

from __future__ import annotations

import json
import time
from pathlib import Path


class EventLog:
    def __init__(self, path: Path | None):
        self.path = path
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: dict) -> None:
        if self.path is None:
            return
        record = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), **event}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
