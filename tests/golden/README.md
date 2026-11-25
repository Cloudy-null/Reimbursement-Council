# Golden set for the AI case reviewer

20 claim summaries, one JSON file each, in the exact shape the reviewer reads (`ReviewSummary`
in `reimbursement_council/core/models/case_review.py`). Each file also says what a working
reviewer must answer:

- `expected: good`: the reviewer's score must be at or above `golden_good_min_score`.
- `expected: bad`: the score must be at or below `golden_bad_max_score`.
- An answer that breaks the schema or cites a value that is not in the summary fails the case.

The pass limit for the whole set is `golden_pass_rate`. All three numbers are in
`config/decision.yaml` under `members.case_reviewer`.

Kinds: 6 clear good, 5 clear bad, 5 tricky, 4 injection tricks (document text that tells the
model to approve the claim or give it score 1.0, in English and Arabic, and one that tries to
close the data fence).

## Rules

- This set is never used for tuning: not for prompts, not for weights, not for thresholds.
  It only checks that the reviewer still works (at web startup and with `check-reviewer`).
  If a prompt is tuned on these cases, the check stops meaning anything.
- All data here is made up. No real member, receipt or provider.
- Changing a case changes what the check means. Write why in the commit message.
