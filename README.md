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
Layers 1 to 3 of the spec are built on synthetic data: receipt photos are read offline with EasyOCR (QR first), claims are decided by hard rules, a council and cost-based lanes, and a website shows the member flow, the reviewer card and the measured numbers. Nothing has been measured on real claims yet. See docs/HANDOVER.md.

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
Needs [uv](https://docs.astral.sh/uv/). It installs Python 3.12 by itself. The `ocr` extra adds EasyOCR and PyTorch (a large download); without it, images are read by their QR code only.

```
uv sync --extra ocr
uv run pytest
uv run reimbursement-council serve
```

Then open http://127.0.0.1:8000. Pick a person and a sample receipt, or upload a photo. The first read loads the OCR model (up to a minute). `--reader qr_only` starts the site without OCR.

Other commands:
- `run-claim CLAIM --reference REF`: decide one claim file and print the result.
- `make-receipts --count 60 --seed 1 --out data/receipts/eval` and `read-accuracy data/receipts/eval`: measure how well receipts are read.
- `make-claims --count 120 --seed 11 --out data/sets/tune`, `run-set data/sets/tune` and `fit-calibration data/sets/tune/results.json`: run a synthetic claim set through the pipeline, score it, and fit the calibration.

Generated data and caches live in data/, which is not committed.
