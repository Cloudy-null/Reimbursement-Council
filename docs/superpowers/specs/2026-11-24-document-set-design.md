# Document set, check before submit, and cross-document checks

Date: 2026-11-24
Status: draft, waiting for owner approval.
Source: docs/brief/project-brief.md (official brief), owner requests on 2026-11-24.

## 1. Why

The brief asks for a claim journey with no manual data entry: the member uploads documents, the system reads them, finds what is missing or does not match, and tells the member exactly what to fix before the claim is sent. Today the website takes one photo, treats it as a receipt, and decides at once. Other documents are stored but never read ("not read yet in this version").

This is the first of four pieces the owner ordered: (1) this piece, (2) JSON export, (3) PDFs and consent, (4) the six UI items, samples page last.

## 2. Goals
- The member uploads several files for one claim. Each file gets a type (invoice, receipt, prescription, medical_report, other) without the member typing it.
- The system works out which documents the claim needs and names any missing one before submit, with a specific request ("Add the prescription for Ibuprofen 400 mg").
- The member sees what was read, can correct it, and then submits.
- Patient, treatment date and provider must agree across documents. A mismatch lowers confidence and asks the member.
- An edit that matches the evidence is fine. An edit that contradicts the evidence goes to a human, with read and typed values side by side.
- Every new rule is measured by the harness on synthetic claims with known right answers.

## 3. Non-goals (later pieces or never)
- PDFs and scanned multi-page files (piece 3). This piece takes PNG and JPG only.
- Consent step and masking personal data in logs (piece 3).
- JSON export and JSON Schema (piece 2).
- Account sign-in, queue colors, samples page, tiers (piece 4).
- Reading medicine names or diagnoses for medical meaning. We read who, when and where, not the medical content.

## 4. Anti-goals (a failure even if it works)
- The member has to type what is already on the documents.
- A member edit can raise the payout with no human seeing it.
- A missing or mismatched document leads to a rejection. Missing documents and mismatches ask the member or a human; only hard rules reject (as today).
- Any document or text leaves the computer (decision 004: offline only).

## 5. Approaches

Picked by the owner on 2026-11-24 (first option in each):

1. Document type: keyword match on the text the reader already finds, in Arabic and English, plus whether a ZATCA QR is present. The member sees the type and can change it. Rejected: the member picks every type (manual entry), a trained classifier (no labeled data).
2. Claim type: worked out from the services read on the invoice or receipt (their price list categories). The member can change it. Rejected: the member picks it first (manual entry).
3. Required documents: config/documents.yaml per benefit category, made-up starting values until Bupa's week 2 process material arrives.
4. Cross-document checks: each document's patient name is compared with the patient's registered names (Arabic and English) on the account, not document with document. Treatment date and provider are compared between documents.

## 6. Design

### 6.1 Config: config/documents.yaml (new)
- `required_by_category`: for each benefit category, a list of required document groups. A group is a list of kinds where any one is enough. Starting values (made up, CHECK for the owner and for the week 2 material):
  - outpatient: [[invoice, receipt], [medical_report]]
  - pharmacy: [[invoice, receipt], [prescription]]
  - lab: [[invoice, receipt]]
  - radiology: [[invoice, receipt], [medical_report]]
  - dental: [[invoice, receipt]]
- `kind_keywords`: for each kind, words in English and Arabic (for example prescription: "prescription", "rx", "وصفة طبية", "وصفة"; medical_report: "medical report", "diagnosis", "تقرير طبي", "التشخيص"; invoice: "tax invoice", "فاتورة ضريبية"; receipt: "receipt", "إيصال").
- `kind_match_ratio`: similarity needed for a keyword (same idea as the label match ratio today).
- `name_match_ratio`: similarity needed for a patient name to count as the same person.
- `date_tolerance_days`: how far apart treatment dates on different documents may be and still agree (start 0; a report written the day after is a CHECK for the owner).
- `cross_check_score_factor`: how much a mismatch lowers the document checker's score.
- Loaded and validated in the one config loader, part of config_version, like the other files.

