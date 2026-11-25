# Headline numbers

Every number here came from the test harness at one commit, **ac2a7e4** (2026-11-25), unless a
row says otherwise. The commands are in docs/EXPERIMENTS.md ("FINAL CHECK of core day 4b").
Synthetic means made by our generator with known right answers; real-derived synthetic means
synthetic claims that copy the layout of one real Bupa claim; real means real scans. One real
Bupa claim is used as a case study (docs/pitch/real_claim_case.md) with the member's consent.

Defaults: the local model reader (qwen3-vl:8b-instruct on our own PC, EasyOCR on the GPU) checked
by EasyOCR, calibration on, the Bupa FAQ rules on, and the AI case reviewer on.

## Precision and recall (SYNTHETIC check set, 60 claims, commit 120febe)

Command: `run-set data/sets/abl/check_v2` (results y_check.json), measures from
`evaluation/flag_metrics.py`. A claim "has a problem" when the generator's truth lists a defect;
"flagged" means asked the member, sent to a person, or rejected.

| Measure | Value | Count | Meaning |
|---|---|---|---|
| Approval precision | 1.0 | 21 of 21 approved | every automatic approval should be paid, at that amount |
| Payable recall | 0.42 | 21 of 50 payable | share of payable claims approved with no person |
| Problem precision | 0.6923 | 27 of 39 flagged | of the claims we stopped, the share with a real problem |
| Problem recall | 0.9 | 27 of 30 with a problem | the other 3 were over a limit or overpriced and were paid the right lower amount |

Real e2e (50 SROIE scans): not computed. Its labels only say each claim is a real receipt and
the right payout is unknown, so these four measures would not mean anything there.

## The real claim

| Number | Source |
|---|---|
| Our estimate before submit: 450 SAR. Bupa paid 450 SAR (1,750 - 1,200 over the frame sub-limit - 100 member share) | real_claim_case.md, commit a8dd032 |
| Read in 6.3 seconds: date, total, VAT, both items, invoice and VAT numbers and the eye test right | same |

The frame sub-limit usage was taken from Bupa's answer, not predicted. In production it comes from
Bupa's records.

## Safety: wrong approvals and wrong rejections

| Number | Test set |
|---|---|
| Auto approve precision 1.0 and 0 false rejects with every switch, except arithmetic checks off (precision 0.9545) | synthetic check, 60 claims |
| 0 wrong approvals at every damage level: blur, motion blur, noise, JPEG, low resolution, shadow, glare, tilt, rotation, crumpled paper, each at levels 1, 3, 5 | real-derived synthetic optical, 150 damaged claims |
| 0 wrong approvals and 0 false rejects | real e2e, 50 SROIE scans |

As photos get worse, claims go to the member for a retake or to a person, never to a wrong
approval (docs/pitch/damage_chart.svg).

## Reading documents

| Number | Test set |
|---|---|
| Total right on 0.6167 of real receipts (EasyOCR alone 0.3333); date 0.6 (0.5333); shop name 0.5167 (0.35) | real SROIE, 60 scans |
| Synthetic Arabic and English receipts: total 1.000, provider 0.950, patient 0.900 | synthetic, 60 receipts |
| Values the model returned that are found nowhere on the document: 0.2885 on real receipts (an upper bound: most are right values EasyOCR misread), all dropped | real SROIE |
| A document in French or Urdu gets a translation request: 6 of 6 each; none of 30 Arabic, English, mixed, Hijri or Arabic-Indic receipts | synthetic languages |

## Automation and the member

| Number | Test set |
|---|---|
| 0.5 of claims decided with no person (EasyOCR only: 0.35) | synthetic check, 60 |
| With the member's fix: 0.6 decided with no person; 6 of 8 fixed claims then paid right | same, `--simulate-fix` |
| Reviews per 1,000 claims: 183.3 with self-fix, 483.3 without | same |
| Documents that disagree (another patient, another date): 3 of 3 caught, 0 false alarms in 57 | same |

## The AI case reviewer

| Number | Test set |
|---|---|
| Held-out golden score 0.95 (19 of 20), run once; the prompt was improved on a separate dev set only | tests/golden_v2 |
| On: precision 1.0, 0 wrong approvals, 1 claim moved to a person, 0 answers thrown out; 1.8 seconds more per claim | synthetic check, 60 |

It can only send a claim to a person, never approve one, and it is benched automatically when a
health check fails.

## Speed

| Number | Test set |
|---|---|
| 8.057 seconds per claim through the website (median 7.122), from 13.855 before EasyOCR moved to the GPU | stand-in live set, 9 claims (commit 09b4717) |

## Structured data (deliverable 2)

| Number | Test set |
|---|---|
| 60 of 60 claim exports valid against the JSON Schema, with sub-limit, member share, VAT and rule sources | synthetic check, 60 |

## Known limits (honest)

- Real SROIE receipts are Malaysian shop receipts: they show safety, not automation.
- Arabic-Indic digits: the OCR garbles them, so the model's right reading cannot be confirmed and
  the member is asked (0 of 6 totals read).
- A photo turned 90 degrees is not read; the member is asked for a new photo.
- Optical set: 0.45 of claims still raise a false patient-name alarm (the member is asked).
