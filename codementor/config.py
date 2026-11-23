"""Settings from environment variables. No live model and no API keys: see providers.py."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    provider: str          # "offline" (pre-written hints) or "scripted" (simulated model)
    max_attempts: int
    log_path: Path | None
    script_path: Path | None = None  # demo script for the simulated model


def load_settings() -> Settings:
    provider = os.environ.get("CODEMENTOR_PROVIDER", "").strip().lower()
    if provider != "scripted":
        provider = "offline"
    log_dir = os.environ.get("CODEMENTOR_LOG_DIR", str(PROJECT_ROOT / "logs"))
    return Settings(
        provider=provider,
        max_attempts=int(os.environ.get("CODEMENTOR_MAX_ATTEMPTS", "3")),
        log_path=Path(log_dir) / f"session-{time.strftime('%Y%m%d')}.jsonl" if log_dir else None,
        script_path=Path(os.environ["CODEMENTOR_SCRIPT"]) if os.environ.get("CODEMENTOR_SCRIPT") else None,
    )
