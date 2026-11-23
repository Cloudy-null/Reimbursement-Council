# Handover

## 1. Current status
Planning only. No code yet. The spec is approved (2026-11-23). The first build plan is written and waiting for owner review: docs/superpowers/plans/2026-11-23-walking-skeleton.md. It builds a walking skeleton: every pipeline stage in Python with tests, a fixture reader instead of OCR, and a run-claim CLI. No screens.

## 2. Architecture overview and folder map
One Python pipeline app (decision 001). Stages: intake, extraction (QR first, vision model, arithmetic checks), hard rules, council, decision (combine, calibrate, lanes), explanation. Three screens plus a metrics page. Planned folder map is in docs/CONVENTIONS.md.

## 3. How to run, test, and deploy
Nothing to run yet.

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
- CHECK: uv is not installed on the owner's machine, and Python 3.12 is missing (3.11 and 3.13 are there). uv can install 3.12 itself.

## 6. Next 3 tasks
1. Owner reviews the walking skeleton plan and picks how to run it (subagent-driven or native).
2. Owner installs uv.
3. Build the plan on branch build/skeleton, starting with Task 1 (project setup and CI).

## 7. Project history
- 2026-11-22: Solve for Bupa workshop day 1. Problem given: make insurance reimbursement claims frictionless and efficient.
- 2026-11-23: Design session. Picked one pipeline app, weighted council with veto rules, cost-based lanes, self-fix, ablation testing. Repo created with docs only. Same day: switched to no paid API (Pro plan only), real test data redefined as public receipts plus synthetic claim context.
- 2026-11-23: Spec approved by the owner. Style reference in DESIGN.md made loose inspiration only. Walking skeleton plan written (15 tasks).
