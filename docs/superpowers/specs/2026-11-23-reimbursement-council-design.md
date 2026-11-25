# Reimbursement Council: Design

Date: 2026-11-23
Owner: Abdulrahman Aljahdali
Status: Approved by the owner on 2026-11-23
Later: the claim as a set of documents with a check step before submit is designed in 2026-11-24-document-set-design.md (from the official brief, docs/brief/project-brief.md; decision 008).

## 1. What this is and why

Reimbursement Council is a system for health insurance reimbursement claims. A member pays for treatment out of pocket, takes a photo of the receipt, and asks to be paid back. Today this flow is slow and full of friction: the member does not know if the claim will pass, a human reviews almost every claim, and the member waits days with no idea why.

We are building our own version of this flow from scratch, hackathon style, for the Solve for Bupa challenge (day 5 demo on 2026-11-26, CHECK: confirm demo date). It is not tied to Bupa's real systems. The goal is the coolest working solution we can prove with numbers.

The system looks at a claim from three sides:

1. Member side. Filing a claim should take one photo and one tap, and the member should see what will happen before they submit.
2. Automation side. Most claims should be decided automatically, with high precision and high recall, and every threshold should have a reason.
3. Reviewer side. When a human is needed, they should see everything they need on one card and decide in seconds.

Every idea in this design is treated as a hypothesis. Each one gets a switch, and we measure what turning it on changes. The day 5 story is "here is what we tried and what the numbers said."

## 2. Goals, non-goals, anti-goals

Goals
- Decide most claims automatically, with measured precision and recall on real receipts.
- Keep the human review lane as small as possible, and make each review fast.
- Every decision comes with a plain reason the member and the reviewer can read.
- Every weight, threshold and cost lives in config files, so changing them needs no code change.
- Every idea can be switched off to measure its effect (ablation).

Non-goals (not now)
- Fraud detection models. Two cheap data quality checks stay in (duplicate receipt, QR does not match printed text), everything else is later.
- SMS, push notifications, email.
- Real integration with Bupa, NPHIES, or payment systems.
- Login and accounts. Demo uses a few seeded members.

Anti-goals (failure even if it works)
- A member gets rejected because they are new, or because of nationality, gender or age. None of these are allowed as features.
- A number on a slide that was not measured by the test harness.
- A live demo that breaks if the internet is slow.
- A UI that looks like generic AI output.

## 3. Constraints

