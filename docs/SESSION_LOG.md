# Session log

## 2026-11-23: design session
- Done: full design worked out from three sides (member, automation, reviewer). Spec, conventions, data model, UI design draft, experiments plan, three decision records, three project skills and two agents written. Found related papers and public receipt datasets.
- Broke: nothing, no code.
- Decisions: 001 one pipeline app, 002 weighted council with veto rules, 003 cost-based lanes, 004 no paid API.
- Next: owner approval, then the build plan, then overnight mode.

## 2026-11-23: plan session
- Done: pushed main to GitHub for the first time. Made the style reference in DESIGN.md loose inspiration, not a target. Owner approved the spec. Wrote the walking skeleton plan (docs/superpowers/plans/2026-11-23-walking-skeleton.md): 15 tasks, every pipeline stage in Python with tests, fixture reader instead of OCR, run-claim CLI, no screens.
- Broke: nothing, no code.
- Decisions: the plan lists 10 calls the spec left open, for the owner to confirm. Main ones: low confidence rule inputs block auto approve, unknown line items never auto approve, partial means a cap or limit cut (not co-pay), member messages live in config/messages.yaml.
- Next: owner reviews the plan and installs uv, then build on branch build/skeleton.

## 2026-11-23: build session (walking skeleton)
- Done: installed uv and Python 3.12. Built all 15 tasks of the walking skeleton plan on branch build/skeleton with tests first: models, config loader, money and ZATCA QR, readers, extraction, hard rules, payout, four council members, lanes, member messages, SQLite store, pipeline, run-claim CLI. Fixture claims reach every lane.
- Broke: nothing lasting. Ruff 0.17 formats Python inside markdown, so docs/ is excluded from ruff.
- Decisions: rulings are in the plan ledger and listed in the final report (CI action versions, LF line endings, patient history for limits, ValueError for non-JSON files).
- Next: owner review of the branch, then the OCR reader plan.
- Review: a data quality reviewer and a fresh code reviewer checked the whole branch. They found money bugs (payout above the receipt total, VAT under and over paid, duplicates missed or blocking a correct resubmission, dates taken in UTC). All Critical and Important findings were fixed with a failing test first. Calls made and deferred items are in HANDOVER section 5.

## 2026-11-24: overnight build (layers 1, 2 and 3)
- Owner said before sleeping: make what we can, download data, train, build the website. Designs and plans for this night were written by Claude without owner review (marked in each doc).
- Done, layer 1 (tag layer-1): EasyOCR spike (works offline, about 6 to 10 s per receipt on CPU); synthetic receipt maker with three layouts, real Arabic, ZATCA QR and photo damage; OCR text parser that finds fields by Arabic and English labels and survives real OCR misreads; disk cache for OCR; QR plus OCR reader in run-claim; make-receipts and read-accuracy. Accuracy on 60 generated receipts is in EXPERIMENTS.md (clean photos: every field right; heavy damage breaks line items).
- Done, layer 2 code: synthetic claim sets with ten kinds of defects and known right answers (make-claims), harness metrics (run-set), Platt calibration fitted with plain Python (fit-calibration, config/calibration.yaml).
- Done, layer 3: FastAPI website (serve): member claim with photo or sample, result with read fields and payout math, self-fix resend, reviewer queue and card with saved decisions, numbers page from harness results. Checked in the browser, desktop and phone, English and Arabic.
- Broke: a long heredoc kept failing in the shell, so edits went through small scripts; uv could not change the venv while a background run held the CLI exe, so background runs and installs were kept apart.
- Process notes: tests came first for most tasks; for the receipt content module and the website, code and tests were written together (said here so the owner knows).
- Decisions: 006 (EasyOCR as an optional extra, Pillow receipts). New config values: reader, passed_check_confidence, ocr factors, paid_right_tolerance_halalas.
- Next: E6 numbers from the tune and check runs, tag layer-2, owner review.

## 2026-11-24: day 3 on the laptop
- Done: cloned to D:\dev\Reimbursement-Council, installed uv and the OCR extra. On fix/day3: fixed the OCR cache (first image of every run was saved under the wrong name and read again), made cache writes safe, added run-set --resume and per-claim timing lines, split row grouping out of the parser, added the heavy damage metric. The data-quality reviewer checked the generator and harness; fixed the false reject cost, calibration on hard rule rejects (decision 007), duplicate timing and originals, set folders and manifests, empty runs. Finished the layer 2 run and recorded E6. Tagged layer-2.
- Broke: uv could not install Python under AppData from inside the Claude desktop app (packaged app writes go to a hidden copy), so UV_PYTHON_INSTALL_DIR points to D:\dev\.uv-python. The exit code 4 crash from the desktop did not happen on the laptop; cause not found.
- Decisions: 007 (what the harness counts as cost and calibration error). calibration_enabled left off for the owner.
- Next: website changes (brainstorming started), owner decides calibration_enabled, then real receipts for E1 and E11.

## 2026-11-24: document set tasks 8 to 15 on the desktop
- Done: synced the laptop's work (PR 4 and 5). Task 8 (lane groups: member first, then a human; document_requests.py), Task 13 (upload several files, check step, submit, fix), Task 9 (prescriptions and medical reports drawn on a shared canvas), Task 10 (synthetic claims with document sets and six document defects), Task 11 (document metrics in run-set, --cross-checks switch), Task 14 (screens checked, decision 008, README), Task 15 (E12). A fresh reviewer checked Tasks 8 and 13; their Critical and Important findings were fixed with tests (the fix step had no guard, files could overwrite each other, a refused file could remove a document, choices were lost after an error).
- Broke: the first E12 run had 19 false alarms in 57 claims. Causes: provider names compared across Arabic and English, a split label word left in the patient name, and an unclear date that asked about the provider. All fixed with tests and rerun; E12 is recorded with both runs.
- Decisions: 008 (a claim is a set of documents, checked before it is sent). Upload size limit moved to config (max_upload_megabytes). Decision now records document_kinds, needs_missing and cross_checks so runs can be scored.
- Not done: saved Playwright screenshots and the Impeccable audit (neither installed in this session); defect weights are still in code; no fixed version of fixable defects.
- Next: owner review of the PR, then why self-fix is so common.

