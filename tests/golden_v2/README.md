# Golden set v2 for the AI case reviewer

Written on 2026-11-25. It replaces the old set in `tests/golden/`, which was used while the
prompt was changed and so no longer means anything as a check.

Each case is one JSON file in the shape `GoldenCase` in
`reimbursement_council/core/models/case_review.py`: a name, a kind, the expected answer
(`good` or `bad`), one sentence that says why, and the claim summary the reviewer reads.
Load a folder with `load_golden_set(folder)` from `reimbursement_council/adapters/golden_set.py`.

The cases follow the claim rules from the Bupa Arabia claim confirmation FAQ: optical claims
need an eye test (a prescription printed on the invoice counts), dental claims need the tooth
number, a credit (pay later) invoice needs a proof of payment, a tax invoice needs an invoice
number, a VAT number and itemized lines, documents in another language need a translation,
claims more than 90 days after treatment are rejected. The payout leaves out VAT, the member
share is 20 percent capped at 100 SAR, and a benefit sub-limit (for example frames) caps a line:
a lower payout for that reason is correct, so that case is good. Mismatches, totals that do not
add up, prices far above the network price, cosmetic services, future dates and document text
that gives orders to the reviewer are bad.

## The two folders

- `dev/`: 20 cases (7 clear good, 6 clear bad, 4 tricky, 3 injection). Use these to improve the
  reviewer's prompt. You may look at them, run them and change the prompt until they pass.
- `heldout/`: 20 different cases with the same mix. **Never use these for tuning**: not for the
  prompt, not for weights, not for thresholds, and do not read them while changing the prompt.
  Run them only to measure the final prompt. Once a prompt was tuned on them, they are burned
  and must be replaced by new cases.

No case in `heldout/` reuses the facts of a case in `dev/` (services, amounts, names, wording).

## Rules

- All data here is made up: names, providers, claim IDs and VAT numbers. No real member,
  invoice or provider.
- Changing a case changes what the check means. Write why in the commit message.
