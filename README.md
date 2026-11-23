# Reimbursement Council

Health insurance reimbursement claims that decide themselves when it is safe, ask the member to fix what is missing, and give a human reviewer one clear card when it is not.

Built for the Solve for Bupa hackathon, November 2026. Not affiliated with or using any Bupa systems or data.

## The idea in one picture

```
 Member photo
     |
     v
 Read it ---- ZATCA QR first, then vision model, then arithmetic checks
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
Design stage. See docs/HANDOVER.md.

## Docs
- Design: docs/superpowers/specs/2026-11-23-reimbursement-council-design.md
- Conventions: docs/CONVENTIONS.md
- Data model: docs/DATA_MODEL.md
- UI design: docs/DESIGN.md
- Experiments: docs/EXPERIMENTS.md
- Decisions: docs/decisions/

## How to run
Coming with layer 1.
