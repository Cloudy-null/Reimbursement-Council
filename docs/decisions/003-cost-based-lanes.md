# 003: Auto approve based on expected loss vs review cost

Date: 2026-11-23
Status: Accepted

## Context
A fixed threshold like "approve above 0.9" ignores that a 150 SAR claim and a 12,000 SAR claim carry very different risk.

## Options
- One fixed probability threshold.
- Approve when expected loss, (1 - p_good) times payout, is below the cost of a human review, with an always-review amount on top.

## Choice
The second. review_cost and the always-review amount live in config/decision.yaml.

## Trade-off
Only works if p_good is calibrated, so this depends on decision 002 and experiment E6. review_cost is a made-up number for now (CHECK). Measured against a fixed threshold in E7.

## Related reading
- Elkan, 2001, The Foundations of Cost-Sensitive Learning
- DeCCaF, 2024, learning to defer under cost and capacity constraints
