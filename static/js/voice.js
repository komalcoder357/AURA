/* Browser speech: recognition (Web Speech API) and synthesis. Nothing here talks to AURA's server. */
(function () {
  const A = (window.Aura = window.Aura || {});
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const synth = window.speechSynthesis;
  const state = { speaking: false };
  let voiceList = [];

  function loadVoices() {
    return new Promise((resolve) => {
      if (!synth) return resolve([]);
      voiceList = synth.getVoices();
      if (voiceList.length) return resolve(voiceList);
      let done = false;
      const finish = () => { if (done) return; done = true; voiceList = synth.getVoices(); resolve(voiceList); };
      synth.addEventListener("voiceschanged", finish, { once: true });
      setTimeout(finish, 1500);
    });
  }
  const GOOD_NAMES = /(female|zira|samantha|jenny|aria|hazel|susan|libby|sonia|natasha|google uk english female|karen|moira|tessa|ava)/i;
  function pickVoice(savedName, langPrefix) {
    const list = synth ? (voiceList.length ? voiceList : synth.getVoices()) : [];
    if (savedName) { const v = list.find((x) => x.name === savedName); if (v) return v; }
    const same = list.filter((x) => x.lang.toLowerCase().startsWith(langPrefix));
    return same.find((x) => GOOD_NAMES.test(x.name)) || same[0] || null;
  }
  function langPrefixFor(text, settings) {
    if (/[\u0600-\u06FF]/.test(text)) return "ur";
    return "en";
  }
  function chunks(text) {
    const parts = text.replace(/\s+/g, " ").match(/[^.!?۔؟]+[.!?۔؟]*\s*/g) || [text];
    const out = []; let cur = "";
    parts.forEach((p) => { if ((cur + p).length > 180 && cur) { out.push(cur); cur = p; } else cur += p; });
    if (cur.trim()) out.push(cur);
    return out;
  }
  // Speak text with the saved voice/speed/volume. handlers: onStart (real playback began), onEnd (finished / cancelled / failed)
  function speak(text, handlers) {
    handlers = handlers || {};
    if (!synth) return { ok: false, reason: "Speech output isn't supported in this browser." };
    const s = (A.settings && A.settings.data) || {};
    const prefix = langPrefixFor(text, s);
    const voice = pickVoice(s.voice_name, prefix);
    if (!voice || !voice.lang.toLowerCase().startsWith(prefix)) {
      return { ok: false, reason: prefix === "ur" ? "No Urdu voice is installed on this device, so I can't speak Urdu aloud." : "No English voice was found on this device." };
    }
    synth.cancel();
    const parts = chunks(text);
    let started = false, finished = false;
    const end = () => { if (finished) return; finished = true; state.speaking = false; if (handlers.onEnd) handlers.onEnd(); };
    parts.forEach((part, i) => {
      const u = new SpeechSynthesisUtterance(part);
      u.voice = voice; u.lang = voice.lang; u.rate = s.voice_rate || 1; u.volume = s.voice_volume == null ? 1 : s.voice_volume;
      u.onstart = () => { if (!started) { started = true; state.speaking = true; if (handlers.onStart) handlers.onStart(); } };
      u.onend = () => { if (i === parts.length - 1) end(); };
      u.onerror = () => end();
      synth.speak(u);
    });
    return { ok: true };
  }
  function cancelSpeech() { if (synth) synth.cancel(); state.speaking = false; }

  const ERRORS = {
    "not-allowed": "Microphone permission was denied. Allow it in your browser's site settings, or type instead.",
    "service-not-allowed": "Speech recognition isn't allowed in this browser. Please type instead.",
    "no-speech": "I didn't hear anything. Tap the microphone and try again.",
    "audio-capture": "No microphone was found. Check that one is connected.",
    network: "Speech recognition needs an internet connection and the network failed. Try again or type instead.",
    "language-not-supported": "This browser doesn't support that speech language. Choose another in Voice preferences.",
  };
  // Returns a controller. onFinal is called exactly once per session with the final transcript (possibly empty).
  function recognizer(opts) {
    if (!SR) return null;
    const rec = new SR();
    rec.lang = opts.lang; rec.interimResults = true; rec.continuous = false; rec.maxAlternatives = 1;
    let finalText = "", interim = "", settled = false, errored = false, noSpeechTimer = null;
    const settle = () => { if (settled) return; settled = true; clearTimeout(noSpeechTimer); opts.onEnd(errored ? "" : (finalText || interim).trim(), errored); };
    rec.onstart = () => { opts.onStart(); noSpeechTimer = setTimeout(() => { try { rec.stop(); } catch (e) {} }, 12000); };
    rec.onresult = (e) => {
      finalText = ""; interim = "";
      for (let i = 0; i < e.results.length; i++) {
        if (e.results[i].isFinal) finalText += e.results[i][0].transcript; else interim += e.results[i][0].transcript;
      }
      opts.onText(finalText, interim);
    };
    rec.onerror = (e) => { if (e.error === "aborted") return; errored = true; opts.onError(ERRORS[e.error] || "Voice input failed (" + e.error + ").", e.error); };
    rec.onend = settle;
    return {
      start() { rec.start(); },
      stop() { try { rec.stop(); } catch (e) {} },
      abort() { settled = true; clearTimeout(noSpeechTimer); try { rec.abort(); } catch (e) {} },
    };
  }
  A.voice = { supported: !!SR, ttsSupported: !!synth, state, voices: loadVoices, pickVoice, speak, cancelSpeech, recognizer };
})();
