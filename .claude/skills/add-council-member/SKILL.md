---
name: add-council-member
description: Use when adding a new council member to Claims Council or changing how an existing member scores a claim.
---

# Add or change a council member

1. Read docs/superpowers/specs/2026-11-23-claims-council-design.md section 5.2 and docs/DATA_MODEL.md (Vote).
2. Write down, before coding: what the member looks at, what its score from 0 to 1 means, and what kind of request it can make for self-fix. Add a row to the council table in the spec.
3. The member lives in claims_council/core/council/<name>.py and follows the shared interface: takes the claim case, returns a Vote. No I/O inside core. If it needs a model call, the call goes through an adapter passed in.
4. The score must be a real number from 0 to 1, never a yes or no. Only hard rules are yes or no.
5. Reason text is plain English, one sentence, and points at evidence (field names or document boxes).
6. Add its weight and an on or off switch to config/decision.yaml. Default weight 1.0 until tuned.
7. Tests first (test-driven-development):
   - Clear good claim gives a high score.
   - Clear bad claim (for this member's job) gives a low score.
   - Missing or low confidence input gives a middle score and a request, not a crash.
   - Output always validates as a Vote.
8. If the member uses member history, tenure or provider trust, it must not be able to push a claim to rejection on its own, and unknown history must score neutral (0.5). Add a test for this.
9. Add an experiment row (member on vs off) to docs/EXPERIMENTS.md and run it with the run-ablation skill.
10. Make sure the reviewer card shows the new member's VoteRow.
