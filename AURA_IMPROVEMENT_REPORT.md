# AURA improvement report

**Scope note.** The upgrade prompts you sent were cut off mid-sentence (the last lines of sections 18/25 are missing), and your
real project folder was not available to me. I therefore upgraded **the AURA codebase built earlier in this conversation**,
not your private copy. Anything specific to code only you have (an old YOLOv8 webcam file, other custom modules) was
not seen or reused.

## 1. Audit of the starting point (what I had built)
Working: auth, streamed-less chat, emotion pipeline, decision engine, memory, 6 themes, search-less sidebar.
Missing / weak vs your prompts: search, profile edit/avatar, custom colours + dark mode, password eye icons + confirm field,
voice screen and reply pipeline, streaming, analytics, webcam module, tiered safety, DB backup/migration, landing page.
Bugs found in my own earlier work during this upgrade (all fixed, with tests): see §4.

## 2. What changed
| Area | Change |
|---|---|
| Data safety | `migrations.py`: backup copy of the SQLite file, then additive `ALTER TABLE` only; "classic"→"neutral" |
| Auth | Eye toggles (all password fields), confirm password, password rule, field errors, generic login error, JSON login with success animation |
| UI | Glassmorphism (blur with solid fallback), Nunito (Google Fonts, system fallbacks), 6 palettes × light/dark, custom colours with HEX, live preview, Apply/Cancel/Reset, contrast check (client + server) |
| Light/Dark | Walking mascot animation (Web Animations API); theme applied by finish-callback **and** a 1.9 s safety timer; immediate when reduced motion/unsupported |
| Profile | Panel (bottom sheet on phones): name edit, avatar upload (content-sniffed, ≤300 KB, private), read-only email, links |
| Mascot | 11 states: idle, greeting, attentive, listening, thinking, speaking, happy, concerned, shy (covers eyes), guiding, walking |
| Voice | Full-screen voice mode + state machine; transcript submitted exactly once; manual review option; mute/stop/exit; settings (voice, speed, volume, greeting, auto-send) |
| Speed | NDJSON streaming with stop/cancel; first-chunk and total timings recorded and shown |
| Search | `/api/search` DB search over own titles + messages, case-insensitive, wildcard-escaped, never sent to Gemini |
| Safety | Tiered detection (direct / indirect / benign idioms excluded); indirect → gentle check-in, direct → safety strategy |
| Webcam | Off by default; permission only on Start; preview + optional browser FaceDetector count; **no expression model**; disclaimer verbatim |
| Analytics | Per-user activity/day, emotion estimates, reply sources, provider errors, latency (stored timings only) |

## 3. Test results
**Passed (run):** 94 pytest code-level tests (auth, isolation, search, profile/avatar, themes/custom colours, streaming incl. cancel/partial,
fallbacks, analytics, safety cases, migration + backup on an old-schema database, CSP/headers). 37 UI checks run in **jsdom** against the
live server (scripts load without errors, send/stream/fallback label, search, rename/profile save, theme + dark + custom colours persist, voice
screen error path, webcam error path/off-by-default, analytics, memory).
**Not run (honest list):**
- Real browser (Chrome/Edge/Firefox/mobile): none available here. Not verified: visual appearance of glass/blur, the walking animation,
  mascot drawings, microphone → recognition → reply → speech end-to-end, real camera permission/tracks release, responsive layouts, screen readers.
- Live Gemini calls (no key here) → latency/before-after speed **not measured**. The app now records and shows its own timings so you can measure.
- Real emotion model (no access to huggingface.co here). `evaluation/eval_emotion.py` reports English as "not run" in my environment.
- Webcam tests 4,5,6,7,10,12,13 need a browser and camera: code written to satisfy them (tracks stopped on Stop, dialog close, pagehide, logout), **unverified**.
- Skipped: custom evaluation of Urdu/Roman Urdu accuracy (keyword list and dataset were both written by me, so any score would be circular).

## 4. Bugs found and fixed during this upgrade
1. Streaming used ORM objects from another DB session (crash) → re-query by id.
2. A missing Gemini SDK/key killed the stream mid-response → now always a labelled fallback; `sdk_not_installed` hint.
3. Migration backup could be taken after the change (backup ran three times) → single backup before any ALTER; test now checks the backup holds the OLD schema.
4. "Why am I so sad" misclassified as a task; "How do I fix this error" must stay a task → rules fixed + tests.
5. Login throttle state leaked between tests.

## 5. Remaining issues / limits
See `docs/limitations.md`. Highlights: no facial-expression model; Urdu/Roman Urdu emotion is experimental; safety screen is pattern-based and misses cases;
voices depend on the device; Google Fonts need internet (fallback fonts otherwise); in-memory login throttle; SQLite only.

## 6. Data preservation
Existing users/hashes/chats/memory are never deleted or rewritten. Only new columns are added; backup in `instance/backups/`.
