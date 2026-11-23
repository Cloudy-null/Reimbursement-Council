# Handover

## 1. Current status
Planning only. No code yet. The design, conventions, data model, UI design, experiments plan, decisions, project skills and agents are written. Waiting for owner approval of the spec and DESIGN.md. Next step after approval: write the build plan with superpowers:writing-plans.

## 2. Architecture overview and folder map
One Python pipeline app (decision 001). Stages: intake, extraction (QR first, vision model, arithmetic checks), hard rules, council, decision (combine, calibrate, lanes), explanation. Three screens plus a metrics page. Planned folder map is in docs/CONVENTIONS.md.

## 3. How to run, test, and deploy
Nothing to run yet.

## 4. Data sources and known data issues
- Synthetic generator (to build) for training and tuning.
- Real extraction test sets: ReceiptSense, SROIE, CORD. Licenses not checked yet.
- Real end to end test set: 50 to 100 anonymized medical receipts, not collected yet.

## 5. Open CHECK items and known bugs
- CHECK: demo date and pitch length.
- CHECK: the second required document in the real flow (proof of payment plus what?).
- CHECK: review_cost value in SAR.
- CHECK: dataset licenses.
- CHECK: Claude API key and budget for overnight and demo.
- CHECK: UI reference sites (blocks UI work).
- CHECK: DESIGN.md color contrast.

## 6. Next 3 tasks
1. Owner reviews and approves the spec and DESIGN.md.
2. Write the build plan for layer 1 and layer 2 with superpowers:writing-plans into docs/superpowers/plans/.
3. Start overnight mode on branch build/overnight.

## 7. Project history
- 2026-11-22: Solve for Bupa workshop day 1. Problem given: make insurance reimbursement claims frictionless and efficient.
- 2026-11-23: Design session. Picked one pipeline app, weighted council with veto rules, cost-based lanes, self-fix, ablation testing. Repo created with docs only.
