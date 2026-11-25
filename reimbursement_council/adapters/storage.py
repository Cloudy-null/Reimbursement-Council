"""SQLite storage for decisions, receipts already sent (duplicate check) and members added
by hand."""

import logging
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime

from reimbursement_council.core.models.claim import Claim, ReaderOutput
from reimbursement_council.core.models.common import Halalas, Model
from reimbursement_council.core.models.decision import Decision
from reimbursement_council.core.new_member import NewMember
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
CREATE TABLE IF NOT EXISTS readings (
    claim_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    json TEXT NOT NULL,
    PRIMARY KEY (claim_id, document_id)
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
CREATE TABLE IF NOT EXISTS added_members (
    policy_id TEXT PRIMARY KEY,
    added_at TEXT NOT NULL,
    json TEXT NOT NULL
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

    def list_claims(self) -> list[Claim]:
        with self._connection() as connection:
            rows = connection.execute("SELECT json FROM claims").fetchall()
        return [Claim.model_validate_json(row[0]) for row in rows]

    def save_readings(self, claim_id: str, readings: Mapping[str, ReaderOutput]) -> None:
        """What was read from each document when the member saw the check screen. The pipeline
        judges exactly this later, so the member and the decision see the same reading."""
        with self._connection() as connection:
            connection.executemany(
                "INSERT OR REPLACE INTO readings (claim_id, document_id, json) VALUES (?, ?, ?)",
                [(claim_id, doc_id, r.model_dump_json()) for doc_id, r in readings.items()],
            )

    def load_readings(self, claim_id: str) -> dict[str, ReaderOutput]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT document_id, json FROM readings WHERE claim_id = ?", (claim_id,)
            ).fetchall()
        return {row[0]: ReaderOutput.model_validate_json(row[1]) for row in rows}

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

    def has_receipt(self, claim_id: str) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM receipts WHERE claim_id = ?", (claim_id,)
            ).fetchone()
        return row is not None

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

    def save_new_member(self, added: NewMember, added_at: AwareDatetime) -> None:
        """One row per added policy: the member, dependants, policy and history as JSON."""
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO added_members (policy_id, added_at, json) VALUES (?, ?, ?)",
                (added.policy.policy_id, added_at.isoformat(), added.model_dump_json()),
            )
        logger.info("added policy %s with %d people", added.policy.policy_id, len(added.members))

    def list_new_members(self) -> list[NewMember]:
        """Oldest first, so the people list keeps its order."""
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT json FROM added_members ORDER BY added_at, rowid"
            ).fetchall()
        return [NewMember.model_validate_json(row[0]) for row in rows]
