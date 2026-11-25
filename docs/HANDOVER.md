# Handover

## web/final note (read first)
Done (tag demo-ready-final-5): EXIF orientation on upload plus a turn retry for weak readings (real invoice at 90 degrees now fully read); Arabic-Indic numbers matched as digit sets (synthetic: date 0 to 0.833, total 0 to 0.5, kept under the floor for the member to confirm); patient names matched word by word, by consonants across Arabic and English, low-confidence names cannot tell, prescriptions may be 30 days older (optical false alarms 0.45 to 0.05, check set still 3 of 3 caught, 0 of 57 false alarms; precision 1.0, false rejects 0).
Not done: full reruns of every set, numbers.md update, reviews. CHECK: the reviewer was benched by its live monitor (discarded answers 0.22 over 0.20) during check runs; golden check 0.95 passed and a person-step reviewer-enable turned it back on; watch it before the demo.

## Core day 4b final report (read this first)

Merged to main and tagged demo-ready-final-4. Numbers are from commit ac2a7e4 (docs/EXPERIMENTS.md
"FINAL CHECK of core day 4b", docs/pitch/numbers.md). After it, only the startup reviewer check
and the e2e test setup changed (081b983). Tests: 865 pass; ruff and mypy clean; the e2e demo
test passes 4 of 4 (add-member and the partial payout path included).

- Case study (docs/pitch/real_claim_case.md): our estimate before submit 450 SAR, Bupa paid 450
  SAR. Sent today: rejected as late (119 days). Sent on Bupa's received date: 450 SAR, a person
  checks it (brand-name items read under the floor).
- Seconds per claim through the website (stand-in set): 13.855 s before, 8.057 s with EasyOCR on
  the GPU (09b4717).
- Real-derived and robustness (synthetic): 150 damaged optical claims (10 kinds x levels 1, 3, 5),
  0 wrong approvals at every level; docs/pitch/damage_chart.svg. Real invoice variants (8): date
  5, total 6, VAT 4, items 4 right; every miss was a blank, never a wrong value.
- Languages: translation asked for French 6 of 6 and Urdu 6 of 6, none of the 30 Arabic, English,
  mixed, Hijri or Arabic-Indic receipts. Arabic-Indic digits are not read (0 of 6 totals).
- AI reviewer: dev set (tuning) 0.65 to 1.0; held-out set (never looked at, run once) 0.95. With
  it on: precision 1.0, 0 wrong approvals, 1 claim moved to a person. It is ON (config) and the
  health file in data/reviewer is healthy after check-reviewer and reviewer-enable. The held-out
  set is the startup golden set; startup only checks an unchecked model and prompt.
- Synthetic check set (60): automation 0.5 with the reviewer (0.5167 without), precision 1.0,
  false rejects 0. Real SROIE: total 0.6167, date 0.6, shop 0.5167; real e2e 0 wrong approvals.
- Live test on data/live_test: no photos were there.

CHECKs:
1. Tabby is treated as paid, not as a credit invoice (the real claim was not held for it).
2. Synthetic dental receipts print no tooth number, so those claims are asked for one.
3. Optical set: 0.45 of claims still raise a false patient-name alarm (the member is asked).
4. Arabic-Indic digits: OCR garbles them, the model's right value is not confirmed.
5. A photo turned 90 degrees is not read (try EasyOCR rotation_info).
6. core/vision_checks.py is 318 lines and core/receipt_parsing.py 302: split next time.
7. The uv cache is on D:\uv-cache (user setting UV_CACHE_DIR); PyTorch 2.14.1+cu130 is pinned
   for Windows; data/ is a junction to D:\rc-data\data.
8. The e2e test runs the demo path with the reviewer off; the reviewer has its own tests.
9. If the model or prompt changes, run check-reviewer and reviewer-enable before a demo, or
   the first start runs a golden check that holds the model for a few minutes.

## Core day 4 report

