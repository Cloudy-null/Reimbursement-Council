# Experiments

Every idea is a hypothesis with a switch. We turn it off, measure, turn it on, measure. Only numbers produced by the test harness go here, with the command and commit. Use the run-ablation skill.

## Main metrics (same for every experiment)
- Automation rate: share of claims decided with no human.
- Auto approve precision: of auto approved claims, share that truly should be paid at that amount.
- Payable recall: of claims that should be paid, share that were auto approved.
- False reject rate: share of payable claims that got auto rejected. Must stay near zero.
- Calibration error (ECE), on claims no hard rule rejected (decision 007).
- Human reviews per 1000 claims.
- Total cost: wrong payouts plus review cost, in SAR. A false reject counts as the payout that should have been made (decision 007).
- Heavy damage lanes: for claims whose photo has heavy or unreadable damage, the share that went to self_fix, auto_approve, auto_reject and human_review, and the count of wrong auto approves among them. Wrong auto approves on unreadable photos is the number we care about most; it should be 0.
- Extraction field accuracy (for extraction experiments).
- Document metrics (synthetic/document_metrics.py, in every run-set output since Task 11). Each is a share with its group size next to it (name_count), so a 0.0 from an empty group is not a bad result.
  - document_kind_accuracy: of all documents, share whose found type equals the true type (strict: a billing document read as receipt when it is an invoice counts as wrong).
  - missing_document_recall: of the required groups that are truly missing, share the pipeline flagged.
  - missing_document_precision: of the groups the pipeline flagged as missing, share that are truly missing.
  - cross_check_catch_rate: of claims with a patient or date mismatch put in on purpose, share where a cross check failed.
  - cross_check_false_alarm_rate: of the other claims, share where a cross check failed anyway.
  - expected_lane_match: of claims whose document defect decides the lane (missing document, mismatch, contradicting edit), share that went to that lane.

## Test sets
- synthetic_tune: generated, used for tuning weights and calibration. Never used for final numbers.
- real_extraction: ReceiptSense, SROIE, CORD samples. Extraction accuracy only.
- real_e2e: real receipt images from the public datasets, each with a synthetic claim context so the correct outcome is known. Final numbers.

## Experiment list

| ID | Idea | Switch | Hypothesis | Main metric | Result |
|---|---|---|---|---|---|
| E1 | Read the ZATCA QR first | qr_first_enabled | QR first improves accuracy on total, date and VAT number | Field accuracy | Real SROIE (60, EasyOCR, no QR on them): total 0.333, date 0.533, provider 0.35 at 79f9aac. QR first not measured on real receipts yet |
| E2 | Arithmetic checks as confidence | arithmetic_checks_enabled | Catches misread totals and lowers wrong approvals | Auto approve precision | Off: correct rejects 0.70 to 0.40 (3 excluded-service claims ask the member instead), automation 0.383 to 0.333; precision 1.0 both (synthetic check, 60) |
| E3 | Council vs one judge | council_enabled | Council beats the case reviewer alone (needs Gemini key) and beats the document checker alone | Precision at the same automation rate | Document checker alone vs full council: 1 more auto approve (an overpriced claim, paid right at the network price), reviews 133 to 117 per 1000; precision 1.0 both (synthetic check, 60). Not the hypothesis; one claim |
| E4 | Tuned weights vs equal weights | weights_tuned | Tuned weights beat equal weights | Total cost | pending |
| E5 | Disagreement sends to human | disagreement_routing_enabled | Catches wrong approvals that the average hides | Auto approve precision | Off: the same one overpriced claim is auto approved instead of reviewed, reviews 133 to 117 per 1000; precision 1.0 both (synthetic check, 60) |
| E6 | Calibration | calibration_enabled | Calibrated scores make cost-based lanes safer | ECE and total cost | ECE 0.155 to 0.051, cost 175 to 125 SAR, precision 1.0 both (synthetic check, 60 claims); day 4 rerun: ECE 0.202 to 0.065, reviews 133 to 100 per 1000, cost 200 to 150 SAR (synthetic check with documents, 60) |
| E7 | Cost-based lanes vs one fixed threshold | cost_lanes_enabled | Fewer reviews for the same precision | Reviews per 1000 | Fixed threshold: 1 fewer auto approve, reviews 133 to 150 per 1000, cost 200 to 225 SAR; precision 1.0 both (synthetic check, 60) |
| E8 | Self-fix choice | self_fix_enabled | Members fix many low scores themselves | Reviews per 1000, self-fix success | With the member's fix simulated: off sends 37 of 60 to a person (617 per 1000, 925 SAR), on 10 (167 per 1000, 250 SAR); 5 of 8 fixed claims then paid right with no person (synthetic check, 60) |
| E9 | History member | history_member_enabled | Raises automation for trusted members and providers | Automation rate; false reject rate new vs tenured | Off: no lane changes, ECE 0.202 to 0.161. Fairness: payable recall new members 0.17 vs tenured 0.37 with it on AND off, false rejects 0 both, so the gap is not from this member (synthetic check, 60) |
| E11 | Reader: EasyOCR vs PaddleOCR vs Gemini free tier | reader | A vision model reads messy and Arabic receipts better than OCR plus rules | Field accuracy | EasyOCR only so far: synthetic total 0.967 (day 2); real SROIE total 0.333, date 0.533, provider 0.35 (79f9aac). PaddleOCR and Gemini not run |
| E10 | Member preview before submit | preview_enabled (simulated) | Fewer bad submissions reach the pipeline | Claims needing self-fix | pending |
| E12 | Cross-document checks | cross_checks_enabled (run-set --cross-checks on or off) | Checking patient and date across the receipt, prescription and report catches mismatches with few false alarms, and sends them to self-fix instead of approving them | cross_check_catch_rate, cross_check_false_alarm_rate, auto approve precision | Catch 3 of 3, false alarms 0 of 57, one wrong auto approve avoided (synthetic check, 60 claims, after 3 fixes) |

