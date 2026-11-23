# 003: Auto approve based on expected loss vs review cost

Date: 2026-11-23
Status: Accepted

## Context
A fixed threshold like "approve above 0.9" ignores that a 150 SAR claim and a 12,000 SAR claim carry very different risk.

## Options
- One fixed probability threshold.
- Approve when expected loss, (1 - p_good) times payout, is below the value of a reviewer's time on the claim (reviewer_time_value). No fixed amount cap; a big claim needs a higher p_good automatically.

## Choice
The second. reviewer_time_value lives in config/decision.yaml. An always-review amount exists only as an ablation switch, off by default, because a fixed cap would send clearly fine big claims to humans.

## Trade-off
Only works if p_good is calibrated, so this depends on decision 002 and experiment E6. reviewer_time_value is a made-up number for now (CHECK). It is reviewer time, not member money. Measured against a fixed threshold in E7.

## Related reading
- Elkan, 2001, The Foundations of Cost-Sensitive Learning
- DeCCaF, 2024, learning to defer under cost and capacity constraints