Branch core/day4, merged to main and tagged demo-ready-final (demo-ready-1 was the halfway
point). Every number below is from commit 38cc89d; commands in docs/EXPERIMENTS.md "FINAL
CHECK" and docs/pitch/numbers.md. Tests: 722 pass, ruff and mypy clean, the browser e2e demo
test passes (2 of 2) with the new default reader.

**Before vs after on real receipts** (60 SROIE scans, read-sroie):

| Field | EasyOCR (before) | Local model + EasyOCR (after) |
|---|---|---|
| Total | 0.3333 | 0.6167 |
| Date | 0.5333 | 0.6 |
| Shop name | 0.35 | 0.5167 |

Real end to end (50): 0 wrong approvals and 0 false rejects before and after. Automation stays 0
on that set: Malaysian shop receipts have no item on our price list, so it can only show safety.
On the synthetic check set (60) automation went from 0.3833 (EasyOCR) to 0.5667 at precision 1.0
and 0 false rejects.

**Live test, seconds per claim:** data/live_test did not exist, so a labeled stand-in set was used
(4 real SROIE scans, 4 synthetic Arabic-first receipts of which 2 heavily damaged, 1 receipt with
its report; re-saved so nothing was cached): 9 of 9 finished, 0 errors, mean 13.855 s, median
13.31 s, max 23.193 s per claim through the website. Run your own photos with
`uv run reimbursement-council live-test data/live_test --url http://127.0.0.1:8000`
(website running; one photo or one folder of photos per claim).

**Made-up rate** (values the model returned that are printed nowhere, all dropped): 0.2865 on real
receipts (an upper bound: most are right values EasyOCR misread), 0.05 on synthetic receipts. 0
of 78 QR comparisons disagreed.

**Golden set score (AI case reviewer):** 0.85 (17 of 20) against a 0.90 limit, so the circuit
breaker benched it. It passed every injection case and every clear case; it missed 3 tricky bad
claims. The prompt was changed twice after seeing golden failures (format, and what the
calculated payout means), so 0.85 is not a clean held-out score.

**On by default, and why:**
- reader ollama (qwen3-vl:8b-instruct) with two readers on: best automation at precision 1.0
  and 0 false rejects on synthetic and real sets. Without the second reader, values only the
  model read sit under the floor and automation falls to 0.3667.
