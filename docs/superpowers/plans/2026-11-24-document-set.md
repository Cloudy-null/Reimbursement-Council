# Document Set, Check Before Submit and Cross-Document Checks: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A claim is a set of documents: each upload gets a type, the claim's needed documents are worked out, patient, date and provider are checked across documents, and the member checks and corrects what was read before submitting.

**Architecture:** New pure modules in `core/` (document kinds, claim categories, document needs, cross checks, edit evidence, member requests) feed a new `pipeline/document_set.py` that reads every document once. `choose_lane` gets explicit member-fixable and human-only inputs. The website gets an upload step and a check step on a draft claim. Synthetic claim sets gain prescriptions and medical reports with known truth.

**Tech Stack:** Python 3.12, pydantic, FastAPI and Jinja2, Pillow, EasyOCR (optional extra), pytest, ruff, mypy. No new library.

**Spec:** `docs/superpowers/specs/2026-11-24-document-set-design.md` (approved 2026-11-24 with the owner's two changes in its section 9). Read it before any task.

## Global Constraints
- Offline only. No new dependency.
- Every threshold, ratio, keyword list and required-document list lives in `config/*.yaml` and is loaded by `config/loader.py` only.
- Layers stay apart: `config/`, `core/` (pure, no I/O), `adapters/`, `pipeline/`, entrypoints (`cli/`, `web/`) thin.
- Every file under about 300 lines; split before going over.
- Tests first for every core function and pipeline stage. Before each commit: `uv run ruff format .`, `uv run ruff check .`, `uv run mypy`, `uv run pytest` all pass.
- Commit messages `<type>: <what changed>`, no Co-Authored-By or generated-by lines.
- Docs and UI text: plain simple English, no emojis, no em dashes. Arabic UI text plain MSA, short sentences.
- Only hard rules reject. Missing documents and mismatches never reject.
- Models forbid unknown keys and are frozen. New fields get defaults so old claim and results JSON still load.
- On this laptop, run uv with `UV_PYTHON_INSTALL_DIR=D:\dev\.uv-python` (HANDOVER section 5).

## Review Focus
1. A photo where nothing is read: its kind is "other", no category is found, and the check screen asks for a clearer photo and lets the member pick the category. No crash, no auto approve. Test in Task 13.
2. The same file uploaded twice in one claim: the second copy (same image hash) is dropped with a note, and it never counts as a second required document. Test in Task 7.
3. A patient name read with different spacing, letter case, Arabic letter forms (أ, ا, ة, ه) or swapped first and last name still matches the account name. Test in Task 5.
4. An edited money field that is empty or not a number (for example "12,50x"): the check page shows a field error and keeps the member's other input. No 500. Test in Task 13.
5. One bad file among several uploads (wrong type or too large): only that file is refused with a message, the others are kept. Test in Task 13.

---

### Task 1: Data model additions

**Files:**
- Modify: `reimbursement_council/core/models/common.py`, `core/models/claim.py`, `core/models/decision.py`, `core/models/case.py`, `core/models/reference.py`
- Modify: `docs/DATA_MODEL.md`
- Test: `tests/core/models/test_document_set_models.py`

**Interfaces:**
- Produces in `common.py`: `FieldSource` gains `"member_typed"`; `RuleName` gains `"member_edit"`; `KindSource = Literal["detected", "member"]`; `EditEvidence = Literal["supports", "contradicts", "none"]`; `CrossCheckName = Literal["patient_matches_account", "dates_agree", "providers_agree"]`; `BILLING_KINDS = PRIMARY_DOCUMENT_KINDS` (alias kept); `RULE_FIELDS: frozenset[str] = MONEY_FIELDS | {"treatment_date", "invoice_timestamp", "patient_name", "vat_number"}`.
- Produces in `reference.py`: `Member.name_ar: str | None = None`.
- Produces in `claim.py`: `Document.kind_source: KindSource = "detected"`, `Document.detected_kind: DocumentKind | None = None`; `FieldEdit(document_id: str, field: FieldName, read_value: str | None, typed_value: str, evidence: EditEvidence = "none", evidence_note: str = "")`; `Claim.claim_categories: list[str] = []`, `Claim.detected_categories: list[str] = []`, `Claim.edits: list[FieldEdit] = []`, `Claim.retake_fields: list[str] = []` (fields the member was already asked to retake; this is how "asked only once" from the spec is recorded); `ReaderOutput.text_lines: list[str] = []`.
- Produces in `decision.py`: `DocumentNeed(group: list[DocumentKind], satisfied: bool, request: MemberMessage)`; `CrossCheckResult(name: CrossCheckName, passed: bool | None, field: FieldName, document_ids: list[str], details: str)`.
- Produces in `case.py`: `ClaimCase.documents_read: dict[str, ExtractionResult] = {}`, `ClaimCase.needs: list[DocumentNeed] = []`, `ClaimCase.cross_checks: list[CrossCheckResult] = []`.

- [ ] **Step 1: Write the failing tests**

```python
def test_old_claim_json_still_loads():
    old = load_fixture_claim("clean")  # tests/fixtures/claims/clean.claim.json as it is today
    assert old.edits == [] and old.claim_categories == [] and old.retake_fields == []
    assert all(d.kind_source == "detected" for d in old.documents)

def test_field_edit_needs_a_typed_value_and_known_evidence():
    with pytest.raises(ValidationError):
        FieldEdit(document_id="d", field="total", read_value="100", typed_value="1", evidence="maybe")

def test_member_name_ar_is_optional():
    assert Member(member_id="m", display_name="Sara", date_joined=date(2023,1,1), policy_id="p").name_ar is None

def test_cross_check_passed_can_be_unknown():
    assert CrossCheckResult(name="dates_agree", passed=None, field="treatment_date", document_ids=[], details="no dates").passed is None
```

- [ ] **Step 2: Run** `uv run pytest tests/core/models/test_document_set_models.py -v`. Expected: FAIL (import errors).
- [ ] **Step 3: Add the fields and models above.** Defaults exactly as listed.
- [ ] **Step 4: Run** the new tests and the whole suite. Expected: PASS, 318 plus the new ones.
- [ ] **Step 5: Update `docs/DATA_MODEL.md`** with every field above, in the same plain style, and add `member_typed` to the source list and `member_edit` to the rule list.
- [ ] **Step 6: Commit** `feat: data model for document sets, member edits and cross checks`

### Task 2: Config for documents

**Files:**
- Create: `config/documents.yaml`
- Modify: `reimbursement_council/config/models.py`, `config/loader.py`, `config/decision.yaml`, `config/messages.yaml`
- Test: `tests/config/test_documents_config.py`

**Interfaces:**
- Produces: `DocumentsConfig(ConfigModel)` with `required_by_category: dict[str, list[list[DocumentKind]]]`, `kind_keywords: dict[DocumentKind, list[str]]`, `kind_match_ratio: Score`, `name_match_ratio: Score`, `date_tolerance_days: int (ge=0)`, `cross_check_score_factor: Score`, `provider_check_categories: list[str]`, `unbacked_edit_confidence: Score`; `Settings.documents: DocumentsConfig`; `DecisionConfig.cross_checks_enabled: bool`; `RequestMessages.missing_document: str` (placeholder `{documents}`), `RequestMessages.mismatch: str` (placeholders `{field}`, `{documents}`); `LanguageMessages.documents: dict[str, str]` (a name per kind).
- `CONFIG_FILES` gains `"documents.yaml"`, so it is part of `config_version`.

Starting values (spec 6.1): required_by_category outpatient `[[invoice, receipt], [medical_report]]`, pharmacy `[[invoice, receipt], [prescription]]`, lab `[[invoice, receipt]]`, radiology `[[invoice, receipt], [medical_report]]`, dental `[[invoice, receipt]]`; kind_keywords as in spec 6.1; kind_match_ratio 0.85; name_match_ratio 0.85; date_tolerance_days 0; cross_check_score_factor 0.5; provider_check_categories `[outpatient, dental]`; unbacked_edit_confidence 0.6 (below the hard rule floor 0.90); `cross_checks_enabled: true`.

- [ ] **Step 1: Write the failing tests**

```python
def test_documents_config_loads_from_repo():
    s = load_settings(REPO_CONFIG, env={})
    assert s.documents.required_by_category["pharmacy"] == [["invoice", "receipt"], ["prescription"]]
    assert s.decision.cross_checks_enabled is True

def test_every_price_category_has_required_documents(tmp_path):
    config = changed_config(tmp_path, "documents.yaml", drop_key("required_by_category", "lab"))
    with pytest.raises(ConfigError, match="lab"):
        load_settings(config, env={})

def test_unknown_document_kind_rejected(tmp_path):
    config = changed_config(tmp_path, "documents.yaml", set_key("required_by_category", "lab", value=[["photo"]]))
    with pytest.raises(ConfigError, match="documents.yaml"):
        load_settings(config, env={})

def test_document_names_exist_in_both_languages():
    s = load_settings(REPO_CONFIG, env={})
    assert set(s.messages.en.documents) == set(s.messages.ar.documents) >= {"invoice", "receipt", "prescription", "medical_report", "other"}
```

- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** the model, the loader change (a validator in `load_settings` that every category in `prices.yaml` has a `required_by_category` entry), the yaml files and the Arabic and English message texts.
- [ ] **Step 4: Run** the new tests and the whole suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat: documents.yaml with required documents, kind keywords and cross check settings`

### Task 3: Document kind detection

**Files:**
- Create: `reimbursement_council/core/document_kinds.py`
- Modify: `reimbursement_council/adapters/readers.py` (QrOcrReader fills `text_lines`)
- Test: `tests/core/test_document_kinds.py`, `tests/adapters/test_ocr_reader.py`

**Interfaces:**
- Produces: `detect_kind(text_lines: Sequence[str], qr_payloads: Sequence[str], config: DocumentsConfig) -> DocumentKind`.
- Rule: a QR payload means a billing document ("invoice" when an invoice keyword is found, else "receipt"). Without a QR, the kind with the best keyword match at or above `kind_match_ratio` wins, ties broken in the order invoice, receipt, prescription, medical_report. No match gives "other". Matching uses `normalize_text` and the same windowed similarity as the receipt parser's labels.

- [ ] **Step 1: Write the failing tests**

```python
def test_qr_means_billing_document(): assert detect_kind(["Al Noor Clinic"], ["AQ..."], cfg()) == "receipt"
def test_tax_invoice_with_qr_is_invoice(): assert detect_kind(["فاتورة ضريبية"], ["AQ..."], cfg()) == "invoice"
def test_arabic_prescription(): assert detect_kind(["وصفة طبية", "المريض: عمر"], [], cfg()) == "prescription"
def test_english_report_with_ocr_typo(): assert detect_kind(["MEDICAL REP0RT", "Diagnosis"], [], cfg()) == "medical_report"
def test_nothing_known_is_other(): assert detect_kind(["hello"], [], cfg()) == "other"
def test_ocr_reader_keeps_row_text(tmp_path): # FakeEngine lines -> output.text_lines == rows joined in reading order
```

- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** `detect_kind`; in `QrOcrReader.read`, set `text_lines=[join_row(row) for row in group_rows(lines, cfg.row_overlap)]`.
- [ ] **Step 4: Run** them and the suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat: detect the document type from its text and QR`

### Task 4: Claim categories and document needs

**Files:**
- Create: `reimbursement_council/core/claim_categories.py`, `reimbursement_council/core/document_needs.py`
- Test: `tests/core/test_claim_categories.py`, `tests/core/test_document_needs.py`

**Interfaces:**
- Produces: `claim_categories(items: Sequence[LineItem], prices: Mapping[str, PriceListItem]) -> list[str]` (sorted, unique, from matched service codes only).
- Produces: `document_needs(categories: Sequence[str], kinds: Sequence[DocumentKind], settings: Settings) -> list[DocumentNeed]` (union of groups over the categories, each group once, `satisfied` when any kind in the group is present; `request` filled from `requests.missing_document` with the group's document names joined by the language's word for "or").

- [ ] **Step 1: Write the failing tests**

```python
def test_categories_from_matched_items_only():
    assert claim_categories([item("MED-IBU"), item(None)], prices()) == ["pharmacy"]
def test_pharmacy_without_prescription_needs_one():
    needs = document_needs(["pharmacy"], ["receipt"], settings())
    assert [(n.group, n.satisfied) for n in needs] == [(["invoice", "receipt"], True), (["prescription"], False)]
    assert "prescription" in needs[1].request.en.lower()
def test_two_categories_need_the_union_once():
    needs = document_needs(["pharmacy", "outpatient"], ["invoice"], settings())
    assert sorted(tuple(n.group) for n in needs) == [("invoice", "receipt"), ("medical_report",), ("prescription",)]
def test_no_category_needs_only_a_billing_document():
    assert [n.group for n in document_needs([], [], settings())] == [["invoice", "receipt"]]
```

- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** both functions.
- [ ] **Step 4: Run** them. Expected: PASS.
- [ ] **Step 5: Commit** `feat: work out claim categories and the documents a claim needs`

### Task 5: Cross-document checks

**Files:**
- Create: `reimbursement_council/core/cross_checks.py`
- Test: `tests/core/test_cross_checks.py`

**Interfaces:**
- Consumes: `ExtractionResult.best`, `ExtractionResult.day`, `core.text.normalize_text`.
- Produces: `cross_checks(documents: Sequence[tuple[Document, ExtractionResult]], patient: Member, categories: Sequence[str], settings: Settings) -> list[CrossCheckResult]`, always three results in the order patient_matches_account, dates_agree, providers_agree.
- Names: each document's `patient_name` is compared with `patient.name_ar` when it has Arabic letters, else `patient.display_name`. Compare after normalizing (case, spaces, Arabic letter forms أإآ to ا, ة to ه, ى to ي) and sorting the words, with `SequenceMatcher` ratio at or above `name_match_ratio`. No name read on any document: `passed=None`.
- Dates: all read `treatment_date` values within `date_tolerance_days` of each other. Fewer than two dates: `passed=None`.
- Providers: only when a category is in `provider_check_categories` and both a medical_report and a billing document have a `provider_name`; else `passed=None`.

- [ ] **Step 1: Write the failing tests** (include Review Focus 3)

```python
def test_same_patient_in_arabic_and_english_passes()
def test_name_with_letter_forms_case_and_swapped_order_passes():
    # "أحمد  عمر" on the report vs account name_ar "عمر احمد"; "OMAR ahmed" vs display_name "Omar Ahmed"
def test_other_patient_on_report_fails_and_names_both_documents()
def test_dates_one_day_apart_fail_with_zero_tolerance()
def test_pharmacy_claim_never_compares_providers():  # result passed is None
def test_outpatient_report_from_another_clinic_fails()
def test_nothing_read_gives_unknown_not_fail()
```

- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** `cross_checks`.
- [ ] **Step 4: Run** them. Expected: PASS.
- [ ] **Step 5: Commit** `feat: cross-document checks for patient, date and provider`

### Task 6: Edit evidence

**Files:**
- Create: `reimbursement_council/core/edit_evidence.py`
- Test: `tests/core/test_edit_evidence.py`

**Interfaces:**
- Produces: `judge_edit(edit: FieldEdit, own: ExtractionResult, others: Sequence[ExtractionResult], settings: Settings) -> FieldEdit` (returns the edit with `evidence` and `evidence_note` set). Order of evidence: the QR field (source "qr") on `own`; the same field on any of `others`; for money fields, `arithmetic_checks` re-run on `own` with the typed value put in. One agreeing source gives "supports"; else one disagreeing source gives "contradicts"; else "none".
- Produces: `apply_edits(reading: ReaderOutput, edits: Sequence[FieldEdit], settings: Settings) -> ReaderOutput`: replaces the read field with a `member_typed` field for every edit that is "supports", or "none" on a field not in `RULE_FIELDS`. Confidence: `settings.decision.passed_check_confidence` for "supports", `settings.documents.unbacked_edit_confidence` (Task 2) for "none". Contradicting edits are not applied (the read value stays for the payout; the reviewer sees both).

- [ ] **Step 1: Write the failing tests**

```python
def test_total_edit_matching_the_qr_supports()
def test_total_edit_against_the_qr_contradicts_and_names_the_qr()
def test_date_edit_matching_the_prescription_supports()
def test_total_edit_that_makes_subtotal_plus_vat_add_up_supports()
def test_total_edit_with_no_qr_no_other_document_no_arithmetic_is_none()
def test_apply_edits_uses_supported_value_as_member_typed()
def test_apply_edits_keeps_read_value_for_contradicting_edit()
def test_unbacked_provider_name_edit_is_applied_with_capped_confidence()
```

- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** both functions.
- [ ] **Step 4: Run** them. Expected: PASS.
- [ ] **Step 5: Commit** `feat: judge member edits against the QR, other documents and the arithmetic`

### Task 7: Read the whole document set in the pipeline

**Files:**
- Create: `reimbursement_council/pipeline/document_set.py`
- Modify: `reimbursement_council/pipeline/process_claim.py`, `core/decision/blockers.py`, `core/council/document_checker.py`
- Modify: `tests/fixtures/build_fixtures.py` and the fixture claims (add a medical report reading to the outpatient fixtures so their lanes stay what the tests expect, or update the expected lanes where a missing document is now right)
- Test: `tests/pipeline/test_document_set.py`, existing pipeline and fixture tests

**Interfaces:**
- Consumes: Tasks 3 to 6.
- Produces: `class DocumentSet(Model)`: `documents: list[Document]` (kinds as detected or as set by the member), `readings: dict[str, ExtractionResult]`, `primary_id: str | None`, `categories: list[str]`, `needs: list[DocumentNeed]`, `cross_checks: list[CrossCheckResult]`, `edits: list[FieldEdit]` (judged), `notes: list[str]` (for example a dropped duplicate file).
- Produces: `read_document_set(claim: Claim, patient: Member, settings: Settings, reader_for: Callable[[Document], DocumentReader], readings: Mapping[str, ReaderOutput] | None = None) -> DocumentSet`.
  - Drops a second document with the same `image_hash` and adds a note (Review Focus 2).
  - Kind: `detect_kind` unless `kind_source == "member"`.
  - Primary: the billing document with a QR, else the first invoice, else the first receipt.
  - Categories: `claim.claim_categories` when the member set them, else `claim_categories` of the primary's items.
  - Cross checks only when `cross_checks_enabled`; else an empty list.
- Produces: `process_claim(..., readings: Mapping[str, ReaderOutput] | None = None) -> Decision` builds the `ClaimCase` with `documents_read`, `needs`, `cross_checks`, and adds `member_edit` rule results: `not_sure` for every contradicting edit and for every type or category change that removes a requirement the detected kinds or categories had.
- `approval_blockers`: the "more than one receipt" blocker now fires only when two billing documents' totals differ; a missing required document is a blocker.
- `document_checker.vote`: score multiplied by `cross_check_score_factor` once per failed cross check.

- [ ] **Step 1: Write the failing tests**

```python
def test_reads_every_document_and_detects_kinds()
def test_same_file_twice_is_dropped_with_a_note()
def test_primary_is_the_billing_document_with_a_qr()
def test_member_set_kind_is_kept()
def test_member_category_change_that_drops_the_prescription_adds_member_edit_not_sure()
def test_stored_readings_are_used_instead_of_reading_again()
def test_invoice_and_receipt_with_the_same_total_do_not_block()
def test_invoice_and_receipt_with_different_totals_block()
def test_cross_checks_off_by_switch()
```

- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** `read_document_set` and the `process_claim`, blocker and document checker changes; rebuild fixtures with `uv run python tests/fixtures/build_fixtures.py`.
- [ ] **Step 4: Run** the whole suite. Expected: PASS. Any fixture test whose expected lane changed is changed on purpose, with the reason in the test name or a comment.
- [ ] **Step 5: Commit** `feat: the pipeline reads every document in a claim`

### Task 8: Lane groups

**Files:**
- Create: `reimbursement_council/core/decision/document_requests.py`
- Modify: `reimbursement_council/core/decision/lanes.py`, `pipeline/process_claim.py`
- Test: `tests/core/decision/test_lane_groups.py`, `tests/core/decision/test_document_requests.py`

**Interfaces:**
- Produces: `member_requests(needs: Sequence[DocumentNeed], cross_checks: Sequence[CrossCheckResult], edits: Sequence[FieldEdit], retake_fields: Sequence[str], settings: Settings) -> list[SelfFixRequest]`, in the order: missing documents (`add_document`, field = first kind of the group), mismatches (`confirm_field`, text from `requests.mismatch`), retakes for no-evidence edits on `RULE_FIELDS` not yet in `retake_fields` (`retake_photo`).
- Produces: `human_reasons(rule_results: Sequence[RuleResult], edits: Sequence[FieldEdit], retake_fields: Sequence[str]) -> list[str]`: contradicting edits (`member_edit` not_sure), possible duplicate, no-evidence edits on `RULE_FIELDS` already in `retake_fields`.
- Changes: `choose_lane(..., member_fixable: Sequence[SelfFixRequest] = (), human_only: Sequence[str] = ()) -> LaneChoice`. Order: hard rule fail: auto_reject. Member-fixable requests and retries left: self_fix with the first request (the reason lists all). Human-only reasons, or member-fixable with no retries left: human_review with all reasons. Then unclear hard rules and the score paths as today. The old duplicate path becomes one of the human-only reasons.
- `process_claim` passes both lists; when the lane is self_fix with a `retake_photo` request, the field goes into the decision's request so the website can add it to `claim.retake_fields` on the next try.

- [ ] **Step 1: Write the failing tests** (spec 6.4 and section 9)

```python
def test_hard_rule_fail_beats_everything()
def test_missing_document_is_self_fix_even_with_a_high_score()
def test_missing_document_and_contradicting_edit_asks_the_member_first()
def test_second_try_with_only_the_contradicting_edit_left_goes_to_a_human()
def test_possible_duplicate_alone_goes_to_a_human()
def test_no_evidence_total_edit_asks_for_a_retake_first()
def test_no_evidence_total_edit_after_the_retake_goes_to_a_human()
def test_member_fixable_with_no_retries_left_goes_to_a_human()
def test_missing_document_is_asked_before_a_mismatch()
```

- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** the two functions and the `choose_lane` change; wire them in `process_claim`.
- [ ] **Step 4: Run** the whole suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat: lanes ask the member first, then send what is left to a human`

### Task 9: Draw prescriptions and medical reports

**Files:**
- Create: `reimbursement_council/adapters/drawing_canvas.py` (moved from `receipt_drawing.py`: fonts, `shape_text`, `_Canvas`, `Damage`, `DAMAGE_PRESETS`, `_damage`), `reimbursement_council/adapters/document_drawing.py`, `reimbursement_council/synthetic/document_content.py`
- Modify: `reimbursement_council/adapters/receipt_drawing.py` (imports from the canvas module, no behavior change)
- Test: `tests/adapters/test_document_drawing.py`

**Interfaces:**
- Produces in `document_content.py`: `ClinicalDocument(Model)`: `kind: Literal["prescription", "medical_report"]`, `provider: ProviderProfile`, `patient: PersonName`, `issued_at: datetime`, `doctor: str`, `lines: list[str]` (medicines or a diagnosis), `language: Literal["ar_first", "en_first"]`; `make_clinical_document(rng: random.Random, kind, provider: ProviderProfile, patient: PersonName, issued_at: datetime, services: Sequence[PriceListItem]) -> ClinicalDocument`.
- Produces in `document_drawing.py`: `draw_clinical_document(content: ClinicalDocument, damage: Damage | None = None) -> DrawnReceipt` (same return type as receipts: png, size, boxes for patient_name, treatment_date, provider_name). The header carries the kind's keyword in Arabic and English so `detect_kind` can find it.

- [ ] **Step 1: Write the failing tests**

```python
def test_receipt_drawing_is_unchanged_after_the_move():  # same png bytes as before for seed 20
def test_prescription_draws_patient_date_and_provider_boxes()
def test_report_header_has_both_language_keywords()
@pytest.mark.slow
def test_easyocr_reads_a_drawn_prescription_as_a_prescription_for_the_right_patient()
```

- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Move** the canvas code (run the receipt tests: PASS, no change), then **implement** the content and drawing.
- [ ] **Step 4: Run** them, including `uv run pytest -m slow tests/adapters/test_document_drawing.py`. Expected: PASS.
- [ ] **Step 5: Commit** `refactor: shared drawing canvas` then `feat: draw prescriptions and medical reports`

### Task 10: Synthetic claims with document sets

Use the add-defect-type skill for each new defect.

**Files:**
- Create: `reimbursement_council/synthetic/document_sets.py`
- Modify: `reimbursement_council/synthetic/claims.py` (call into document_sets; keep under 300 lines), `reimbursement_council/cli/claims_set.py` (write every document's png, kinds in the claim JSON)
- Test: `tests/synthetic/test_document_sets.py`, `tests/cli/test_claims_set_commands.py`

**Interfaces:**
- Produces: `GroundTruth` gains `document_kinds: dict[str, DocumentKind] = {}`, `needs_missing: list[list[DocumentKind]] = []`, `expected_lane: Lane | None = None`.
- Produces: `add_documents(case: SyntheticCase, defect: str, rng: random.Random, settings: Settings) -> SyntheticCase` with its own `random.Random(seed * 7_000_003 + index)` so the receipt does not change when only documents change.
- New defects and weights: `missing_prescription` 5, `missing_medical_report` 5, `patient_name_mismatch` 4, `date_mismatch` 4, `member_edit_supported` 3, `member_edit_contradicts` 3. Expected lanes: the first four self_fix, `member_edit_supported` none (no expected lane, the rest of the claim decides), `member_edit_contradicts` human_review.
- Members get `name_ar` from `PEOPLE`.
- Claim JSON documents carry `kind` = the true kind and `kind_source="detected"`; the pipeline detects the kind again, so the truth is not used by the pipeline.

- [ ] **Step 1: Write the failing tests**

```python
def test_pharmacy_case_gets_a_prescription_unless_missing()
def test_receipt_is_the_same_when_only_documents_change()
def test_name_mismatch_puts_another_known_person_on_the_second_document()
def test_contradicting_edit_types_a_total_the_qr_disagrees_with()
def test_truth_lists_kinds_missing_needs_and_expected_lane()
def test_make_claims_writes_one_png_per_document()
```

- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat: synthetic claims with prescriptions, reports and document defects`

### Task 11: Harness metrics for documents

**Files:**
- Modify: `reimbursement_council/synthetic/metrics.py` (or a new `synthetic/document_metrics.py` if metrics.py passes 300 lines), `cli/claims_set.py`
- Modify: `docs/EXPERIMENTS.md` (new metrics in the list; row E12 cross-document checks, switch `cross_checks_enabled`)
- Test: `tests/synthetic/test_document_metrics.py`

**Interfaces:**
- `RunRow` gains `kinds_read: dict[str, str] = {}`, `kinds_true: dict[str, str] = {}`, `needs_flagged: list[list[str]] = []`, `needs_missing: list[list[str]] = []`, `cross_check_failed: bool = False`, `cross_check_expected: bool = False`, `expected_lane: str | None = None`.
- Produces: `document_metrics(rows: Sequence[RunRow]) -> dict[str, float]` with `document_kind_accuracy`, `missing_document_recall`, `missing_document_precision`, `cross_check_catch_rate`, `cross_check_false_alarm_rate`, `expected_lane_match`; empty groups give 0.0 and the group size is reported next to each (`..._count`).

- [ ] **Step 1: Write the failing tests** with small hand-made rows for each metric, including an empty group.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** and add the metrics to run-set's output.
- [ ] **Step 4: Run** the suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat: run-set scores document types, missing documents and cross checks`

### Task 12: Split the website routes

**Files:**
- Create: `reimbursement_council/web/claim_routes.py`
- Modify: `reimbursement_council/web/app.py`
- Test: existing web tests

**Interfaces:**
- Produces: `add_claim_routes(app: FastAPI, ctx: WebContext, page: PageRenderer) -> None` holding the member claim routes (new claim, create, show, fix, to-reviewer, samples, document). `app.py` keeps the context, helpers and reviewer routes. No behavior change.

- [ ] **Step 1: Run** the web tests. Expected: PASS (baseline).
- [ ] **Step 2: Move** the routes.
- [ ] **Step 3: Run** the web tests and the suite. Expected: PASS, same count.
- [ ] **Step 4: Commit** `refactor: member claim routes in their own module`

### Task 13: Upload step and check step

**Files:**
- Modify: `reimbursement_council/web/claim_routes.py`, `web/views.py`, `web/i18n.py`, `web/templates/new_claim.html`, `web/templates/review.html`, `web/static/app.css` (tokens only)
- Create: `web/templates/check_claim.html`
- Modify: `reimbursement_council/adapters/storage.py` (`save_readings(claim_id: str, readings: Mapping[str, ReaderOutput]) -> None`, `load_readings(claim_id: str) -> dict[str, ReaderOutput]`)
- Test: `tests/web/test_check_step.py`, `tests/adapters/test_storage.py`

**Interfaces:**
- Routes: `POST /claims` takes the person and one or more files, saves a draft claim (status "draft") and its readings, redirects to `GET /claims/{id}/check`. `POST /claims/{id}/documents` adds files to a draft. `POST /claims/{id}/submit` takes per-document kinds, the categories and the edited fields, builds `FieldEdit`s for fields whose value changed, sets `kind_source="member"` for changed kinds, then runs `process_claim(..., readings=store.load_readings(id))`. The fix route becomes "add or replace a document" through the same check step, and adds a retake field to `claim.retake_fields` when the last request was a retake.
- Check page shows per document: the image, the kind select, the read fields (editable on the primary), and above them the missing-document requests with an add button and the cross-check mismatches. Arabic and English.
- Review card shows read and typed values side by side with the evidence note for each edit.

- [ ] **Step 1: Write the failing tests** (TestClient with a fake reader; include Review Focus 1, 4 and 5)

```python
def test_upload_saves_a_draft_and_shows_the_check_page()
def test_check_page_lists_the_missing_prescription_for_a_pharmacy_receipt()
def test_submit_with_an_unchanged_form_makes_no_edits()
def test_submit_with_a_changed_total_records_a_field_edit()
def test_unreadable_photo_shows_retake_and_category_pick_without_error()
def test_bad_money_text_shows_a_field_error_and_keeps_other_input()
def test_one_bad_file_is_refused_and_the_others_kept()
def test_review_card_shows_read_and_typed_side_by_side()
```

- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement**, building screens from docs/DESIGN.md tokens and existing components (frontend-design skill).
- [ ] **Step 4: Run** the suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat: upload several documents, check what was read, then submit`

### Task 14: Screens checked, docs updated

**Files:**
- Modify: `README.md`, `docs/HANDOVER.md`, `docs/SESSION_LOG.md`, `docs/superpowers/specs/2026-11-23-reimbursement-council-design.md` (link to this design and the brief)
- Create: `docs/decisions/008-document-sets.md`

- [ ] **Step 1:** Start the website and take screenshots of the upload step, the check step (with a missing document and a mismatch) and the review card: desktop and phone, Arabic and English. Check them against docs/DESIGN.md and run the Impeccable audit. Fix what is off, with tests where it is behavior.
- [ ] **Step 2:** Write decision 008 (context, options, choice, trade-off) from spec section 5 and the owner decisions in section 9.
- [ ] **Step 3:** Update README (what the claim flow does now, how to run), HANDOVER sections 1 to 6, append SESSION_LOG.
- [ ] **Step 4:** Run ruff, mypy and pytest. Expected: all pass.
- [ ] **Step 5: Commit** `docs: decision 008, handover and README for document sets`

### Task 15: Baselines and E12

Use the run-ablation skill.

- [ ] **Step 1:** Make new sets in empty folders: `make-claims --count 120 --seed 11 --out data/sets/docs/tune` and `--count 60 --seed 12 --out data/sets/docs/check`.
- [ ] **Step 2:** Run the check set with `cross_checks_enabled` off and on (EasyOCR, `--resume`, separate results names). Sanity checks from the skill: same claim count, no impossible metric, find out why before recording a surprising change.
- [ ] **Step 3:** Record E12 in EXPERIMENTS.md with commit, commands, both metric sets, and the document metrics. Update HANDOVER.
- [ ] **Step 4: Commit** `docs: E12 cross-document checks results`