### 6.2 Data model changes (DATA_MODEL.md updated with them)
- Member gets `name_ar` (optional). The synthetic generator fills it from the people it already has.
- Document gets `kind_source`: "detected" or "member". The kind itself keeps its current field.
- ExtractedField source gets a new value `member_typed`.
- New `FieldEdit`: document_id, field, read_value (or none), typed_value, evidence (supports, contradicts, none), evidence_note (plain text: which QR, document or check).
- Claim gets `claim_categories` (list of benefit categories, worked out or changed by the member) and `edits` (list of FieldEdit).
- New `DocumentNeed`: group (list of kinds), satisfied (bool), request_text. A list of these is computed, not stored.
- New `CrossCheckResult`: name (patient_matches_account, dates_agree, providers_agree), passed (bool or none when there is not enough data), document_ids, details.
- ClaimCase gets `documents_read` (one ExtractionResult per document), `needs` and `cross_checks`. `extraction` stays: it is the primary invoice or receipt, so the payout and the current members keep working.
- RuleResult gets a new rule `member_edit` (outcome not_sure when an edit contradicts evidence).

### 6.3 Reading every document
- The pipeline reads every document, not only the first receipt. The receipt parser already finds patient, date and provider by labels; the same parser is used for prescriptions and reports, and money fields from non-billing documents are ignored.
- core/document_kinds.py (pure): detect the kind from the OCR text and QR presence using kind_keywords. A ZATCA QR means invoice or receipt. No keyword match means "other".
- core/claim_categories.py (pure): the benefit categories of the matched line items on the billing document. No matched items gives an empty list, and then the member picks the category on the check screen.
- core/document_needs.py (pure): from the categories and the kinds present, the list of DocumentNeed, with request text from config/messages.yaml in Arabic and English.
- core/cross_checks.py (pure): the three cross checks. Names are compared with the patient's name_en or name_ar, picking the one in the same script as the read name. Missing data gives passed = none, not a failure.
- Which documents must share a provider (my call): only a medical report and the invoice or receipt of an outpatient or dental claim. A prescription often comes from a clinic and the invoice from a pharmacy, and a lab or radiology invoice often comes from a different place than the report, so those pairs are not compared for provider. Patient and date are compared on every document.
- Reading happens once, at upload (my call). Each document's ReaderOutput is stored with the draft claim. process_claim gets the stored readings as an argument and reads only documents that have none (the harness and run-claim pass none, so they read as today). This way the pipeline judges exactly what the member saw, and FieldEdit.read_value always matches.
- An invoice and a receipt for the same purchase (my call): both are allowed. The one with a ZATCA QR, else the invoice, is the primary billing document used for the payout. The other is evidence: its total and VAT number are compared with the primary. The blocker "more than one receipt or invoice" stays only when two billing documents disagree on the total, because then we do not know which purchase is claimed.

### 6.4 What decides the lane
choose_lane gets explicit paths, in this order (my call): (1) a hard rule failed: auto_reject; (2) a member edit contradicts evidence: human_review; (3) possible duplicate: human_review; (4) a required document is missing: self_fix with an add_document request, human_review with no retries left; (5) a cross-check mismatch: self_fix with a request to replace the document or correct the field, human_review with no retries left; (6) a hard rule could not run: as today; (7) approve or score paths as today. Paths 4 and 5 do not depend on the score, so the harness can expect self_fix for those defects. When a document is missing and there is also a mismatch, the missing document is asked for first, because adding it can settle both. The document checker makes the add_document and mismatch requests.

- Missing required document: an approval blocker (never auto approve) and a council request of kind add_document naming the missing group. With retries left this is self_fix; without, human_review.
- Cross-check mismatch: the document checker's score is multiplied by cross_check_score_factor and it adds a confirm_field request naming the field and the two documents. This lowers p_good and usually gives self_fix.
- Member edit that contradicts evidence: rule `member_edit` is not_sure, and choose_lane sends it to human_review straight away (the same special path as a possible duplicate), never self_fix, because asking the same member again does not settle it. The reviewer card shows read and typed values side by side with the evidence note.
- Member edit that matches evidence: the field is used with source member_typed and its evidence confidence. No human needed.
- Member edit with no evidence either way (my call): a field that feeds the payout or a hard rule (subtotal, VAT, total, treatment date, invoice time, patient name, VAT number) counts as contradicting and goes to a human. Asking the member again would only loop. Any other field (provider name) is used as member_typed.
- Changing a document's type or the claim category is also an edit (my call). If the change removes a required document that the detected type or category asked for, it goes to a human like a contradicting edit. A change that adds a requirement, or keeps the same requirements, needs no human.
- What clears a mismatch on the second try (my call): replacing or adding a document, or correcting the field so it matches the other documents. If the member keeps the mismatched value and sends again, that is an edit that contradicts evidence, so it goes to a human, not round again.
- Evidence for an edit, in order: the QR on the same document, the same field on another document, the arithmetic checks with the edited value put in. One source that agrees is "supports"; one that disagrees (and none that agrees) is "contradicts".
- Only hard rules reject, as today.

