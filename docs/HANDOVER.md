# Handover

## 1. Current status
Branch fix/day3, cut from main at c53f064 (PRs #1 to #3 are merged). Not merged, not pushed. Layers 1, 2 and 3 are done. Layer 2 is tagged layer-2 on this laptop; layer-1 exists only on the desktop (CHECK below).

Day 3 list, item by item:
1. Push the layer-1 tag: blocked, the tag is not in this clone or on GitHub.
2. run-set crash: the OCR cache bug is fixed (the first image of every run was saved under a name without the EasyOCR version and read again every run). Cache files are written safely and a cut off one is read again. run-set --resume continues a stopped run (one database per results file, refused if the reader, calibration, config or set seed differ). Each claim logs a start line and a finish line with read and total seconds. The exit code 4 crash was not reproduced and its cause is not found (CHECK below).
3. Data review: done. Labels match the data. Fixed: ECE and the calibration fit leave out hard rule rejects, a false reject costs the payout it should have made (decision 007), duplicates come after a readable original and keep its defects, make-claims needs an empty folder and writes set.json, empty runs are an error. The rest are CHECK items below.
4. Parser split: row grouping is in core/receipt_rows.py, no behavior change.
5. Heavy damage metric: run-set reports where heavy and unreadable photos go and how many were wrongly auto approved.
6. Layer 2 run: done, E6 in EXPERIMENTS.md. Calibration cuts ECE from 0.155 to 0.051 on the synthetic check set with precision 1.0 and no false rejects. config/calibration.yaml is committed; calibration_enabled is still false (CHECK below).
7. Real receipts (E1, E11): not started.

318 tests pass, ruff and mypy clean. Generated data is not in git: the day 3 sets are in data/sets/day3 on the laptop, and make-claims with the same seed makes them again. On the laptop, uv from the Claude desktop app needs UV_PYTHON_INSTALL_DIR=D:\dev\.uv-python (see section 5). The website runs with uv run reimbursement-council serve, or from the app's browser pane with .claude/launch.json (not committed, it holds a laptop path).

Now building on branch feat/document-set (cut from fix/day3, PR #4 still open): the official brief is in docs/brief/project-brief.md. Design: docs/superpowers/specs/2026-11-24-document-set-design.md (approved with the owner's two changes). Plan: docs/superpowers/plans/2026-11-24-document-set.md, 15 tasks, built by Claude with a fresh reviewer after tasks 7, 8 and 13. If usage runs low, tasks 1 to 8, 12 and 13 first; 9 to 11 and 15 tonight. Progress ledger (git-ignored): .superpowers/sdd/2026-11-24-document-set/progress.md.
Document set progress: Task 1 done (data model). Task 2 done (config/documents.yaml: required documents per category, kind keywords, name and date settings; cross_checks_enabled in decision.yaml; missing_document, mismatch and member_edit messages and document names in both languages). Task 3 done (core/document_kinds.py finds the type from text keywords and the QR; the OCR reader keeps the text row by row). Task 4 done (core/claim_categories.py and core/document_needs.py: every claim needs an invoice or receipt, plus the groups of its categories, each with an Arabic and English request). Task 5 done (core/cross_checks.py: patient against the account in the same script, dates across documents, provider only between a report and an outpatient or dental invoice; unknown when data is missing). Task 6 done (core/edit_evidence.py: judge_edit against the QR, other documents and the arithmetic; apply_edits puts supported edits, and unbacked edits on fields that are not money or hard rule fields, in as member_typed). Task 7 done (pipeline/document_set.py reads every document once, picks the primary billing document, judges edits, works out categories, needs and cross checks, and adds member_edit rule results; blockers now fire on a missing document or two billing documents with different totals; outpatient fixtures got a same-day medical report). Task 12 done (web/app.py split into context.py, claim_routes.py and a 93 line app.py, no behavior change). A fresh reviewer is checking Task 7; its findings get fixed before Task 8 (lane groups).

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
- CHECK (data review 4): weak-key collisions. With 4 providers, 18 days and fixed prices, clean claims often share VAT number, date and total, so about 6 percent of a set goes to human review as "Possible duplicate" even with a perfect reader. This lowers automation for reasons that are not the council. Fix options: vary prices or quantities, widen the dates, or record the collision in the truth.
- CHECK (data review 6): "light" damage breaks the QR on about half of QR receipts (15 of 29 on seed 11), and 2 undamaged receipts (claim_11_0082, claim_11_0113) have a QR our reader cannot decode. Labels are not wrong, but truth has no qr_readable field. Likely fix: larger QR with a white quiet zone.
- CHECK (data review 7): no claim is near the 90 day line (delays are 1 to 4 or 95 to 130 days), all receipt times are 08:00 to 20:00 so UTC and local dates never differ, and no Hijri dates are printed. A date bug of that kind could not change any number. One seed 12 late claim is submitted on 2026-11-26, after today.
- CHECK (data review 8, docs vs code): DATA_MODEL.md GroundTruth lists correct_fields, fixable and fixed_version_document_ids, which the code does not write. DATA_MODEL and spec section 7 list defects qr_mismatch, arithmetic_error, multiple_patients and missing_prescription, which are not generated, and the doc does not list not_covered, unlisted and tampered_total. The add-defect-type skill wants a fixed version for fixable defects (unreadable); none exists, so self-fix cannot be measured. The layer 2 spec says seeds 1 and 2; the runs use 11 and 12.
- CHECK (data review 9): auto_approve_precision is 0.0 both when nothing was approved and when every approval was wrong. Returning None for an empty group changes the results format and the numbers page, so it was not changed.
- CHECK (data review 10): money as float in receipt_content.py (round(network_price * price_factor)); damage noise seed is the claim index, so claim k in tune and check get the same noise, and make-claims rotation is never negative; read-accuracy matches line items by position; "VAT 15%" is hardcoded in receipt_drawing.py.
- CHECK (decision 007): self fix has no cost in total cost. Decide what asking the member to fix should cost.
- CHECK (E6): turn calibration_enabled on? On the synthetic check set it cut ECE from 0.155 to 0.051 and moved 2 of 60 claims out of human review, with precision 1.0 both ways. It is a 60 claim synthetic set, and the cost gain is partly because self fix costs nothing yet. Left off until the owner decides.
- CHECK (E6 run): self fix is very common. On the tune set 46 of 120 claims went to self_fix, and 16 of those had no photo damage at all. This lowers automation for reasons that are not the photo. Worth finding out why before tuning anything else.
- CHECK: run-set exit code 4 after about 34 claims (seen on the desktop PC, no error in the log). Not reproduced on the laptop: a 120 claim tune run on the same seed went past claim 57 with no crash, while pytest and a second run-set ran at the same time. Memory stayed flat at about 2 GB private across 13 claims, so no leak. Our code only returns 0 or 2, and a Python error would print a traceback, so code 4 came from outside our code (the process was stopped, or native code in torch failed). Not proven which. If it happens again: run with --resume to continue, and keep the last "claim n/total id: start" line and the Windows Event Viewer Application log entry from that minute.
- CHECK: the layer-1 tag exists only on the desktop PC. It is not in the laptop clone and not on GitHub (git ls-remote --tags origin is empty). Push it from the PC with git push origin layer-1, or say which commit it should point to and make it on the laptop.
- On the laptop, uv run from the Claude desktop app needs UV_PYTHON_INSTALL_DIR=D:\dev\.uv-python. The app is a packaged Windows app, so its writes to AppData\Roaming go to a hidden copy and uv's Python link breaks there. A normal terminal does not need this.
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
1. Website changes: finish the design with the owner (open question: what happens when a member edits a field the reader got wrong), then a plan, then build. E10 (member preview before submit) in EXPERIMENTS.md is the matching experiment.
2. Owner decides calibration_enabled (E6 result) and reviews decision 007.
3. Item 7: check dataset licenses (SROIE, ReceiptSense), write them here, then run the reader on 50 real receipts for E1 and E11.

## 7. Project history
- 2026-11-22: Solve for Bupa workshop day 1. Problem given: make insurance reimbursement claims frictionless and efficient.
- 2026-11-23: Design session. Picked one pipeline app, weighted council with veto rules, cost-based lanes, self-fix, ablation testing. Repo created with docs only. Same day: switched to no paid API (Pro plan only), real test data redefined as public receipts plus synthetic claim context.
- 2026-11-23: Spec approved by the owner. Style reference in DESIGN.md made loose inspiration only. Walking skeleton plan written (15 tasks).
- 2026-11-23: Walking skeleton built on build/skeleton: 15 tasks, every stage with tests, run-claim CLI.
- 2026-11-24: Moved to the laptop. Day 3 fixes on fix/day3: OCR cache bug, resumable run-set, data review fixes (decision 007), parser split, heavy damage metric. Layer 2 run finished, E6 recorded, tagged layer-2. Owner asked for website changes; brainstorming started.
