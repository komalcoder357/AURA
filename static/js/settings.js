(function () {
  const A = (window.Aura = window.Aura || {});
  const html = document.documentElement;
  const THEME_NAMES = { "baby-pink": "Baby Pink", lavender: "Lavender", mint: "Mint Green", peach: "Peach", sky: "Sky Pastel", neutral: "Neutral Warm" };
  const state = { data: null, profile: null, savedColors: null, draft: null, walkAnim: null, pendingMode: null };

  /* ---------- helpers ---------- */
  const store = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
  async function patch(change) {
    try { const r = await A.api("/api/settings", { method: "PATCH", body: change }); state.data = r.settings; A.settings.data = r.settings; return r.settings; }
    catch (e) { A.toast(e.message); throw e; }
  }
  function hexToRgb(h) { h = h.replace("#", ""); return [0, 2, 4].map((i) => parseInt(h.substr(i, 2), 16)); }
  function lum(h) { const c = hexToRgb(h).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; }
  function contrast(a, b) { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
  function mix(a, b, t) { const x = hexToRgb(a), y = hexToRgb(b); return "#" + x.map((v, i) => Math.round(v * t + y[i] * (1 - t)).toString(16).padStart(2, "0")).join(""); }
  const HEX = /^#[0-9a-fA-F]{6}$/;

  /* ---------- theme + mode ---------- */
  function fade() { html.classList.add("theme-fade"); setTimeout(() => html.classList.remove("theme-fade"), 700); }
  function applyTheme(t) {
    html.dataset.theme = t; store("aura.theme", t);
    document.querySelectorAll("[data-theme-choice]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.themeChoice === t)));
    A.$("#profTheme").textContent = (THEME_NAMES[t] || t) + (html.dataset.custom === "1" ? " + custom colours" : "") + (html.dataset.mode === "dark" ? " (dark)" : "");
  }
  function applyMode(m) {
    fade(); html.dataset.mode = m; store("aura.mode", m);
    document.querySelectorAll("[data-mode-choice]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.modeChoice === m)));
    positionWalker(m); applyTheme(html.dataset.theme);
  }
  function applyMotion(reduced) {
    if (reduced) html.dataset.motion = "reduced"; else delete html.dataset.motion;
    store("aura.motion", reduced ? "reduced" : "normal");
  }

  /* ---------- walking mascot switch ---------- */
  const track = A.$("#modeSwitch"), walker = A.$("#modeWalker");
  function destCenter(mode) {
    const d = A.$(mode === "dark" ? "#destDark" : "#destLight").getBoundingClientRect(), t = track.getBoundingClientRect();
    return { x: d.left - t.left + d.width / 2, y: d.top - t.top + d.height / 2, r: d.width / 2 };
  }
  function positionWalker(mode) {
    if (!track.offsetWidth) return;
    const c = destCenter(mode || html.dataset.mode || "light");
    walker.style.left = (c.x - walker.offsetWidth / 2) + "px"; walker.style.top = (c.y - walker.offsetHeight / 2) + "px";
  }
  function setMode(to) {
    const from = html.dataset.mode || "light";
    if (state.walkAnim) { state.walkAnim.cancel(); state.walkAnim = null; if (state.pendingMode) applyMode(state.pendingMode); }
    if (to === from && !state.pendingMode) return;
    patch({ appearance: to }).catch(() => {});                       // saved immediately, independent of the animation
    if (A.reducedMotion() || !walker.animate || !track.offsetWidth) { applyMode(to); return; }
    try {
      const a = destCenter(from), b = destCenter(to), D = b.x - a.x, s = Math.sign(D) || 1, r = a.r;
      const p1 = s * (r + 6), p2 = p1 + s * 20, p3 = p2 + s * 20;
      const pts = [[0, 0], [p1 / 2, -14], [p1, 0], [(p1 + p2) / 2, -10], [p2, 0], [(p2 + p3) / 2, -10], [p3, 0], [(p3 + D) / 2, -52], [D, 0]];
      const frames = pts.map((p, i) => ({ transform: "translate(" + p[0] + "px," + p[1] + "px)", offset: i / (pts.length - 1), easing: "ease-in-out" }));
      state.pendingMode = to;
      A.mascot.set(walker, "walking");
      let applied = false;
      const finish = () => {
        if (applied) return; applied = true; state.walkAnim = null; state.pendingMode = null;
        applyMode(to); A.mascot.pulse(walker, "happy", 1200, "idle");
      };
      const anim = walker.animate(frames, { duration: 1500, fill: "none" });
      state.walkAnim = anim;
      anim.finished.then(finish).catch(() => {});
      setTimeout(finish, 1900);                                       // the theme is applied even if the animation stalls
    } catch (e) { state.pendingMode = null; applyMode(to); }
  }

  /* ---------- custom colours ---------- */
  const FALLBACK_PICKS = { bg: "#FFF5F8", accent: "#B8426D", card: "#FFFFFF", text: "#4A3A41" };
  const DEFAULT_PICKS = () => {
    const cs = getComputedStyle(html), g = (v, k) => { const x = cs.getPropertyValue(v).trim(); return HEX.test(x) ? x : FALLBACK_PICKS[k]; };
    return { bg: g("--bg", "bg"), accent: g("--accent-strong", "accent"), card: g("--surface", "card"), text: g("--text", "text") };
  };
  function deriveVars(c) {
    const on = contrast("#ffffff", c.accent) >= contrast("#111111", c.accent) ? "#ffffff" : "#111111";
    return { "--bg": c.bg, "--surface": c.card, "--text": c.text, "--accent": c.accent, "--accent-strong": c.accent, "--on-accent": on,
      "--surface-2": mix(c.accent, c.card, 0.14), "--accent-soft": mix(c.accent, c.card, 0.3), "--muted": mix(c.text, c.bg, 0.72),
      "--border": mix(c.accent, c.bg, 0.28), "--bubble-user": mix(c.accent, c.card, 0.3), "--mascot-body": mix(c.accent, "#ffffff", 0.35), "--mascot-ear": mix(c.accent, "#ffffff", 0.6) };
  }
  function clearCustomVars() { ["--bg", "--surface", "--text", "--accent", "--accent-strong", "--on-accent", "--surface-2", "--accent-soft", "--muted", "--border", "--bubble-user", "--mascot-body", "--mascot-ear"].forEach((v) => html.style.removeProperty(v)); }
  function preview(c) { const v = deriveVars(c); html.dataset.custom = "1"; Object.keys(v).forEach((k) => html.style.setProperty(k, v[k])); }
  function readInputs() { const c = {}; ["bg", "accent", "card", "text"].forEach((k) => { c[k] = A.$('[data-color-hex="' + k + '"]').value.trim(); }); return c; }
  function fillInputs(c) { ["bg", "accent", "card", "text"].forEach((k) => { A.$('[data-color-hex="' + k + '"]').value = c[k].toUpperCase(); A.$('[data-color-picker="' + k + '"]').value = c[k].toLowerCase(); }); }
  function validateDraft(c) {
    const note = A.$("#contrastNote"), apply = A.$("#colorApply");
    const bad = ["bg", "accent", "card", "text"].filter((k) => !HEX.test(c[k]));
    if (bad.length) { note.textContent = "Enter valid HEX colours like #FFAABB (" + bad.join(", ") + ")."; apply.disabled = true; return false; }
    const a = contrast(c.text, c.card), b = contrast(c.text, c.bg);
    if (a < 4.5 || b < 4.5) { note.textContent = "Text contrast is too low (" + Math.min(a, b).toFixed(1) + ":1). At least 4.5:1 is needed to stay readable."; apply.disabled = true; return false; }
    note.textContent = "Contrast OK (" + Math.min(a, b).toFixed(1) + ":1)."; apply.disabled = false; return true;
  }
  function onColorInput(key, value, fromPicker) {
    if (fromPicker) A.$('[data-color-hex="' + key + '"]').value = value.toUpperCase();
    else if (HEX.test(value)) A.$('[data-color-picker="' + key + '"]').value = value.toLowerCase();
    const c = readInputs();
    if (validateDraft(c)) { state.draft = c; preview(c); }
  }
  function restoreSaved() {
    clearCustomVars();
    if (state.savedColors) preview(state.savedColors); else delete html.dataset.custom;
    applyTheme(html.dataset.theme);
  }
  function openColors() {
    const c = state.savedColors || DEFAULT_PICKS(); fillInputs(c); state.draft = null; validateDraft(readInputs());
  }

  /* ---------- profile ---------- */
  function setAvatarEls(url, initials) {
    ["#avatar", "#profAvatar"].forEach((sel) => {
      const el = A.$(sel); el.textContent = "";
      if (url) { const img = document.createElement("img"); img.src = url; img.alt = ""; el.appendChild(img); } else el.textContent = initials;
    });
    A.$("#avatarRemove").hidden = !url;
  }
  function showProfile(p) {
    state.profile = p;
    A.$("#accountName").textContent = p.display_name; A.$("#nameInput").value = p.display_name;
    A.$("#profEmail").textContent = p.email; A.$("#nameSave").disabled = true;
    setAvatarEls(p.avatar_url, p.initials);
  }

  /* ---------- voices ---------- */
  async function fillVoices() {
    const sel = A.$("#setVoiceName"), voices = await A.voice.voices();
    sel.textContent = "";
    const auto = document.createElement("option"); auto.value = ""; auto.textContent = "Automatic (best available for the language)"; sel.appendChild(auto);
    voices.slice().sort((a, b) => a.lang.localeCompare(b.lang) || a.name.localeCompare(b.name)).forEach((v) => {
      const o = document.createElement("option"); o.value = v.name; o.textContent = v.name + " (" + v.lang + ")"; sel.appendChild(o);
    });
    A.$("#voiceCount").textContent = voices.length ? "(" + voices.length + " available on this device)" : "(none found: speech output isn't available here)";
    sel.value = (state.data && state.data.voice_name) || "";
    if (sel.value !== ((state.data && state.data.voice_name) || "")) sel.value = "";
  }

  /* ---------- load + wire ---------- */
  function fillFromData(d) {
    A.$("#setLanguage").value = d.language; A.$("#setStyle").value = d.response_style; A.$("#setVoiceLang").value = d.voice_lang;
    A.$("#setAutoSpeak").checked = d.auto_speak; A.$("#setVoiceResponses").checked = d.voice_responses; A.$("#setVoiceGreeting").checked = d.voice_greeting;
    A.$("#setVoiceAuto").checked = d.voice_auto_submit; A.$("#setReduceMotion").checked = d.reduce_motion;
    A.$("#setVoiceRate").value = d.voice_rate; A.$("#rateOut").textContent = d.voice_rate.toFixed(1) + "×";
    A.$("#setVoiceVolume").value = d.voice_volume; A.$("#volOut").textContent = Math.round(d.voice_volume * 100) + "%";
  }
  async function load() {
    const r = await A.api("/api/settings");
    state.data = r.settings; A.settings.data = r.settings; state.savedColors = r.settings.custom_colors;
    if (r.settings.custom_colors) { preview(r.settings.custom_colors); } else { clearCustomVars(); delete html.dataset.custom; }
    html.dataset.mode = r.settings.appearance; store("aura.mode", r.settings.appearance);
    applyTheme(r.settings.theme); applyMotion(r.settings.reduce_motion);
    document.querySelectorAll("[data-mode-choice]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.modeChoice === r.settings.appearance)));
    fillFromData(r.settings); showProfile(r.profile); positionWalker(r.settings.appearance);
  }

  document.querySelectorAll("[data-theme-choice]").forEach((b) => b.addEventListener("click", () => { fade(); applyTheme(b.dataset.themeChoice); patch({ theme: b.dataset.themeChoice }); }));
  document.querySelectorAll("[data-mode-choice]").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.modeChoice)));
  document.querySelectorAll("[data-color-picker]").forEach((i) => i.addEventListener("input", () => onColorInput(i.dataset.colorPicker, i.value, true)));
  document.querySelectorAll("[data-color-hex]").forEach((i) => i.addEventListener("input", () => onColorInput(i.dataset.colorHex, i.value.trim(), false)));
  A.$("#colorApply").addEventListener("click", async () => {
    const c = readInputs(); if (!validateDraft(c)) return;
    const lower = {}; Object.keys(c).forEach((k) => (lower[k] = c[k].toLowerCase()));
    try { await patch({ custom_colors: lower }); state.savedColors = lower; preview(lower); applyTheme(html.dataset.theme); A.toast("Custom colours saved."); } catch (e) { /* toast shown */ }
  });
  A.$("#colorCancel").addEventListener("click", () => { restoreSaved(); openColors(); });
  A.$("#colorReset").addEventListener("click", async () => {
    try { await patch({ custom_colors: null }); state.savedColors = null; clearCustomVars(); delete html.dataset.custom; applyTheme(html.dataset.theme); openColors(); A.toast("Colours reset to the theme default."); } catch (e) { /* toast shown */ }
  });
  A.$("#dlgAppearance").addEventListener("aura:open", () => { openColors(); requestAnimationFrame(() => positionWalker(html.dataset.mode)); });
  A.$("#dlgAppearance").addEventListener("close", restoreSaved);      // unsaved previews never stick
  window.addEventListener("resize", () => positionWalker(html.dataset.mode));
  A.$("#setReduceMotion").addEventListener("change", (e) => { applyMotion(e.target.checked); patch({ reduce_motion: e.target.checked }); });

  A.$("#setLanguage").addEventListener("change", (e) => patch({ language: e.target.value }));
  A.$("#setStyle").addEventListener("change", (e) => patch({ response_style: e.target.value }));
  A.$("#setVoiceLang").addEventListener("change", (e) => patch({ voice_lang: e.target.value }));
  A.$("#setAutoSpeak").addEventListener("change", (e) => patch({ auto_speak: e.target.checked }));
  A.$("#setVoiceResponses").addEventListener("change", (e) => patch({ voice_responses: e.target.checked }));
  A.$("#setVoiceGreeting").addEventListener("change", (e) => patch({ voice_greeting: e.target.checked }));
  A.$("#setVoiceAuto").addEventListener("change", (e) => patch({ voice_auto_submit: e.target.checked }));
  A.$("#setVoiceName").addEventListener("change", (e) => patch({ voice_name: e.target.value }));
  let rateT = null;
  A.$("#setVoiceRate").addEventListener("input", (e) => { A.$("#rateOut").textContent = Number(e.target.value).toFixed(1) + "×"; clearTimeout(rateT); rateT = setTimeout(() => patch({ voice_rate: Number(e.target.value) }), 300); });
  let volT = null;
  A.$("#setVoiceVolume").addEventListener("input", (e) => { A.$("#volOut").textContent = Math.round(e.target.value * 100) + "%"; clearTimeout(volT); volT = setTimeout(() => patch({ voice_volume: Number(e.target.value) }), 300); });
  A.$("#dlgVoice").addEventListener("aura:open", fillVoices);
  A.$("#voiceStop").addEventListener("click", () => A.voice.cancelSpeech());
  A.$("#voiceTest").addEventListener("click", () => {
    const urdu = (state.data && state.data.voice_lang) === "ur-PK";
    const r = A.voice.speak(urdu ? "ہائے! میں آورا ہوں۔ میری آواز ایسی ہے۔" : "Hi! I'm AURA. This is how I sound.");
    if (!r.ok) A.toast(r.reason);
  });

  const nameInput = A.$("#nameInput"), nameSave = A.$("#nameSave"), nameErr = A.$("#nameError");
  nameInput.addEventListener("input", () => { const v = nameInput.value.trim(); nameSave.disabled = !v || v === (state.profile && state.profile.display_name); nameErr.textContent = !v ? "Name cannot be empty." : ""; });
  nameSave.addEventListener("click", async () => {
    nameSave.disabled = true;
    try { const r = await A.api("/api/profile", { method: "PATCH", body: { display_name: nameInput.value } }); showProfile(Object.assign({}, state.profile, r)); nameErr.textContent = ""; A.toast("Name updated."); }
    catch (e) { nameErr.textContent = e.message; nameSave.disabled = false; }
  });
  A.$("#avatarEdit").addEventListener("click", () => A.$("#avatarFile").click());
  A.$("#avatarFile").addEventListener("change", async (e) => {
    const f = e.target.files[0]; e.target.value = "";
    if (!f) return;
    if (f.size > 300 * 1024) return A.toast("Image is too large (max 300 KB).");
    const fd = new FormData(); fd.append("avatar", f);
    try { const r = await A.upload("/api/profile/avatar", fd); state.profile.avatar_url = r.avatar_url; setAvatarEls(r.avatar_url, state.profile.initials); A.toast("Profile picture updated."); } catch (err) { A.toast(err.message); }
  });
  A.$("#avatarRemove").addEventListener("click", async () => {
    try { await A.api("/api/profile/avatar", { method: "DELETE" }); state.profile.avatar_url = null; setAvatarEls(null, state.profile.initials); } catch (e) { A.toast(e.message); }
  });

  A.settings = { data: null, load, applyTheme, applyMode, setMode, deriveVars, contrast };
})();
