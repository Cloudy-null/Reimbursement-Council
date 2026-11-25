# A real claim, start to finish

One real Bupa Arabia reimbursement claim: an optical invoice the member sent, and Bupa's decision
on it. The member gave the project owner permission to use it for testing and for this pitch. No
name, membership, claim, invoice or VAT number, and no shop name appears here. The files stay
in realtest/ (never committed).

## The claim

- An optical shop invoice (a PDF tax invoice, mostly Arabic): a frame for 1,600 SAR and lenses
  for 150 SAR, total 1,750 SAR, VAT 0.00, paid with Tabby (a pay later service).
- An eye prescription (SPH, CYL, axis) is printed on the invoice itself.
- Treatment date 2026-07-29. Bupa received the claim on 2026-07-30.

## Bupa's decision

Claimed 1,750 SAR. Approved 450 SAR. Rejected 1,200 SAR with the reason "Member consumed Frame
sub-limit". Member contribution 100 SAR. So 1,750 - 1,200 - 100 = 450.

## What our system did

We added the member with add-member, with 600 SAR of the 1,000 SAR frame sub-limit already
used, so that 1,200 of the claim is over the sub-limit. Then we sent the PDF through the website
like a member would (live-test, commit a8dd032).

**What we read** (local model and EasyOCR together, 6.3 seconds):

| Field | Read |
|---|---|
| Treatment date | 2026-07-29 (right) |
| Total | 1,750.00 (right) |
| VAT | 0.00 (right) |
| Items | frame 1,600.00 and lenses 150.00 (right). The names are brand names, so the type came from the model and stays under the confidence floor |
| Invoice number, VAT number | found, so the invoice counts as a valid tax invoice |
| Eye test | found on the invoice, so no separate prescription was asked for |
| Proof of payment | not asked: Tabby is not treated as a credit invoice (Bupa did not hold this claim for it) |

**What we would have told the member before submit** (the check page):

- Estimated payout: 450.00 SAR of the 1750.00 SAR you paid.
- 1200.00 SAR is over your eyeglass frames limit for this year (400.00 SAR of 1000.00 SAR was
  left).
- Your share: 100.00 SAR (20 percent, at most 100.00 SAR).

**Bupa's actual result:** 450 SAR. Our estimate matches it to the riyal.

**The decision:**
- Sent today (2026-11-25), the claim is rejected for being late: 119 days after the treatment,
  over the 90 day limit. That is right.
- Decided as if sent on Bupa's received date (2026-07-30), the payout is 450.00 SAR and the claim
  goes to a person, not to automatic approval.
  - The reason: the brand-name items and the shop name were read with confidence under our
    floor, so the expected loss (98.78 SAR) is above the review cost (25 SAR).
  - Safe, but not yet straight through.

## Important

The sub-limit usage was taken from Bupa's answer, not predicted. In production it comes from
Bupa's own records of what the member already used this year.

## Rules this case added (source: Bupa Arabia claim confirmation FAQ)

- Payout excludes VAT.
- Member share 20 percent, capped at 100 SAR.
- Benefit sub-limits (frames) with usage so far.
- Optical claims need an eye test, and a prescription printed on the invoice counts.
- Other rules came from the same FAQ: tooth number for dental claims, proof of payment for
  credit invoices, a valid tax invoice, and a translation for other languages.

## Reading fixes this case found (each with a test)

- A date printed year first with slashes (2026/07/29) was not read.
- An invoice number printed before its Arabic label was not found.
- The model wrote a brand name with Persian letters (ک, ی) for Arabic ones (ك, ى), so it was
  not matched to the print.
- Brand-name items matched no service; the model now names the item type (frame, lenses, ...),
  used only under the confidence floor.
