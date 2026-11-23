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