E9 has a fairness check: the false reject rate for new members must not be higher than for tenured members. If it is, the history member is off until fixed.

## Results log
Add one block per run, newest at the bottom.

```
Run: E?
Date:
Commit:
Command:
Test set:
Switch off: <metrics>
Switch on: <metrics>
What it means, in one or two plain sentences:
```

```
Run: E11 part 1, EasyOCR reader alone (no PaddleOCR or Gemini comparison yet)
Date: 2026-11-24
Commit: f087ab9
Command: uv run --extra ocr reimbursement-council make-receipts --count 60 --seed 1 --out data/receipts/eval_s1
         uv run --extra ocr reimbursement-council read-accuracy data/receipts/eval_s1 --reader easyocr
Test set: 60 generated receipts (seed 1). Synthetic, not real. Layouts: clinic_arabic_first 29,
          clinic_bilingual 23, pharmacy_bilingual 8. About 70 percent carry a ZATCA QR.
          Photo damage: none 18, light 29, heavy 13.
Result, share of receipts where the field was read exactly right (QR first, then checks):
  total 0.967, subtotal 0.983, VAT amount 0.867, VAT number 0.983, treatment date 1.000,
  invoice time 0.967, provider 0.900, patient 0.550, QR found when present 0.783,
  line item service codes 0.622.
By damage:
  none (18):  every field 1.000, item codes 1.000
  light (29): total 1.000, VAT amount 1.000, patient 0.517, QR 0.759, item codes 0.701
  heavy (13): total 0.846, VAT amount 0.385, patient 0.000, QR 0.538, item codes 0.000
Time: 604 seconds for 60 receipts on a laptop CPU (cached afterwards).
What it means: on a clean photo the reader gets everything right. Amounts survive light damage
because the arithmetic checks and the QR back them up. Names and line items are the weak spot
on damaged photos, and heavy damage breaks item reading, so those claims must go to self-fix or
a human, not auto approve.
```

```
Run: E6, Platt calibration
Date: 2026-11-24
Commit: 9732afa (code); calibration fitted by this run, committed as config/calibration.yaml
Command: uv run reimbursement-council make-claims --count 120 --seed 11 --out data/sets/day3/tune
         uv run reimbursement-council make-claims --count 60 --seed 12 --out data/sets/day3/check
         uv run reimbursement-council run-set data/sets/day3/tune --reader easyocr --calibration off --resume
         uv run reimbursement-council fit-calibration data/sets/day3/tune/results.json
           -> a=17.1744 b=-12.5467, fitted on 102 claims (18 rejected by a hard rule left out)
         uv run reimbursement-council run-set data/sets/day3/check --reader easyocr --calibration off --results-name results_raw.json --resume
         uv run reimbursement-council run-set data/sets/day3/check --reader easyocr --calibration on --results-name results_calibrated.json --resume
Test set: synthetic check set, 60 claims (seed 12), read with EasyOCR. Fitted on the synthetic
          tune set (seed 11, 120 claims). Synthetic, not real_e2e, so not a number for slides.
Switch off: automation 0.4500, auto approve precision 1.0, payable recall 0.3556,
            false reject 0.0, correct reject 0.7333, reviews per 1000 116.7,
            self-fix per 1000 433.3, ECE 0.1551, total cost 175.00 SAR,
            heavy damage: 3 claims, all self_fix, 0 wrong auto approves.
            Lanes: auto_approve 16, auto_reject 11, self_fix 26, human_review 7.
Switch on:  automation 0.4667, auto approve precision 1.0, payable recall 0.3778,
            false reject 0.0, correct reject 0.7333, reviews per 1000 83.3,
            self-fix per 1000 450.0, ECE 0.0510, total cost 125.00 SAR,
            heavy damage: 3 claims, all self_fix, 0 wrong auto approves.
            Lanes: auto_approve 17, auto_reject 11, self_fix 27, human_review 5.
Changed lanes (2 of 60, both payable): claim_12_0058 human_review -> auto_approve, paid right;
            claim_12_0039 (light damage, payout not read) human_review -> self_fix.
Tune set, switch off, for reference: automation 0.3667, precision 1.0, false reject 0.0,
            ECE 0.1774, total cost 750.00 SAR, self-fix per 1000 383.3 (46 claims: 16 with no
            damage, 20 light, 10 unreadable), heavy damage 10 claims all self_fix.
What it means: calibration cuts the calibration error to a third (0.155 to 0.051) with no wrong
approvals and no false rejects. The cost drop (175 to 125 SAR) is only two fewer reviews, and one
of them became a self-fix, which has no cost yet (CHECK in HANDOVER), so the cost gain is small
and partly an effect of how cost is counted. 60 claims is a small set.
```