- calibration on (refitted on the tune set with the model reader): ECE 0.1059 to 0.0991,
  precision 1.0 and 0 false rejects both ways (the owner's rule).
- confidence per field, and the one-tap date confirm rule (another document agrees, or more than
  7 days from the claim window limit and the policy dates, and the two readers agree).
- AI case reviewer: OFF. It is built with its guard, golden set and circuit breaker, but benched
  at 0.85. The numbers page shows its state.

**Demo over Tailscale:** Tailscale is not installed on this PC. Steps in docs/DEMO.md: install and
sign in on both machines, then on the PC
`uv run reimbursement-council serve --host <tailscale ip> --port 8000`, and open
`http://<tailscale ip>:8000` on the laptop. Plan B: the laptop with EasyOCR. Plan C: demo mode.

**What failed or is weak:**
- The plain qwen3-vl:8b tag thinks and returned empty answers; the 8b-instruct tag is used.
- EasyOCR runs on the CPU (torch CPU build; the CUDA build does not fit on C:), which is most of
  the 14 seconds per new photo.
- Drive C: hit 7 MB free. data/ was moved to D:\rc-data\data with a junction at the old path.
- First tries corrected before recording: exact grounding dropped right dates (one digit of
  noise is now allowed, kept under the floor); names in both scripts were joined.

**CHECKs for you** (all in section 5; the new ones start with "CHECK (core day 4"):
1. Put real photos in data/live_test and run live-test; install Tailscale.
2. Free space on C: and install the CUDA build of torch for faster OCR.
3. The switches were chosen on the synthetic check set; there is no fresh held-out set.
4. The reviewer stays benched until its golden score passes; decide whether to keep it.
5. The Saudi VAT number format (15 digits, first and last 3) was not checked against the ZATCA
   document itself.
6. The review items not fixed are listed in section 5.

## 1. Current status
Core day 4b in progress on branch core/day4b (main at 541f75d, tag demo-ready-final-2: Steps 0
and 1). Done on the branch so far, each with tests:
- Step 0: realtest/ ignored and never committed; logs mask 7+ digit numbers; live-test reports
  mask names and long numbers; consent recorded in MODEL_SAFETY.md.
- Step 1: EasyOCR on the GPU (CUDA 13.0 PyTorch on Windows, decision 012); the model and EasyOCR
  take turns on the one GPU. Live seconds per claim 13.855 to 8.057 (stand-in set).
- Step 2: add-member (CLI and website form), merged from core/day4b-member.
- Step 3: Bupa FAQ rules: VAT not paid, member share 20 percent capped at 100 SAR, benefit
  sub-limits (optical frames), optical and dental services, eye test (on the invoice counts),
  tooth number, proof of payment for credit invoices, invoice validity, translation; the check
  page shows the expected payout and why before submit; export carries the new fields.
- Step 4: real case study (docs/pitch/real_claim_case.md): estimate 450 SAR before submit, Bupa
  paid 450 SAR. Four reading bugs found and fixed. Model prompt version 2 (item types).
- Step 4b part: 8 image variants of the real invoice measured.
- Step 5 part: HEIC uploads (decision 013).
Running: Track B generators (worktree D:\rc-worktrees\gen, branch core/day4b-gen) and the new
reviewer dev and held-out sets (tests/golden_v2).

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
- Rulings made while building the document set plan (for the owner to check): FieldEdit.retake_asked from the spec is Claim.retake_fields; the word joining document names (or / أو) is in messages.yaml; apply_edits takes document_id first; Decision and ClaimCase carry the judged edits; outpatient fixture claims got a same-day medical report and receipt fixtures got printed text; the "second receipt blocks" rule is replaced by "block when billing documents differ in total or VAT number"; web shared code is in web/context.py; a photo with no text and no QR is "other".
- Deferred minors from the Task 7 review: notes about dropped edits are only logged, not shown to the reviewer; a category change can switch off the provider check without being flagged; claim_categories accepts unknown names; relabeling a receipt as invoice picks the primary; some pure rules (_primary, _edit_rules, billing comparison) sit in pipeline/ and could move to core/.
- CHECK: run-set exit code 4 after about 34 claims (seen on the desktop PC, no error in the log). Not reproduced on the laptop: a 120 claim tune run on the same seed went past claim 57 with no crash, while pytest and a second run-set ran at the same time. Memory stayed flat at about 2 GB private across 13 claims, so no leak. Our code only returns 0 or 2, and a Python error would print a traceback, so code 4 came from outside our code (the process was stopped, or native code in torch failed). Not proven which. If it happens again: run with --resume to continue, and keep the last "claim n/total id: start" line and the Windows Event Viewer Application log entry from that minute.
- On the laptop, uv run from the Claude desktop app needs UV_PYTHON_INSTALL_DIR=D:\dev\.uv-python. The app is a packaged Windows app, so its writes to AppData\Roaming go to a hidden copy and uv's Python link breaks there. A normal terminal does not need this.
- CHECK (Task 10): the defect weights, including the six new document defects, live in synthetic/claims.py and synthetic/document_sets.py, not in config/*.yaml. The add-defect-type skill asks for a config knob. Moving them is a small change; left as is to keep Task 10 small.
- CHECK (Task 10): no fixed version is made for the fixable document defects (the missing prescription or report, the right patient or date), so self-fix cannot be simulated end to end yet.
- CHECK (Task 10): with the qr_only reader a prescription or report has no QR and no text, so it reads as "other" and every claim that needs one goes to self_fix. Document set numbers only mean something with EasyOCR.
- CHECK (Task 10): the clean share of a set fell from 45 of 100 to 45 of 124 weight, so earlier E-numbers and new ones are not on the same mix.
- Deferred Task 13 review minors: hardcoded cat_* labels in i18n (a new category in config has no label), POST /claims with a refused file renders the check page instead of redirecting (a refresh makes a second draft), edits are cleared after /fix so the member retypes them, the old /claims/{id}/document route is redundant, a replaced document's reading row stays in the readings table.
- CHECK (Task 14): the browser keeps an old app.css after a change (a hard refresh fixes it). A version query on the CSS link would stop this before the demo.
- CHECK (Task 14): screenshots were checked in the built-in browser only. Saved Playwright screenshots and an Impeccable audit are still to do (neither is installed here).
- CHECK (E12): the check set has only 3 mismatch claims and no missing-document claims. The tune set run (120 claims, recorded in EXPERIMENTS) agrees: 7 of 7 mismatches caught, 2 false alarms in 113 from OCR misreading the Arabic patient name on a medical report, and 1 missing prescription not found because no line items were read.
- CHECK (E12): a cross check on a low-confidence OCR name still counts as a mismatch. After the fixes no false alarms were left, but a heavy-damage name could still trip it. Consider "cannot tell" below the confidence floor.
- (Closed on core day 4: docs/INTEGRATION.md now says the national eClaims system is built on FHIR R4, from the simplifier.net Saudi Arabia jurisdiction page. The 2026 State of FHIR survey report itself was not found.)
- CHECK (core day 4): Saudi VAT number format in config (decision.yaml vision.vat_number_pattern) is 15 digits, first and last digit 3. Several guides say so and one cites ZATCA e-invoicing rule BR-KSA-40; the official ZATCA document was not opened.
- CHECK (day 4): one-tap date confirm sends a "yes" to a person instead of letting the tap clear the late and policy_inactive rules. Safer, but it does not raise automation. Owner to decide if a confirmed date that another document also shows may count.
- CHECK (day 4): TIFF scans are refused; PDFs read only up to max_pdf_pages (3) pages and through OCR, not their text layer.
- CHECK (day 4): log masking hides Arabic text, long numbers and emails in our log lines; uvicorn's own access log is not filtered (it holds only paths with claim ids).
- CHECK (day 4, real data): EasyOCR loaded with Arabic and English reads faint Latin print as Arabic glyphs on about 6 of the 10 worst SROIE receipts. Options: guess the script per document and read with one language, or a second English-only pass. Not done.
- CHECK (day 4, licenses): SROIE copy at github.com/zzzDavid/ICDAR-2019-SROIE is MIT (the original ICDAR 2019 competition data is for research). ReceiptSense (Hugging Face abdoelsayed/CORU): the card metadata says CC-BY-4.0, a search summary said MIT; its images are in 1 to 9 GB zips, so it was not used. Data is in data/real (never committed).
- CHECK (day 4): E3's switch council_enabled does not exist; E3 was run as document checker alone (the other members turned off with --set).
- CHECK (day 4, PC): the C: drive had 445 MB free. Playwright's own Chromium could not be installed, so the e2e test and screenshots use Microsoft Edge. Free some space before the demo.
- CHECK (day 4): there is no demo-ready-1 tag, so both reviews covered everything since main (5a6cd51).
- CHECK (day 4, data review 2): with self-fix and the member's fix simulated, 24 of 60 claims are still waiting for the member at the end (21 had no fix file; all 24 ask to confirm the treatment date). They count as no review and no cost. The numbers say so next to the cost.
- CHECK (day 4, data review 2): the root of most self-fix requests is old code: receipt_parsing takes the lowest confidence on the whole row, including a misread label such as the Arabic word for date, so a right date on a clean receipt gets 0.61 to 0.78 and is under the 0.90 floor. Using the confidence of the date text itself would cut self-fix a lot. Not changed tonight (it moves every number).
- CHECK (day 4, data review 7): weak-key collisions (dental provider has 2 services) send 2 clean claims to a person as "possible duplicate" in the fix run.
- CHECK (day 4, data review 8): real_e2e truth has correct_payout 0 (unknown). Today there are no auto approves on it, so no money metric is affected; if there were, precision there would be meaningless.
- CHECK (day 4, data review 10): the provider cross check now says "cannot tell" when the two names are in different scripts only. Fair, but fewer provider mismatches are caught.
- CHECK (day 4, code review): not fixed yet: error pages after a POST come out in English and HTTPException details are English strings; a refresh after a partly refused upload makes a second draft; lane changes in the fix, confirm and to-reviewer routes should move to core; cli/run_set.py (about 310 lines) and core/receipt_parsing.py (about 360) are past the 300 line rule and should be split; demo files are written without a temp file and rename; the upload size is checked after the file is in memory; English names in log lines are not masked (none are logged today).
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

- CHECK (core day 4): Tailscale is not installed on this PC, so the site could not be tested
  over Tailscale. docs/DEMO.md has the steps; serve --host already takes the address.
- CHECK (core day 4): data/live_test/ did not exist when the night started. The live-test
  command is built and tested; live results are in the report only if photos were there.
- CHECK (core day 4): drive C: has about 30 MB free. Runs and the database write under the repo
  on C:. Please free space before the demo.

- CHECK (core day 4, reviews, not fixed): the prompt says "under 200 characters" but
  max_reason_characters is 300; fence words could be dodged with look-alike Unicode (the guard
  limits the harm to sending claims to a person); the model answer cache key leaves out
  max_image_side, num_ctx, num_predict and the schema (bump prompt_version when changing them);
  run-set has no switch to skip the model answer cache, so run-set seconds can be cache hits
  (live seconds come from live-test on fresh photos); rates on empty groups show 0.0 (for
  example auto_approve_precision on real_e2e with no approvals); made_up counts only answers
  that arrived.
- CHECK (core day 4, data review 7): the switches (calibration on, reader ollama, two readers
  on) were chosen on the synthetic check set. There is no fresh held-out synthetic set yet.
- CHECK (core day 4, data review 14): the tune and check sets were made with different set
  config versions (e36450954f90 and 2d82d0d23bfe).
- CHECK (core day 4): real_e2e (SROIE, Malaysian shop receipts) can measure safety but never
  automation: no item is on our price list and no provider can match.
- CHECK (core day 4): the AI reviewer golden prompts 2 and 3 were changed after seeing golden
  failures, so its 0.85 is not a clean held-out score. It stays benched and off.
- CHECK (core day 4): EasyOCR runs on the CPU (torch CPU build). The CUDA build would cut about
  15 s per new photo but does not fit on C:. Install it after freeing space:
  uv pip install torch --index-url https://download.pytorch.org/whl/cu124 (check the version).

## 6. Next 3 tasks
1. Merge Track B, generate the optical, dental, damage and language sets, measure (4b, 4c).
2. Step 4d: tune the reviewer prompt on tests/golden_v2/dev only, run heldout once.
3. Step 5 demo claims and e2e; Step 6 rerun, docs, merge, tag demo-ready-final-3.

## 7. Project history
- 2026-11-22: Solve for Bupa workshop day 1. Problem given: make insurance reimbursement claims frictionless and efficient.
- 2026-11-23: Design session. Picked one pipeline app, weighted council with veto rules, cost-based lanes, self-fix, ablation testing. Repo created with docs only. Same day: switched to no paid API (Pro plan only), real test data redefined as public receipts plus synthetic claim context.
- 2026-11-23: Spec approved by the owner. Style reference in DESIGN.md made loose inspiration only. Walking skeleton plan written (15 tasks).
- 2026-11-23: Walking skeleton built on build/skeleton: 15 tasks, every stage with tests, run-claim CLI.
- 2026-11-24: Moved to the laptop. Day 3 fixes on fix/day3: OCR cache bug, resumable run-set, data review fixes (decision 007), parser split, heavy damage metric. Layer 2 run finished, E6 recorded, tagged layer-2. Owner asked for website changes; brainstorming started.
