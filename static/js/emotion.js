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

  let conversationObservations = [];
  let faceObservations = [];
  const conversationTimes = new Map();
  let faceSequence = 0;

  function el(name, attrs, parent) {
    const n = document.createElementNS(NS, name);
    Object.keys(attrs || {}).forEach((k) => n.setAttribute(k, attrs[k]));
    if (parent) parent.appendChild(n);
    return n;
  }

  function scoreFor(o) {
    const value = o.source === "webcam" ? o.model_score : o.confidence;
    return Number.isFinite(Number(value)) && value !== null && value !== "" ? Number(value) : null;
  }

  function sourceName(o) {
    return o.source === "webcam" ? "Webcam" : "Conversation";
  }

  function drawGraph(observations) {
    const box = A.$("#graph"), note = A.$("#trendNote");
    if (!box || !note) return;
    box.textContent = "";
    const data = observations.slice(-12);
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

    const xs = data.map((_, i) => data.length === 1 ? (L + W - R) / 2 : L + 8 + (i * (W - L - R - 16)) / (data.length - 1));
    const yOf = (score) => T + (1 - score) * (H - T - B);

    // Draw separate line segments per source so the graph does not imply that
    // webcam model scores and conversation confidence are directly comparable.
    ["conversation", "webcam"].forEach((source) => {
      let segment = [];
      const flush = () => {
        if (segment.length >= 2) {
          const path = segment.map((point, i) => (i ? "L" : "M") + xs[point.index].toFixed(1) + " " + yOf(point.score).toFixed(1)).join(" ");
          el("path", { class: "g-line", d: path }, svg);
        }
        segment = [];
      };
      data.forEach((o, i) => {
        const score = scoreFor(o);
        if ((o.source === "webcam" ? "webcam" : "conversation") === source && score !== null && score >= 0 && score <= 1) segment.push({ index: i, score });
        else flush();
      });
      flush();
    });

    const seen = [];
    data.forEach((o, i) => {
      const score = scoreFor(o);
      const webcam = o.source === "webcam";
      const emotion = o.emotion || "no emotion";
      const scoreLabel = score === null ? "no score" : webcam
        ? "normalized model score " + score.toFixed(3) + " (not calibrated confidence)"
        : Math.round(score * 100) + "% conversation-model confidence";
      const label = sourceName(o) + " — " + emotion + " — " + scoreLabel;
      const xLabel = webcam ? "W" + (o.faceTurn || i + 1) : "C" + (o.turn || i + 1);
      const validScore = score !== null && score >= 0 && score <= 1;
      if (validScore && o.emotion) {
        const circle = el("circle", {
          class: "g-dot emo-" + (KNOWN.indexOf(o.emotion) >= 0 ? o.emotion : "other"),
          cx: xs[i], cy: yOf(score), r: webcam ? 4 : 5,
          "stroke-dasharray": webcam ? "2 2" : "none"
        }, svg);
        el("title", {}, circle).textContent = label;
      } else {
        const hollow = el("circle", { class: "g-miss", cx: xs[i], cy: H - B - 4, r: 4 }, svg);
        el("title", {}, hollow).textContent = label;
      }
      el("text", { class: "g-label", x: xs[i], y: H - 6, "text-anchor": "middle" }, svg).textContent = xLabel;
      if (o.emotion && seen.indexOf(o.emotion) < 0) seen.push(o.emotion);
    });

    if (seen.length) {
      const legend = document.createElement("div");
      legend.className = "legend";
      seen.forEach((emotion) => {
        const span = document.createElement("span"), dot = document.createElement("i");
        dot.className = "emo-" + (KNOWN.indexOf(emotion) >= 0 ? emotion : "other");
        span.appendChild(dot);
        span.appendChild(document.createTextNode(cap(emotion)));
        legend.appendChild(span);
      });
      box.appendChild(legend);
    }
    const hasWebcam = data.some((o) => o.source === "webcam");
    const hasConversation = data.some((o) => o.source !== "webcam");
    note.textContent = data.length + " observations shown (C = conversation, W = webcam). " +
      (hasWebcam && hasConversation
        ? "Webcam normalized model scores and conversation confidence are different measures; compare them separately."
        : hasWebcam
          ? "Webcam score is a normalized model score, not calibrated confidence or a measure of inner emotion."
          : "Conversation score is model confidence in its label, not how strongly a person feels it.");
  }

  function renderGraph() {
    drawGraph(conversationObservations.concat(faceObservations).sort((a, b) => a._time - b._time));
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

  function setObservations(obs) {
    const now = Date.now();
    conversationObservations = (obs || []).map((original, index) => {
      const o = Object.assign({}, original, { source: "conversation" });
      const key = String(o.turn || index + 1) + "|" + String(o.emotion || "") + "|" + String(o.method || o.analysis_method || "");
      if (!conversationTimes.has(key)) conversationTimes.set(key, now - ((obs || []).length - index) * 1000);
      o._time = conversationTimes.get(key);
      return o;
    });
    renderGraph();
  }

  function addFaceObservation(observation) {
    if (!observation || !observation.emotion) return;
    const score = Number(observation.model_score);
    faceSequence += 1;
    faceObservations.push({
      source: "webcam",
      emotion: String(observation.emotion),
      model_score: Number.isFinite(score) ? score : null,
      faceTurn: faceSequence,
      _time: Number(observation.timestamp) || Date.now()
    });
    // Keep webcam samples bounded in memory and let conversation data remain intact.
    if (faceObservations.length > 8) faceObservations = faceObservations.slice(-8);
    renderGraph();
  }

  function reset() {
    A.$("#emoEmpty").hidden = false;
    A.$("#emoStats").hidden = true;
    A.$("#speedInfo").textContent = "–";
    A.mascot.set(A.$("#panelMascot"), "idle");
    conversationObservations = [];
    faceObservations = [];
    conversationTimes.clear();
    faceSequence = 0;
    renderGraph();
  }

  A.emotion = { update, setObservations, addFaceObservation, reset, setSpeed };
})();