```
Run: E12, cross-document checks (patient, treatment date, provider)
Date: 2026-11-24
Commit: 0deac30 (rerun after three fixes). The first run at 507fdfd found the bugs, see below.
Command: uv run --extra ocr reimbursement-council make-claims --count 60 --seed 12 --out data/sets/docs/check
         uv run --no-sync reimbursement-council run-set data/sets/docs/check --reader easyocr --cross-checks off --results-name e12b_off.json
         uv run --no-sync reimbursement-council run-set data/sets/docs/check --reader easyocr --cross-checks on --results-name e12b_on.json
Test set: synthetic check set, 60 claims (seed 12) with document sets: 110 documents. Only 3
          claims carry a patient or date mismatch and none a missing prescription or report, so
          the document numbers rest on few claims. Calibration off. Synthetic, not real.
Switch off: lanes auto_reject 7, auto_approve 17, self_fix 28, human_review 8.
  automation_rate 0.40, auto_approve_precision 1.0, payable_recall 0.34, false_reject_rate 0.0,
  correct_reject_rate 0.70, reviews_per_1000 133.3, self_fix_per_1000 466.7, ece 0.1997,
  total_cost_sar 200.0, heavy damage: 5 claims, all self_fix, 0 wrong auto approves.
  document_kind_accuracy 0.9545 (110), missing_document_recall 0.0 (0 missing),
  missing_document_precision 0.0 (5 flagged), cross_check_catch_rate 0.0 (3),
  cross_check_false_alarm_rate 0.0 (57), expected_lane_match 0.8 (5).
Switch on: lanes auto_reject 7, auto_approve 16, self_fix 29, human_review 8.
  automation_rate 0.3833, auto_approve_precision 1.0, payable_recall 0.32, false_reject_rate 0.0,
  correct_reject_rate 0.70, reviews_per_1000 133.3, self_fix_per_1000 483.3, ece 0.2023,
  total_cost_sar 200.0, heavy damage: 5 claims, all self_fix, 0 wrong auto approves.
  document_kind_accuracy 0.9545 (110), missing_document_recall 0.0 (0 missing),
  missing_document_precision 0.0 (5 flagged), cross_check_catch_rate 1.0 (3),
  cross_check_false_alarm_rate 0.0 (57), expected_lane_match 1.0 (5).
First run (507fdfd, e12_off.json and e12_on.json in the same folder): with checks on, 19 of the
  57 claims with no mismatch had a failed cross check (false alarm rate 0.3333), automation fell
  from 0.40 to 0.25 and self_fix rose from 28 to 42. Causes, all fixed with tests before the
  rerun: (1) the QR gives the provider's Arabic name and the report was read in English, so the
  provider check compared two scripts and always failed (12 claims); (2) OCR split the label
  "اسم المريض" and "اسم" stayed in the patient name (8 claims, all light damage); (3) found
  while looking: an unclear treatment date asked the member to confirm the provider name.
What it means: the only lane change is claim_12_0016, which has another patient's name on its
  medical report. With checks off it was auto approved; with checks on it goes to self_fix and
  asks the member. No false alarms after the fixes. The 5 flagged missing documents are all
  receipts with an unreadable photo (read as "other"), which is the right thing to ask for.
  Too few document defects in this set to call it a final number.
```

```
Run: E12 on the tune set (more document defects than the check set)
Date: 2026-11-24
Commit: 0deac30
Command: uv run --extra ocr reimbursement-council make-claims --count 120 --seed 11 --out data/sets/docs/tune
         uv run --no-sync reimbursement-council run-set data/sets/docs/tune --reader easyocr --cross-checks off --results-name e12_off.json --resume
         uv run --no-sync reimbursement-council run-set data/sets/docs/tune --reader easyocr --cross-checks on --results-name e12_on.json --resume
Test set: synthetic tune set, 120 claims (seed 11), 217 documents, 7 mismatch claims, 9 missing
          documents. Calibration off. Synthetic, not real; tune sets are not for final numbers.
Switch off: lanes human_review 27, auto_approve 22, self_fix 58, auto_reject 13.
  automation_rate 0.2917, auto_approve_precision 1.0, payable_recall 0.2095,
  false_reject_rate 0.0, correct_reject_rate 0.8667, reviews_per_1000 225.0,
  self_fix_per_1000 483.3, ece 0.1544, total_cost_sar 675.0, heavy damage: 10 claims, all
  self_fix, 0 wrong auto approves. document_kind_accuracy 0.9539 (217),
  missing_document_recall 0.8889 (9), missing_document_precision 0.4444 (18),
  cross_check_catch_rate 0.0 (7), cross_check_false_alarm_rate 0.0 (113),
  expected_lane_match 0.8421 (19).
Switch on: lanes human_review 25, auto_approve 21, self_fix 61, auto_reject 13.
  automation_rate 0.2833, auto_approve_precision 1.0, payable_recall 0.2, false_reject_rate 0.0,
  correct_reject_rate 0.8667, reviews_per_1000 208.3, self_fix_per_1000 508.3, ece 0.1573,
  total_cost_sar 625.0, heavy damage: same. document metrics the same except
  cross_check_catch_rate 1.0 (7), cross_check_false_alarm_rate 0.0177 (2 of 113),
  expected_lane_match 1.0 (19).
Lane changes: 3 patient name mismatches. claim_11_0039 was auto approved with checks off and
  goes to self_fix with them on; claim_11_0035 and claim_11_0095 went to a person and now ask
  the member first.
Found: the 2 false alarms (claim_11_0034, claim_11_0068, no damage) are the Arabic patient name
  on the medical report misread by OCR at 0.57 to 0.64 confidence. The one missed missing
  prescription (claim_11_0044, light damage) had no line items read, so no category and no
  need was known. Low missing_document_precision is mostly unreadable receipts flagged as a
  missing invoice. Not tuned away; see the CHECK items in HANDOVER.
What it means: same picture as the check set with more cases. Cross checks catch every
  mismatch put in, stop a wrong auto approve, and send mismatches to the member before a
  person, which cuts reviews from 225 to 208 per 1000 and cost from 675 to 625 SAR. The price
  is 2 false alarms in 113 from OCR on Arabic names.
```

