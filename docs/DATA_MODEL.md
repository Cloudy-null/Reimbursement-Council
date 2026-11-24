# Data model

The shapes every stage passes around. Loosely based on the HL7 FHIR claim resources (Claim, ClaimResponse, ExplanationOfBenefit, Coverage) so the names make sense to anyone from health insurance, but simplified for this project. Money in halalas, dates in ISO 8601, see CONVENTIONS.md.

The code for these shapes lives in reimbursement_council/core/models/. Every model forbids unknown keys and is frozen.

## Reference data

Member
- member_id, display_name, date_joined
- name_ar (optional): the member's name in Arabic, used to match the patient name on Arabic documents
- policy_id
- No nationality, gender or age fields. On purpose (see spec, anti-goals).

Policy (like FHIR Coverage)
- policy_id, tier, start_date, end_date, status (active, inactive)
- covered_people: list of member_id
- Limits and co-pay are not stored per policy. They come from the policy's tier in config/policy.yaml: limits_halalas per benefit category, and copay_rate per benefit category (a fraction, 0.10 means 10 percent).

Provider
- provider_id, name, vat_number, city, in_network (bool)
- trust_score (0 to 1), from past claims history, neutral 0.5 for unknown
- An unknown provider (no match on VAT number) has provider_id "unknown", trust 0.5, in_network false.

MemberHistory
- member_id, past_claims, past_claims_paid (never more than past_claims)
- limits_used: halalas already used per benefit category in this policy period
- A member with no record has an empty history (0 past claims, nothing used).

PriceListItem
- service_code, description, network_price, category (benefit category, for example outpatient, lab, pharmacy)

## A claim

Claim (like FHIR Claim)
- claim_id, member_id, patient_member_id, policy_id, submitted_at (timezone-aware)
- status: draft, submitted, decided
- documents: list of Document
- retries_used (for self-fix)
- claim_categories: benefit categories of the claim (worked out from the invoice, or set by the member); detected_categories: what the system worked out, kept so a member change can be compared
- edits: list of FieldEdit (fields the member changed on the check screen)
- retake_fields: fields the member was already asked to retake a photo for (a retake is asked only once)

Document
- document_id, claim_id, kind (receipt, invoice, prescription, medical_report, other), file_path, image_hash, uploaded_at
- kind_source: detected or member; detected_kind: what the system found, kept when the member changes the kind
- Receipts and invoices are billing documents. The billing document with a ZATCA QR, else the first invoice, else the first receipt, is the primary one used for the payout.

FieldEdit
- document_id, field, read_value (or none), typed_value
- evidence: supports, contradicts or none, from the QR on the same document, the same field on another document, or the arithmetic checks; evidence_note says which

ExtractedField
- document_id, name (provider_name, vat_number, invoice_timestamp, treatment_date, subtotal, vat_total, total, patient_name)
- value, original_text
- source: qr, ocr, vision, member_confirmed, member_typed, reviewer. member_typed is a value the member typed on the check screen. ocr is the default offline reader. vision is the optional Gemini reader.
- confidence (0 to 1)
- location: page and box, optional
- Value format: money fields are halalas as digits ("17250"), checked when the field is built, so a reader that hands over "22.50" is refused. treatment_date is YYYY-MM-DD in local time, invoice_timestamp is the raw ISO text from the receipt, the rest is text.

LineItem
- description, service_code (matched, optional), quantity, unit_price, amount, confidence (0 to 1)

CheckResult (arithmetic and QR match)
- name (items_sum_to_subtotal, vat_is_15_percent, subtotal_plus_vat_is_total, qr_matches_text)
- passed (bool), details, fields (the fields the check looked at)
- items_sum_to_subtotal compares the items with the subtotal, else with total minus VAT, else with the total.
- Any failed check blocks auto approve.

ReaderOutput (what a reader returns for one document)
- fields: list of ExtractedField, line_items: list of LineItem, qr_payloads: list of raw QR strings, text_lines: the read text row by row (used to find the document type)

ExtractionResult (one document after QR merge and checks)
- document_id, fields, line_items, checks

RuleResult (hard rules)
- rule (late, policy_inactive, person_not_covered, excluded_service, duplicate, multiple_patients, member_edit)
- member_edit is not_sure when a member edit contradicts the evidence, or a type or category change removes a required document
- outcome: pass, fail, not_sure (data below the confidence floor)
- reason (plain text), fields (the fields the rule looked at)

ReceiptKeys and SeenReceipts (duplicate check)
- fingerprint: VAT number, invoice time in UTC, total. A confident match is a duplicate.
- weak_key: VAT number, treatment date, total. A match is only a possible duplicate, sent to a human.
- The store keeps one receipt row per claim with its lane. Receipts of rejected claims are not counted.

ClaimCase (what every council member reads)
- claim, member, policy, provider, history
- extraction (the primary billing document, or none), rule_results, payout (or none)
- documents_read: one ExtractionResult per document; needs: list of DocumentNeed; cross_checks: list of CrossCheckResult

DocumentNeed (computed, not stored)
- group: the kinds where any one is enough (for example invoice or receipt), satisfied (bool), request (Arabic and English text asking for it)

CrossCheckResult
- name (patient_matches_account, dates_agree, providers_agree), passed (true, false, or none when there is not enough data), field, document_ids, details

Vote (one per council member)
- member (document_checker, coverage_checker, price_checker, case_reviewer, history_member)
- score (0 to 1), weight (copied from config at decision time)
- reason (plain text), evidence (list of field names or document boxes)
- request (optional plain text, for self-fix), request_kind (retake_photo, add_document, confirm_field), request_field (the field or document asked for). The three are all set or all empty.

PayoutResult
- requested (item amounts plus VAT on the receipt)
- network_cap_cut, copay, limit_cut, vat_paid
- calculated (what we pay)
- unmatched_items (descriptions of items not in the price list)
- is_partial (true when the network cap or a limit cut the payout, or an item is unmatched; co-pay alone does not make it partial)

SelfFixRequest
- kind (retake_photo, add_document, confirm_field), field, text

Decision (like FHIR ClaimResponse)
- claim_id, decided_at, config_version (hash of the config files)
- combined_score, p_good (calibrated), disagreement
- payout_requested, payout_calculated, expected_loss, reviewer_time_value
- lane: auto_approve, auto_reject, self_fix, human_review
- lane_reason (plain text, why it is in this lane)
- outcome: complete, partial, error, queued
- self_fix_request (for the self_fix lane)
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

Review and GroundTruth are built in later layers.
