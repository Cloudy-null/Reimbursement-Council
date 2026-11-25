# Integration: the claim export

This is brief deliverable 2: structured, submission-ready claim data that a claims system can
read without opening the photos.

- Schema: `schemas/claim-export.schema.json` (JSON Schema 2020-12). It is generated from the
  `ClaimExport` model in `reimbursement_council/core/models/export.py`. A test fails if the two
  drift apart. To write it again: `uv run reimbursement-council write-schema`.
- One claim: `GET /api/claims/{claim_id}/export` on the website. Add `?download=1` to save it
  as a file. The result page and the reviewer card have a "Download claim data (JSON)" button.
  A claim that has not been sent yet, or was sent back to the check step by a fix, gives 409.
- A whole set: `uv run reimbursement-council export-set FOLDER --out outputs/export`. It
  decides every claim, writes one JSON file per claim, checks each file against the schema,
  and writes `summary.json`.
- The export is rebuilt from what is stored (claim, decision, stored readings, review). The
  photos are not read again.

## Rules that hold for every field

- Money is whole halalas (1 SAR = 100 halalas), in fields that end in `_halalas`. No amount is
  ever a decimal number, so no rounding can creep in.
- Dates are `YYYY-MM-DD`. Times carry a UTC offset (`Z` is UTC).
- Every value we read has a `source` (`qr`, `ocr`, `member_typed`, ...) and a `confidence`
  from 0 to 1. A claims system can decide its own trust level.
- People, policies and providers are given by id, pointing into the claims system's own
  records. The export does not repeat a member's name. The patient name read from a document
  is only inside `documents[].fields`, where it is evidence.
- `schema_version` is `"1.0"`. A change that breaks a reader raises it.

## Field by field

### Top level

| Field | What it is |
|---|---|
| `schema_version` | Version of this format, now `"1.0"`. |
| `exported_at` | When this file was made. |
| `claim_id` | Our claim id. |
| `status` | `submitted` once the member sent it. |
| `submitted_at` | When the member sent it. |
| `member_id` | The member who filed the claim. |
| `patient_member_id` | The person treated (may be a family member on the same policy). |
| `policy_id` | The policy the claim is filed under. |
| `categories` | Benefit categories (`outpatient`, `pharmacy`, `lab`, `radiology`, `dental`): found from the services, or picked by the member. |
| `consented_at` | When the member agreed that their documents may be read. Empty only for synthetic claims. |
| `ready_for_processing` | `true` when the claim was auto approved and the payout worked out again from the stored reading agrees with the decided payout, or when a person approved it. A person's review always decides: a rejected review makes it `false`. This is the one flag a claims system needs for straight-through processing. |
| `provider` | See below. |
| `invoice` | See below. Empty when no billing document could be read. |
| `documents` | Every document in the claim. See below. |
| `missing_documents` | Required document groups the claim does not have, for example `[["prescription"]]`. Any one kind in a group is enough. |
| `cross_checks` | Do the documents agree on patient, treatment date and provider? Each has `passed` (`true`, `false`, or empty when there was not enough to compare) and the documents involved. |
| `member_edits` | Values the member changed on the check screen: what was read, what they typed, and whether the evidence (`supports`, `contradicts`, `none`) backs it. |
| `payout` | See below. Empty when there is no billing document. |
| `decision` | See below. |
| `review` | The human reviewer's decision, when there was one. |
| `case_review` | What the AI case reviewer said (decision 010). Empty when it is switched off. `status` is `used`, `discarded` (the answer broke the schema or cited a value we did not read), `skipped` (no answer in time, an error, or the lane is not reviewed) or `benched` (switched off by its health checks); `problem` says why. `score`, `reason` and `cited_fields` are the model's answer; `changed_lane` is `true` when it sent a claim that would be auto approved to a person. It can never approve or reject a claim. |

### provider

| Field | What it is |
|---|---|
| `name` | Provider name as read (the QR gives the Arabic name). |
| `vat_number` | The 15 digit VAT number. |
| `provider_id` | The provider in the claims system, matched by VAT number. Empty when no provider matches. |
| `in_network` | Whether that provider is in the network. Empty when not matched. |

### invoice (the billing document the money comes from)

| Field | What it is |
|---|---|
| `treatment_date`, `invoice_timestamp` | When the treatment was, and the invoice time from the QR. |
| `currency` | Always `SAR`. |
| `subtotal_halalas`, `vat_total_halalas`, `total_halalas` | Amounts after the QR, the arithmetic checks and any member edit the evidence backs. |
| `line_items[]` | Each service: `description`, `service_code` (our price list code, empty when not listed), `category`, `quantity`, `unit_price_halalas`, `amount_halalas`, `confidence`. |
| `checks[]` | Arithmetic and QR checks (`items_sum_to_subtotal`, `qr_matches_text`, ...) with `passed` and a plain reason. |

