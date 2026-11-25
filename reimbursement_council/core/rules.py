"""Hard rules: yes or no vetoes. A rule only runs on data at or above the confidence floor.

Below the floor the answer is not_sure, which sends the claim to the member to confirm
instead of rejecting it on a guess.
"""

from collections.abc import Sequence
from datetime import date

from reimbursement_council.config.models import Settings
from reimbursement_council.core.dates import local_date_of, utc_timestamp
from reimbursement_council.core.models.claim import Claim, ExtractionResult
from reimbursement_council.core.models.common import FieldName, Model, RuleName, RuleOutcome
from reimbursement_council.core.models.decision import RuleResult
from reimbursement_council.core.models.reference import Policy

NO_RECEIPT = ["receipt"]


class SeenReceipts(Model):
    """Receipts already sent in other claims that were not rejected."""

    fingerprints: frozenset[str]
    image_hashes: frozenset[str]
    weak_keys: frozenset[str] = frozenset()


class ReceiptKeys(Model):
    """How we recognize a receipt again, whatever the confidence of its parts.

    fingerprint: seller VAT number, invoice time (in UTC) and total. A match on a confident
    fingerprint is a duplicate. weak_key: VAT number, treatment date and total. A match is
    only a possible duplicate (two family members can pay the same clinic the same price on
    the same day), so it goes to a human, never to rejection.
    """

    fingerprint: str | None
    weak_key: str | None


def _result(rule: RuleName, outcome: RuleOutcome, reason: str, fields: list[str]) -> RuleResult:
    return RuleResult(rule=rule, outcome=outcome, reason=reason, fields=fields)


def _confident_value(extraction: ExtractionResult, name: FieldName, floor: float) -> str | None:
    field = extraction.best(name)
    if field is None or field.confidence < floor:
        return None
    return field.value


def _value(extraction: ExtractionResult, name: FieldName) -> str | None:
    field = extraction.best(name)
    return None if field is None else field.value


def receipt_keys(extraction: ExtractionResult, offset_hours: int) -> ReceiptKeys:
    vat = _value(extraction, "vat_number")
    total = _value(extraction, "total")
    timestamp = _value(extraction, "invoice_timestamp")
    day = _value(extraction, "treatment_date")
    instant = None if timestamp is None else utc_timestamp(timestamp, offset_hours)
    fingerprint = f"{vat}|{instant}|{total}" if vat and instant and total else None
    weak_key = f"{vat}|{day}|{total}" if vat and day and total else None
    return ReceiptKeys(fingerprint=fingerprint, weak_key=weak_key)


def _fingerprint_confident(extraction: ExtractionResult, floor: float) -> bool:
    return all(
        _confident_value(extraction, name, floor) is not None
        for name in ("vat_number", "invoice_timestamp", "total")
    )


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
    submitted = local_date_of(claim.submitted_at, settings.policy.local_utc_offset_hours)
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
    fields = ["patient_member_id", "member_id"]
    if claim.patient_member_id not in policy.covered_people:
        return _result("person_not_covered", "fail", "Patient is not on the policy.", fields)
    if claim.member_id not in policy.covered_people:
        return _result(
            "person_not_covered", "fail", "The member filing is not on this policy.", fields
        )
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
    if extraction is None:
        return _result("duplicate", "pass", "Not seen in another claim.", fields)
    keys = receipt_keys(extraction, settings.policy.local_utc_offset_hours)
    if keys.fingerprint is not None and keys.fingerprint in seen.fingerprints:
        if _fingerprint_confident(extraction, settings.decision.hard_rule_confidence_floor):
            return _result(
                "duplicate", "fail", "The same receipt was sent in another claim.", fields
            )
        return _result(
            "duplicate", "not_sure", "May be a receipt already sent; parts are unclear.", fields
        )
    if keys.weak_key is not None and keys.weak_key in seen.weak_keys:
        return _result(
            "duplicate",
            "not_sure",
            "Same provider, date and total as a receipt in another claim.",
            fields,
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


def date_reading(
    primary: ExtractionResult | None, others: Sequence[ExtractionResult], floor: float
) -> ExtractionResult | None:
    """The reading the date rules use: the billing document, or, when it has no confident
    date, the other document with the most confident one (fix/final: a claim with no receipt
    but a report dated two years ago was sent to a person instead of rejected as late)."""
    if primary is not None and _confident_date(primary, floor) is not None:
        return primary
    dated = [r for r in others if _confident_date(r, floor) is not None]
    if not dated:
        return primary
    return max(dated, key=lambda r: r.best("treatment_date").confidence)  # type: ignore[union-attr]


def run_hard_rules(
    claim: Claim,
    policy: Policy,
    extraction: ExtractionResult | None,
    image_hash: str | None,
    seen: SeenReceipts,
    settings: Settings,
    dated: ExtractionResult | None = None,
) -> list[RuleResult]:
    """Every hard rule, always in the same order. When the billing document cannot tell the
    date, a confident date on another document (`dated`) may make a date rule fail, never pass:
    the member is still asked about an unclear date, but a claim that is plainly late or
    outside the policy is rejected (fix/final)."""
    late = _late(claim, extraction, settings)
    inactive = _policy_inactive(policy, extraction, settings)
    if dated is not None and dated is not extraction:
        if (
            late.outcome == "not_sure"
            and (other := _late(claim, dated, settings)).outcome == "fail"
        ):
            late = other
        inactive_other = _policy_inactive(policy, dated, settings)
        if inactive.outcome == "not_sure" and inactive_other.outcome == "fail":
            inactive = inactive_other
    return [
        late,
        inactive,
        _person_not_covered(claim, policy),
        _excluded_service(extraction, settings),
        _duplicate(extraction, image_hash, seen, settings),
        _multiple_patients(extraction, settings),
    ]
