---
name: run-ablation
description: Use whenever you measure the effect of a switch, weight, threshold or council member in Reimbursement Council, or when asked to fill in a result in docs/EXPERIMENTS.md.
---

# Run an ablation

Goal: a fair before and after number for one idea, that anyone can reproduce.

1. Find the experiment row in docs/EXPERIMENTS.md. If it is not there, add a row first (ID, idea, switch, hypothesis, main metric) and write the hypothesis before running anything.
2. Check the switch exists in config (today the switches are in config/decision.yaml; config/experiments.yaml for named switch sets is planned, not built yet) and is read from config, not hardcoded. If not, add it and a test that proves it changes behavior.
3. Make sure the working tree is clean and commit any change first. Note the commit hash.
4. Pick the test set:
   - Tuning a weight or threshold: synthetic_tune only.
   - Final number for slides or docs: real_e2e (or real_extraction for extraction ideas). Never tune on these.
5. Run the harness twice with the same seed and the same data: switch off, then switch on. Change only that one switch.
6. Record all main metrics from EXPERIMENTS.md for both runs, not just the one that looks good.
7. Sanity check before writing anything:
   - Did both runs process the same number of claims?
   - Is any metric impossible (precision above 1, empty test set)?
   - If the change is surprisingly big, find out why before recording it (use systematic-debugging).
8. Append a results block to docs/EXPERIMENTS.md with date, commit, exact command, test set, both metric sets, and one or two plain sentences on what it means. Update the Result column in the table.
9. If the result changes a decision (for example, turn an idea off), write docs/decisions/NNN-title.md.

A result where the idea did not help is still a result. Record it the same way.
