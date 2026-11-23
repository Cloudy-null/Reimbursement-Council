---
name: add-defect-type
description: Use when adding a new kind of bad or tricky claim to the Claims Council synthetic data generator, or when a real test receipt shows a failure the synthetic data does not cover.
---

# Add a defect type to the synthetic data

1. Name the defect in snake_case and describe it in one sentence: what is wrong with the claim and what the correct outcome is (reject, partial payout, self-fix, human review).
2. Add it to the defects list under GroundTruth in docs/DATA_MODEL.md and to the defect list in the spec, section 7.
3. Decide if it is fixable by the member. If yes, the generator must also create the fixed version (for example a clear photo, or the missing prescription) so self-fix can be simulated.
4. Implement it in the generator with a config knob for how often it appears. Keep the base claim realistic: only the defect should differ.
5. Tests:
   - Generated claims with this defect carry the right GroundTruth label.
   - The defect actually appears in the image or data (for image defects, check the rendered file, not just the label).
   - Claims without the defect are unchanged.
6. Run the harness on synthetic_tune and check which lane these claims land in. If they land in the wrong lane, that is a finding: write it in HANDOVER and EXPERIMENTS.md, do not quietly tune it away.
7. If the defect came from a real receipt failure, link the real example (anonymized ID only) in the SESSION_LOG entry.
