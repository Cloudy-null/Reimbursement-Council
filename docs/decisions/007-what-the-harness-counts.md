# 007: What the harness counts as cost and as calibration error

Date: 2026-11-24
Status: Accepted by Claude while fixing the day 3 data review; owner to review.

## Context
The data-quality reviewer found two ways the harness scored runs wrong, before any E6 number was recorded.
- Total cost counted wrong money only on auto approved claims. A payable claim that was auto rejected cost nothing, so rejecting every claim gave a total cost of 0 SAR. EXPERIMENTS.md says total cost is "wrong payouts plus review cost", and not paying a payable claim is a wrong payout.
- ECE and the Platt fit used every claim. The council never sees the hard rules, so a late or not covered claim can have a council score of 0.93 while its right answer is "do not pay". With a perfect reader on seed 11, the 24 claims a hard rule rejected had a mean p_good of 0.931. ECE was 0.1731 with them and 0.0741 without them, and a Platt fit on all claims mapped a raw 0.933 down to 0.798. That would push claims that are paid right out of auto approve.

## Options
- Cost: keep counting only auto approved claims, or also count the right payout of every payable claim that was auto rejected.
- Calibration: fit and score on every claim; fit and score only on claims no hard rule rejected; or set p_good to 0 in the pipeline when a hard rule fails.

## Choice
- A false reject costs the payout that should have been made. Self fix and human review add no wrong money (review adds review cost). Self fix has no cost yet; see CHECK in HANDOVER.
- ECE and fit-calibration use only claims where no hard rule failed. Each run row now has hard_rule_failed. calibration.yaml says how many claims were left out.
- p_good in the pipeline is not changed. A hard rule fail already sends the claim to auto_reject before p_good is looked at.

## Trade-off
ECE now measures the council score only on the claims where it decides the lane, not on every claim. A run's ECE and the ECE of an older run are not comparable. No E6 number had been recorded before this change.
