# Walking Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One claim goes in as a file and comes out with fields, checks, hard rule results, council votes, a lane and a member message in Arabic and English. Every stage is real Python with tests, except text reading, which uses a fixture reader for now.

**Architecture:** One Python package with separate layers: `config` (load and validate YAML and env), `core` (pure logic, no I/O), `adapters` (files, QR from images, SQLite), `pipeline` (wires the stages), `cli` (thin entrypoint). Each stage is a pure function from one shape in docs/DATA_MODEL.md to the next. This covers spec layer 1 and the shape of layer 2, with no screens.

**Tech Stack:** Python 3.12, uv, Pydantic v2, PyYAML, OpenCV (QR only), sqlite3 (stdlib), pytest, ruff, mypy, GitHub Actions.

**Spec:** docs/superpowers/specs/2026-11-23-reimbursement-council-design.md (also docs/CONVENTIONS.md and docs/DATA_MODEL.md)

## Global Constraints

- Python 3.12 managed with uv. Every dependency pinned with `==` in pyproject.toml and locked in uv.lock.
- New libraries in this plan, with the reason: pydantic (every data model, validation of untrusted input), pyyaml (config files), opencv-python-headless (QR detection, no system packages), pytest, ruff, mypy, types-PyYAML (dev only). No others without a decision record.
- No paid API. The app runs with no keys at all.
- Money is integer halalas (1 SAR = 100 halalas). Rate math uses `Decimal(str(rate))` and `ROUND_HALF_UP`. Never a float for money.
- Dates ISO 8601. `submitted_at` and `decided_at` are timezone-aware UTC.
- Scores and probabilities are floats from 0 to 1. Rates (co-pay, VAT) are fractions, never percents.
- Every weight, threshold, cost and switch lives in config/*.yaml. Code holds none.
- Lanes are exactly `auto_approve`, `auto_reject`, `self_fix`, `human_review`. Members are `document_checker`, `coverage_checker`, `price_checker`, `case_reviewer`, `history_member`. Switches are `<thing>_enabled`.
- No nationality, gender or age fields anywhere.
- `core` never imports `adapters`, `pipeline` or `cli`, and does no I/O.
- Logging, not print. One logger per module. Claim log lines include the claim_id. No receipt text or patient names at info level. CLI results go to stdout with `sys.stdout.write`.
- Files stay under about 300 lines.
- Docs and UI text: plain English, no emojis, no em dashes. Arabic is short Modern Standard Arabic.
- Commits: `<type>: <what changed>`. No Co-Authored-By, no "Generated with" lines.
- Work on branch `build/skeleton`, never on main. After each task: commit, then update "Current status" and "Next 3 tasks" in docs/HANDOVER.md and commit again.
- Never commit data/. Files in tests/fixtures/ are small hand-written synthetic data only.
- File input and reader output are untrusted. Validate with Pydantic and fail with a clear message.

## Decisions this plan makes (owner please check)

The spec leaves these open or says them loosely. The plan picks the safe version.

1. A hard rule that cannot run because its input is below the confidence floor gives `not_sure`. Any `not_sure` blocks auto approve and sends the claim to self-fix (or human review when no retries are left). The spec says this for rules that would fail; we apply it to every low confidence rule input.
2. A claim with no line items, or with a line item not in the price list, never auto approves. Paying less without telling anyone would be a silent underpayment.
3. "Partial" means part of the claim was cut by the network price cap or a benefit limit. Normal co-pay does not make a claim partial.
4. VAT is paid on the covered part, at the policy VAT rate, when the receipt charged VAT.
5. The duplicate fingerprint is seller VAT number plus the full invoice timestamp plus total. A date alone would flag two family members seen the same day for the same price.
6. The history member does not use tenure yet. Unknown history and unknown provider score exactly 0.5.
7. Benefit limits and co-pay come from the policy tier in config/policy.yaml. A Policy record stores only its tier.
8. Member messages are fixed templates in config/messages.yaml, so wording can change without code.
9. QR fields keep confidence 1.0 even when an arithmetic check fails. The penalty applies only to fields the reader produced.
10. New config values the spec does not name, all starting values to tune: `self_fix_p_good_limit` 0.6, `failed_check_confidence_factor` 0.5, `arithmetic_tolerance_halalas` 1, `partial_payout_tolerance_halalas` 100, `fixed_p_good_threshold` 0.9, `always_review_amount_halalas` 500000, document checker `failed_check_score_cap` 0.5, coverage checker `no_items_score` 0.3, price checker `zero_score_ratio` 3.0 and `unknown_item_score` 0.5, history member `min_past_claims` 3.

Known effect to expect: with equal weights, a neutral history vote (0.5) pulls every new member's combined score down. That is what experiment E9 measures.

Not in this plan (next plans): EasyOCR text reading, PDFs, Hijri dates, Platt calibration, case reviewer and Gemini reader, synthetic generator, test harness and metrics, screens and reviewer card, demo mode, config/experiments.yaml.

## Review Focus

1. Money text in Arabic-Indic digits and separators, for example `١٬١٥٠٫٥٠`, must parse to 115050 halalas, and malformed text must give None, never a crash or a float. Test in Task 4.
2. A QR that is not a ZATCA invoice (a URL, truncated TLV, bad base64) must be ignored, and the claim must continue on reader fields. Tests in Task 4 and Task 6.
3. A self-fix resubmission of the same claim must not trip the duplicate rule, while the same receipt under a new claim must. Tests in Task 13 and Task 14.
4. Line items not in the price list must never auto approve with a silent underpayment. Tests in Task 8, Task 11 and Task 14.
5. A member who used all self-fix retries must go to human review, never back to self-fix. Tests in Task 11 and Task 14.

---

## File Structure

```
pyproject.toml, uv.lock, .python-version          Task 1
.github/workflows/ci.yml                          Task 1
config/policy.yaml, decision.yaml,
       prices.yaml, messages.yaml                 Task 3
reimbursement_council/
  __init__.py                                     Task 1  (__version__)
  config/models.py       config shapes            Task 3
  config/loader.py       load_settings            Task 3
  core/models/common.py  literals, Score, Halalas Task 2
  core/models/reference.py  Member, Policy, ...   Task 2
  core/models/claim.py   Claim, fields, reading   Task 2
  core/models/decision.py   rules, votes, payout  Task 2
  core/models/case.py    ClaimCase                Task 2
  core/money.py          parse and format SAR     Task 4
  core/zatca.py          ZATCA TLV encode/decode  Task 4
  core/extraction.py     merge, checks, penalties Task 6
  core/rules.py          hard rules, fingerprint  Task 7
  core/payout.py         payout math              Task 8
  core/council/          one file per member      Task 9, 10
  core/decision/combine.py, lanes.py              Task 11
  core/explain.py        member message           Task 12
  adapters/qr_image.py   QR payloads from image   Task 5
  adapters/readers.py    reader protocol, readers Task 5
  adapters/storage.py    SQLite ClaimStore        Task 13
  adapters/files.py      load claim and reference Task 13
  pipeline/process_claim.py                       Task 14
  cli/main.py                                     Task 15
tests/  mirrors the package; tests/factories.py (Task 2, 3, 9); tests/fixtures/ (Task 14)
```

---

### Task 1: Project setup and CI

**Files:**
- Create: `pyproject.toml`, `.python-version`, `uv.lock`, `.github/workflows/ci.yml`
- Create: `reimbursement_council/__init__.py` and empty `__init__.py` in `config/`, `core/`, `core/models/`, `core/council/`, `core/decision/`, `adapters/`, `pipeline/`, `cli/`
- Test: `tests/test_package.py`

**Interfaces:**
- Produces: `reimbursement_council.__version__ == "0.1.0"`; commands `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`

- [ ] **Step 1: Branch and Python**

Run: `git switch -c build/skeleton` then `uv python install 3.12`
Expected: on branch build/skeleton, Python 3.12 available to uv.

- [ ] **Step 2: Write pyproject.toml**

Project `reimbursement-council`, version `0.1.0`, `requires-python = ">=3.12,<3.13"`, script `reimbursement-council = "reimbursement_council.cli.main:main"`, hatchling build. Run `uv add pydantic pyyaml` and `uv add --dev pytest ruff mypy types-PyYAML`, then change every `>=` to `==` with the version in uv.lock and run `uv lock`. Tool config:
- ruff: line-length 100, target py312, lint select `E, F, I, B, UP, N, SIM`.
- mypy: `strict = true`, `files = ["reimbursement_council"]`, `plugins = ["pydantic.mypy"]`.
- pytest: `testpaths = ["tests"]`.

- [ ] **Step 3: Write the failing test**

```python
import reimbursement_council

def test_version() -> None:
    assert reimbursement_council.__version__ == "0.1.0"
```

- [ ] **Step 4: Run it, add `__version__`, run again**

Run: `uv run pytest tests/test_package.py -v` (FAIL), set `__version__ = "0.1.0"`, run again.
Expected: PASS.

- [ ] **Step 5: CI workflow**

`.github/workflows/ci.yml` on push and pull_request: `actions/checkout@v4`, `astral-sh/setup-uv` (current major from its README), `uv sync --locked`, then ruff check, ruff format check, mypy, pytest.

- [ ] **Step 6: Verify and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: all pass.

```bash
git add pyproject.toml uv.lock .python-version .github reimbursement_council tests
git commit -m "chore: project setup with uv, ruff, mypy, pytest and CI"
```

---

### Task 2: Domain models

**Files:**
- Create: `reimbursement_council/core/models/{common,reference,claim,decision,case}.py`
- Create: `tests/factories.py`
- Modify: `docs/DATA_MODEL.md` (first, before code)
- Test: `tests/core/models/test_models.py`

**Interfaces:**
- Produces (`common.py`): `Score = Annotated[float, Field(ge=0, le=1)]`, `Halalas = Annotated[int, Field(ge=0)]`, and Literals `Lane`, `Outcome` (`complete, partial, error, queued`), `FieldSource` (`qr, ocr, vision, member_confirmed, reviewer`), `FieldName` (`provider_name, vat_number, invoice_timestamp, treatment_date, subtotal, vat_total, total, patient_name`), `DocumentKind`, `MemberName`, `RuleName`, `RuleOutcome` (`pass, fail, not_sure`), `CheckName`, `RequestKind` (`retake_photo, add_document, confirm_field`).
- Produces (`reference.py`): `Member(member_id, display_name, date_joined: date, policy_id)`, `Policy(policy_id, tier, start_date, end_date, status: Literal["active","inactive"], covered_people: list[str])`, `Provider(provider_id, name, vat_number, city, in_network: bool, trust_score: Score)` with `Provider.unknown(vat_number: str | None) -> Provider` (provider_id `"unknown"`, trust 0.5, in_network False), `MemberHistory(member_id, past_claims: int, past_claims_paid: int, limits_used: dict[str, Halalas])` with `paid <= past` validated, `PriceListItem(service_code, description, network_price: Halalas, category)`, `ReferenceData(members, policies, providers, histories)` with `member(id) -> Member`, `policy(id) -> Policy` (both raise `LookupError` naming the id), `provider_by_vat(vat: str | None) -> Provider` (unknown when not found), `history(member_id) -> MemberHistory` (empty history when not found).
- Produces (`claim.py`): `Document(document_id, claim_id, kind, file_path: str, image_hash: str | None, uploaded_at: AwareDatetime)`, `Claim(claim_id, member_id, patient_member_id, policy_id, submitted_at: AwareDatetime, status, documents: list[Document], retries_used: int >= 0)`, `FieldLocation(page: int, box: tuple[int, int, int, int])`, `ExtractedField(document_id, name: FieldName, value: str, original_text: str, source, confidence: Score, location: FieldLocation | None)`, `LineItem(description, service_code: str | None, quantity: int >= 1, unit_price: Halalas, amount: Halalas, confidence: Score)`, `CheckResult(name: CheckName, passed: bool, details: str, fields: list[str])`, `ReaderOutput(fields, line_items, qr_payloads: list[str])`, `ExtractionResult(document_id, fields, line_items, checks)` with `best(name) -> ExtractedField | None` (highest confidence), `all_named(name) -> list[ExtractedField]`, `money(name) -> int | None`, `day(name) -> date | None`.
- Value format in `ExtractedField.value`: money fields are halalas as digits (`"17250"`), `treatment_date` is `YYYY-MM-DD`, `invoice_timestamp` is the raw ISO text, others are text.
- Produces (`decision.py`): `RuleResult(rule, outcome, reason, fields: list[str])`, `Vote(member, score: Score, weight: float >= 0 = 1.0, reason, evidence: list[str], request: str | None, request_kind: RequestKind | None, request_field: str | None)` with the three request fields all set or all None, `SelfFixRequest(kind, field, text)`, `PayoutResult(requested, network_cap_cut, copay, limit_cut, vat_paid, calculated: Halalas, unmatched_items: list[str], is_partial: bool)`, `MemberMessage(en, ar)`, `Decision(claim_id, decided_at: AwareDatetime, config_version, combined_score, p_good, disagreement: Score, payout_requested: Halalas | None, payout_calculated: Halalas | None, expected_loss: Halalas | None, reviewer_time_value: Halalas, lane, outcome, lane_reason, self_fix_request: SelfFixRequest | None, member_message, votes, rule_results, check_results)`.
- Produces (`case.py`): `ClaimCase(claim, member, policy, provider, history, extraction: ExtractionResult | None, rule_results, payout: PayoutResult | None)`.
- All models: `model_config = ConfigDict(extra="forbid", frozen=True)`.
- Produces (`tests/factories.py`): `DOC_ID`, `make_field(name, value, confidence=0.95, source="ocr") -> ExtractedField`, `make_item(code, amount, quantity=1, confidence=0.95, description="item") -> LineItem` (unit_price = amount // quantity), `make_extraction(fields, line_items=(), checks=()) -> ExtractionResult`.

- [ ] **Step 1: Update docs/DATA_MODEL.md**

Add field source `ocr`; add `confidence` to LineItem; add `category` to PriceListItem; Policy limits and co-pay come from its tier in config/policy.yaml, co-pay is `copay_rate` (fraction); Vote gains `request_field`; CheckResult and RuleResult gain `fields`; Decision gains `lane_reason` and `self_fix_request`; add ReaderOutput, ExtractionResult, PayoutResult, MemberHistory, ClaimCase. Review and GroundTruth stay as written (built in later layers).

- [ ] **Step 2: Write the failing tests**

```python
def test_score_out_of_range_rejected():
    with pytest.raises(ValidationError):
        make_field("total", "100", confidence=1.5)

def test_money_never_float():
    with pytest.raises(ValidationError):
        LineItem(description="x", service_code=None, quantity=1, unit_price=10.5, amount=10, confidence=0.9)

def test_naive_submitted_at_rejected():
    with pytest.raises(ValidationError):
        Claim(..., submitted_at=datetime(2026, 11, 20, 9, 0), ...)

def test_unknown_lane_rejected(): ...           # Decision(lane="maybe") raises
def test_vote_request_all_or_nothing(): ...     # request text without request_kind raises
def test_extra_keys_rejected(): ...             # Member(..., nationality="x") raises

def test_extraction_accessors():
    ex = make_extraction([make_field("total", "17250", 0.6), make_field("total", "17000", 0.95),
                          make_field("treatment_date", "2026-11-15")])
    assert ex.best("total").value == "17000"
    assert ex.money("total") == 17000
    assert ex.day("treatment_date") == date(2026, 11, 15)
    assert ex.money("vat_total") is None

def test_unknown_provider_is_neutral():
    p = Provider.unknown("300000000000003")
    assert p.trust_score == 0.5 and p.in_network is False

def test_history_paid_cannot_exceed_past(): ...
def test_reference_lookup_errors_name_the_id(): ...  # LookupError message contains the id
```

- [ ] **Step 3: Run to see them fail, implement the models, run to see them pass**

Run: `uv run pytest tests/core/models -v`
Expected: FAIL (import error), then PASS. Use `StrictInt` for halalas fields so `10.5` and `"10"` fail.

- [ ] **Step 4: Lint, types, commit**

Run: `uv run ruff check . && uv run mypy`
```bash
git commit -m "feat: domain models from DATA_MODEL with validation"
```

---

### Task 3: Config files and loader

**Files:**
- Create: `config/policy.yaml`, `config/decision.yaml`, `config/prices.yaml`, `config/messages.yaml`
- Create: `reimbursement_council/config/models.py`, `reimbursement_council/config/loader.py`
- Modify: `.env.example` (rename `CLAIMS_DEMO_MODE` to `DEMO_MODE`), `tests/factories.py`
- Test: `tests/config/test_loader.py`

**Interfaces:**
- Consumes: `PriceListItem` (Task 2)
- Produces: `PolicyConfig`, `TierConfig(limits_halalas: dict[str, Halalas], copay_rate: dict[str, Score])`, `MemberConfig(enabled: bool, weight: float >= 0)` plus subclasses with each member's extra fields, `DecisionConfig`, `MessageConfig(en: LanguageMessages, ar: LanguageMessages)`, `LanguageMessages(lanes, rules, requests, fields: dict[str, str])`, `Settings(policy, decision, prices: dict[str, PriceListItem], messages, config_version: str, gemini_api_key: str | None, demo_mode: bool)`.
- Produces: `load_settings(config_dir: Path, env: Mapping[str, str] | None = None) -> Settings` (env defaults to `os.environ`; reads `GEMINI_API_KEY`, `DEMO_MODE`). `config_version` is the first 12 hex chars of sha256 over the four files' names and bytes, in sorted order.
- Produces (`tests/factories.py`): `REPO_CONFIG: Path`, `settings_with(**decision_changes) -> Settings` (loads repo config, applies changes to `decision` with `model_copy`).

- [ ] **Step 1: Write the config files**

`config/policy.yaml`:
```yaml
claim_window_days: 90
vat_rate: 0.15
exclusions: [DENT-WHITEN, COSM-BOTOX]
tiers:
  silver:
    limits_halalas: {outpatient: 1500000, lab: 500000, pharmacy: 300000}
    copay_rate: {outpatient: 0.10, lab: 0.0, pharmacy: 0.20}
```
`config/prices.yaml`: a list of items with `service_code, description, network_price, category`: `CONS-GP` General consultation 15000 outpatient; `LAB-CBC` Complete blood count 8000 lab; `MED-PARA` Paracetamol 500 mg 1500 pharmacy; `DENT-WHITEN` Teeth whitening 60000 outpatient; `COSM-BOTOX` Botox 120000 outpatient.

`config/decision.yaml`:
```yaml
hard_rule_confidence_floor: 0.90
disagreement_limit: 0.25
reviewer_time_value_halalas: 2500
qr_first_enabled: true
arithmetic_checks_enabled: true
arithmetic_tolerance_halalas: 1
failed_check_confidence_factor: 0.5
partial_payout_tolerance_halalas: 100
calibration_enabled: false
calibration_method: platt
disagreement_routing_enabled: true
cost_lanes_enabled: true
fixed_p_good_threshold: 0.90
always_review_amount_enabled: false
always_review_amount_halalas: 500000
self_fix_enabled: true
self_fix_max_retries: 2
self_fix_p_good_limit: 0.6
gemini_reader_enabled: false
members:
  document_checker: {enabled: true, weight: 1.0, required_fields: [provider_name, treatment_date, total], failed_check_score_cap: 0.5}
  coverage_checker: {enabled: true, weight: 1.0, no_items_score: 0.3}
  price_checker: {enabled: true, weight: 1.0, zero_score_ratio: 3.0, unknown_item_score: 0.5}
  history_member: {enabled: true, weight: 1.0, min_past_claims: 3}
  case_reviewer: {enabled: false, weight: 1.0}
```

`config/messages.yaml` (exact copy; keys under `lanes` are `approved, approved_partial, rejected, self_fix, human_review`):
```yaml
en:
  lanes:
    approved: "Your claim is approved. We will send you {amount} SAR."
    approved_partial: "Your claim is approved in part. We will send you {amount} SAR of the {requested} SAR you asked for."
    rejected: "Your claim was not approved. Reason: {reason}"
    self_fix: "We need one thing from you to finish your claim. {request}"
    human_review: "A reviewer from our team will look at your claim. We will tell you the result when it is done."
  rules:
    late: "The treatment date is more than {claim_window_days} days before you sent the claim."
    policy_inactive: "Your policy was not active on the treatment date."
    person_not_covered: "The patient is not covered by this policy."
    excluded_service: "The receipt includes a service this policy does not cover."
    duplicate: "This receipt was already sent in another claim."
    multiple_patients: "The documents show more than one patient. Please send one claim for each person."
  requests:
    retake_photo: "We could not read the {field}. Please take a clearer photo."
    add_document: "Please add the {field}."
    confirm_field: "Please check the {field} we read and fix it if needed."
  fields:
    provider_name: "provider name"
    treatment_date: "treatment date"
    total: "total amount"
    vat_number: "VAT number"
    patient_name: "patient name"
    receipt: "receipt"
    itemized_invoice: "itemized invoice that lists each service"
ar:
  lanes:
    approved: "تمت الموافقة على مطالبتك. سنحول لك {amount} ريال."
    approved_partial: "تمت الموافقة على جزء من مطالبتك. سنحول لك {amount} ريال من أصل {requested} ريال."
    rejected: "لم تتم الموافقة على مطالبتك. السبب: {reason}"
    self_fix: "نحتاج منك أمرا واحدا لإكمال مطالبتك. {request}"
    human_review: "سيراجع أحد موظفينا مطالبتك. سنخبرك بالنتيجة عند الانتهاء."
  rules:
    late: "تاريخ العلاج أقدم من {claim_window_days} يوما قبل تقديم المطالبة."
    policy_inactive: "لم تكن وثيقتك سارية في تاريخ العلاج."
    person_not_covered: "المريض غير مشمول في هذه الوثيقة."
    excluded_service: "الفاتورة تشمل خدمة لا تغطيها وثيقتك."
    duplicate: "هذه الفاتورة قدمت من قبل في مطالبة أخرى."
    multiple_patients: "المستندات تخص أكثر من مريض. قدم مطالبة لكل شخص."
  requests:
    retake_photo: "لم نتمكن من قراءة {field}. التقط صورة أوضح من فضلك."
    add_document: "أضف {field} من فضلك."
    confirm_field: "راجع {field} كما قرأناه وصححه إن لزم."
  fields:
    provider_name: "اسم مقدم الخدمة"
    treatment_date: "تاريخ العلاج"
    total: "المبلغ الإجمالي"
    vat_number: "الرقم الضريبي"
    patient_name: "اسم المريض"
    receipt: "الفاتورة"
    itemized_invoice: "فاتورة مفصلة تذكر كل خدمة"
```

- [ ] **Step 2: Write the failing tests**

```python
def test_repo_config_loads():
    s = load_settings(REPO_CONFIG, env={})
    assert s.decision.reviewer_time_value_halalas == 2500
    assert s.prices["CONS-GP"].network_price == 15000
    assert len(s.config_version) == 12 and s.gemini_api_key is None and s.demo_mode is False

def test_env_read_in_one_place():
    s = load_settings(REPO_CONFIG, env={"GEMINI_API_KEY": "k", "DEMO_MODE": "true"})
    assert s.gemini_api_key == "k" and s.demo_mode is True
```
Plus one failing-load test each, written by copying the repo config to `tmp_path` and changing one value; each must raise `ConfigError` whose message names the file and key:
`test_unknown_key_rejected` (typo `reviewer_time_valu_halalas`), `test_floor_above_one_rejected`, `test_negative_weight_rejected`, `test_no_enabled_member_rejected`, `test_case_reviewer_not_built_yet`, `test_calibration_not_built_yet`, `test_gemini_reader_not_built_yet`, `test_price_category_missing_from_tier_rejected`, `test_duplicate_service_code_rejected`, `test_messages_languages_must_have_same_keys`, `test_missing_config_file_names_it`.

- [ ] **Step 3: Run to fail, implement, run to pass**

`ConfigError(Exception)` lives in `config/loader.py` and wraps `ValidationError`, `yaml.YAMLError` and missing files with the file name. All config models use `extra="forbid"`.
Run: `uv run pytest tests/config -v` (FAIL, then PASS).

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: config files and validated settings loader"
```

---

### Task 4: Money parsing and ZATCA QR decoding

**Files:**
- Create: `reimbursement_council/core/money.py`, `reimbursement_council/core/zatca.py`
- Test: `tests/core/test_money.py`, `tests/core/test_zatca.py`

**Interfaces:**
- Produces: `parse_sar_to_halalas(text: str) -> int | None`, `format_sar(halalas: int) -> str`, `apply_rate(halalas: int, rate: float) -> int` (Decimal, ROUND_HALF_UP).
- Produces: `ZatcaInvoice(seller_name: str, vat_number: str, timestamp: str, total_with_vat: Halalas, vat_total: Halalas)` (timestamp must start with a valid ISO date), `encode_zatca_tlv(invoice: ZatcaInvoice) -> str`, `decode_zatca_tlv(payload: str) -> ZatcaInvoice | None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_plain_and_grouped():
    assert parse_sar_to_halalas("115") == 11500
    assert parse_sar_to_halalas("115.5") == 11550
    assert parse_sar_to_halalas("1,150.50 SAR") == 115050

def test_parse_arabic_indic_digits():              # Review Focus 1
    assert parse_sar_to_halalas("١٬١٥٠٫٥٠") == 115050
    assert parse_sar_to_halalas("١١٥ ر.س") == 11500

def test_parse_rejects_garbage():                  # Review Focus 1
    for text in ["", "abc", "12.345", "-5", "1.2.3", "SAR"]:
        assert parse_sar_to_halalas(text) is None

def test_format_and_rate():
    assert format_sar(15525) == "155.25" and format_sar(0) == "0.00"
    assert apply_rate(15, 0.10) == 2          # 1.5 rounds half up
    assert apply_rate(13500, 0.15) == 2025

def test_zatca_round_trip():
    inv = ZatcaInvoice(seller_name="عيادة النور", vat_number="300000000000003",
                       timestamp="2026-11-15T10:30:00Z", total_with_vat=17250, vat_total=2250)
    assert decode_zatca_tlv(encode_zatca_tlv(inv)) == inv

def test_zatca_decodes_hand_built_payload(): ...   # bytes built by hand: tag, length, UTF-8 value for tags 1..5, totals "172.50" and "22.50"
def test_zatca_ignores_phase_two_tags(): ...        # extra tags 6..9 after tag 5 still decode

def test_zatca_rejects_non_zatca_payloads():       # Review Focus 2
    # a URL, bad base64, a truncated TLV, a TLV missing tag 4, a TLV whose total is "abc"
    bad = ["https://example.com", "not base64!!", b64(b"\x01\x05abc"), b64(tlv_without_tag_4), b64(tlv_total_abc)]
    for payload in bad:
        assert decode_zatca_tlv(payload) is None
```

- [ ] **Step 2: Run to fail, implement, run to pass**

Money: map Arabic-Indic (U+0660 to U+0669) and Persian (U+06F0 to U+06F9) digits to ASCII, `٫` to `.`, `٬` to `,`, strip `SAR`, `ر.س`, `﷼` and spaces, drop `,`, then match `^\d+(\.\d{1,2})?$`. TLV: base64 decode (`validate=True`), then loop tag byte, length byte, value bytes; any overrun, bad UTF-8 or missing tag 1 to 5 gives None. Encode raises `ValueError` for a value over 255 bytes.
Run: `uv run pytest tests/core/test_money.py tests/core/test_zatca.py -v`

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: SAR money parsing and ZATCA QR TLV decoding"
```

---

### Task 5: Readers and QR from images

**Files:**
- Create: `reimbursement_council/adapters/qr_image.py`, `reimbursement_council/adapters/readers.py`
- Modify: `pyproject.toml` (add `opencv-python-headless`, pinned; mypy override `ignore_missing_imports` for `cv2`)
- Test: `tests/adapters/test_qr_image.py`, `tests/adapters/test_readers.py`

**Interfaces:**
- Consumes: `Document`, `ReaderOutput` (Task 2)
- Produces: `find_qr_payloads(image_bytes: bytes) -> list[str]` (never raises; logs a warning and returns `[]` for bytes that are not an image).
- Produces: `DocumentReader` Protocol with `read(document: Document) -> ReaderOutput`; `FixtureReader` (loads a `*.reading.json` file into `ReaderOutput`); `QrImageReader` (reads `.png/.jpg/.jpeg`, returns QR payloads and no fields; text reading comes with EasyOCR in the next plan); `reader_for(document: Document) -> DocumentReader` (picks by suffix, `ValueError` naming the suffix otherwise).

- [ ] **Step 1: Write the failing tests**

```python
def qr_png(text: str) -> bytes:
    img = cv2.QRCodeEncoder.create().encode(text)
    img = cv2.resize(img, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
    img = cv2.copyMakeBorder(img, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    return cv2.imencode(".png", img)[1].tobytes()

def test_reads_generated_qr():
    assert find_qr_payloads(qr_png("hello zatca")) == ["hello zatca"]

def test_blank_image_has_no_qr(): ...        # white PNG -> []
def test_not_an_image(): assert find_qr_payloads(b"not an image") == []
def test_fixture_reader_loads(tmp_path): ...  # write a reading.json, read it, compare ReaderOutput
def test_fixture_reader_rejects_bad_confidence(tmp_path): ...  # confidence 1.5 -> ValidationError
def test_reader_for_picks_by_suffix(): ...    # .reading.json -> FixtureReader, .png -> QrImageReader, .pdf -> ValueError
```

- [ ] **Step 2: Run to fail, implement, run to pass**

`cv2.imdecode(np.frombuffer(...), cv2.IMREAD_COLOR)`, then `cv2.QRCodeDetector().detectAndDecodeMulti`; keep non-empty strings in detection order.
Run: `uv run pytest tests/adapters -v`

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: document readers and QR payloads from images"
```

---

### Task 6: Extraction stage

**Files:**
- Create: `reimbursement_council/core/extraction.py`
- Test: `tests/core/test_extraction.py`

**Interfaces:**
- Consumes: `decode_zatca_tlv`, `apply_rate` (Task 4), `ReaderOutput`, `ExtractionResult` (Task 2), `Settings` (Task 3)
- Produces: `extract_document(document_id: str, reading: ReaderOutput, settings: Settings) -> ExtractionResult`; `arithmetic_checks(fields: list[ExtractedField], line_items: list[LineItem], vat_rate: float, tolerance: int) -> list[CheckResult]`.

Order inside `extract_document`:
1. Decode QR payloads; the first valid one gives fields with source `qr`, confidence 1.0: `provider_name` (seller name), `vat_number`, `invoice_timestamp`, `treatment_date` (first 10 chars of timestamp), `total`, `vat_total`.
2. If `qr_first_enabled`, QR fields replace reader fields of the same name; otherwise QR fields are not used as fields.
3. If a QR decoded, check `qr_matches_text` on `total`, `vat_total`, `vat_number`, `treatment_date` where the reader also has them (never on names). Failed details name the fields that differ.
4. If `arithmetic_checks_enabled`: `items_sum_to_subtotal` (needs items and subtotal), `vat_is_15_percent` (needs subtotal and vat_total > 0), `subtotal_plus_vat_is_total` (needs all three). Each compares within `arithmetic_tolerance_halalas`. A missing input skips that check.
5. For each failed arithmetic check, multiply the confidence of its non-QR fields (and line items, for the items check) by `failed_check_confidence_factor`.

- [ ] **Step 1: Write the failing tests**

```python
def test_qr_fields_win_when_qr_first(): ...           # reader total 17000, QR total 17250 -> best("total").value == "17250", source "qr", 1.0; qr_matches_text failed, "total" in details
def test_reader_fields_when_qr_first_disabled(): ...  # settings_with(qr_first_enabled=False) -> total "17000" source "ocr"; qr_matches_text still failed
def test_bad_qr_payload_ignored():                    # Review Focus 2
    result = extract_document(DOC_ID, ReaderOutput(fields=reader_fields, line_items=items, qr_payloads=["https://example.com"]), settings)
    assert {f.value for f in result.fields} == {f.value for f in reader_fields}
    assert "qr_matches_text" not in {c.name for c in result.checks}
def test_consistent_receipt_passes_all_checks(): ...  # 15000 / 2250 / 17250 with one 15000 item
def test_wrong_vat_lowers_confidence():
    # subtotal 15000, vat_total 3000, total 18000: vat check fails, sum check passes
    assert result.best("vat_total").confidence == pytest.approx(0.95 * 0.5)
def test_qr_fields_not_penalized(): ...               # failed check leaves QR total at 1.0
def test_checks_off_when_disabled(): ...               # settings_with(arithmetic_checks_enabled=False) -> no arithmetic check names
def test_no_vat_check_when_vat_is_zero(): ...
```

- [ ] **Step 2: Run to fail, implement, run to pass**

Run: `uv run pytest tests/core/test_extraction.py -v`

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: extraction stage with QR first, arithmetic checks and confidence penalties"
```

---

### Task 7: Hard rules

**Files:**
- Create: `reimbursement_council/core/rules.py`
- Test: `tests/core/test_rules.py`

**Interfaces:**
- Consumes: `Claim`, `Policy`, `ExtractionResult`, `RuleResult` (Task 2), `Settings` (Task 3)
- Produces: `SeenReceipts(fingerprints: frozenset[str], image_hashes: frozenset[str])` (frozen Pydantic model), `receipt_fingerprint(extraction: ExtractionResult, floor: float) -> str | None` (`"{vat_number}|{invoice_timestamp}|{total}"`, None if any part is missing or below floor), `run_hard_rules(claim: Claim, policy: Policy, extraction: ExtractionResult | None, image_hash: str | None, seen: SeenReceipts, settings: Settings) -> list[RuleResult]`, always in the order `late, policy_inactive, person_not_covered, excluded_service, duplicate, multiple_patients`.

Rule logic (floor = `hard_rule_confidence_floor`):
- `late`: needs `treatment_date` at or above floor, else `not_sure`. Date after `submitted_at` date gives `not_sure`. Days between > `claim_window_days` gives `fail`.
- `policy_inactive`: needs a confident date, else `not_sure`. `fail` if status is inactive or the date is outside start to end.
- `person_not_covered`: `fail` if `patient_member_id` is not in `covered_people`.
- `excluded_service`: an excluded code on a confident line item gives `fail`; on a low confidence item gives `not_sure`.
- `duplicate`: `fail` if image_hash is in seen, or the fingerprint is in seen.
- `multiple_patients`: distinct names after casefold and whitespace collapse; more than one confident name gives `fail`; more than one name with any low gives `not_sure`.
- With `extraction` None: `late` and `policy_inactive` are `not_sure` with `fields == ["receipt"]`; `excluded_service`, `duplicate`, `multiple_patients` pass.
- Every result lists the fields it used in `fields`, and a one sentence English reason.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("days, outcome", [(90, "pass"), (91, "fail")])
def test_late_window(days, outcome): ...
def test_late_not_sure_below_floor(): ...       # date confidence 0.6
def test_late_not_sure_when_missing(): ...
def test_future_treatment_date_not_sure(): ...
def test_policy_outside_dates_fails(): ...
def test_policy_status_inactive_fails(): ...
def test_person_not_covered_fails(): ...
def test_excluded_confident_fails_low_is_not_sure(): ...
def test_duplicate_by_image_hash(): ...
def test_duplicate_by_fingerprint(): ...
def test_same_day_same_total_new_timestamp_not_duplicate(): ...
def test_fingerprint_none_when_low_confidence(): ...
def test_two_patients_fail_same_name_spacing_passes(): ...   # "Sara  Ahmed" and "sara ahmed" count as one
def test_no_extraction(): ...                                # late and policy_inactive not_sure with fields ["receipt"]
def test_result_order(): ...
```

- [ ] **Step 2: Run to fail, implement, run to pass**

Run: `uv run pytest tests/core/test_rules.py -v`

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: hard rules with confidence floor and receipt fingerprint"
```

---

### Task 8: Payout math

**Files:**
- Create: `reimbursement_council/core/payout.py`
- Test: `tests/core/test_payout.py`

**Interfaces:**
- Consumes: `ExtractionResult`, `Policy`, `MemberHistory`, `PayoutResult` (Task 2), `apply_rate` (Task 4), `Settings` (Task 3)
- Produces: `calculate_payout(extraction: ExtractionResult, policy: Policy, history: MemberHistory, settings: Settings) -> PayoutResult | None` (None when there are no line items).

Algorithm:
1. Each line item with a known `service_code`: allowed = min(amount, network_price x quantity); `network_cap_cut` += amount minus allowed; add allowed to its category. Unknown or missing code: description goes to `unmatched_items`, nothing paid for it.
2. Each category: copay = `apply_rate(allowed, tier.copay_rate[cat])`; after = allowed minus copay; remaining = max(0, limit minus `history.limits_used.get(cat, 0)`); paid = min(after, remaining); `limit_cut` += after minus paid.
3. `vat_paid` = `apply_rate(sum of paid, vat_rate)` if the receipt `vat_total` > 0, else 0.
4. `requested` = sum of item amounts plus `vat_total` (0 if missing). `calculated` = sum of paid plus `vat_paid`.
5. `is_partial` = cap cut plus limit cut > `partial_payout_tolerance_halalas`, or any unmatched item.

- [ ] **Step 1: Write the failing tests**

```python
def test_clean_consultation():            # CONS-GP 15000, vat_total 2250
    p = calculate_payout(...)
    assert (p.network_cap_cut, p.copay, p.limit_cut, p.vat_paid) == (0, 1500, 0, 2025)
    assert (p.requested, p.calculated, p.is_partial) == (17250, 15525, False)

def test_network_cap():                   # CONS-GP 40000, vat 6000
    assert (p.network_cap_cut, p.calculated, p.is_partial) == (25000, 15525, True)

def test_limit_cut():                     # outpatient used 1495000
    assert (p.limit_cut, p.vat_paid, p.calculated, p.is_partial) == (8500, 750, 5750, True)

def test_limit_fully_used(): ...          # calculated 0, is_partial True, result is not None
def test_unmatched_item():                # Review Focus 4: code None "Physio session" 20000, vat 3000
    assert p.unmatched_items == ["Physio session"] and p.requested == 23000 and p.calculated == 0 and p.is_partial
def test_no_line_items_gives_none(): ...
def test_no_vat_receipt(): ...            # vat_total 0 -> vat_paid 0
def test_quantity(): ...                  # MED-PARA quantity 3 amount 4500 -> cap 0, copay 900, paid 3600
```

- [ ] **Step 2: Run to fail, implement, run to pass**

Run: `uv run pytest tests/core/test_payout.py -v`

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: payout math with network cap, co-pay, limits and VAT"
```

---

### Task 9: Council interface, document checker, coverage checker

Use the add-council-member skill for this task and Task 10.

**Files:**
- Create: `reimbursement_council/core/council/document_checker.py`, `reimbursement_council/core/council/coverage_checker.py`
- Modify: `tests/factories.py`
- Test: `tests/core/council/test_document_checker.py`, `tests/core/council/test_coverage_checker.py`

**Interfaces:**
- Consumes: `ClaimCase`, `Vote` (Task 2), `Settings` (Task 3)
- Produces: every member module exposes `vote(case: ClaimCase, settings: Settings) -> Vote`, with `member` set to its name and `weight` left at 1.0 (the registry sets the real weight).
- Produces (`tests/factories.py`): `make_case(extraction=..., payout=None, history=None, provider=None, rule_results=()) -> ClaimCase` with a default member, active silver policy and unknown provider.

Scoring:
- `document_checker`: score = mean confidence of `required_fields` (missing counts 0). If any check failed, score = min(score, `failed_check_score_cap`). Request for the first required field that is missing (`retake_photo`) or below the floor (`confirm_field`). Extraction None: score 0.0, request `add_document` with field `receipt`.
- `coverage_checker`: score = matched item amount / all item amount. No request for unmatched items (the member cannot fix our price list). Payout None with an extraction: score `no_items_score`, request `add_document` field `itemized_invoice`. Extraction None: score 0.0, no request.

- [ ] **Step 1: Write the failing tests**

```python
def test_document_all_confident(): ...        # three QR fields -> 1.0, no request
def test_document_missing_total():
    v = document_checker.vote(case_without_total, settings)
    assert v.score == pytest.approx(2 / 3)
    assert (v.request_kind, v.request_field) == ("retake_photo", "total")
def test_document_low_date_asks_confirm(): ... # date 0.6 -> confirm_field treatment_date
def test_document_failed_check_caps_score(): ...
def test_document_no_extraction(): ...         # 0.0, add_document receipt
def test_coverage_all_matched(): ...           # 1.0
def test_coverage_half_unmatched(): ...        # 0.5 by amount, no request
def test_coverage_no_items_asks_itemized(): ...# 0.3, add_document itemized_invoice
def test_votes_are_named(): ...                # member field matches the module
```

- [ ] **Step 2: Run to fail, implement, run to pass**

Run: `uv run pytest tests/core/council -v`

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: document checker and coverage checker council members"
```

---

### Task 10: Price checker, history member, council registry

**Files:**
- Create: `reimbursement_council/core/council/price_checker.py`, `reimbursement_council/core/council/history_member.py`, `reimbursement_council/core/council/registry.py`
- Test: `tests/core/council/test_price_checker.py`, `tests/core/council/test_history_member.py`, `tests/core/council/test_registry.py`

**Interfaces:**
- Consumes: `vote` modules from Task 9, `make_case` (Task 9)
- Produces: `run_council(case: ClaimCase, settings: Settings) -> list[Vote]` (enabled members in config order, each vote's `weight` copied from config).

Scoring:
- `price_checker`: per item with a known code, ratio = unit_price / network_price; item score 1.0 if ratio <= 1, else max(0, 1 minus (ratio minus 1) / (`zero_score_ratio` minus 1)). Unknown code scores `unknown_item_score`. Score = amount-weighted mean. No items or no extraction: `unknown_item_score`.
- `history_member`: member part = paid / past if past >= `min_past_claims`, else 0.5. Score = mean of member part and `provider.trust_score`. Never requests anything.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("unit_price, score", [(15000, 1.0), (30000, 0.5), (45000, 0.0), (60000, 0.0)])
def test_price_ratio(unit_price, score): ...
def test_price_unknown_code_neutral(): ...
def test_price_amount_weighted(): ...          # 15000 at ratio 1 and 15000 at ratio 3 -> 0.5
def test_history_new_member_unknown_provider_is_exactly_neutral():
    assert history_member.vote(make_case(history=empty, provider=Provider.unknown(None)), s).score == 0.5
def test_history_trusted(): ...                 # 5 of 5 paid, trust 0.8 -> 0.9
def test_history_few_claims_neutral_part(): ... # 2 past -> member part 0.5
def test_history_low(): ...                     # 0 of 5 paid, trust 0.5 -> 0.25
def test_council_order_and_weights(): ...       # 4 votes in config order; price weight 2.0 in config -> vote.weight 2.0
def test_council_skips_disabled(): ...          # history disabled -> 3 votes
```

- [ ] **Step 2: Run to fail, implement, run to pass**

Run: `uv run pytest tests/core/council -v`

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: price checker, history member and council registry"
```

---

### Task 11: Combine votes and choose the lane

**Files:**
- Create: `reimbursement_council/core/decision/combine.py`, `reimbursement_council/core/decision/lanes.py`
- Test: `tests/core/decision/test_combine.py`, `tests/core/decision/test_lanes.py`

**Interfaces:**
- Consumes: `Vote`, `RuleResult`, `PayoutResult`, `SelfFixRequest` (Task 2), `Settings` (Task 3)
- Produces: `combine_votes(votes: list[Vote]) -> tuple[float, float]` (weighted mean, weighted standard deviation; `ValueError` if total weight is 0); `p_good_from_score(score: float, settings: Settings) -> float` (returns the score while calibration is off); `expected_loss(p_good: float, payout_calculated: int) -> int` (Decimal, half up); `LaneChoice(lane, outcome, reason: str, request: SelfFixRequest | None)`; `choose_lane(rule_results, votes, p_good, disagreement, payout: PayoutResult | None, retries_used: int, settings: Settings) -> LaneChoice`.

Lane order (first match wins; "retries left" = `self_fix_enabled` and `retries_used < self_fix_max_retries`):
1. Any rule `fail`: `auto_reject`, outcome `complete`, reason names the rule.
2. Any rule `not_sure`: `self_fix` if retries left, else `human_review`. Request = first vote request, else `confirm_field` on the rule's first field.
3. Can approve when payout is not None, has no unmatched items, the always-review cap does not apply (`always_review_amount_enabled` and calculated >= `always_review_amount_halalas`), disagreement < `disagreement_limit` (skipped when `disagreement_routing_enabled` is off), and either `expected_loss` < `reviewer_time_value_halalas` (cost lanes on) or p_good >= `fixed_p_good_threshold` (cost lanes off). Then `auto_approve`, outcome `partial` if `payout.is_partial` else `complete`.
4. p_good < `self_fix_p_good_limit`, some vote has a request, retries left: `self_fix` with the first vote request.
5. Otherwise `human_review`, outcome `queued`, reason lists every condition from step 3 that blocked approval.

Self-fix and human review have outcome `queued`.

- [ ] **Step 1: Write the failing tests**

```python
def test_combine_equal_weights():
    assert combine_votes(votes(1.0, 1.0, 1.0, 0.9)) == pytest.approx((0.975, 0.0433), abs=1e-4)
def test_combine_weighted():   # score 1.0 weight 3, score 0.0 weight 1
    assert combine_votes(weighted_votes) == pytest.approx((0.75, 0.4330), abs=1e-4)
def test_combine_zero_weight_raises(): ...
def test_expected_loss(): assert expected_loss(0.975, 15525) == 388
def test_hard_fail_rejects_even_with_high_score(): ...
def test_not_sure_goes_to_self_fix_with_vote_request(): ...
def test_not_sure_without_vote_request_confirms_rule_field(): ...
def test_retries_exhausted_goes_to_human():                    # Review Focus 5
    choice = choose_lane([not_sure_late], votes_with_request, 0.4, 0.1, payout, retries_used=2, settings=s)
    assert choice.lane == "human_review"
def test_low_score_request_exhausted_goes_to_human(): ...      # Review Focus 5, step 4 path
def test_approve_complete_and_partial(): ...
def test_disagreement_blocks_approve_unless_switch_off(): ...
def test_no_payout_never_approves(): ...
def test_unmatched_items_never_approve(): ...                  # Review Focus 4
def test_always_review_cap_switch(): ...
def test_fixed_threshold_when_cost_lanes_off(): ...
def test_self_fix_switch_off_goes_to_human(): ...
def test_no_reject_without_hard_rule(): ...                    # p_good 0.0, no rule fail -> lane is not auto_reject
```

- [ ] **Step 2: Run to fail, implement, run to pass**

Run: `uv run pytest tests/core/decision -v`

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: weighted combine, disagreement and cost-based lanes"
```

---

### Task 12: Member message

**Files:**
- Create: `reimbursement_council/core/explain.py`
- Test: `tests/core/test_explain.py`

**Interfaces:**
- Consumes: `LaneChoice` (Task 11), `RuleResult`, `PayoutResult`, `MemberMessage` (Task 2), `format_sar` (Task 4), `Settings.messages` (Task 3)
- Produces: `build_member_message(choice: LaneChoice, rule_results: list[RuleResult], payout: PayoutResult | None, settings: Settings) -> MemberMessage`.

Template choice: `auto_approve` uses `approved` or `approved_partial` (with `amount`, `requested`); `auto_reject` uses `rejected` with `reason` = the first failed rule's template (filled with `claim_window_days`); `self_fix` uses `self_fix` with `request` = the request kind template filled with the field label (raw field name when the label is missing); `human_review` uses `human_review`.

- [ ] **Step 1: Write the failing tests**

```python
def test_approved():
    m = build_member_message(approve_choice, [], payout_15525, s)
    assert m.en == "Your claim is approved. We will send you 155.25 SAR."
    assert "155.25" in m.ar
def test_partial(): ...      # en contains "155.25" and "460.00"
def test_rejected_late():
    assert m.en == "Your claim was not approved. Reason: The treatment date is more than 90 days before you sent the claim."
def test_self_fix_confirm_date():
    assert m.en == "We need one thing from you to finish your claim. Please check the treatment date we read and fix it if needed."
    assert "تاريخ العلاج" in m.ar
def test_human_review(): ...
def test_unknown_field_label_falls_back_to_name(): ...
```

- [ ] **Step 2: Run to fail, implement, run to pass**

Run: `uv run pytest tests/core/test_explain.py -v`

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: member messages in Arabic and English from templates"
```

---

### Task 13: Storage and file loading

**Files:**
- Create: `reimbursement_council/adapters/storage.py`, `reimbursement_council/adapters/files.py`
- Test: `tests/adapters/test_storage.py`, `tests/adapters/test_files.py`

**Interfaces:**
- Consumes: `Decision`, `Claim`, `ReferenceData` (Task 2), `SeenReceipts` (Task 7)
- Produces: `ClaimStore(db_path: Path)` (creates the parent folder and tables `decisions(claim_id PRIMARY KEY, decided_at, json)` and `receipts(claim_id, image_hash, fingerprint)`), with `save_decision(decision: Decision) -> None` (replace on same claim_id), `load_decision(claim_id: str) -> Decision | None`, `record_receipt(claim_id: str, image_hash: str | None, fingerprint: str | None) -> None`, `seen_receipts(excluding_claim_id: str) -> SeenReceipts`.
- Produces: `load_claim_file(path: Path) -> Claim` (document `file_path` resolved against the claim file's folder; `image_hash` = sha256 hex of the document bytes; `FileNotFoundError` naming the missing document), `load_reference_file(path: Path) -> ReferenceData`.

- [ ] **Step 1: Write the failing tests**

```python
def test_decision_round_trip(tmp_path): ...
def test_seen_excludes_own_claim(tmp_path):        # Review Focus 3
    store.record_receipt("claim-a", "hash1", "fp1")
    assert store.seen_receipts("claim-a") == SeenReceipts(fingerprints=frozenset(), image_hashes=frozenset())
    assert "hash1" in store.seen_receipts("claim-b").image_hashes
def test_load_claim_resolves_and_hashes(tmp_path): ...
def test_load_claim_missing_document_names_it(tmp_path): ...
def test_load_claim_bad_json_raises_validation_error(tmp_path): ...
```

- [ ] **Step 2: Run to fail, implement, run to pass**

Use stdlib `sqlite3` with one connection per call and `with` blocks; decisions stored with `model_dump_json`.
Run: `uv run pytest tests/adapters -v`

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: SQLite claim store and claim file loading"
```

---

### Task 14: Pipeline and end to end data test

**Files:**
- Create: `reimbursement_council/pipeline/process_claim.py`
- Create: `tests/fixtures/reference.json`, `tests/fixtures/claims/*.claim.json`, `tests/fixtures/claims/*.reading.json`
- Test: `tests/pipeline/test_process_claim.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `process_claim(claim: Claim, reference: ReferenceData, settings: Settings, store: ClaimStore, now: datetime, reader_for: Callable[[Document], DocumentReader] = readers.reader_for) -> Decision`.

Steps inside `process_claim`: look up member, policy, history; primary document = first `receipt` or `invoice` (others are logged and skipped for now); extract it; provider by the extracted `vat_number`; `seen_receipts(claim.claim_id)`; hard rules; payout; `ClaimCase`; council; combine; p_good; lane; message; build `Decision` (`expected_loss` None when payout is None); `save_decision`; `record_receipt` with the primary image hash and fingerprint; return it.

Fixtures (all IDs are fixed UUIDs; submitted 2026-11-20T09:00:00Z; member and patient Sara, policy silver active 2026-01-01 to 2026-12-31 covering Sara and Omar; provider Al Noor Clinic, VAT 300000000000003, in network, trust 0.8; Sara's history 5 past, 5 paid; reader fields confidence 0.95; QR payloads made with `encode_zatca_tlv`):

| Claim file | Receipt | Expected |
|---|---|---|
| clean | CONS-GP 15000, VAT 2250, total 17250, QR 2026-11-15T10:30:00Z | auto_approve, complete, calculated 15525 |
| late | same, treatment 2026-07-01 (QR too) | auto_reject, `late` failed |
| blurry_date | no QR, treatment_date confidence 0.60 | self_fix, confirm_field treatment_date |
| blurry_date_no_retries | as blurry_date, retries_used 2 | human_review |
| overpriced | CONS-GP 40000, VAT 6000, total 46000, QR 2026-11-16T11:00:00Z | human_review, calculated 15525, is_partial |
| unlisted_service | no code "Physio session" 20000, VAT 3000, total 23000, QR 2026-11-17T09:00:00Z | human_review, unmatched ["Physio session"] |
| prescription_only | one `prescription` document, patient name only | self_fix, add_document receipt |

- [ ] **Step 1: Write the fixtures and the failing test**

```python
@pytest.mark.parametrize("name, lane", [("clean", "auto_approve"), ("late", "auto_reject"),
    ("blurry_date", "self_fix"), ("blurry_date_no_retries", "human_review"),
    ("overpriced", "human_review"), ("unlisted_service", "human_review"), ("prescription_only", "self_fix")])
def test_fixture_lanes(name, lane, tmp_path): ...    # also check the extra expectations in the table
def test_decision_is_stored(tmp_path): ...
def test_same_receipt_new_claim_is_duplicate(tmp_path):   # Review Focus 3
    first = run("clean"); second = run(clean_claim.model_copy(update={"claim_id": NEW_ID}))
    assert second.lane == "auto_reject" and any(r.rule == "duplicate" and r.outcome == "fail" for r in second.rule_results)
def test_resubmitting_same_claim_is_not_duplicate(tmp_path):  # Review Focus 3
    run("clean"); again = run("clean")
    assert again.lane == "auto_approve"
```

- [ ] **Step 2: Run to fail, implement, run to pass**

Run: `uv run pytest tests/pipeline -v`
If a lane differs from the table, use superpowers:systematic-debugging and check the numbers in Tasks 8 and 11 before changing any config value.

- [ ] **Step 3: Full check and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`
```bash
git commit -m "feat: claim pipeline wired end to end with fixture claims"
```

- [ ] **Step 4: Data review**

Run the data-quality-reviewer agent on the branch diff. Fix what it confirms, then commit.

---

### Task 15: CLI, README and handover

**Files:**
- Create: `reimbursement_council/cli/main.py`
- Modify: `README.md` (How to run, diagram line "QR first, then offline reader, then arithmetic checks", status), `docs/HANDOVER.md`, `docs/SESSION_LOG.md`
- Test: `tests/cli/test_main.py`

**Interfaces:**
- Consumes: `load_settings`, `load_claim_file`, `load_reference_file`, `ClaimStore`, `process_claim`
- Produces: `main(argv: list[str] | None = None) -> int`. Command `run-claim CLAIM_PATH --reference PATH [--config-dir config] [--db data/claims.sqlite]`. Writes a summary to stdout: lines `lane: <lane>`, `outcome: <outcome>`, `payout: <SAR> SAR` (or `payout: none`), `reason: <lane_reason>`, `message (en): ...`, `message (ar): ...`. Logging to stderr at info. Exit 0 on success; exit 2 with one logged error line (no traceback) for `ConfigError`, `ValidationError`, `LookupError`, `FileNotFoundError`.

- [ ] **Step 1: Write the failing tests**

```python
def test_run_clean_claim(tmp_path, capsys):
    code = main(["run-claim", str(CLAIMS / "clean.claim.json"), "--reference", str(FIXTURES / "reference.json"),
                 "--config-dir", str(REPO_CONFIG), "--db", str(tmp_path / "c.sqlite")])
    out = capsys.readouterr().out
    assert code == 0 and "lane: auto_approve" in out and "payout: 155.25 SAR" in out
def test_unknown_member_exits_2(tmp_path): ...
def test_bad_config_exits_2(tmp_path): ...
```

- [ ] **Step 2: Run to fail, implement, run to pass**

Run: `uv run pytest tests/cli -v`, then by hand:
`uv run reimbursement-council run-claim tests/fixtures/claims/clean.claim.json --reference tests/fixtures/reference.json`
Expected: `lane: auto_approve` and `payout: 155.25 SAR`.

- [ ] **Step 3: Docs**

README "How to run" in under 5 commands (`uv sync`, `uv run pytest`, the run-claim command). HANDOVER sections 1 to 6 rewritten to the new state, with CHECK lines for the decisions list at the top of this plan; section 7 gets one history line. SESSION_LOG gets a dated entry.

- [ ] **Step 4: Verify and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`
```bash
git commit -m "feat: run-claim CLI and docs for the walking skeleton"
```

- [ ] **Step 5: Code review**

Use superpowers:requesting-code-review on the whole branch. Do not merge to main; the owner reviews.