```
Run: ablations E2, E3, E5, E6, E7, E8, E9 (one switch at a time) with the fairness check
Date: 2026-11-25
Commit: 95745da (code), config_version 2d82d0d23bfe (calibration.yaml from day 3)
Command: uv run --extra ocr reimbursement-council make-claims --count 60 --seed 12 --out data/sets/abl/check
         then, with S=data/sets/abl/check and --reader easyocr on every run:
         run-set $S --results-name base.json
         run-set $S --results-name base_fix.json --simulate-fix
         run-set $S --results-name e2_off.json --set arithmetic_checks_enabled=false
         run-set $S --results-name e3_single.json --set members.coverage_checker.enabled=false
                 --set members.price_checker.enabled=false --set members.history_member.enabled=false
         run-set $S --results-name e5_off.json --set disagreement_routing_enabled=false
         run-set $S --results-name e6_on.json --calibration on
         run-set $S --results-name e7_off.json --set cost_lanes_enabled=false
         run-set $S --results-name e8_off_fix.json --set self_fix_enabled=false --simulate-fix
         run-set $S --results-name e9_off.json --set members.history_member.enabled=false
Test set: synthetic check set with documents, 60 claims (seed 12), the same claims as E12, plus the
          fixed file of each fixable defect (8 files). Synthetic, not real. The base is the
          config as it is (calibration off). Every run processed all 60 claims.

                            base  e2_off e3_one  e5_off  e6_on  e7_off  e9_off  base+fix e8_off+fix
automation_rate            0.383  0.333  0.400   0.400   0.383  0.367   0.383   0.433    0.383
auto_approve_precision     1.0    1.0    1.0     1.0     1.0    1.0     1.0     1.0      1.0
payable_recall             0.32   0.32   0.34    0.34    0.32   0.30    0.32    0.38     0.32
false_reject_rate          0.0    0.0    0.0     0.0     0.0    0.0     0.0     0.0      0.0
correct_reject_rate        0.70   0.40   0.70    0.70    0.70   0.70    0.70    0.70     0.70
reviews_per_1000           133.3  133.3  116.7   116.7   100.0  150.0   133.3   166.7    616.7
self_fix_per_1000          483.3  533.3  483.3   483.3   516.7  483.3   483.3   400.0    0.0
ece                        0.2023 0.2044 0.1609  0.2023  0.0654 0.2023  0.1608  0.1762   0.2023
total_cost_sar             200    200    175     175     150    225     200     250      925
heavy_damage_wrong_approves 0     0      0       0       0      0       0       0        0
self-fix tried / paid right                                                     8 / 5    0
fairness, payable claims: new members (fewer than 3 past claims) 12, tenured 38 in every run.
  false_reject_rate new 0.0 and tenured 0.0 in every run.
  payable_recall new 0.1667 in every run; tenured 0.3684 (base, e2, e6, e9, e8),
  0.3947 (e3, e5), 0.3421 (e7), 0.4474 (base+fix).

Lane changes against base, claim by claim (checked by hand before writing this):
- E2 off: claim_12_0000, 0010, 0053 (excluded service) go from auto_reject to self_fix. Passed
  checks raise the confidence of the line items; without them the exclusion rule is not sure,
  so it asks the member instead of rejecting.
- E3 one member and E5 off: claim_12_0055 (overpriced) goes from human_review to auto_approve,
  paid right at the network price. The price checker's low vote made the council disagree.
- E6 on: claim_12_0005 (over limit) and claim_12_0039 (clean) go from human_review to self_fix.
- E7 off: claim_12_0036 (overpriced) goes from auto_approve to human_review.
- E9 off: no lane changes.
- base+fix: 5 of the 8 fixed claims (4 unreadable photos, 1 patient mismatch) are then auto
  approved and paid right. Two clean claims (claim_12_0038, 0051) that were auto approved go to
  a person as "possible duplicate": once the unreadable receipts are read clearly, their weak key
  (VAT number, date, total) matches these claims. This is the weak-key CHECK from data review 4.
What it means: on this small synthetic set no switch changed precision (1.0 everywhere) or caused
  a false reject. Calibration (E6) and self-fix (E8) change the most: self-fix with the member's
  fix keeps 27 of 60 claims away from a person. Arithmetic checks matter for confident rejects
  (E2). The council's extra members and disagreement routing (E3, E5) cost one review on one
  overpriced claim and did not catch a wrong approval here. Each change is one to three claims of
  60, so none of these is a final number.
```

```
Run: E1 / E11 part 2, EasyOCR on real receipts (SROIE), before and after the failure review
Date: 2026-11-25
Commit: 6943ee7 (baseline), 79f9aac (after the fixes below)
Command: uv run --no-sync reimbursement-council read-sroie data/real/sroie --reader easyocr
         --results-name accuracy_<commit>.json
Test set: real_extraction, 60 scanned receipts from SROIE (ICDAR 2019; every 10th of the 626 in
          github.com/zzzDavid/ICDAR-2019-SROIE, MIT). Malaysian shops, English, ringgit, no QR
          code, no Arabic. Truth: company, date and total from the dataset's key files. Not
          used for tuning: the fixes come from reading the rows of the failures, not from
          trying settings against the score.
Baseline (6943ee7): provider 0.35, date 0.3667, total 0.3167 (60 of 60 have each truth). 1086
          seconds on a desktop CPU (about 18 s per receipt; the scans are large).
After (79f9aac): provider 0.35, date 0.5333, total 0.3333. The OCR results are cached, so only
          the parser changed between the two runs.
The 10 worst (every field wrong in the baseline): 010, 070, 130, 180, 190, 230, 250, 260, 300, 310.
What went wrong, looked at by eye and in the OCR rows:
- Arabic glyphs in Latin text (070, 190, 230, 250, 260, 300): EasyOCR is loaded with Arabic and
  English, and on faint dot-matrix or thermal print it reads Latin letters and digits as Arabic
  ones ("MR. D.I.Y." became Arabic digits). Names, totals and dates are lost together. Not fixed:
  it needs a per-document language guess or a second English-only pass (CHECK).
- Faint or coloured print (230 purple thermal, 070 dot matrix): low contrast; OCR drops or
  merges characters ("Tota/", "Tola/").
- Date forms we did not read (010 "29-12-2017", 060 "12/03/18", 070 "05 02-18"): fixed for
  dashes, dots and two digit years.
- The wrong "total" row (350 took "Total Qty 65.00"; 120 took a tax row): fixed, counts,
  savings, cash, change and tax-only rows are skipped.
- Provider is the first Latin row at the top (160 took "Your order number is", 230 has a logo
  above the name, 000 took a person's name): not fixed.
- Comma read for the decimal point ("77,20", "0,36"): not fixed, it would clash with thousands
  separators.
- First version of the total fix made total worse (0.3167 to 0.2667: it skipped "Total with
  GST", "Total (Excluding GST)" and "Total After Rounding" rows). Narrowed before recording;
  each of those real rows is now a test.
What it means: on real scans the reader is weak. Dates are now read on about half; totals and
  names on about a third. Our own synthetic receipts read far better, so synthetic numbers must
  not be shown as real accuracy. Real Saudi receipts carry a ZATCA QR, which these do not.
```

