# AURA — Emotion-Aware AI Companion (upgraded)

Flask app: accounts, streamed Gemini chat, voice mode, text-emotion estimates with an honest analysis panel, rule-based
decision engine, layered safety screen, user-controlled memory, chat search, profile/avatar, 6 palettes + dark mode +
custom colours, analytics, and an opt-in webcam preview demo. Glassmorphism UI.

## Upgrade an existing install (keeps your data)
1. Stop the server. **Keep** your `.env` and `instance/` folder (they are not in the zip).
2. Extract this zip over your AURA folder, overwriting files. Then `pip install -r requirements.txt`.
3. Start with `python app.py`. On first start AURA copies `instance/aura.db` to `instance/backups/aura-<time>.db`
   and only ADDS the new columns (nothing is dropped). Your users, password hashes, chats and memory stay.
4. Old theme "Classic White" is mapped to "Neutral Warm".

## Fresh install
```bash
python -m venv venv && venv\Scripts\activate          # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                                 # set SECRET_KEY and GEMINI_API_KEY
python check_gemini.py                                 # confirms the key/model work
python app.py                                          # http://localhost:5000
```
The camera and microphone need **localhost or HTTPS**. Chrome/Edge give the best speech support.

## Tests
```bash
python -m pytest -q                      # 94 code-level tests (fake Gemini + fake classifier; no network)
python evaluation/eval_emotion.py        # measures the CURRENT emotion pipeline on a small starter set
```
See `AURA_IMPROVEMENT_REPORT.md` for exactly what was and was not verified, and `docs/limitations.md`.

## Environment variables
`SECRET_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `DATABASE_URL`, `EMOTION_MODEL_EN`, `EMOTION_MODEL_MULTI`,
`EMOTION_LOAD` (startup|lazy|off), `EMOTION_MIN_CONFIDENCE`, `SAFETY_RESOURCES`, `SESSION_COOKIE_SECURE`. Never commit `.env`.

## Layout
`modules/` language, emotion, decision_engine, distress, safety, memory, ai_service, theme · `routes/` auth, chat, memory, profile,
settings · `migrations.py` additive schema upgrade + backup · `templates/`, `static/css`, `static/js` · `tests/` · `evaluation/` · `docs/`
