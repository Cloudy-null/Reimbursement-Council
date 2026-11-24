# Handover

## 1. Current status
Day 3 work is on branch fix/day3, cut from main at c53f064 (PRs #1, #2 and #3 are merged into main). Item 1 (push layer-1 tag) is blocked, see CHECK in section 5. Item 4 done: row grouping moved from core/receipt_parsing.py (now 287 lines) to core/receipt_rows.py, no behavior change. Item 2 partly done: (a) OCR cache bug fixed. The old EasyOcrEngine name had no version until the model loaded, and the cache built the file name before reading, so the first image of every run was saved as <hash>-easyocr-ar-en.json and never found again (seen on disk on the laptop). Now the name comes from the installed package version at start. (b) A cut off cache file is read again, and cache files are written to a .partial file and renamed. (c) run-set --resume keeps stored results and runs only the missing claims; each results file has its own database (<results stem>.sqlite plus <stem>.run.json), and --resume refuses a database made with another reader, calibration or config. (d) Each claim logs a start line (claim n/total id) and a finish line with read and total seconds. Checked by hand on 10 tune claims: second run read nothing (0.2 s per claim), --resume took 2.8 s with equal rows. 307 tests pass. NOT found: the cause of the exit code 4 crash, see CHECK in section 5. Layer 1 done (receipt photos read with EasyOCR; accuracy in EXPERIMENTS.md; tag layer-1 only on the desktop). Layer 3 website done (uv run reimbursement-council serve). Layer 2 code done and tested, but the measuring run is NOT finished: it was paused on 2026-11-24 at 78 of 120 tuning claims to move to the owner's laptop. No calibration has been fitted yet and config/calibration.yaml does not exist. Generated data is not in git: the laptop must make the sets again (same seeds give the same claims) and read them with OCR (about 10 seconds per receipt, cached after). Resume steps: uv sync --extra ocr; uv run reimbursement-council make-claims --count 120 --seed 11 --out data/sets/tune; uv run reimbursement-council make-claims --count 60 --seed 12 --out data/sets/check; uv run reimbursement-council run-set data/sets/tune --reader easyocr --calibration off; uv run reimbursement-council fit-calibration data/sets/tune/results.json; uv run reimbursement-council run-set data/sets/check --reader easyocr --calibration off --results-name results_raw.json; uv run reimbursement-council run-set data/sets/check --reader easyocr --calibration on --results-name results_calibrated.json. Keep the laptop awake for about 45 minutes.

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
- CHECK: run-set exit code 4 after about 34 claims (seen on the desktop PC, no error in the log). Not reproduced on the laptop: a 120 claim tune run on the same seed went past claim 57 with no crash, while pytest and a second run-set ran at the same time. Memory stayed flat at about 2 GB private across 13 claims, so no leak. Our code only returns 0 or 2, and a Python error would print a traceback, so code 4 came from outside our code (the process was stopped, or native code in torch failed). Not proven which. If it happens again: run with --resume to continue, and keep the last "claim n/total id: start" line and the Windows Event Viewer Application log entry from that minute.
- CHECK: the layer-1 tag exists only on the desktop PC. It is not in the laptop clone and not on GitHub (git ls-remote --tags origin is empty). Push it from the PC with git push origin layer-1, or say which commit it should point to and make it on the laptop.
- CHECK: the run-ablation skill says switches live in config/experiments.yaml, but that file does not exist. calibration_enabled is in config/decision.yaml. Fix the skill text or move the switch.
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
1. Finish the layer 2 run with the resume steps in section 1 (on the laptop).
2. Write the E6 numbers (calibration off vs on, check set) into EXPERIMENTS.md with command and commit; commit config/calibration.yaml; decide whether calibration_enabled should be true; tag layer-2.
3. Owner review of the designs written by Claude overnight and the new config values.

## 7. Project history
- 2026-11-22: Solve for Bupa workshop day 1. Problem given: make insurance reimbursement claims frictionless and efficient.
- 2026-11-23: Design session. Picked one pipeline app, weighted council with veto rules, cost-based lanes, self-fix, ablation testing. Repo created with docs only. Same day: switched to no paid API (Pro plan only), real test data redefined as public receipts plus synthetic claim context.
- 2026-11-23: Spec approved by the owner. Style reference in DESIGN.md made loose inspiration only. Walking skeleton plan written (15 tasks).
- 2026-11-23: Walking skeleton built on build/skeleton: 15 tasks, every stage with tests, run-claim CLI.
