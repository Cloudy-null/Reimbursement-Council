# Handover

## 1. Current status
Building the walking skeleton plan (docs/superpowers/plans/2026-11-23-walking-skeleton.md) on branch build/skeleton, native execution. Spec approved 2026-11-23.
Progress: Task 6 of 15 done (extraction stage). Every task is one or more commits; git log is the record.

## 2. Architecture overview and folder map
One Python pipeline app (decision 001). Stages: intake, extraction (QR first, vision model, arithmetic checks), hard rules, council, decision (combine, calibrate, lanes), explanation. Three screens plus a metrics page. Planned folder map is in docs/CONVENTIONS.md.

## 3. How to run, test, and deploy
Install uv, then: `uv sync` and `uv run pytest`. Checks: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`.

## 4. Data sources and known data issues
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

## 6. Next 3 tasks
1. Task 7: hard rules.
2. Task 8: payout math.
3. Task 9: document and coverage checkers.

## 7. Project history
- 2026-11-22: Solve for Bupa workshop day 1. Problem given: make insurance reimbursement claims frictionless and efficient.
- 2026-11-23: Design session. Picked one pipeline app, weighted council with veto rules, cost-based lanes, self-fix, ablation testing. Repo created with docs only. Same day: switched to no paid API (Pro plan only), real test data redefined as public receipts plus synthetic claim context.
- 2026-11-23: Spec approved by the owner. Style reference in DESIGN.md made loose inspiration only. Walking skeleton plan written (15 tasks).