```
Run: real end to end, 50 SROIE receipts in a synthetic claim context
Date: 2026-11-25
Commit: 79f9aac
Command: uv run --no-sync reimbursement-council make-real-claims data/real/sroie --out data/sets/real_e2e --seed 1 --count 50
         uv run --no-sync reimbursement-council run-set data/sets/real_e2e --reader easyocr --results-name e2e_79f9aac.json
Test set: real_e2e, the first 50 of the 60 receipts above, each in a generated claim: a member on
          an active policy that covers the receipt date, sent 1 to 5 days after it. So every
          claim should be paid; the right amount is not known (the shops' goods are not on our
          price list) and is not scored.
Result: lanes self_fix 50 of 50. automation_rate 0.0, wrong auto approves 0, false rejects 0
          (auto_reject 0), self_fix 1000 per 1000.
Why, from the stored decisions: 31 ask the member to confirm the treatment date (read below the
          0.90 confidence floor), 17 ask for an invoice or receipt (the document type was not
          found: 14 read as "other", 3 as a prescription because of an "Rx"-like word), 1 asks
          to confirm the provider, 1 a patient name mismatch.
What it means: on real documents it reads badly, it asks the member instead of guessing; it
          never approved or rejected a claim it could not read. That is safe but gives no
          automation on these receipts.
```

```
Run: final check of the headline numbers after the code and data reviews
Date: 2026-11-25
Commit: 98c360a
Command: run-set data/sets/abl/check --reader easyocr (base), plus --simulate-fix, plus
         --set self_fix_enabled=false --simulate-fix; read-sroie data/real/sroie --reader easyocr;
         run-set data/sets/real_e2e --reader easyocr; export-set data/sets/docs/check and tune
Result: synthetic base, base+fix and self-fix off+fix: the same lanes and metrics as at 95745da
          (precision 1.0, false rejects 0; reviews 133.3, 166.7 and 616.7 per 1000; cost 200, 250
          and 925 SAR; 5 of 8 fixes then paid right). Real SROIE: provider 0.35, date 0.5333,
          total 0.3333 (the same as 79f9aac). Real end to end: 50 of 50 self_fix. Export: 60 of
          60 and 120 of 120 valid.
In between (78608a0) the date reader was made stricter after the data review (Hijri years,
          codes like "Ref 10-10-10"): real date fell to 0.45 because 5 real dates like
          "17-03-18 14:49" were dropped. The rule now takes a short dashed date when the row also
          has a time or the word date; those 5 rows are tests.
Data review note on E8: in base+fix, 24 of 60 claims are still in self_fix at the end (21 had
          no fix file in the set; all 24 ask to confirm the treatment date) and count as no
          review and no cost. So "10 reviews against 37" leaves those 24 waiting for the member.
```


## Core day 4 night (branch core/day4)

```
Run: confidence per field (date and item numbers, not the row minimum), then E6 again
Date: 2026-11-25
Commit: 296002e (confidence per field), 522713c (calibration refitted and on)
Command: run-set data/sets/docs/tune --reader easyocr --calibration off --results-name results_core_fit.json
         fit-calibration data/sets/docs/tune/results_core_fit.json  (a=18.988158, b=-13.597297;
           107 claims, 13 hard rule rejects left out)
         run-set data/sets/abl/check --reader easyocr --calibration off --results-name results_core_caloff.json
         run-set data/sets/abl/check --reader easyocr --calibration on --results-name results_core_calon.json
Test set: synthetic check, 60 claims (seed 12); fit on synthetic tune, 120 claims (seed 11)
Result, check set, calibration off (296002e): lanes auto_reject 7, auto_approve 18,
         human_review 14, self_fix 21; automation 0.4167; precision 1.0; false rejects 0.0;
         reviews 233.3 per 1000; ECE 0.2023; cost 350 SAR.
         Before confidence per field (base.json, 95745da): auto_approve 16, self_fix 29,
         human_review 8, automation 0.3833, reviews 133.3. 8 claims left self_fix: 2 to
         auto_approve, 6 to human_review (expected loss above the review cost, no payout priced,
         or a possible duplicate). The date no longer stops them, so the council sees them.
Result, check set, calibration on (522713c): lanes auto_reject 7, auto_approve 20,
         self_fix 26, human_review 7; automation 0.45; precision 1.0; false rejects 0.0;
         reviews 116.7 per 1000; ECE 0.0602; cost 175 SAR.
Decision: calibration on by default (the owner's rule: only if precision stays 1.0 and false
         rejects stay 0; both hold).
```

