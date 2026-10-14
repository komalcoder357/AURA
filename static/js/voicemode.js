/* Voice mode: microphone -> recognition -> transcript -> chat (streamed) -> reply -> speech.
   Explicit state machine: idle | listening | transcribing | thinking | speaking | error | closed. */
(function () {
  const A = (window.Aura = window.Aura || {});
  const screen = A.$("#voiceScreen"), mascot = A.$("#voiceMascot"), statusEl = A.$("#vsStatus"), errEl = A.$("#vsError");
  const youEl = A.$("#vsYou"), replyEl = A.$("#vsReply"), editEl = A.$("#vsEdit");
  const micBtn = A.$("#vsMic"), micLabel = A.$("#vsMicLabel"), sendBtn = A.$("#vsSend"), muteBtn = A.$("#vsMute");
  const GREETING = { "en-US": "Hey! I'm AURA. How are you feeling today?", "ur-PK": "ہائے! میں آورا ہوں۔ آج آپ کیسا محسوس کر رہے ہیں؟" };
  const LABEL = { idle: "Tap the microphone to talk", listening: "Listening…", transcribing: "Review what I heard", thinking: "Thinking…", speaking: "Speaking…", error: "Something went wrong" };
  const MASCOT = { idle: "idle", listening: "listening", transcribing: "attentive", thinking: "processing", speaking: "speaking", error: "concerned", closed: "idle" };
  let state = "closed", rec = null, abort = null, muted = false, submitting = false, turns = 0, timeout = null;
  const prefs = () => (A.settings && A.settings.data) || {};

  function setState(s, text) {
    state = s;
    A.mascot.set(mascot, MASCOT[s] || "idle");
    statusEl.textContent = text || LABEL[s] || "";
    micBtn.setAttribute("aria-pressed", String(s === "listening"));
    micLabel.textContent = s === "listening" ? "Stop listening" : "Talk";
    sendBtn.hidden = s !== "transcribing";
    editEl.hidden = s !== "transcribing"; youEl.hidden = s === "transcribing";
    if (s !== "error") { errEl.hidden = true; errEl.textContent = ""; }
  }
  function showError(msg) { setState("error"); errEl.textContent = msg; errEl.hidden = false; }

  function speakText(text, after) {
    const p = prefs();
    if (muted || p.voice_responses === false) { setState("idle"); if (after) after(); return; }
    const r = A.voice.speak(text, {
      onStart: () => setState("speaking"),
      onEnd: () => { if (state === "speaking") setState("idle"); if (after) after(); },
    });
    if (!r.ok) { setState("idle"); A.toast(r.reason); if (after) after(); }
  }

  function startListening() {
    if (!A.voice.supported) return showError("Voice input isn't supported in this browser. Chrome or Edge work best. You can close voice mode and type instead.");
    if (state === "thinking") return;
    A.voice.cancelSpeech(); stopRec();
    youEl.textContent = "…"; editEl.value = "";
    rec = A.voice.recognizer({
      lang: prefs().voice_lang || "en-US",
      onStart: () => setState("listening"),
      onText: (fin, interim) => { youEl.textContent = (fin + " " + interim).trim() || "…"; },
      onError: (msg) => showError(msg),
      onEnd: (text, errored) => {
        rec = null;
        if (errored || state === "closed" || state === "error") return;
        if (!text) return showError("I didn't catch anything. Tap the microphone and try again, or type instead.");
        youEl.textContent = text;
        if (prefs().voice_auto_submit === false) { editEl.value = text; setState("transcribing"); editEl.focus(); }
        else submit(text);
      },
    });
    try { rec.start(); } catch (e) { rec = null; showError("Couldn't start the microphone. Please try again."); }
  }
  function stopRec() { if (rec) { rec.abort(); rec = null; } }

  async function submit(text) {
    text = (text || "").trim();
    if (submitting) return;                       // never submit the same transcript twice
    if (!text) return showError("There's nothing to send yet.");
    submitting = true; youEl.textContent = text; replyEl.textContent = "…";
    setState("thinking");
    abort = new AbortController();
    timeout = setTimeout(() => abort && abort.abort("timeout"), 60000);
    let reply = "";
    try {
      const { done } = await A.chat.runTurn({ conversation_id: A.chat.state.conversationId, message: text }, {
        onDelta: (t) => { reply += t; replyEl.textContent = reply; },
      }, abort.signal);
      turns++;
      const src = done.assistant_message.source;
      replyEl.textContent = done.assistant_message.content;
      if (src === "gemini") speakText(done.assistant_message.content);
      else { showError(src === "fallback" ? "AI replies are unavailable right now. Close voice mode and use Retry in the chat, or try again later." : "I couldn't finish that reply."); if (src === "safety_template") speakText(done.assistant_message.content); }
    } catch (e) {
      if (state === "closed") return;
      if (e.name === "AbortError") { if (abort && abort.signal.reason === "timeout") showError("That took too long. Please try again."); else setState("idle"); }
      else showError("Couldn't get a reply: " + e.message + ". Check your connection, or close voice mode and type instead.");
    } finally { clearTimeout(timeout); submitting = false; abort = null; }
  }

  function stopAll() {            // the Stop button: stops mic, request and speech; calm idle state
    stopRec(); A.voice.cancelSpeech(); if (abort) abort.abort();
    if (state !== "closed") setState("idle");
  }
  function open() {
    if (state !== "closed") return;
    screen.hidden = false; muted = false; muteBtn.setAttribute("aria-pressed", "false"); muteBtn.textContent = "🔊 Mute";
    youEl.textContent = "…"; replyEl.textContent = "…"; turns = 0;
    setState("idle"); A.mascot.set(mascot, "greeting");
    const p = prefs(), greet = GREETING[p.voice_lang] || GREETING["en-US"];
    if (p.voice_greeting !== false) {
      replyEl.textContent = greet;
      if (p.voice_responses !== false) {
        const r = A.voice.speak(greet, { onStart: () => setState("speaking"), onEnd: () => { if (state === "speaking") setState("idle"); } });
        if (!r.ok) { A.toast(r.reason); setTimeout(() => state === "idle" && A.mascot.set(mascot, "idle"), 2600); }
      } else setTimeout(() => state === "idle" && A.mascot.set(mascot, "idle"), 2600);
    } else setTimeout(() => state === "idle" && A.mascot.set(mascot, "idle"), 1500);
    micBtn.focus();
  }
  function close() {
    if (state === "closed") return;
    stopRec(); A.voice.cancelSpeech(); if (abort) abort.abort();
    clearTimeout(timeout); submitting = false;
    state = "closed"; screen.hidden = true;
    if (turns > 0 && A.chat.state.conversationId) A.chat.load(A.chat.state.conversationId).catch(() => {});
    A.$("#voiceBtn").focus();
  }

  micBtn.addEventListener("click", () => { if (state === "listening") { if (rec) rec.stop(); } else startListening(); });
  sendBtn.addEventListener("click", () => submit(editEl.value));
  A.$("#vsStop").addEventListener("click", stopAll);
  A.$("#vsClose").addEventListener("click", close);
  muteBtn.addEventListener("click", () => {
    muted = !muted; muteBtn.setAttribute("aria-pressed", String(muted)); muteBtn.textContent = muted ? "🔇 Unmute" : "🔊 Mute";
    if (muted) { A.voice.cancelSpeech(); if (state === "speaking") setState("idle"); }
  });
  A.$("#vsSettings").addEventListener("click", () => A.openDialog("dlgVoice"));
  A.$("#voiceBtn").addEventListener("click", open);
  screen.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.preventDefault(); close(); return; }
    if (e.key === "Tab") {      // keep focus inside the voice screen
      const f = [...screen.querySelectorAll("button:not([hidden]), textarea:not([hidden])")].filter((x) => !x.disabled);
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  window.addEventListener("pagehide", () => { stopRec(); A.voice.cancelSpeech(); });
  A.voicemode = { open, close, getState: () => state };
})();
