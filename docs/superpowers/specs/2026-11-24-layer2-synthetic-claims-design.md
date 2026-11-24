# Layer 2: Synthetic claims, harness and calibration

Date: 2026-11-24
Status: Written by Claude in overnight mode (owner: "make what we can, do it"). Not reviewed yet. Choices are Claude's calls unless the main spec already made them.

## Why
Main spec section 9, layer 2 is done when the synthetic set runs end to end and produces lanes. Calibration (spec 5.3) needs a labeled tuning set, and every number on a slide must come from a harness run (CLAUDE.md). This layer makes that set, a harness that scores the pipeline on it, and fits the Platt calibration ("train").

## Goals
- A generator of synthetic claims: members, one policy, providers, history, and claims whose receipt is a generated image, each with a known right answer (should we pay, how much).
- Defects injected on purpose with known effect: late, inactive policy, patient not covered, excluded service, duplicate receipt, over the benefit limit, overpriced, service not on the price list, unreadable photo, tampered total.
- A harness command that runs a set through the real pipeline and reports the main metrics in EXPERIMENTS.md: automation rate, auto approve precision, payable recall, false reject rate, reviews per 1000, calibration error (ECE), total cost.
- Platt calibration fitted on the tune set with numpy (no new library), saved to config/calibration.yaml, used when calibration_enabled is true.

## Non-goals
- Tuning council weights (E4) and the ablation runner. Later, with the run-ablation skill.
- Real receipts. Still a CHECK on dataset licenses.

## Right answer (ground truth), Claude's call
- should_pay is false when the claim breaks a hard rule (late, inactive, not covered, excluded, duplicate). Otherwise true.
- correct_payout is the payout our policy gives on the true receipt values (network cap, co-pay, limits, VAT on the covered part). Items not on the price list pay nothing. This uses our own payout code on perfect data as the oracle; it measures reading and deciding, not the payout rules themselves.
- "Paid right" means paid within 1 SAR of correct_payout (main spec section 11).
- A label for calibration is 1 when should_pay is true and the calculated payout is right, else 0.

## Design
- `reimbursement_council/synthetic/claims.py` (pure): `make_claim_set(seed, count, settings) -> SyntheticSet` with reference data and cases. Each case has the claim, its receipt content, the damage name, its defects and its ground truth.
- The CLI `make-claims` draws each receipt and writes a folder: reference.json, one .claim.json, .png and .truth.json per case, so `run-claim` can also run any single case.
- `reimbursement_council/synthetic/metrics.py` (pure): metrics from (decision, truth) pairs, including ECE with 10 bins.
- `reimbursement_council/core/decision/calibration.py` (pure): fit and apply Platt scaling with numpy Newton steps.
- CLI `run-set` runs every case through process_claim with a fresh store per run (duplicates are found inside the set), writes results.json and prints the metrics. `fit-calibration` fits Platt on a run's results and writes config/calibration.yaml.
- Sets: synthetic_tune (seed 1) for fitting; synthetic_check (seed 2) to report numbers after fitting. Both use the real EasyOCR reader with the disk cache.
