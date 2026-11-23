# Data model

The shapes every stage passes around. Loosely based on the HL7 FHIR claim resources (Claim, ClaimResponse, ExplanationOfBenefit, Coverage) so the names make sense to anyone from health insurance, but simplified for this project. Money in halalas, dates in ISO 8601, see CONVENTIONS.md.

## Reference data

Member
- member_id, display_name, date_joined
- policy_id
- No nationality, gender or age fields. On purpose (see spec, anti-goals).

Policy (like FHIR Coverage)
- policy_id, tier, start_date, end_date, status (active, inactive)
- covered_people: list of member_id
- limits: per benefit category, total for the policy period
- copay_percent per benefit category

Provider
- provider_id, name, vat_number, city, in_network (bool)
- trust_score (0 to 1), from past claims history, neutral 0.5 for unknown

PriceListItem
- service_code, description, network_price

## A claim

Claim (like FHIR Claim)
- claim_id, member_id, patient_member_id, policy_id, submitted_at
- status: draft, submitted, decided
- documents: list of Document
- retries_used (for self-fix)

Document
- document_id, claim_id, kind (receipt, invoice, prescription, medical_report, other), file_path, image_hash, uploaded_at

ExtractedField
- document_id, name (provider_name, vat_number, treatment_date, total, vat_total, patient_name, line_item, ...)
- value, original_text
- source: qr, vision, member_confirmed, reviewer
- confidence (0 to 1)
- location: page and box, optional

LineItem
- description, service_code (matched, optional), quantity, unit_price, amount

CheckResult (arithmetic and QR match)
- name (items_sum_to_subtotal, vat_is_15_percent, subtotal_plus_vat_is_total, qr_matches_text)
- passed (bool), details

RuleResult (hard rules)
- rule (late, policy_inactive, person_not_covered, excluded_service, duplicate, multiple_patients)
- outcome: pass, fail, not_sure (data below the confidence floor)
- reason (plain text)

Vote (one per council member)
- member (document_checker, coverage_checker, price_checker, case_reviewer, history_member)
- score (0 to 1), weight (copied from config at decision time)
- reason (plain text), evidence (list of field names or document boxes)
- request (optional plain text, for self-fix), request_kind (retake_photo, add_document, confirm_field)

Decision (like FHIR ClaimResponse)
- claim_id, decided_at, config_version (git commit or config hash)
- combined_score, p_good (calibrated), disagreement
- payout_requested, payout_calculated, expected_loss, review_cost
- lane: auto_approve, auto_reject, self_fix, human_review
- outcome: complete, partial, error, queued
- member_message (plain text, Arabic and English)
- votes, rule_results, check_results

Review (human)
- claim_id, reviewer, started_at, finished_at
- action: approve, approve_amount, reject, ask_member
- amount, reason
- Every review is also stored as a labeled example for tuning.

## Labels (test and synthetic data only)

GroundTruth
- claim_id
- correct_fields (the true values)
- should_pay (bool), correct_payout
- defects (list: late, inactive, excluded, duplicate, over_limit, overpriced, unreadable, qr_mismatch, arithmetic_error, multiple_patients, missing_prescription)
- fixable (bool), fixed_version_document_ids
