"""Keeps the AI case reviewer's health in one small JSON file under data/.

One process at a time: a lock guards the website's threads, and each save writes a new file
and swaps it in, so a crash never leaves half a file. A file that cannot be read benches the
reviewer (the safe side), it never turns it on.
"""

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from reimbursement_council.core.models.case_review import ReviewerHealth

logger = logging.getLogger(__name__)

HEALTH_FILE = Path("reviewer") / "health.json"
"""Under the data folder."""


class ReviewerHealthStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def _read(self) -> ReviewerHealth:
        if not self.path.is_file():
            return ReviewerHealth()
        try:
            return ReviewerHealth.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (ValidationError, OSError, ValueError) as error:
            logger.error("reviewer health file %s is unreadable, benching: %s", self.path, error)
            return ReviewerHealth(
                status="benched",
                bench_reason="the health file could not be read",
                benched_at=datetime.now(UTC),
            )

    def _write(self, health: ReviewerHealth) -> None:
        """A failed write (full disk) is logged; the file keeps its last state, never a cut one."""
        temporary = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(health.model_dump_json(indent=1), encoding="utf-8")
            temporary.replace(self.path)
        except OSError as error:
            logger.error("could not save the reviewer health file %s: %s", self.path, error)

    def load(self) -> ReviewerHealth:
        with self._lock:
            return self._read()

    def update(self, change: Callable[[ReviewerHealth], ReviewerHealth]) -> ReviewerHealth:
        """Read, change and save in one step, so two threads never lose each other's answer."""
        with self._lock:
            before = self._read()
            after = change(before)
            if after != before:
                self._write(after)
            return after
