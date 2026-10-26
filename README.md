# Class Quality AI

Rates an online children's class recording as **Poor / Average / Good / Excellent** and explains why, using timestamped evidence from what is said, how the class sounds, and what is on screen.

## How it works

```
recording ──► ffmpeg signals ────────────────┐   (silence %, long silences, loudness,
   │                                         │    screen-change rate, duration)
   └──► compress (360p, 1 fps, mono 16 kHz) ─┤
                                             ▼
                     Gemini (video + audio in one call)
                     8-dimension rubric, 1–4 each, JSON schema enforced,
                     2–4 timestamped evidence items per dimension
                                             │
                                             ▼
             weighted score ─► thresholds (calibrated on the labelled samples)
             cross-checked against the model's holistic label ─► final label + confidence
```

Rubric (weights in `core/rubric.py`): student engagement 20%, interaction & questioning 15%, clarity of explanation 15%, structure & pacing 10%, teacher energy & warmth 10%, use of screen & activities 10%, checking understanding 10%, management & technical quality 10%.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # also needs ffmpeg on PATH
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # add your Gemini key
streamlit run app.py
```

## Calibrate on the sample recordings

Put the samples in `samples/` (git-ignored) with the label in the file or folder name, or supply a `labels.csv` (`filename,label`):

```bash
GEMINI_API_KEY=... python calibrate.py samples/ [labels.csv]
```

This writes `calibration.json` (thresholds + per-label average scores, numbers only) and prints how well the system matches the given labels. The app picks it up automatically, and the per-label profiles are fed to the model as reference points.

## Deploy (Streamlit Community Cloud)

1. Push this repo to GitHub (it can be private). No recordings or secrets are committed.
2. On share.streamlit.io, create an app from `app.py`. `packages.txt` installs ffmpeg.
3. Under app **Secrets**, paste the contents of `secrets.toml.example` with real values. `APP_PASSWORD` gates the app so only evaluators can use it.

## Data handling

- Recordings are written only to a temp folder and deleted after each run.
- The uploaded copy is deleted from Gemini once the assessment returns.
- Use a **paid-tier** Gemini API key. Free-tier traffic can be used by Google to improve products.
- The prompt tells the model never to name children ("Student A", …) and not to describe their appearance.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI (upload or link, results view, JSON export) |
| `core/signals.py` | ffmpeg measurements and compression |
| `core/analyzer.py` | Gemini prompt, response schema, upload/cleanup |
| `core/scoring.py` | weighted score, thresholds, disagreement check |
| `core/rubric.py` | dimensions, weights, default thresholds |
| `calibrate.py` | fits thresholds on the labelled samples |
