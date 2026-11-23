"""SQLite storage for decisions and for receipts already sent (duplicate check)."""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime

from reimbursement_council.core.models.claim import Claim
from reimbursement_council.core.models.common import Halalas, Model
from reimbursement_council.core.models.decision import Decision
from reimbursement_council.core.rules import SeenReceipts

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    claim_id TEXT PRIMARY KEY,
    decided_at TEXT NOT NULL,
    json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    claim_id TEXT PRIMARY KEY,
    json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS receipts (
    claim_id TEXT PRIMARY KEY,
    image_hash TEXT,
    fingerprint TEXT,
    weak_key TEXT,
    lane TEXT NOT NULL
);
"""


class ReviewRecord(Model):
    """A human reviewer's decision (DATA_MODEL: Review). Also a labeled example for tuning."""

    claim_id: str
    reviewer: str
    started_at: AwareDatetime
    finished_at: AwareDatetime
    action: Literal["approve", "approve_amount", "reject", "ask_member"]
    amount: Halalas | None
    reason: str


class ClaimStore:
    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save_decision(self, decision: Decision) -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO decisions (claim_id, decided_at, json) VALUES (?, ?, ?)",
                (decision.claim_id, decision.decided_at.isoformat(), decision.model_dump_json()),
            )
        logger.info("claim %s: decision saved, lane %s", decision.claim_id, decision.lane)

    def load_decision(self, claim_id: str) -> Decision | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT json FROM decisions WHERE claim_id = ?", (claim_id,)
            ).fetchone()
        return None if row is None else Decision.model_validate_json(row[0])

    def save_claim(self, claim: Claim) -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO claims (claim_id, json) VALUES (?, ?)",
                (claim.claim_id, claim.model_dump_json()),
            )

    def load_claim(self, claim_id: str) -> Claim | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT json FROM claims WHERE claim_id = ?", (claim_id,)
            ).fetchone()
        return None if row is None else Claim.model_validate_json(row[0])

    def list_decisions(self, lane: str | None = None) -> list[Decision]:
        """Newest first. With a lane, only decisions in that lane."""
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT json FROM decisions ORDER BY decided_at DESC"
            ).fetchall()
        decisions = [Decision.model_validate_json(row[0]) for row in rows]
        return [d for d in decisions if lane is None or d.lane == lane]

    def save_review(self, review: ReviewRecord) -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO reviews (claim_id, json) VALUES (?, ?)",
                (review.claim_id, review.model_dump_json()),
            )

    def load_review(self, claim_id: str) -> ReviewRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT json FROM reviews WHERE claim_id = ?", (claim_id,)
            ).fetchone()
        return None if row is None else ReviewRecord.model_validate_json(row[0])

    def record_receipt(
        self,
        claim_id: str,
        image_hash: str | None,
        fingerprint: str | None,
        weak_key: str | None,
        lane: str,
    ) -> None:
        """One receipt row per claim; a newer decision for the same claim replaces it."""
        with self._connection() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO receipts"
                " (claim_id, image_hash, fingerprint, weak_key, lane) VALUES (?, ?, ?, ?, ?)",
                (claim_id, image_hash, fingerprint, weak_key, lane),
            )

    def seen_receipts(self, excluding_claim_id: str) -> SeenReceipts:
        """Receipts from every other claim that was not rejected.

        A claim never duplicates itself (self-fix resends), and a rejected claim's receipt
        can be sent again correctly.
        """
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT image_hash, fingerprint, weak_key FROM receipts"
                " WHERE claim_id != ? AND lane != 'auto_reject'",
                (excluding_claim_id,),
            ).fetchall()
        return SeenReceipts(
            image_hashes=frozenset(row[0] for row in rows if row[0] is not None),
            fingerprints=frozenset(row[1] for row in rows if row[1] is not None),
            weak_keys=frozenset(row[2] for row in rows if row[2] is not None),
        )