### 6.5 Website: two steps
- Step 1, upload: pick the person (the current list stays until piece 4), add one or more PNG or JPG files. Nothing is decided yet. The claim is saved with status draft.
- Step 2, check: each document is shown with its photo, its detected type (a select to change it), and the read fields. The billing document's fields are editable (the read value is filled in). Above them: missing documents as specific requests with an "add a file" button, and cross-check mismatches in plain words. The claim category is shown, and can be changed only when no category was worked out or the member opens it on purpose.
- Submit sends the claim with its edits and kinds to the pipeline. The member can submit with a document still missing; the page says this will come back as a request.
- Arabic and English, using the existing i18n file, DESIGN.md tokens and components. Screenshots and the Impeccable audit as in CLAUDE.md.
- The self-fix page today replaces the one photo. It changes to "add or replace a document", using the same check step.

### 6.6 Synthetic data and the harness
- Drawing: adapters/document_drawing.py (new) draws a prescription and a medical report with Pillow, reusing the receipt canvas: provider header, patient, date, doctor, and medicines or a short diagnosis line. Same fonts, same damage presets.
- Claim sets: each claim gets the documents its category needs. New defects, each with its expected lane in the truth: missing_prescription and missing_medical_report (self_fix, request names the document), patient_name_mismatch and date_mismatch on the second document (self_fix, confirm_field), member_edit_supported and member_edit_contradicts (simulated edits: none and human_review). They are added through the add-defect-type skill.
- Truth gets `document_kinds` (true kind per document), `needs_missing` (the true missing groups) and `expected_lane` for the defects whose lane is fixed by a rule (missing documents, mismatches, contradicting edits). run-set reports how often the lane matched.
- Old seeds (my call): the new defects change which defect each claim gets, so seeds 11 and 12 will make different claims than the day 3 runs. That is fine: every recorded result names its commit, and the baselines are run again on the new sets before E12. Extra documents are drawn from their own random stream per claim, so a claim's receipt stays the same when only its documents change.
- New run-set metrics: document type accuracy, missing document recall and precision (a needed document flagged, nothing flagged that was there), cross-check catch rate and false alarm rate, and the existing lane metrics.
- New experiment row in EXPERIMENTS.md: E12 cross-document checks (switch cross_checks_enabled in config/decision.yaml), measured off vs on with run-ablation. Missing document flags are not switched off: they are a product rule, not a tuning idea.

### 6.7 Code layers
- core/: document_kinds, claim_categories, document_needs, cross_checks, edit_evidence (all pure, with unit tests first).
- adapters/: document_drawing (new), readers (read any kind), storage (draft claims, edits).
- pipeline/process_claim.py: read all documents, build needs and cross checks, apply edits, then the stages as today.
- web/: the two steps; app.py is 324 lines today, so routes for the claim journey move to web/claim_routes.py (a split proposed under the 300 line rule).

## 7. Constraints
- Offline only, no new library (Pillow, EasyOCR and the existing parser are enough).
- Every threshold, ratio and required document list lives in config.
- Tests first for every core function and pipeline stage; ruff, mypy and pytest pass before each commit.

## 8. Left to the builder
- Exact keyword lists and starting ratios (in config, tuned later on synthetic_tune).
- Layout of the drawn prescription and report, within DESIGN.md for the website and plain document style for the drawings.
- How the check page lays out several documents on a phone.

## 9. Calls made in this design, for the owner to check
- Lane order: hard rule fail, contradicting edit, duplicate, missing document, mismatch, unclear hard rule, then the score paths.
- Reading once at upload; the pipeline judges the stored reading.
- Provider is compared only between a medical report and an outpatient or dental invoice.
- An invoice and a receipt for one purchase are both allowed; the QR one is primary, the other is evidence.
- A no-evidence edit to any field that feeds the payout or a hard rule goes to a human.
- Changing a type or category that removes a required document goes to a human.
- Keeping a mismatched value on the second try goes to a human.
- New sets replace the old seeds' claims; baselines are run again before E12.
- A date mismatch between documents starts at 0 days of tolerance.
- Required documents per category are made up until the week 2 material.
- Missing documents block auto approve and ask the member; they never reject.
- Member's Arabic name is added to the account data.
