# Limitations and what is verified

See AURA_IMPROVEMENT_REPORT.md section 3 for the full Passed / Not run lists.

## Verified by automated tests (fakes, no network): 94 pytest + 37 jsdom UI checks
## NOT verified: real browsers, real microphone/camera/speech, live Gemini, real emotion model, visual design, animations, screen readers.

## Known limits
- No facial-expression model exists in AURA. The webcam demo shows a preview and, only where the browser supports FaceDetector, a face count. It never shows emotion from a face.
- Text emotion: English uses j-hartmann/emotion-english-distilroberta-base (raw softmax scores, not calibrated, intensity not estimated). Urdu/Roman Urdu use an experimental keyword list (no confidence) unless you configure EMOTION_MODEL_MULTI after reading its model card.
- Distress-related signal = share of negative labels in recent messages: heuristic, not validated, not a diagnosis.
- Safety screen is pattern-based (direct, indirect, idiom exclusions). It will miss cases and over-flag some; it is not a risk assessment. Add verified local helpline text via SAFETY_RESOURCES.
- Memory: saved only when the user explicitly asks or adds it; retrieval is keyword overlap.
- Voice: Web Speech API (Chrome/Edge best). Chrome may send audio to its speech service. Urdu recognition/voices depend on the device. No server-side speech-to-text fallback. AURA cannot know which installed voice sounds "cute".
- Fonts load from Google Fonts (needs internet); otherwise system fonts are used.
- Login throttle is in-memory per process. SQLite only (models are PostgreSQL-friendly).
