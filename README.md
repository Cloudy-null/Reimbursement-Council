# Reimbursement Council

Health insurance reimbursement claims that decide themselves when it is safe, ask the member to fix what is missing, and give a human reviewer one clear card when it is not.

Built for the Solve for Bupa hackathon, November 2026. Not affiliated with or using any Bupa systems or data.

## The idea in one picture

```
 Member photo
     |
     v
 Read it ---- ZATCA QR first, then offline reader, then arithmetic checks
     |
     v
 Hard rules -- yes or no veto (late, not covered, duplicate, ...)
     |
     v
 Council ----- document, coverage, price, case reviewer, history
     |         each gives a weighted score from 0 to 1
     v
 Decide ------ calibrated score, disagreement, expected loss vs review cost
     |
     +--> auto approve (full or partial)
     +--> self-fix: member adds the exact missing thing, or picks a human
     +--> human review: one card with all the evidence
     +--> auto reject: only on a confident hard rule
```

## Status
Walking skeleton: every pipeline stage runs in Python with tests, on hand-made synthetic claims. Text reading (OCR), screens and the test harness come next. See docs/HANDOVER.md.

## Code map
```
config/                   every weight, threshold, cost, switch and member message
reimbursement_council/
  config/                 load and validate config/*.yaml and env vars
  core/                   pure logic: money, ZATCA QR, extraction, rules, payout,
                          council members, combine and lanes, member message
  adapters/               readers, QR from images, SQLite store, file loading
  pipeline/               process_claim wires the stages together
  cli/                    run-claim command
tests/                    mirrors the package; tests/fixtures holds synthetic claims
```

## Docs
- Design: docs/superpowers/specs/2026-11-23-reimbursement-council-design.md
- Conventions: docs/CONVENTIONS.md
- Data model: docs/DATA_MODEL.md
- UI design: docs/DESIGN.md
- Experiments: docs/EXPERIMENTS.md
- Decisions: docs/decisions/

## How to run
Needs [uv](https://docs.astral.sh/uv/). It installs Python 3.12 by itself.

```
uv sync
uv run pytest
uv run reimbursement-council run-claim tests/fixtures/claims/clean.claim.json --reference tests/fixtures/reference.json
```

The last command prints the lane, the payout, the reason and the member message in English and Arabic. Try the other files in tests/fixtures/claims/ (late, blurry_date, overpriced, unlisted_service, prescription_only) to see each lane. Decisions are stored in data/claims.sqlite, which is not committed.