## 2026-11-25: overnight day 4 (branch overnight/day4, tags day4-a to day4-f)
- Done, part A: claim export (model, builder, JSON Schema, API route, download button, export-set; 60 of 60 and 120 of 120 valid), docs/INTEGRATION.md with a base FHIR R4 mapping, PDF and scanned input, consent step, log masking, CSS version hash, defect weights in config/synthetic.yaml, one-tap date confirm.
- Done, part B: 60 SROIE receipts (real) read with EasyOCR: total 0.317, date 0.367, name 0.35; after two parser fixes from the failure review: 0.333, 0.533, 0.35. 50 real receipts end to end: all self_fix, no wrong approval, no wrong rejection.
- Done, part C: fixed versions of fixable defects, run-set --set and --simulate-fix, fairness metric; ablations E2, E3, E5, E6, E7, E8, E9 on the synthetic check set.
- Done, part D: demo mode (five demo claims, OCR warm-up, /api/ready), Playwright end to end test (passes), 36 screenshots, accessibility pass (one color failed AA, fixed), friendly error pages.
- Done, part E: README, docs/pitch/numbers.md, docs/SUMMARY.md; data-quality and code reviews (see HANDOVER for their findings and fixes).
- Broke: the first version of the total-row fix made real totals worse (0.317 to 0.267); narrowed with real rows as tests before recording. The e2e test first hung: an unread stderr pipe blocked the server, and two threads used one EasyOCR model (now a lock). Playwright's own Chromium could not be installed: the C: drive had 445 MB free; Microsoft Edge is used instead.
- Decisions: 009 (jsonschema and pypdfium2). One-tap date confirm sends a "yes" to a person (safest). NPHIES not claimed to be FHIR (not verified).
- Next: owner reads the report at the top of HANDOVER, reviews PR 6 and this branch, frees disk space.

## 2026-11-25: core day 4 (live path, decisions, local model reader, AI case reviewer)
- Done: seconds per claim in the harness and a live-test command; docs/DEMO.md; confidence per
  field; one-tap date confirm rule; calibration on (refitted twice, last on the model reader);
  local model reader (Ollama, qwen3-vl:8b-instruct) with schema, grounding, QR, plausibility and
  two-reader checks; AI case reviewer with guard, golden set and circuit breaker (built in a
  worktree by a second agent, merged); reviewer status line on the numbers page; file splits;
  docs MODEL_SAFETY, DEMO, decision 011, INTEGRATION FHIR line, numbers, summary, README.
- Broke and fixed: the qwen3-vl:8b tag thinks and gave empty answers (use 8b-instruct); the 4096
  context cut answers; quantity 2.0 read as 20; exact grounding dropped right dates; names in
  two scripts joined; reviewer answers discarded (long reasons, whole number scores, repeated
  citations); C: ran out of space (data/ moved to D: with a junction).
- Reviews: code review (1 Critical, 6 Important) and data review (2 Critical, 7 Important).
  All Critical and most Important fixed with tests; the rest are CHECKs in HANDOVER.
- Decisions: 011 (local model reader). Defaults: reader ollama, two readers on, calibration on,
  reviewer off (benched at golden 0.85).
- Next: the owner's live photos and Tailscale; CUDA torch after freeing C:; a held-out set.
- Tags: demo-ready-1 (d736d1d), demo-ready-final.

## 2026-11-25: core day 4b (stopped at the usage limit)
- Done: privacy for realtest/, EasyOCR on the GPU, add-member, Bupa FAQ rules, real case study (450 SAR matches Bupa), real variants, generators, reviewer dev and held-out sets (held-out 0.95), HEIC, two demo claims, e2e extended.
- Left: final reruns in /d/rc-tmp/f3 not recorded, numbers and summary not updated, reviewer stays off.

## 2026-11-25: core day 4b, finished after the pause
- Done: final reruns at ac2a7e4, reviewer back on (held-out 0.95, 0 wrong approvals), staff names and cities no longer read as the patient, Urdu found by its words, damage chart, numbers, summary, model safety, startup check only for an unchecked reviewer, e2e 4 of 4.
- Tag: demo-ready-final-4.

## 2026-11-26: final pitch deck
- Done: 17 slide deck from the Tuwaiq template (python-pptx), PDF copy, QA_PREP.md with 12 judge questions, fresh English desktop screenshots of demo claims, stack icons from simple-icons (EasyOCR as a text badge).
- Broke and fixed: the reviewer's why box printed typed money in halalas; now riyals (test added).
- Decisions: sources go in speaker notes (the template's corner squares covered footers); "31 of 60" instead of a rounded percent.
- Next: rehearse with the notes (timings add to about 12 minutes), check the reviewer status line before 09:00.

## 2026-11-26: pitch deck v2
- Done: v2 deck (20 slides), PDF, presenter script from the speaker notes; left-to-right text on every slide; one large screenshot per prototype slide; Thank You spacing; speed and estimate wording.
- Decisions: the speed tile is tagged Mixed (real SROIE plus synthetic Arabic), as the owner described the 9 stand-in claims.
- Next: rehearse from the script; reviewer check before 09:00.
