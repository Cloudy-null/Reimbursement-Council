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
