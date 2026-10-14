(function () {
  const A = (window.Aura = window.Aura || {});
  const LANGS = { en: "English", ur: "Urdu", roman_ur: "Roman Urdu", mixed: "Mixed", unknown: "Unknown" };
  const STATUS = {
    success: "Success", uncertain: "Uncertain (low confidence)", experimental: "Experimental",
    model_unavailable: "Model unavailable", model_error: "Model error", insufficient_text: "Not enough text",
    no_signal: "No emotion signal found", unavailable: "Unavailable",
  };
  const DISTRESS = { insufficient_data: "Not enough messages yet", low: "Low", moderate: "Moderate", elevated: "Elevated" };
  const KNOWN = ["joy", "sadness", "anger", "fear", "surprise", "disgust", "neutral", "love"];
  const NS = "http://www.w3.org/2000/svg";
  const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
  const mascotStateFor = (strategy) =>
    ({ celebrate: "happy", empathize: "empathetic", support: "empathetic", safety_support: "concerned", neutral: "neutral" }[strategy] || "idle");

  function el(name, attrs, parent) {
    const n = document.createElementNS(NS, name);
    Object.keys(attrs || {}).forEach((k) => n.setAttribute(k, attrs[k]));
    if (parent) parent.appendChild(n);
    return n;
  }

  function drawGraph(obs) {
    const box = A.$("#graph"), note = A.$("#trendNote");
    box.textContent = "";
    const data = obs.slice(-12);
    const W = 300, H = 130, L = 28, R = 8, T = 8, B = 20;
    const svg = el("svg", { viewBox: "0 0 " + W + " " + H });
    box.appendChild(svg);
    [0, 0.5, 1].forEach((v) => {
      const y = T + (1 - v) * (H - T - B);
      el("line", { class: "g-axis", x1: L, x2: W - R, y1: y, y2: y }, svg);
      el("text", { class: "g-label", x: 2, y: y + 3 }, svg).textContent = Math.round(v * 100) + "%";
    });
    if (!data.length) {
      el("text", { class: "g-label", x: W / 2, y: H / 2, "text-anchor": "middle" }, svg).textContent = "No analysed messages yet";
      note.textContent = "";
      return;
    }
    const xs = data.map((_, i) => (data.length === 1 ? (L + W - R) / 2 : L + 8 + (i * (W - L - R - 16)) / (data.length - 1)));
    const yOf = (c) => T + (1 - c) * (H - T - B);
    let d = "";
    data.forEach((o, i) => { if (o.confidence != null) d += (d ? " L" : "M") + xs[i].toFixed(1) + " " + yOf(o.confidence).toFixed(1); });
    if (d) el("path", { class: "g-line", d: d }, svg);
    data.forEach((o, i) => {
      const label = "Turn " + o.turn + ": " + (o.emotion || "no emotion") + (o.confidence != null ? " (" + Math.round(o.confidence * 100) + "% model confidence)" : " (no confidence score)");
      if (o.confidence != null && o.emotion) {
        const c = el("circle", { class: "g-dot emo-" + (KNOWN.indexOf(o.emotion) >= 0 ? o.emotion : "other"), cx: xs[i], cy: yOf(o.confidence), r: 5 }, svg);
        el("title", {}, c).textContent = label;
      } else {
        el("title", {}, el("circle", { class: "g-miss", cx: xs[i], cy: H - B - 4, r: 4 }, svg)).textContent = label;
      }
      el("text", { class: "g-label", x: xs[i], y: H - 6, "text-anchor": "middle" }, svg).textContent = o.turn;
    });
    const seen = [];
    data.forEach((o) => { if (o.emotion && seen.indexOf(o.emotion) < 0) seen.push(o.emotion); });
    if (seen.length) {
      const lg = document.createElement("div");
      lg.className = "legend";
      seen.forEach((e) => {
        const s = document.createElement("span"), dot = document.createElement("i");
        dot.className = "emo-" + (KNOWN.indexOf(e) >= 0 ? e : "other");
        s.appendChild(dot); s.appendChild(document.createTextNode(cap(e))); lg.appendChild(s);
      });
      box.appendChild(lg);
    }
    note.textContent = data.length < 3
      ? "Only " + data.length + " observation" + (data.length === 1 ? "" : "s") + ": too few to show a trend. Hollow circles mean no confidence score."
      : data.length + " analysed turns. Height is the model's confidence in its label, not how strongly you feel it.";
  }

  function update(analysis, decision, distress) {
    if (!analysis) return;
    A.$("#emoEmpty").hidden = true;
    A.$("#emoStats").hidden = false;
    A.$("#emoLabel").textContent = analysis.emotion ? cap(analysis.emotion) : "Not available";
    const c = analysis.emotion_confidence;
    A.$("#emoConf").textContent = c != null ? Math.round(c * 100) + "%" : "Not available";
    A.$("#confBar").style.width = c != null ? Math.round(c * 100) + "%" : "0%";
    A.$("#emoIntensity").textContent = "Not estimated";
    A.$("#distressLevel").textContent = DISTRESS[(distress || analysis.distress || {}).level] || "Not available";
    A.$("#emoLang").textContent = LANGS[analysis.language] || "Unknown";
    let status = STATUS[analysis.analysis_status] || analysis.analysis_status || "Unavailable";
    if (analysis.analysis_method === "lexicon_experimental") status += " (keyword list)";
    A.$("#emoStatus").textContent = status;
    A.$("#strategy").textContent = decision ? cap(decision.strategy.replace("_", " ")) : "–";
    A.$("#reasons").textContent = decision ? decision.reason_codes.join(", ").replace(/_/g, " ") : "";
    A.mascot.set(A.$("#panelMascot"), decision ? mascotStateFor(decision.strategy) : "idle");
  }
  function setSpeed(t) {
    if (!t) return;
    const parts = [];
    if (t.first_chunk != null) parts.push("first text " + t.first_chunk + " ms");
    parts.push("total " + t.total + " ms");
    parts.push("emotion " + t.emotion + " ms");
    A.$("#speedInfo").textContent = parts.join(" · ");
  }
  function setObservations(obs) { drawGraph(obs || []); }
  function reset() {
    A.$("#emoEmpty").hidden = false;
    A.$("#emoStats").hidden = true;
    A.$("#speedInfo").textContent = "–";
    A.mascot.set(A.$("#panelMascot"), "idle");
    setObservations([]);
  }
  A.emotion = { update, setObservations, reset, setSpeed };
})();
