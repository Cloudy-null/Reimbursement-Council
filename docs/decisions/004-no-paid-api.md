# 004: No paid AI API, offline reader by default

Date: 2026-11-23
Status: Accepted

## Context
The owner is on the Claude Pro plan. Pro includes Claude Code but no API credits, so the app cannot call Claude at runtime. Pro also has a 5 hour limit and a weekly limit shared with chat, so the overnight build will pause.

## Options
- Pay for API credits.
- Call Claude Code headless from the app on the owner's subscription. Hacky, eats the same limits as the build, and fragile in a demo.
- Offline open-source OCR plus rules as the default reader, with a free tier vision model (Gemini API free tier) as an optional switch.

## Choice
The third. The app runs with no keys at all. The case reviewer and the Gemini reader are optional council parts behind switches. Experiment E11 compares readers.

## Trade-off
OCR plus rules will read messy and Arabic receipts worse than a vision model, so automation may be lower. That is measured, not hidden. Free tier data may be used by the provider, so only synthetic and public dataset images are ever sent to it. Overnight mode saves progress after every task so a usage limit stop loses nothing.