```
Run: new real baseline after part (b)
Date: 2026-11-25
Commit: 522713c
Command: read-sroie data/real/sroie --reader easyocr --results-name accuracy_core_base.json
         run-set data/sets/real_e2e --reader easyocr --results-name results_core_base.json
Test set: real_extraction, 60 SROIE scans; real_e2e, 50 SROIE scans in a synthetic claim context
Result: SROIE provider 0.35, date 0.5333, total 0.3333 (unchanged: field accuracy does not use
         confidence). Real e2e: 50 of 50 self_fix, automation 0.0, 0 wrong approvals, 0 false
         rejects. Seconds per claim 0.153 mean with the OCR cache (not a live timing).
```

```
Run: local model reader on real receipts (E1, E11 with the model)
Date: 2026-11-25
Model: qwen3-vl:8b-instruct through Ollama, temperature 0, seed 7, prompt version 1
Commit: dcecc4d (first run, model answers not cached yet), 5cff017 (after grounding allows one
         digit of OCR noise; model answers from the cache, same answers)
Command: read-sroie data/real/sroie --reader ollama --two-readers off|on --results-name accuracy_core_ollama_<off|on>.json
Test set: real_extraction, 60 SROIE scans (Malaysia, English, no QR)
Result (5cff017):
         EasyOCR alone (522713c): provider 0.35, date 0.5333, total 0.3333
         model alone (two readers off): provider 0.5167, date 0.5167, total 0.6167
         model + EasyOCR (two readers on): provider 0.5167, date 0.6, total 0.6167;
           readers agreed on 87 fields and disagreed on 27 (those go under the floor)
         made-up rate 0.2865: values the model returned that were found neither in the OCR
           text nor in a QR code, out of 363 returned (dropped). Most are real values EasyOCR
           misread (receipt 000: EasyOCR read 2013 for 2018), so this is "not confirmed", an
           upper bound on invention. Implausible 70 of 363 (Malaysian GST numbers do not match
           the Saudi VAT format, so every one is dropped). QR mismatch: no QR on SROIE.
         Seconds per receipt with the model (dcecc4d, uncached): mean 4.232, median 4.061,
           max 8.087 (EasyOCR from its cache).
First try (dcecc4d, grounding exact): model alone provider 0.5167, date 0.45, total 0.5333;
         made-up rate 0.3278. Exact grounding dropped right dates when EasyOCR misread one digit.
Earlier failure: the qwen3-vl:8b tag thinks before answering and ignored think=false: every
         answer hit the 1200 token cap with no content. Fixed by the 8b-instruct tag (63ba4de).
```

```
Run: real end to end with the local model reader
Date: 2026-11-25
Commit: 5cff017
Command: run-set data/sets/real_e2e --reader ollama --set two_readers_enabled=true|false
Test set: real_e2e, 50 SROIE scans in a synthetic claim context
Result: two readers on: self_fix 48, human_review 2; off: self_fix 46, human_review 4.
         Automation 0.0, wrong approvals 0, false rejects 0 in both.
Why no automation: SROIE receipts are Malaysian shop receipts (glue, food). No item is on our
         price list and no provider can match, so the coverage and price members score near 0
         and the member is asked (15 about the provider, 14 to confirm the date). This set
         measures safety only; it cannot show automation for any reader.
```

```
Run: local model reader on the synthetic check set (one switch at a time)
Date: 2026-11-25
Commit: 5cff017 (code), runs started from it; calibration on
Command: run-set data/sets/abl/check --reader ollama --set two_readers_enabled=true|false
         --results-name results_core_ollama_tr_<true|false>.json
Test set: synthetic check, 60 claims with documents (seed 12)
Result:
         EasyOCR (522713c, calibration on): automation 0.45, precision 1.0, false rejects 0,
           reviews 116.7 per 1000, self_fix 433.3, ECE 0.0602, cross check false alarms 0 of 57
         model + EasyOCR (two readers on): lanes auto_reject 10, auto_approve 26, human_review 13,
           self_fix 11; automation 0.6, precision 1.0, false rejects 0.0, reviews 216.7,
           self_fix 183.3, ECE 0.087, cost 325 SAR, document kind accuracy 1.0, cross checks
           caught 3 of 3 with false alarm rate 0.0351 (2 of 57), heavy damage wrong approves 0.
           Seconds per claim 5.811 mean (model answers not cached; read 5.757).
         model alone (two readers off): auto_approve 27, self_fix 10, otherwise the same;
           automation 0.6167, precision 1.0, false rejects 0.0, ECE 0.0879.
Decision: reader ollama with two readers on is the new default. Both keep wrong approvals and
         false rejects at 0 here and on real_e2e. Two readers costs 1 approval of 60 here but
         raised the real date accuracy from 0.5167 to 0.6 and sends every disagreement to the
         member, which is the safer side for documents judges hand us.
```

```
Run: AI case reviewer golden set with the real model (check-reviewer)
Date: 2026-11-25
Model: qwen3-vl:8b-instruct, text only, temperature 0, seed 7
Command: check-reviewer --data-dir <separate folder>
Test set: tests/golden, 20 claim summaries (6 clear good, 5 clear bad, 5 tricky, 4 injection)
Result:
         8d239e3, reviewer prompt 2: pass rate 0.35 (limit 0.90), benched. 13 answers discarded
           by the schema check: the model wrote a whole number score (0), and repeated the same
           cited field until the answer was cut off.
         first run (e59b4e6, prompt 1): pass rate 0.25, benched. Reasons longer than 300
           characters were discarded.
         6b60397, reviewer prompt 3: pass rate 0.85 (17 of 20), benched (limit 0.90). Every clear
           good, clear bad and injection case passed. Failed: tricky_bad_cosmetic_as_consult,
           tricky_bad_date_in_future, tricky_bad_huge_quantity (scored 1.0, expected bad).
Honesty note: prompts 2 and 3 were written after seeing golden failures (format fixes, and
         one sentence that the calculated payout is normally lower than the requested one after
         co-pay). So 0.85 is not a clean held-out score. No more changes were made against it.
Decision: the reviewer stays off by default and benched. The circuit breaker worked as built.
```