- Built mostly overnight by Claude Code, from this spec and a plan, on a Claude Pro plan. Pro has a 5 hour limit and a weekly limit shared with chat, so the build will pause. Work must be saved after every task.
- No paid AI API. The app must run fully offline with free tools. A free tier vision model (Gemini API free tier) is an optional extra behind a switch, never a requirement. Free tier data may be used by the provider to improve its products, so only synthetic or public dataset images are ever sent to it.
- No real claims data. We train and tune on synthetic data, and test on real receipts.
- Money is in SAR. Saudi receipts can be Arabic, English or both, and can have Hijri dates.
- Saudi simplified tax invoices carry a ZATCA QR code (TLV, base64) with five fields: seller name, seller VAT number, timestamp, total with VAT, VAT total. Not every receipt has one.
- The policy rules are made up but realistic. Example: claims are accepted only within 90 days of treatment (this matches Bupa Arabia's published claim form). Payouts are capped at network prices.

## 4. Approaches considered

A. One clean pipeline app (picked). One Python service, stages in order: read, check rules, council, decide, explain. One database. Three screens. Easiest to finish and test overnight. Each stage has a clean boundary, so it can be split later.

B. Event-driven pipeline. Each stage is a worker connected by a queue, plus a small warehouse for metrics. Looks most like big data engineering, but many more moving parts to break overnight, and judges cannot see the queue in a demo.

C. One AI agent with tools. A single agent calls tools and decides. Flashy, but hard to make repeatable, and it works against weighted numeric votes, calibration and measured precision.

Picked A because it gives B's design in one process and keeps every decision measurable. Owner agreed on 2026-11-23.

## 5. The pipeline

A claim moves through these stages. Each stage is its own module with a clear input and output (see docs/DATA_MODEL.md).

1. Intake. Member uploads one or more images or PDFs and picks who the claim is for.
2. Extraction. Get the fields off the documents, in this order:
   - Decode the ZATCA QR if present. Fields from the QR are marked source qr with confidence 1.0.
   - Read the rest with the reader into a fixed schema (provider, date, line items, totals, patient name, document type). Each field gets a confidence. The reader is an adapter with two versions:
     - Default, offline: open-source OCR with Arabic and English support (start with EasyOCR, PaddleOCR as an ablation), then layout and pattern rules to turn the text into fields. Confidence comes from the OCR score and from whether the field matched its expected pattern.
     - Optional: Gemini API free tier vision model returning the same schema. Switch gemini_reader_enabled, off by default.
   - Arithmetic checks: line items add up to the subtotal, VAT is 15 percent where VAT applies, subtotal plus VAT equals total. A failed check lowers the confidence of the fields involved.
   - QR versus printed text: if both exist and disagree, flag it.
3. Hard rules. Yes or no only. Run only on fields with confidence above the hard rule confidence floor in config. If a rule fails on low confidence data, the claim goes to the member as needs info instead of being rejected.
4. Council. Each member gives a score from 0 to 1, a reason, evidence pointers, and optionally a specific request for more information.
5. Decision. Combine, calibrate, compute expected loss, pick a lane.
6. Explanation. Write the member message and build the reviewer card.

### 5.1 Hard rules (veto, yes or no)

Starting list, all parameters in config/policy.yaml:
- Late: treatment date more than 90 days before submission.
- Policy inactive on the treatment date.
- Person not on the policy.
- Excluded service (exclusion list in config).
- Duplicate: the same receipt (same seller VAT number, timestamp and total, or same image hash) already submitted.
- One person per claim: documents show more than one patient.

Over-limit is not a hard rule. It becomes a partial payout.

### 5.2 The council

Each council member is a module with the same interface: it takes the claim case and returns a vote.

| Member | Looks at | Score means |
|---|---|---|
| Document checker | Field confidences, arithmetic checks, QR match, image quality | How sure we are the document is valid and read correctly |
| Coverage checker | Policy, benefit limits used so far, co-pay, network price | How sure we are of the payout amount; also computes the payout |
| Price checker | Line item prices against a reference price list | How normal the prices are |
| Case reviewer | An LLM reading the whole case summary (Gemini free tier, optional, switch case_reviewer_enabled) | Overall judgment, with a written reason. When off, the other members carry the decision |
| History member | Member tenure, past claims, provider trust | How much history supports this claim |

Guardrail for the history member: it can raise trust or push a claim toward review. It can never push a claim to rejection on its own, and a new member with no history gets a neutral score, not a low one.

Each vote can carry a request, for example "the date is unreadable, please retake the photo" or "this medicine needs a prescription, please add it". These feed the self-fix step.

### 5.3 Combining votes

- Weighted average of member scores, weights in config/decision.yaml.
- Calibration maps the combined score to p_good, the probability the claim should be paid as calculated. Fit on the labeled tuning set. Start with Platt scaling, try isotonic as an ablation.
- Disagreement is the weighted spread of member scores. High disagreement is its own signal.

### 5.4 Lanes

Inputs: p_good, disagreement, payout, reviewer_time_value, any hard rule results.

reviewer_time_value is not money the member pays. It is what a reviewer's time on one claim is worth, in SAR, plus the cost of making the member wait. It is the single knob that decides how many claims go to humans: raise it and more claims auto approve, lower it and more go to review.

1. Any hard rule fails on confident data: auto reject, with the rule as the reason.
2. Expected loss = (1 - p_good) x payout.
3. If expected loss is below reviewer_time_value and disagreement is below the disagreement limit: auto approve (full or partial payout as computed). There is no fixed amount cap. A big claim needs a much higher p_good to pass, because expected loss grows with the amount, but a big claim that is clearly fine still auto approves. An optional cap exists as a switch (always_review_amount_enabled, off by default) for an ablation.
4. Else, if p_good is low and at least one council member made a specific request, and the member has retries left (max 2): self-fix. The member chooses to upload what was asked now, or to send it to a human and wait longer.
5. Else: human review.

Outcome codes follow the FHIR ClaimResponse idea: queued, complete, partial, error, plus our lane label.

## 6. The three sides in detail

### 6.1 Member side

- Upload screen: take or pick photos, pick the patient.
- Preview screen: shows what we read (provider, date, items, total), with low confidence fields highlighted for the member to confirm or fix, and the estimated payout with a short why ("network price for this service is 300 SAR, co-pay 10 percent").
- If a hard rule will fail, the preview says so before submitting.
- Result screen: approved with amount, or a specific request (self-fix choice), or "a reviewer will look at this", or rejected with the reason.
- Must work on a phone screen and in Arabic (right to left) and English.

### 6.2 Automation side

Covered by sections 5.1 to 5.4. Every switch, weight and threshold is in config.

### 6.3 Reviewer side

- One card per claim. Left: the document image with the fields we read highlighted on it. Right: why it is here (the lane reason), each council member's score and reason, hard rule results, payout math.
- Actions: approve, approve with a different amount, reject with a reason, ask the member for something.
- The card records how long the decision took. Every human decision is stored as a labeled example.

### 6.4 Metrics page

Automation rate, precision and recall of auto approve, false reject rate, calibration error (ECE) with a reliability diagram, review count, self-fix success rate, total cost (wrong payouts plus review cost), and the ablation table. Numbers come only from the test harness.

## 7. Data plan

- Synthetic data for building and tuning. A generator creates members, policies, providers, a price list, and receipt images (Arabic, English, mixed; with and without a ZATCA QR) with known truth. It injects defects on purpose: late, inactive policy, excluded service, duplicate, over limit, overpriced, unreadable photo, QR mismatch, arithmetic error, two patients on one receipt, missing prescription, missing medical report, another patient's name on the prescription or report, a different date on the prescription or report, a member edit the QR supports, and a member edit the QR contradicts. Each claim also gets the prescription or medical report its services need (section 6.6). Fixable defects also get a fixed version, used to simulate self-fix.
- Real data for testing.
  - Extraction accuracy: public receipt datasets. ReceiptSense (Arabic and English receipts), SROIE, CORD. CHECK: licenses allow this use.
  - End to end: real receipt images from the public datasets, each paired with a synthetic claim context (member, policy, history, submission date). The document is real, so reading is tested for real; the claim context is generated, so the correct outcome is known from our policy without hand labeling. Field labels come with the datasets.
  - Real invoices the team finds online (for example medical and care home invoices) are used to make the generator's templates look realistic. Because they are copied in style, they count as synthetic, not as real test data.
- Splits: synthetic train and tune; real test is never used for tuning.
- Raw data is never committed. data/ is in .gitignore. Download and generation are scripts.

## 8. Experiments

Listed in docs/EXPERIMENTS.md. Each idea has a switch, a hypothesis, a metric and a result slot.

## 9. Build order (layers)

Each layer must leave a working demo. Tag each finished layer in git (layer-1, layer-2, ...) so any layer can be returned to.

1. Spine. Intake, QR decode, extraction with the offline reader, arithmetic checks, hard rules, data model, storage. Done when a receipt image goes in and stored fields plus hard rule results come out, with tests.
2. Decision. Council members, weighted combine, calibration, disagreement, lanes, cost-based approval. Done when the synthetic set runs end to end and produces lanes.
3. Screens. Member upload, preview, result, self-fix choice. Reviewer card. Done when a full claim can be filed and reviewed in the browser, on desktop and phone sizes.
4. Proof. Test harness, real test set runner, switches, metrics page, ablation runs. Done when docs/EXPERIMENTS.md has real numbers.

Demo safety: a demo mode replays saved results for the demo claims so the demo works with no internet.

## 10. Decided by the owner

- Hackathon framing, not tied to Bupa systems.
- Three sides: member, automation, reviewer.
- Council with weighted numeric votes; only hard rules are yes or no.
- Cost-based auto approve, using provider trust and member history.
- Self-fix choice for low scores.
- Fraud detection later.
- Train on synthetic, test on real.
- Every idea is tested by ablation.
- Git and GitHub from the start; style and design in shared .md files; use skills.
- Pro plan only, no paid API (decision 004).
- Real test data: public dataset receipts with synthetic claim context. Online invoices are mimicked for the generator only.
- UI: build from the DESIGN.md draft, owner corrects as we go.

## 11. Calls made during the builder check

These were open in the first draft. Settled here so the overnight build does not guess. Owner can change any of them.

- Starting values in config/decision.yaml, to be tuned on synthetic_tune: hard rule confidence floor 0.90, disagreement limit 0.25, reviewer_time_value 25 SAR (owner said a review costs time, not member money; this is that time in SAR), always-review cap off, self-fix max retries 2, all council weights 1.0.
- "Paid at the right amount" in metrics means the payout is within 1 SAR of the correct payout.
- Reader and model outputs are cached on disk by image hash plus reader version plus model name. Ablation reruns read the cache, so they cost nothing and give the same extraction. A prompt change bumps the prompt version.
- synthetic_tune starts at 500 claims. Grow it only after checking API cost (see CHECK on budget).
- The generator also creates claim history per member and per provider, so the history member and benefit limits used so far have something to read.
- Self-fix is simulated in the harness: for a fixable defect, the member uploads the fixed version with a probability from config (start 0.7). Unfixable cases or a "no" go to human review.
- Member messages come from fixed templates in Arabic and English, filled with values. The LLM does not write member messages, so they stay consistent and safe.
- The price checker matches line item text to service codes with simple text matching first and the vision model's suggested code second. A low match confidence lowers its score instead of guessing.

## 12. Left to the builder

- Library choices inside the stack in docs/CONVENTIONS.md, if a better one is justified in a decision record.
- Exact prompt wording for the vision model and the case reviewer.
- Internal module layout inside the layers defined in CLAUDE.md.
- Visual details inside docs/DESIGN.md tokens.

## 13. Open CHECK items

- CHECK: demo date and pitch length.
- CHECK: the second required document in the real Bupa flow (proof of payment plus what?).
- CHECK: reviewer_time_value. Owner may prefer dropping it; if so, cost-based lanes (decision 003) fall back to a fixed threshold.
- CHECK: dataset licenses.
- CHECK: owner creates a free Gemini API key if we want the optional reader and case reviewer.
