"""Assistance-level state, owned by the application and never by the model.

Rules:
- Levels go 1 (Concept) -> 2 (Location) -> 3 (Likely fault). There is no level
  that shows the solution.
- The first hint request gets level 1. After that the student chooses: ask
  again at the same level, or explicitly ask for a more specific hint.
- The level is tied to a problem focus: the set of failing tests. When a new
  test run fails a different set of tests, the student is working on a different
  problem, so the level goes back to 0 and the next hint starts at level 1.
- Nothing the student types, and nothing the model returns, changes the level.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAX_LEVEL = 3


@dataclass
class HintController:
    level: int = 0  # 0 means no hint yet for the current focus
    focus: frozenset[str] | None = None
    resets: int = 0
    history: list[int] = field(default_factory=list)

    @property
    def can_escalate(self) -> bool:
        return 0 < self.level < MAX_LEVEL

    def level_for_request(self, escalate: bool) -> int:
        """The level the next hint will be written at. Does not change state."""
        if self.level == 0:
            return 1
        if escalate:
            return min(self.level + 1, MAX_LEVEL)
        return self.level

    def record_hint(self, level: int) -> None:
        if not 1 <= level <= MAX_LEVEL:
            raise ValueError(f"invalid level {level}")
        self.level = level
        self.history.append(level)

    def update_focus(self, failing_ids: frozenset[str]) -> bool:
        """Call after every test run. Returns True if the level was reset."""
        changed = self.focus is not None and failing_ids != self.focus
        self.focus = failing_ids
        if changed and self.level:
            self.level = 0
            self.resets += 1
            return True
        return False
