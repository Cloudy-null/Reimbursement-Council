# Handover

## 1. Current status
Overnight build on branch build/overnight (owner said: make what we can, do it). Walking skeleton (PR #1) is merged to main. Layer 1 in progress: reading receipt photos. Design and plan written by Claude, not yet reviewed: docs/superpowers/specs/2026-11-23-layer1-receipt-reading-design.md, docs/superpowers/plans/2026-11-23-layer1-receipt-reading.md. Done: EasyOCR spike, price aliases, synthetic receipt content and drawing (three layouts), the OCR text parser (core/receipt_parsing.py, tested on real EasyOCR output saved in tests/fixtures/ocr), and corroboration (all checks pass means the OCR amounts are trusted). EasyOCR is an optional extra: uv sync --extra ocr.

## 2. Architecture overview and folder map
One Python pipeline app (decision 001). Stages in reimbursement_council/pipeline/process_claim.py: read the primary receipt (adapters/readers.py), extraction with QR first and arithmetic checks (core/extraction.py), hard rules (core/rules.py), payout (core/payout.py), council (core/council/), combine and lanes (core/decision/), member message (core/explain.py), store (adapters/storage.py). Config loading in reimbursement_council/config/. Folder map in README.md and docs/CONVENTIONS.md.

## 3. How to run, test, and deploy
Install uv (owner's machine: winget, lives in %LOCALAPPDATA%\Microsoft\WinGet\Links). Then `uv sync`, `uv run pytest`, and `uv run reimbursement-council run-claim tests/fixtures/claims/clean.claim.json --reference tests/fixtures/reference.json`. Checks: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`. CI runs all four on every push. Fixtures are rebuilt with `uv run python tests/fixtures/build_fixtures.py`.

## 4. Data sources and known data issues
- tests/fixtures/: hand-made synthetic claims and readings (7 claims, one reference file). Not real data.
- Synthetic generator (to build) for training and tuning.
- Real extraction test sets: ReceiptSense, SROIE, CORD. Licenses not checked yet.
- Real end to end test set: public dataset receipts plus synthetic claim context (member, policy, history).
- Team-found online invoices: used only to make generator templates realistic.

## 5. Open CHECK items and known bugs
- CHECK: demo date and pitch length.
- CHECK: the second required document in the real flow (proof of payment plus what?).
- CHECK: reviewer_time_value in SAR.
- CHECK: dataset licenses.
- CHECK: optional free Gemini API key.
- CHECK: DESIGN.md color contrast.
- CHECK: the walking skeleton plan makes 10 calls the spec left open (list at the top of the plan, "Decisions this plan makes"). Owner to confirm or change.
- CHECK: calls made while building, owner to confirm:
  - history and benefit limits come from the patient, not the member filing (limits are per person treated).
  - the member filing must also be on the claim's policy, or person_not_covered fails.
  - auto approve is also blocked by: a failed check, a missing or unclear receipt total, a payout above the receipt total, or more than one receipt in the claim.
  - a possible duplicate (same VAT number, treatment date and total, or a fingerprint match with unclear parts) goes to human review, never to self-fix or rejection.
  - a rejected claim's receipt can be sent again in a new claim.
  - VAT paid is never more than the VAT on the receipt.
  - dates are compared in local time, a fixed UTC+3 offset in config/policy.yaml.
- Deferred, not built yet:
  - add-council-member skill steps 9 (ablation run) and 10 (reviewer card row): need the harness and the screens.
  - a fully used benefit limit gives "approved in part, 0.00 SAR". A clearer message is needed.
  - a PDF document stops the claim with an input error and stores no decision (PDFs are the next plan).
  - the provider is matched on a VAT number of any confidence.
  - the CLI treats any ValueError as bad input, so a code bug can look like bad input.
  - saving the decision and the receipt are two transactions, not one.
  - an infinite weight in YAML would give a NaN score.
  - a receipt that matches a still-open claim (self_fix or human_review) is rejected as a duplicate instead of going to a human.

## 6. Next 3 tasks
1. EasyOCR engine adapter, disk cache, QR plus OCR reader, reader setting wired into the pipeline and CLI.
2. make-receipts and read-accuracy commands; run on generated receipts; numbers into EXPERIMENTS.md; tag layer-1.
3. Layer 2: synthetic claims set end to end, then calibration.

## 7. Project history
- 2026-11-22: Solve for Bupa workshop day 1. Problem given: make insurance reimbursement claims frictionless and efficient.
- 2026-11-23: Design session. Picked one pipeline app, weighted council with veto rules, cost-based lanes, self-fix, ablation testing. Repo created with docs only. Same day: switched to no paid API (Pro plan only), real test data redefined as public receipts plus synthetic claim context.
- 2026-11-23: Spec approved by the owner. Style reference in DESIGN.md made loose inspiration only. Walking skeleton plan written (15 tasks).
- 2026-11-23: Walking skeleton built on build/skeleton: 15 tasks, every stage with tests, run-claim CLI.
