# Q&A prep: the 12 most likely judge questions

Short, honest answers. Every number comes from docs/pitch/numbers.md, web/headline.json,
docs/pitch/real_claim_case.md, docs/EXPERIMENTS.md or docs/MODEL_SAFETY.md, with its test set.
Say "synthetic" or "real" every time you give a number.

## 1. How accurate is it on weak or real scans?

- On 60 real receipts (SROIE, Malaysian shop receipts), the total was read right on 0.6167 of
  them with our AI reader, against 0.3333 with OCR alone. Date 0.6, shop name 0.5167. (Real,
  n=60, commit ac2a7e4.)
- When a reading is weak, we do not guess. The member is asked to confirm or retake the photo.
- We damaged 150 photos in 10 ways at 3 strengths: 0 wrong approvals at every level. Worse
  photos go to the member or a person. (Synthetic, n=150.)

## 2. Where does the data go? What about privacy?

- Nowhere. The AI model runs on our own GPU through Ollama. No document leaves the machine and
  there is no paid AI API.
- The member gives consent before any upload. Logs mask names, emails, phone numbers and long
  numbers. The real claim was never committed to GitHub (docs/MODEL_SAFETY.md).

## 3. How would it connect to Bupa's systems?

- Every claim leaves as structured JSON, checked against a JSON Schema: 60 of 60 exports valid
  (Synthetic, n=60).
- The export maps field by field to FHIR R4, the standard NPHIES is built on
  (docs/INTEGRATION.md).
- To go live it needs Bupa's real benefit tables and member records. Rules and limits are config
  files, not code.

## 4. What if the AI is wrong?

- The AI only reads and gives an opinion. It never approves a claim on its own.
- Every value it reads must be on the page or in the QR code, or it is dropped. On real receipts
  0.2885 of the model's values were dropped this way (an upper bound: most were right values that
  OCR misread). (Real, n=60.)
- The QR code wins over the model. Totals must add up.
- Result: 21 of 21 automatic approvals were right (Synthetic, n=21), and 0 wrong approvals on 50
  real receipts (Real, n=50).

## 5. What does it cost to run?

- No per-claim fee: no paid API. It runs on one consumer GPU (an RTX 4070 Super).
- About 8 seconds per claim through the website: 8.057 s mean, 7.122 s median (Synthetic
  stand-in claims, n=9, commit 09b4717). The AI reviewer adds 1.8 s per claim.
- We did not price servers. That is a question for Bupa's own infrastructure team.

## 6. How does it scale?

- Honest answer: we measured one PC, one claim at a time. We did not run a load test.
- The work is one claim at a time with no shared state, so more claims means more machines or
  more GPUs side by side. On one GPU the OCR and the model take turns.

## 7. Only 69 percent of your flags were real problems. Why so many false flags?

- Problem precision is 0.6923: 27 of 39 flagged claims had a real problem (Synthetic, n=39). We
  caught 27 of 30 problems (recall 0.9).
- That is a choice. A false flag costs the member a confirm click or a person a short review. A
  wrong approval costs money. We tuned for 0 wrong approvals.
- The cost: only 21 of 50 payable claims (0.42) were approved with no person.

## 8. Is it all synthetic data?

- Synthetic data has known right answers, so it gives precision and recall: check set of 60
  claims, 31 of 60 decided with no person.
- Real data shows safety: 50 real receipts end to end, 0 wrong approvals and 0 wrong rejections.
  60 real receipts for reading accuracy. One real Bupa claim.
- On real receipts we cannot compute precision and recall: their labels only say they are real,
  and the right payout is unknown.

## 9. You have one real Bupa claim. Is that enough?

- No, and we say so. It is one case study (Real, n=1), used with the member's consent: we said
  450 SAR before send, Bupa paid 450 SAR.
- The frame sub-limit usage came from Bupa's answer. In production it comes from Bupa's records.
- Next step: test on Bupa's historical claims.

## 10. Why did the real claim go to a person and not straight through?

- The item names were brand names and the shop name was read with confidence under our floor. The
  expected loss (98.78 SAR) was above the review cost (25 SAR), so a person checks it.
- Safe, but not yet straight through. Better item matching would fix it.

## 11. Arabic? Other languages?

- Every screen is in Arabic and English. Synthetic Arabic and English receipts: total 1.000,
  provider 0.950, patient 0.900 (Synthetic, n=60).
- A French or Urdu document gets a translation request: 6 of 6 each, and none of 30 Arabic,
  English, mixed, Hijri or Arabic-Indic receipts (Synthetic).
- Known limit: OCR garbles Arabic-Indic digits, so the model's reading cannot be confirmed and the
  member is asked.

## 12. How do you know the AI reviewer is any good?

- It scored 0.95 (19 of 20) on a held-out test set that was never used to improve the prompt.
  The prompt was improved on a separate dev set only (Synthetic, n=20).
- It passed every prompt injection case. It can only move a claim to a person.
- It is watched by health checks and benched automatically if it drifts. Status at the demo:
  healthy, golden set 0.95.