### documents[]

| Field | What it is |
|---|---|
| `document_id` | Our id for the document. |
| `kind` | `invoice`, `receipt`, `prescription`, `medical_report` or `other`. |
| `kind_source` | `detected` (from the words and the QR) or `member` (the member changed it). |
| `file_name`, `sha256` | The stored file name and a hash of its bytes, to find the original. |
| `is_primary` | `true` for the billing document the money comes from. |
| `fields[]` | Every value read: `name`, `value`, `source`, `confidence`. |

### payout

`requested_halalas` (the billed total), then what is taken off: `network_cap_cut_halalas`
(price above the network price), `copay_halalas`, `limit_cut_halalas` (benefit limit), the VAT
we pay back (`vat_paid_halalas`), and the result, `calculated_halalas`. `unmatched_items` lists
services not on the price list. `is_partial` is `true` when less than the claim is paid.

### decision

`lane` (`auto_approve`, `auto_reject`, `self_fix`, `human_review`), `outcome`, `reason` (plain
words), `p_good` (how likely the claim is right, 0 to 1), `payout_calculated_halalas` (the
payout decided; the `payout` section is its breakdown, worked out again), `decided_at`, `config_version` (a hash
of the settings that made the decision, so it can be reproduced), `self_fix_request` (what we
asked the member), `member_message` (Arabic and English), and `rule_results` (each hard rule
with `pass`, `fail` or `not_sure` and its reason).

## How a claims system would use it

1. Read `ready_for_processing`. When it is `true`, post the payment of
   `decision.payout_calculated_halalas` (or `review.amount_halalas` when a reviewer set an amount) to
   `member_id` under `policy_id`. Nothing needs re-keying.
2. When it is `false`, the `decision.lane` says why: waiting for the member (`self_fix`), with a
   person (`human_review`), or rejected by a hard rule (`auto_reject`, the failed rule is in
   `decision.rule_results`).
3. Keep `config_version` and `exported_at` with the payment, for audit.
4. Check each file against `schemas/claim-export.schema.json` before reading it. Any JSON
   Schema 2020-12 validator works.

## Mapping to HL7 FHIR R4

FHIR R4 has a `Claim` resource for what is asked and a `ClaimResponse` resource for what was
decided. Our export holds both. The mapping below uses the base FHIR R4 resources only. It is a
guide for building an adapter, not a tested conversion.

| Export | FHIR R4 |
|---|---|
| `claim_id` | `Claim.identifier` |
| `status` | `Claim.status` = `active` |
| `categories` | `Claim.type` (pharmacy maps to `pharmacy`, dental to `oral`, the rest to `professional`) |
| (always) | `Claim.use` = `claim` |
| `patient_member_id` | `Claim.patient` (Reference to Patient) |
| `submitted_at` | `Claim.created` |
| `provider.provider_id` | `Claim.provider` (Reference to Organization) |
| `policy_id` | `Claim.insurance.coverage` (Reference to Coverage) |
| `invoice.line_items[]` | `Claim.item[]`: `productOrService` (service code), `servicedDate` (treatment date), `quantity`, `unitPrice` and `net` (halalas / 100, currency SAR) |
| `invoice.total_halalas` | `Claim.total` |
| `documents[]` | `Claim.supportingInfo[]` with an `attachment` per document |
| `decision.outcome`, `decision.lane` | `ClaimResponse.outcome` (`complete`, `partial`, `queued`, `error`) and `ClaimResponse.disposition` (the reason) |
| `payout.calculated_halalas` | `ClaimResponse.payment.amount` and `ClaimResponse.total` |
| `payout` cuts | `ClaimResponse.item.adjudication` (copay, deductible style amounts) |
| `decision.self_fix_request` | `ClaimResponse.processNote` |

What does not map one to one: our confidence per value, the cross checks and the member edits
with their evidence. In FHIR they would go in extensions.

**Saudi Arabia:** the national eClaims system is built on FHIR R4. Source: the Saudi Arabia
jurisdiction page of the FHIR registry (simplifier.net, https://api.simplifier.net/jurisdictions/SA,
mirrored at https://packages.fhir.org/jurisdictions/SA), which says the active FHIR version in
the country is R4 and that the national eClaims system is built on it. Those pages are filled in
from the HL7 State of FHIR survey; we did not find the 2026 survey report itself. Our mapping above
uses base FHIR R4 only: the national profiles add their own required fields and code systems, so
an adapter would still have to follow those profiles.

## Where the numbers come from

The export of the synthetic check set (60 claims, seed 12) and tune set (120 claims, seed 11)
with EasyOCR at commit 55431ba: 60 of 60 and 120 of 120 files valid against the schema. 16 and
21 of them `ready_for_processing`. Commands: `uv run --no-sync reimbursement-council export-set
data/sets/docs/check --reader easyocr --out outputs/export`, and the same with `tune`.
