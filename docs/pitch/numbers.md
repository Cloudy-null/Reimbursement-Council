# Headline numbers

Every number here came from the test harness at one commit, **38cc89d** (2026-11-25), unless a
row says otherwise. Each row has its test set and command; the full list is the "FINAL CHECK"
block in docs/EXPERIMENTS.md. Synthetic means made by our generator with known right answers;
real means real receipt scans (SROIE, Malaysian shops). Nothing was measured on Bupa data.

Defaults at that commit: the local model reader (qwen3-vl:8b-instruct on our own PC) checked by
EasyOCR (two readers), calibration on, the AI case reviewer off.

## Safety: wrong approvals and wrong rejections

| Number | Test set | Command |
|---|---|---|
| Auto approve precision 1.0 and 0 false rejects in every run at this commit except one (arithmetic checks off) | synthetic check, 60 claims (seed 12) | `run-set data/sets/abl/check` plus one switch each |
| With the arithmetic checks off, precision falls to 0.8889 (wrong approvals appear) | same | `--set arithmetic_checks_enabled=false` |
| 0 wrong approvals and 0 false rejects on 50 real receipts | real_e2e, 50 SROIE scans in a synthetic claim context | `run-set data/sets/real_e2e` |

What it means: when the system approves, it was right every time we measured, and it never
rejected a claim that should have been paid. The arithmetic checks are what keep it that way.

## Reading documents with the local model

| Number | Test set | Command |
|---|---|---|
| Total right on 0.6167 of real receipts, from 0.3333 with EasyOCR alone | real_extraction, 60 SROIE scans | `read-sroie data/real/sroie --reader ollama` vs `--reader easyocr` |
| Date 0.6 (from 0.5333), shop name 0.5167 (from 0.35) | same | same |
| Synthetic Arabic and English receipts: total 1.000 (from 0.967), patient name 0.917 (from 0.800), provider 0.950 (from 0.900) | synthetic, 60 receipts (seed 1) | `read-accuracy data/receipts/eval_s1 --reader ollama` |
| Values the model returned that are printed nowhere: 0.2865 on real receipts, 0.05 on synthetic ones; all dropped | same two sets | same |
| 0 of 78 QR comparisons disagreed (synthetic) | synthetic, 60 receipts | same |

What it means: the local model reads much better than OCR alone, and nothing it says is used
until it is found on the document or the QR code. The 0.2865 is an upper bound: most of those
values are right but EasyOCR misread them, so they could not be confirmed. Real scans are harder
than synthetic ones; the synthetic numbers must not be shown as real accuracy.

## Automation (synthetic claims)

| Number | Test set | Command |
|---|---|---|
| 0.5667 of claims decided with no person, from 0.3833 with EasyOCR alone | synthetic check, 60 | `run-set data/sets/abl/check` vs `--reader easyocr` |
| With the member's fix: none left waiting; 23 of 60 reach a person, against 26 with self-fix off; 5 of 8 fixed claims then paid right with no person | same | `--simulate-fix` and `--set self_fix_enabled=false --simulate-fix` |

What it means: the model reader takes many claims off the member and the claims team, at the
same safety. On real receipts automation stays 0: those Malaysian shop receipts sell items that
are not on our price list, so the set can show safety but never automation.

## Documents that do not agree (cross checks, E12)

| Number | Test set | Command |
|---|---|---|
| 3 of 3 patient or date mismatches caught, 0 false alarms in 57 | synthetic check, 60 | `run-set data/sets/docs/check --cross-checks on` vs `off` |
| 7 of 7 caught, 2 false alarms in 113 | synthetic tune, 120 | same on `data/sets/docs/tune` |

## Structured data for the claims system (deliverable 2)

| Number | Test set | Command |
|---|---|---|
| 60 of 60 and 120 of 120 claim exports valid against the published JSON Schema | synthetic check and tune | `export-set data/sets/docs/check` and `tune` |

## Speed

| Number | Test set | Command |
|---|---|---|
| 13.855 seconds per claim through the website (median 13.31, max 23.193), new photos, model and EasyOCR reading at the same time | stand-in live set: 9 claims, 4 real SROIE scans and 5 synthetic Arabic documents (not the owner's photos) | `live-test data/live_standin_final` |
| About 4 seconds of model time per receipt (mean 4.232) | real_extraction, 60 | `read-sroie` at dcecc4d (before answers were cached) |

EasyOCR runs on the CPU on this PC and is the slower of the two readers (the model answered in
about 3 to 5 seconds in the server log). The GPU version of torch would cut that, after disk
space is freed (HANDOVER CHECK).

## Calibration (E6)

| Number | Test set | Command |
|---|---|---|
| ECE 0.1059 without, 0.0991 with; precision 1.0 and 0 false rejects both ways | synthetic check, 60 | `run-set ... --calibration off` vs default |

## The AI case reviewer and its safety net

| Number | Test set | Command |
|---|---|---|
| Golden set pass rate 0.85 (17 of 20), under the 0.90 limit: benched automatically, so it is off | tests/golden, 20 cases | `check-reviewer` at 6b60397 |
| Every prompt injection case and every clear case passed; 3 tricky bad claims missed | same | same |
| Forced on: 1 more claim to a person, precision 1.0 both ways, 2.7 s more per claim | synthetic check, 60 | `--set members.case_reviewer.enabled=true` |

What it means: the reviewer can only send a claim to a person, never approve one, and a health
check benches it when it is not good enough. It is benched now, and that is the safety net
working.

## Website quality

| Number | Test | Command |
|---|---|---|
| The full demo path passes in a real browser (2 of 2 tests, 81 s, real reading) | tests/e2e/test_demo_path.py | `uv run pytest -m e2e` |
| Every text color meets WCAG AA contrast | tests/web/test_accessibility.py | `uv run pytest tests/web/test_accessibility.py` |
