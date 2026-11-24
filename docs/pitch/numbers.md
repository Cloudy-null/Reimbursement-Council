# Headline numbers

Every number here came from the test harness. Each one has the command, the commit and the test
set, and one plain sentence on what it means. Synthetic means made by our generator with known
right answers; real means real receipt scans (SROIE). Nothing here was measured on Bupa data.
Full results: docs/EXPERIMENTS.md.

## Safety: wrong approvals and wrong rejections

| Number | Test set | Commit | Command |
|---|---|---|---|
| 1.0 auto approve precision, 0 false rejects, in all 9 ablation runs | synthetic check, 60 claims with documents (seed 12) | 95745da | `run-set data/sets/abl/check --reader easyocr` (plus one `--set` per ablation) |
| 0 wrong auto approves and 0 false rejects on 50 real receipts | real_e2e: 50 SROIE scans in a synthetic claim context | 79f9aac | `run-set data/sets/real_e2e --reader easyocr` |
| 0 wrong auto approves on badly damaged photos (5 of 5 sent to self-fix) | synthetic check, 60 | 95745da | `run-set data/sets/abl/check --reader easyocr` |

What it means: when the system approves, it was right every time we measured, and it never
rejected a claim that should have been paid. On real documents it could not read well, it asked
the member instead of guessing.

## Asking the member first (self-fix)

| Number | Test set | Commit | Command |
|---|---|---|---|
| With the member's fix: 10 of 60 claims reach a person; with self-fix off: 37 of 60 | synthetic check, 60 | 95745da | `run-set ... --simulate-fix` and `--set self_fix_enabled=false --simulate-fix` |
| 5 of 8 claims fixed by the member are then paid right with no person | synthetic check, 60 | 95745da | `run-set ... --simulate-fix` |
| Review cost 250 SAR with self-fix, 925 SAR without (60 claims, 25 SAR per review) | synthetic check, 60 | 95745da | same two runs |

What it means: telling the member exactly what to add or fix keeps most claims away from a
person, and many of them then finish on their own.

## Documents that do not agree (cross checks, E12)

| Number | Test set | Commit | Command |
|---|---|---|---|
| 3 of 3 patient or date mismatches caught, 0 false alarms in 57 | synthetic check, 60 | 0deac30 | `run-set data/sets/docs/check --reader easyocr --cross-checks on` vs `off` |
| 7 of 7 caught, 2 false alarms in 113 | synthetic tune, 120 | 0deac30 | same on `data/sets/docs/tune` |
| 1 wrong auto approve avoided in each set (another patient's name on the report) | both | 0deac30 | same |

What it means: a medical report for another person, or from another day, is caught before money
moves. The two false alarms came from OCR misreading an Arabic name.

## Structured data for the claims system (deliverable 2)

| Number | Test set | Commit | Command |
|---|---|---|---|
| 60 of 60 claim exports valid against the published JSON Schema | synthetic check, 60 | 55431ba | `export-set data/sets/docs/check --reader easyocr --out outputs/export` |
| 120 of 120 valid | synthetic tune, 120 | 55431ba | same on `data/sets/docs/tune` |

What it means: every decided claim comes out as the same machine-readable structure, with money
in whole halalas and a confidence on every value (docs/INTEGRATION.md).

## Reading real receipts (E1, E11)

| Number | Test set | Commit | Command |
|---|---|---|---|
| Total right on 0.333, date on 0.533, shop name on 0.35 | real_extraction: 60 SROIE scans, EasyOCR | 79f9aac | `read-sroie data/real/sroie --reader easyocr` |
| Before two parser fixes: total 0.317, date 0.367, name 0.35 | same | 6943ee7 | same |
| On our own synthetic receipts: total 0.967 | synthetic, 60 receipts (seed 1) | f087ab9 | `read-accuracy data/receipts/eval_s1 --reader easyocr` |

What it means: real scans are much harder than our synthetic ones. These receipts have no ZATCA
QR code, which Saudi receipts carry and which we read first. The synthetic reading number must
not be shown as real accuracy.

## Calibration (E6)

| Number | Test set | Commit | Command |
|---|---|---|---|
| Calibration error (ECE) 0.202 without, 0.065 with | synthetic check, 60 | 95745da | `run-set ... --calibration on` |

What it means: with calibration, "90 percent sure" means about 90 percent right. It is still off
by default; the owner decides.

## Website quality

| Number | Test | Commit | Command |
|---|---|---|---|
| The full demo path passes in a real browser (2 of 2 tests, 84 s, real OCR) | tests/e2e/test_demo_path.py | 82f3413 | `uv run pytest -m e2e` |
| Every text color meets WCAG AA contrast (4.5 to 1) in light and dark | tests/web/test_accessibility.py | 0f26447 | `uv run pytest tests/web/test_accessibility.py` |
