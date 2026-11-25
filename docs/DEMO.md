# Running the live demo

The website and the local model run on the desktop PC (RTX 4070 Super). The laptop on stage only
opens the website in a browser over Tailscale. No document leaves our own two machines.

## Plan A: the PC serves, the laptop opens it over Tailscale

One time, on both machines:
1. Install Tailscale from https://tailscale.com/download and sign in with the same account on
   the PC and the laptop. Both must show "Connected".
2. On the PC, find its Tailscale address: `tailscale ip -4` (it starts with 100.).

Before the demo, on the PC (in the repo folder):
1. Make sure Ollama is running (the tray icon, or `ollama list` answers). The model is
   qwen3-vl:8b; its files are in D:\ollama-models.
2. Start the website on the Tailscale address only, so the venue Wi-Fi cannot reach it:

   ```
   uv run reimbursement-council serve --host 100.x.y.z --port 8000
   ```

   Use the address from step 2 above. Windows may ask about the firewall the first time: allow
   it for private networks.
3. Wait until `http://100.x.y.z:8000/api/ready` says ready (the reader warm-up reads the demo
   files once, so the first claim does not wait).

On the laptop: open `http://100.x.y.z:8000` in the browser. Run one demo claim before going on
stage.

Checks before going on stage:
- `uv run reimbursement-council live-test data/live_test --url http://100.x.y.z:8000` sends our
  own test photos through the website and prints seconds per claim (run it from the PC).
- The numbers page says whether the AI reviewer is healthy or benched.
- Drive C: has free space (it had almost none on 2026-11-25; the OCR cache and the database
  write there).

## Plan B: the laptop runs everything with EasyOCR

If Tailscale or the PC fails. The laptop has no strong GPU, so it uses EasyOCR (slower, weaker
on faint print) and not the local model.

```
git pull
uv sync --extra ocr
uv run reimbursement-council serve
```

Then open `http://127.0.0.1:8000`. In config/decision.yaml the reader must be `easyocr` and
the local model switches must be off (they are listed in docs/MODEL_SAFETY.md).

## Plan C: demo mode only

If live reading fails on stage, use the five demo claim buttons on the new claim page (clean,
missing prescription, report for another patient, changed total, PDF). Their files are read at
startup, so they answer fast. This shows the whole flow but not a document the judges hand us.
