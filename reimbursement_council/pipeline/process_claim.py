"""Wire the stages together for one claim: read, rules, payout, council, decide, explain, store."""

import logging
import time
from collections.abc import Callable
from datetime import datetime

from reimbursement_council.adapters import readers
from reimbursement_council.adapters.readers import DocumentReader
from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.config.models import Settings
from reimbursement_council.core.council.registry import run_council
from reimbursement_council.core.decision.blockers import approval_blockers
from reimbursement_council.core.decision.combine import combine_votes, p_good_from_score
from reimbursement_council.core.decision.lanes import choose_lane, expected_loss
from reimbursement_council.core.explain import build_member_message
from reimbursement_council.core.extraction import extract_document
from reimbursement_council.core.models.case import ClaimCase
from reimbursement_council.core.models.claim import Claim, Document, ExtractionResult
from reimbursement_council.core.models.common import PRIMARY_DOCUMENT_KINDS
from reimbursement_council.core.models.decision import Decision
from reimbursement_council.core.models.reference import ReferenceData
from reimbursement_council.core.payout import calculate_payout
from reimbursement_council.core.rules import receipt_keys, run_hard_rules

logger = logging.getLogger(__name__)


def _primary_document(claim: Claim) -> Document | None:
    primary = next((doc for doc in claim.documents if doc.kind in PRIMARY_DOCUMENT_KINDS), None)
    for document in claim.documents:
        if document is not primary:
            logger.info(
                "claim %s: document %s (%s) not read yet in this version",
                claim.claim_id,
                document.document_id,
                document.kind,
            )
    return primary


def _vat_number(extraction: ExtractionResult | None) -> str | None:
    if extraction is None:
        return None
    field = extraction.best("vat_number")
    return None if field is None else field.value


def process_claim(
    claim: Claim,
    reference: ReferenceData,
    settings: Settings,
    store: ClaimStore,
    now: datetime,
    reader_for: Callable[[Document], DocumentReader] = readers.reader_for,
) -> Decision:
    started = time.perf_counter()
    member = reference.member(claim.member_id)
    policy = reference.policy(claim.policy_id)
    history = reference.history(claim.patient_member_id)

    primary = _primary_document(claim)
    extraction = (
        None
        if primary is None
        else extract_document(primary.document_id, reader_for(primary).read(primary), settings)
    )
    read_seconds = time.perf_counter() - started
    provider = reference.provider_by_vat(_vat_number(extraction))
    image_hash = None if primary is None else primary.image_hash

    rule_results = run_hard_rules(
        claim, policy, extraction, image_hash, store.seen_receipts(claim.claim_id), settings
    )
    payout = None if extraction is None else calculate_payout(extraction, policy, history, settings)
    case = ClaimCase(
        claim=claim,
        member=member,
        policy=policy,
        provider=provider,
        history=history,
        extraction=extraction,
        rule_results=rule_results,
        payout=payout,
    )
    votes = run_council(case, settings)
    combined, disagreement = combine_votes(votes)
    p_good = p_good_from_score(combined, settings)
    choice = choose_lane(
        rule_results,
        votes,
        p_good,
        disagreement,
        payout,
        claim.retries_used,
        settings,
        approval_blockers(claim, extraction, payout, settings),
    )

    decision = Decision(
        claim_id=claim.claim_id,
        decided_at=now,
        config_version=settings.config_version,
        combined_score=combined,
        p_good=p_good,
        disagreement=disagreement,
        payout_requested=None if payout is None else payout.requested,
        payout_calculated=None if payout is None else payout.calculated,
        expected_loss=None if payout is None else expected_loss(p_good, payout.calculated),
        reviewer_time_value=settings.decision.reviewer_time_value_halalas,
        lane=choice.lane,
        lane_reason=choice.reason,
        outcome=choice.outcome,
        self_fix_request=choice.request,
        member_message=build_member_message(choice, rule_results, payout, settings),
        votes=votes,
        rule_results=rule_results,
        check_results=[] if extraction is None else extraction.checks,
    )
    store.save_decision(decision)
    keys = (
        None
        if extraction is None
        else receipt_keys(extraction, settings.policy.local_utc_offset_hours)
    )
    store.record_receipt(
        claim.claim_id,
        image_hash,
        None if keys is None else keys.fingerprint,
        None if keys is None else keys.weak_key,
        decision.lane,
    )
    logger.info(
        "claim %s: lane %s, p_good %.3f, disagreement %.3f, read %.1fs, total %.1fs",
        claim.claim_id,
        decision.lane,
        p_good,
        disagreement,
        read_seconds,
        time.perf_counter() - started,
    )
    return decision
