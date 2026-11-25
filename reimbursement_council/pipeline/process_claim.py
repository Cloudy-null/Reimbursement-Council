"""Wire the stages together for one claim: read every document, rules, payout, council,
decide, explain, store."""

import logging
import time
from collections.abc import Callable, Mapping
from datetime import datetime

from reimbursement_council.adapters import readers
from reimbursement_council.adapters.readers import DocumentReader
from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.config.models import Settings
from reimbursement_council.core.council.registry import run_council
from reimbursement_council.core.decision.blockers import approval_blockers
from reimbursement_council.core.decision.document_requests import human_reasons, member_requests
from reimbursement_council.core.decision.lanes import LaneChoice, choose_lane, expected_loss
from reimbursement_council.core.explain import build_member_message
from reimbursement_council.core.models.case import ClaimCase
from reimbursement_council.core.models.claim import Claim, Document, ExtractionResult, ReaderOutput
from reimbursement_council.core.models.decision import Decision
from reimbursement_council.core.models.reference import Member, ReferenceData
from reimbursement_council.core.payout import calculate_payout
from reimbursement_council.core.rules import receipt_keys, run_hard_rules
from reimbursement_council.pipeline.case_review import CaseReviewerService, decide_with_reviewer
from reimbursement_council.pipeline.document_set import read_document_set

logger = logging.getLogger(__name__)


def patient_of(reference: ReferenceData, claim: Claim, member: Member) -> Member:
    """The person treated, for the name check. An unknown patient is checked against the
    member filing (the person_not_covered rule handles the coverage question)."""
    try:
        return reference.member(claim.patient_member_id)
    except LookupError:
        return member


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
    readings: Mapping[str, ReaderOutput] | None = None,
    case_reviewer: CaseReviewerService | None = None,
) -> Decision:
    """readings: what was read when the member saw the check screen, by document id. The
    pipeline judges exactly that, and reads only documents that have none.
    case_reviewer: the AI case reviewer, used only when it is switched on in config."""
    started = time.perf_counter()
    member = reference.member(claim.member_id)
    policy = reference.policy(claim.policy_id)
    history = reference.history(claim.patient_member_id)

    documents = read_document_set(
        claim, patient_of(reference, claim, member), settings, reader_for, readings
    )
    primary = next((d for d in documents.documents if d.document_id == documents.primary_id), None)
    extraction = None if primary is None else documents.readings[primary.document_id]
    read_seconds = time.perf_counter() - started
    provider = reference.provider_by_vat(_vat_number(extraction))
    image_hash = None if primary is None else primary.image_hash

    rule_results = run_hard_rules(
        claim, policy, extraction, image_hash, store.seen_receipts(claim.claim_id), settings
    ) + list(documents.edit_rule_results)
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
        documents_read=documents.readings,
        needs=documents.needs,
        cross_checks=documents.cross_checks,
        edits=documents.edits,
    )
    votes = run_council(case, settings)
    blockers = approval_blockers(
        claim,
        extraction,
        payout,
        settings,
        missing=documents.missing,
        billing_documents_differ=documents.billing_documents_differ,
    )
    fixable = member_requests(
        documents.needs,
        documents.cross_checks,
        documents.edits,
        claim.retake_fields,
        settings,
        {d.document_id: d.kind for d in documents.documents},
    )
    human_only = human_reasons(
        rule_results, documents.edits, documents.cross_checks, claim.retake_fields, settings
    )

    def decide(p_good: float, disagreement: float) -> LaneChoice:
        return choose_lane(
            rule_results,
            votes,
            p_good,
            disagreement,
            payout,
            claim.retries_used,
            settings,
            blockers,
            member_fixable=fixable,
            human_only=human_only,
        )

    guarded, case_review = decide_with_reviewer(case, votes, decide, settings, case_reviewer, now)
    combined, disagreement, p_good = guarded.combined_score, guarded.disagreement, guarded.p_good
    choice = guarded.choice

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
        edits=documents.edits,
        document_kinds={d.document_id: d.kind for d in documents.documents},
        needs_missing=[list(n.group) for n in documents.missing],
        cross_checks=documents.cross_checks,
        case_review=case_review,
    )
    store.save_decision(decision)
    store.save_claim(claim)
    store.save_readings(claim.claim_id, documents.raw_readings)
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