```
Run: E3, council with vs without the AI case reviewer
Date: 2026-11-25
Commit: 6b60397 (reader ollama with two readers, calibration on; model answers cached)
Command: run-set data/sets/abl/check --results-name results_core_e3_off.json
         run-set data/sets/abl/check --set members.case_reviewer.enabled=true
           --set members.case_reviewer.golden_pass_rate=0.85 --data-dir <separate folder>
           --results-name results_core_e3_on.json
         (the pass limit was lowered for this measurement only, so the benched reviewer runs)
Test set: synthetic check, 60 claims (seed 12)
Result: off: auto_approve 26, human_review 13, self_fix 11, auto_reject 10; automation 0.6,
         precision 1.0, false rejects 0.0, reviews 216.7 per 1000, ECE 0.087, 0.145 s per claim.
         on: auto_approve 25, human_review 14; automation 0.5833, precision 1.0, false rejects
         0.0, reviews 233.3, ECE 0.0715, 2.549 s per claim. Reviewer used on 39 claims, skipped
         on 21 (lanes it does not review), 0 discarded. It moved 1 claim, claim_12_0036
         (payable, overpriced: paid in part) from auto_approve to a person.
Meaning: on this set the reviewer only costs: there was no wrong approval for it to stop.
```

```
Run: (e) Arabic and English reading on the synthetic receipts, EasyOCR vs the local model
Date: 2026-11-25
Commit: 9671aea (model answers cached from the first run at 1625c6a; the code change in
         between only turns a name printed in both scripts into its Latin words)
Command: read-accuracy data/receipts/eval_s1 --reader easyocr --results-name accuracy_core_easyocr.json
         read-accuracy data/receipts/eval_s1 --reader ollama --two-readers on --results-name accuracy_core_ollama.json
Test set: SYNTHETIC receipts, 60 (seed 1): 29 Arabic-first clinic invoices, 23 bilingual clinic
         invoices, 8 bilingual pharmacy receipts, with light and heavy photo damage. Not real data.
Result: EasyOCR: provider 0.900, VAT number 0.983, date 1.000, time 0.967, patient 0.800,
         subtotal 0.983, VAT 0.867, total 0.967, item codes 0.622.
         Model + EasyOCR: provider 0.950, VAT number 0.983, date 1.000, time 0.983,
         patient 0.917, subtotal 0.983, VAT 0.933, total 1.000, item codes 0.803.
         Made-up rate 0.05 (values not found in the OCR text or QR, dropped). QR mismatch rate
         0.0 (0 of 78 compared). Readers agreed on 442 fields and disagreed on 7.
         Arabic-first layout (29): provider 0.966, total 1.0. Bilingual clinic (23): provider
         0.913, total 1.0. Pharmacy (8): provider 1.0, total 1.0.
         First run at 1625c6a gave provider 0.683: the model wrote both names together
         ("مركز الشفاء الطبي Al Shifa Medical Center"); fixed in core with a test.
```

```
Run: FINAL CHECK, every headline number from one commit (core day 4)
Date: 2026-11-25
Commit: 38cc89d (after the code and data reviews; calibration refitted on the tune set with
         the model reader: a=12.744003, b=-9.393948, 105 claims, 15 hard rule rejects left out)
Script: D:\rc-tmp\final\run_all.sh (each command below; results named f_*.json)
Defaults: reader ollama (qwen3-vl:8b-instruct) with two readers on, calibration on, AI case
         reviewer off.

Synthetic check set, 60 claims (seed 12): run-set data/sets/abl/check [switch]
  default          auto_approve 24, human_review 18, self_fix 8, auto_reject 10; automation 0.5667,
                   precision 1.0, false rejects 0.0, reviews 300.0/1000, ECE 0.0991, cost 450 SAR
  --calibration off   automation 0.6, precision 1.0, false rejects 0.0, reviews 266.7, ECE 0.1059
  E2 arithmetic off   automation 0.55, precision 0.8889, false rejects 0.0, ECE 0.1952, cost 892.5
  E3 one member       automation 0.6667, precision 1.0, false rejects 0.0, reviews 200.0
  E5 routing off      automation 0.5833, precision 1.0, false rejects 0.0, reviews 283.3
  E7 cost lanes off   automation 0.55, precision 1.0, false rejects 0.0, reviews 316.7
  E9 history off      automation 0.6167, precision 1.0, false rejects 0.0, reviews 250.0
  two readers off     automation 0.3667, precision 1.0, false rejects 0.0, self_fix 466.7
  --reader easyocr    automation 0.3833, precision 1.0, false rejects 0.0, self_fix 433.3
  E8 --simulate-fix   auto_approve 27, human_review 23, none left waiting; automation 0.6167,
                      precision 1.0, 8 fixes tried, 5 then paid right (0.625), cost 575 SAR
  E8 self-fix off + fix  human_review 26, automation 0.5667, cost 650 SAR
  E3 AI reviewer on (golden limit 0.85 for this run only)  automation 0.55, precision 1.0,
                      false rejects 0.0, reviews 316.7, 2.745 s per claim
E12 cross checks: run-set data/sets/docs/check|tune --cross-checks on|off
  check (60): on: 3 of 3 caught, false alarms 0 of 57, automation 0.5667; off: 0 caught,
              automation 0.6 (precision 1.0 both)
  tune (120): on: 7 of 7 caught, false alarm rate 0.0177 (2 of 113), automation 0.4;
              off: 0 caught, automation 0.4167 (precision 1.0 both)
Real SROIE, 60 scans: read-sroie data/real/sroie --reader ollama|easyocr [--two-readers on|off]
  EasyOCR: provider 0.35, date 0.5333, total 0.3333
  model + EasyOCR: provider 0.5167, date 0.6, total 0.6167; made-up rate 0.2865 (104 of 363
              returned values not found in the OCR text; 15 more only one digit away, kept under
              the floor); readers agreed 87, disagreed 27
  model alone: provider 0.5167, date 0.5167, total 0.6167
Real e2e, 50: run-set data/sets/real_e2e: model reader self_fix 48, human_review 2; EasyOCR
              self_fix 50. Automation 0.0, precision n/a (no approvals), false rejects 0.0.
Synthetic receipts, 60 (Arabic-first and bilingual): read-accuracy data/receipts/eval_s1
  EasyOCR: provider 0.900, date 1.000, patient 0.800, VAT 0.867, total 0.967, item codes 0.622
  model + EasyOCR: provider 0.950, date 1.000, patient 0.917, VAT 0.933, total 1.000,
              item codes 0.803
Export: export-set data/sets/docs/check|tune: 60 of 60 and 120 of 120 valid; 24 and 33 ready
              for processing.
Live, through the website: live-test data/live_standin_final --url http://127.0.0.1:8011
  (STAND-IN set, not the owner's photos: 4 real SROIE scans, 4 synthetic Arabic-first receipts
  of which 2 heavily damaged, 1 receipt with its report; re-saved so no answer was cached):
  9 of 9 finished, 0 errors, 9 schema valid; seconds per claim mean 13.855, median 13.31,
  max 23.193 (upload and read 13.802, send and decide 0.054). Before the model and EasyOCR
  read at the same time (1cdb625): mean 20.766 (8 claims re-saved once, 0e8b746).
Browser e2e demo test: uv run pytest -m e2e: 2 passed in 81.37 s.
```

