# Testing

```bash
python -m pytest -q                   # code-level tests, fake Gemini and fake classifier
python check_gemini.py                # LIVE Gemini check (needs your key)
python evaluation/eval_emotion.py     # measures the current emotion pipeline on evaluation/dataset.csv
```
Results are reported as Passed / Failed / Skipped / Not run in AURA_IMPROVEMENT_REPORT.md. Browser-only behaviour (animations, mic, camera,
layout, accessibility with a screen reader) must be checked manually; a manual checklist is the "Not run" list in that report.

## Emotion evaluation plan
1. Collect 50+ sentences per language (English, Urdu, Roman Urdu) written/labelled by people other than the model author.
2. Run `eval_emotion.py`; record accuracy, abstention rate and per-class confusion; keep the CSV in version control.
3. Report per-language numbers separately; never claim equal accuracy across languages.
