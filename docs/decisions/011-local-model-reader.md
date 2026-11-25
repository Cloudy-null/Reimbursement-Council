# 011: A local vision model reads documents (Ollama, qwen3-vl:8b)

Date: 2026-11-25. Status: accepted.

## Context

EasyOCR with our hand-written parser reads real receipts badly: on 60 SROIE scans it got the
total right on 0.3333, the date on 0.5333 and the shop name on 0.35 (commit 522713c). It turns faint
Latin print into Arabic letters, and every layout needs new parsing rules. The judges will hand us
an Arabic or unclear document on stage. Medical documents hold personal health data, so a
cloud model would mean sending them outside, which the brief's privacy point argues against, and
the project has no paid API.

## Options

1. Keep EasyOCR and add more parsing rules. Cheap, but each new layout needs new rules.
2. A cloud vision model (Gemini free tier). Strong, but documents leave the machine, rate limits
   on stage, and a key to manage.
3. A local vision model through Ollama on the PC's RTX 4070 Super (12 GB).

## Choice

Option 3, with qwen3-vl:8b. It reads Arabic and English, runs in about 6 GB of GPU memory with
room left for EasyOCR, and in a first probe (2026-11-25) read a synthetic Arabic and English
invoice and a SROIE receipt in about 5 to 7 seconds each once loaded (52 seconds for the first
call, which loads the model). Ollama keeps the model loaded (keep_alive 30m). The client refuses
any server that is not on this machine.

The model only reads. Every value it returns goes through core/vision_checks.py: the answer must
match a strict schema (else asked once more, then dropped), every value must appear in the OCR
text or the QR code (else counted as made up and dropped), total, date and VAT number are compared
with the QR code, and amounts, dates and VAT numbers must be plausible. With two_readers_enabled,
EasyOCR's own reading raises a field's confidence when it agrees and lowers it under the floor
when it does not, so the member is asked. Rules, the council and the lanes decide, as before.

## Trade-off

Each document now takes seconds of GPU time instead of a fraction of a second, and the demo needs
the PC (the laptop fallback uses EasyOCR, docs/DEMO.md). Grounding needs the OCR text, so a value
the model reads correctly but EasyOCR garbles is dropped: safe, but it loses some right values.
Temperature 0 and a fixed seed make answers repeatable; answers are cached by image hash, model
and prompt version.
