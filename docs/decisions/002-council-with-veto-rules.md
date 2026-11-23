# 002: Weighted council with veto rules and disagreement routing

Date: 2026-11-23
Status: Accepted

## Context
We want high precision and recall on automatic decisions and a small human lane. One model's confidence is not reliable on its own.

## Options
- One LLM judge that says approve or reject.
- A council of several judges, averaged.
- A council of specialists with different jobs, numeric weighted scores, hard rules as yes or no vetoes, and disagreement as its own signal.

## Choice
The third. Hard rules are yes or no and act as a veto. Council members each give a score from 0 to 1 with a weight from config. Scores are combined and calibrated. High disagreement sends the claim to a human instead of being averaged away.

## Trade-off
More parts to build and tune than one judge. Weights and calibration need labeled data. We accept this because each part can be switched off and measured (E3, E4, E5, E6 in EXPERIMENTS.md). If the numbers show a single judge is as good, we say so.

## Related reading
- Verga et al., 2024, Replacing Judges with Juries (panel of diverse models beats one large judge, on text evaluation)
- Mozannar and Sontag, learning to defer to an expert
- Guo et al., 2017, On Calibration of Modern Neural Networks
