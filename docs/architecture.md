# Architecture

Request flow for `POST /api/chat`:
1. Validate + detect language (`en`, `ur`, `roman_ur`, `mixed`) and normalise.
2. Emotion analysis once per message (HF model for English; experimental lexicon or configured multilingual model otherwise).
3. Safety screen, then distress heuristic over recent stored observations.
4. `decide()` picks a strategy: casual, empathize, support, celebrate, clarify, neutral, safety_support. Reason codes list only rules that fired.
5. Explicit "remember that ..." is saved (if memory is on); relevant memory is retrieved by keyword overlap.
6. Gemini is called with a bounded history (`CONTEXT_MESSAGES`) and a strategy prompt. On failure the reply is a labelled fallback (`fallback` / `safety_template`), never presented as Gemini.
7. Both messages and the analysis JSON are stored; timings (not content) are logged.

Data policy: deleting a conversation deletes its messages and analysis; memory items are separate and are only removed by the memory controls.

Endpoints (all JSON, login + CSRF required): `/api/chat`, `/api/conversations[/<id>]` (GET/PATCH/DELETE), `/api/memory[/<id>]`, `/api/settings`.
Conversation and memory IDs are random UUIDs; every query is filtered by the logged-in user.