## Core day 4b (branch core/day4b)

```
Run: Step 1, speed: EasyOCR on the GPU
Date: 2026-11-25
Change: PyTorch 2.14.1+cu130 on Windows (was 2.15.0 CPU build), ocr.use_gpu true; the model and
         EasyOCR take turns on the one GPU (vision.parallel_ocr false)
Command: live-test <stand-in set, re-saved so nothing is cached> --url http://127.0.0.1:8011
Test set: the 9 claim stand-in live set (4 real SROIE scans, 4 synthetic Arabic-first receipts of
         which 2 heavily damaged, 1 receipt with its report). Not the owner's photos.
Before (38cc89d, EasyOCR on the CPU, reading in parallel): mean 13.855 s per claim, median 13.31,
         max 23.193
After (09b4717, EasyOCR on the GPU, taking turns): mean 8.057 s, median 7.122, max 12.509;
         9 of 9 finished, 0 errors, 0 model timeouts
First try (12510f0, GPU and parallel): stopped after 20 minutes with 2 model timeouts. GPU memory
         was 11.8 of 12.3 GB (model 6.6 GB, EasyOCR up to 1.6 GB, desktop apps), and the two
         slowed each other to a crawl.
EasyOCR alone, 3 documents, model unloaded: GPU 1.09, 0.99, 0.52 s (1556 MB); CPU 12.79, 9.96,
         5.97 s.
```

```
Run: Step 4, the real case study (one real Bupa optical claim, personal data kept out)
Date: 2026-11-25
Commit: a8dd032
Command: add-member --name "Case Member" --tier silver --used optical_frames=600 --data-dir <tmp>
         serve --port 8011 --data-dir <tmp>; live-test realtest/case --patient <id> --out realtest/out
         then the same stored readings decided with submission 2026-07-30 (Bupa's received date)
Test set: 1 real claim (realtest/, gitignored)
Result: read in 6.3 s. Date, total, VAT, both items, invoice and VAT numbers and the eye test read
         right. Check page before submit: estimated payout 450.00 SAR (1,200 over the frame
         sub-limit, share 100). Bupa approved 450 SAR. Sent today: auto_reject, late (119 days).
         Sent on 2026-07-30: payout 450.00 SAR, human_review (expected loss 98.78 SAR).
First run (0f4b592): no date (2026/07/29 not read), invoice number not found (printed before
         its label), frame item dropped (the model wrote Persian letters), so the estimate was
         0.00 and the member was asked for a full tax invoice. Fixed with tests in a8dd032.
The sub-limit usage came from Bupa's answer, not from a prediction.
```

```
Run: Step 4b, image variants of the real invoice (real data, kept in realtest/variants)
Date: 2026-11-25
Commit: 5746949
Command: D:\rc-tmp\real_variants.py (reader ollama with two readers; fields compared with the
         known right values: date, total, VAT, the two item amounts)
Result (right fields; a miss was always a blank field, never a wrong value):
  pdf (original)      date, total, VAT, items all right; 12.04 s (first call)
  image (rendered)    all right; 7.0 s
  rotated 90 degrees  nothing read (EasyOCR and the model lost the text); 6.67 s
  rotated 7 degrees   date, total, items right; VAT not read; 6.91 s
  blurry (radius 2.5) nothing read; 8.09 s
  low light (0.35)    all right; 8.54 s
  cropped edge (10%)  total and VAT right; date and items not read; 7.58 s
  photo of a screen   date and total right (total under the floor: readers disagreed);
                      VAT and items not read; 8.74 s
  Totals over 8 variants: date 5, total 6, VAT 4, items 4.
Meaning: when quality drops the fields go blank and the member is asked for a clearer photo.
         A 90 degree rotation is not handled (CHECK: try EasyOCR's rotation_info).
```
