"""SQLite storage for decisions and for receipts already sent (duplicate check)."""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from reimbursement_council.core.models.decision import Decision
from reimbursement_council.core.rules import SeenReceipts

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    claim_id TEXT PRIMARY KEY,
    decided_at TEXT NOT NULL,
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
