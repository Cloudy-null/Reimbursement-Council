"""Hard rules: yes or no vetoes. A rule only runs on data at or above the confidence floor.

Below the floor the answer is not_sure, which sends the claim to the member to confirm
instead of rejecting it on a guess.
"""

from datetime import date

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import Claim, ExtractionResult
from reimbursement_council.core.models.common import FieldName, Model, RuleName, RuleOutcome
from reimbursement_council.core.models.decision import RuleResult
from reimbursement_council.core.models.reference import Policy

NO_RECEIPT = ["receipt"]


class SeenReceipts(Model):
    """Receipts already sent in other claims."""

    fingerprints: frozenset[str]
    image_hashes: frozenset[str]


def _result(rule: RuleName, outcome: RuleOutcome, reason: str, fields: list[str]) -> RuleResult:
    return RuleResult(rule=rule, outcome=outcome, reason=reason, fields=fields)


def _confident_value(extraction: ExtractionResult, name: FieldName, floor: float) -> str | None:
    field = extraction.best(name)
    if field is None or field.confidence < floor:
        return None
    return field.value


def receipt_fingerprint(extraction: ExtractionResult, floor: float) -> str | None:
    """Seller VAT number, full invoice timestamp and total. None if any part is unclear."""
    parts = [
        _confident_value(extraction, name, floor)
        for name in ("vat_number", "invoice_timestamp", "total")
    ]
    if any(part is None for part in parts):
        return None
    return "|".join(part for part in parts if part is not None)


def _confident_date(extraction: ExtractionResult, floor: float) -> date | None:
    field = extraction.best("treatment_date")
    if field is None or field.confidence < floor:
        return None
    return extraction.day("treatment_date")


def _late(claim: Claim, extraction: ExtractionResult | None, settings: Settings) -> RuleResult:
    if extraction is None:
        return _result(
            "late", "not_sure", "No receipt to read the treatment date from.", NO_RECEIPT
        )
    fields = ["treatment_date"]
    treated = _confident_date(extraction, settings.decision.hard_rule_confidence_floor)
    if treated is None:
        return _result("late", "not_sure", "Treatment date is missing or unclear.", fields)
    submitted = claim.submitted_at.date()
    if treated > submitted:
        return _result("late", "not_sure", "Treatment date is after the submission date.", fields)
    days = (submitted - treated).days
    window = settings.policy.claim_window_days
    if days > window:
        return _result("late", "fail", f"Sent {days} days after treatment, limit {window}.", fields)
    return _result("late", "pass", f"Sent {days} days after treatment.", fields)


def _policy_inactive(
    policy: Policy, extraction: ExtractionResult | None, settings: Settings
) -> RuleResult:
    rule: RuleName = "policy_inactive"
    if extraction is None:
        return _result(rule, "not_sure", "No receipt to read the treatment date from.", NO_RECEIPT)
    fields = ["treatment_date"]
    treated = _confident_date(extraction, settings.decision.hard_rule_confidence_floor)
    if treated is None:
        return _result(rule, "not_sure", "Treatment date is missing or unclear.", fields)
    if policy.status != "active":
        return _result(rule, "fail", "Policy is not active.", fields)
    if not policy.start_date <= treated <= policy.end_date:
        return _result(rule, "fail", "Treatment date is outside the policy dates.", fields)
    return _result(rule, "pass", "Policy was active on the treatment date.", fields)


def _person_not_covered(claim: Claim, policy: Policy) -> RuleResult:
    fields = ["patient_member_id"]
    if claim.patient_member_id not in policy.covered_people:
        return _result("person_not_covered", "fail", "Patient is not on the policy.", fields)
    return _result("person_not_covered", "pass", "Patient is on the policy.", fields)


def _excluded_service(extraction: ExtractionResult | None, settings: Settings) -> RuleResult:
    rule: RuleName = "excluded_service"
    fields = ["line_items"]
    if extraction is None:
        return _result(rule, "pass", "No line items to check.", fields)
    floor = settings.decision.hard_rule_confidence_floor
    excluded = [
        item for item in extraction.line_items if item.service_code in settings.policy.exclusions
    ]
    if any(item.confidence >= floor for item in excluded):
        codes = sorted({str(item.service_code) for item in excluded})
        return _result(rule, "fail", f"Excluded service: {', '.join(codes)}.", fields)
    if excluded:
        return _result(rule, "not_sure", "A line item may be an excluded service.", fields)
    return _result(rule, "pass", "No excluded services.", fields)


def _duplicate(
    extraction: ExtractionResult | None,
    image_hash: str | None,
    seen: SeenReceipts,
    settings: Settings,
) -> RuleResult:
    fields = ["image_hash", "vat_number", "invoice_timestamp", "total"]
    if image_hash is not None and image_hash in seen.image_hashes:
        return _result("duplicate", "fail", "The same image was sent in another claim.", fields)
    if extraction is not None:
        fingerprint = receipt_fingerprint(extraction, settings.decision.hard_rule_confidence_floor)
        if fingerprint is not None and fingerprint in seen.fingerprints:
            return _result(
                "duplicate", "fail", "The same receipt was sent in another claim.", fields
            )
    return _result("duplicate", "pass", "Not seen in another claim.", fields)


def _normalize_name(name: str) -> str:
    return " ".join(name.casefold().split())


def _multiple_patients(extraction: ExtractionResult | None, settings: Settings) -> RuleResult:
    rule: RuleName = "multiple_patients"
    fields = ["patient_name"]
    if extraction is None:
        return _result(rule, "pass", "No patient names to check.", fields)
    floor = settings.decision.hard_rule_confidence_floor
    names = extraction.all_named("patient_name")
    confident = {_normalize_name(f.value) for f in names if f.confidence >= floor}
    every = {_normalize_name(f.value) for f in names}
    if len(confident) > 1:
        return _result(rule, "fail", f"{len(confident)} different patient names.", fields)
    if len(every) > 1:
        return _result(rule, "not_sure", "Patient names may differ.", fields)
    return _result(rule, "pass", "One patient.", fields)


def run_hard_rules(
    claim: Claim,
    policy: Policy,
    extraction: ExtractionResult | None,
    image_hash: str | None,
    seen: SeenReceipts,
    settings: Settings,
) -> list[RuleResult]:
    """Every hard rule, always in the same order."""
    return [
        _late(claim, extraction, settings),
        _policy_inactive(policy, extraction, settings),
        _person_not_covered(claim, policy),
        _excluded_service(extraction, settings),
        _duplicate(extraction, image_hash, seen, settings),
        _multiple_patients(extraction, settings),
    ]
