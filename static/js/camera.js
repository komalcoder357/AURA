/* AURA local facial-expression analysis.
   Frames are sent only to the same-origin AURA server for analysis.
   This file does not save or send frames to external AI providers.
*/
(function () {
  "use strict";

  const A = (window.Aura = window.Aura || {});
  const dlg = A.$("#dlgCam");
  const video = A.$("#camVideo");
  const ph = A.$("#camPlaceholder");
  const stateEl = A.$("#camState");
  const anEl = A.$("#camAnalysis");
  const resEl = A.$("#camResult");
  const startB = A.$("#camStart");
  const stopB = A.$("#camStop");
  const pauseB = A.$("#camPause");
  const logoutBtn = A.$("#logoutBtn");

  const st = {
    stream: null, starting: false, timer: null, paused: false, busy: false,
    stopped: true, controller: null, canvas: document.createElement("canvas")
  };

  function setCam(text) { stateEl.textContent = "Camera: " + text; }
  function setAn(text) { anEl.textContent = "Analysis: " + text; }
  function setRes(text) { resEl.textContent = text; }

  function getCsrfToken() {
    const form = logoutBtn && logoutBtn.closest("form");
    const input = form && form.querySelector('input[name="csrf_token"]');
    return input ? input.value : "";
  }

  async function start() {
    if (st.stream || st.starting) return;
    if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCam("Error"); setRes("Camera access requires HTTPS or localhost."); return;
    }
    if (!getCsrfToken()) {
      setCam("Error"); setRes("Security token not found. Refresh AURA and try again."); return;
    }
    st.starting = true; startB.disabled = true;
    setCam("Requesting permission"); ph.textContent = "Waiting for camera permission...";
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" }, audio: false
      });
      if (!dlg.open) { stream.getTracks().forEach((track) => track.stop()); return; }
      st.stream = stream; st.stopped = false; st.paused = false;
      video.srcObject = stream; video.hidden = false; ph.hidden = true;
      await video.play();
      stopB.disabled = false; pauseB.disabled = false; pauseB.textContent = "Pause analysis";
      stream.getVideoTracks().forEach((track) => track.addEventListener("ended", () => stop("The camera was disconnected.")));
      setCam("Active"); setAn("Connecting to local model");
      setRes("Analyzing facial-expression patterns locally...");
      st.timer = setInterval(tick, 1500); tick();
    } catch (error) {
      const messages = {
        NotAllowedError: "Camera permission was denied. Allow camera access in browser settings.",
        NotFoundError: "No camera was found on this device.",
        NotReadableError: "The camera is being used by another app.",
        OverconstrainedError: "The camera does not support the requested settings."
      };
      setCam("Error"); setAn("Not running"); ph.hidden = false; ph.textContent = "Camera is off.";
      setRes(messages[error.name] || "Could not start the camera."); startB.disabled = false;
      if (st.stream) stop();
    } finally { st.starting = false; }
  }

  async function tick() {
    if (st.stopped || st.paused || st.busy || !st.stream || video.readyState < 2 || document.hidden) return;
    st.busy = true;
    let controller;
    try {
      const sourceWidth = video.videoWidth, sourceHeight = video.videoHeight;
      if (!sourceWidth || !sourceHeight) { setAn("Waiting for video"); return; }
      const scale = Math.min(1, 640 / sourceWidth, 480 / sourceHeight);
      const width = Math.max(1, Math.round(sourceWidth * scale));
      const height = Math.max(1, Math.round(sourceHeight * scale));
      st.canvas.width = width; st.canvas.height = height;
      const context = st.canvas.getContext("2d");
      context.drawImage(video, 0, 0, width, height);
      const image = st.canvas.toDataURL("image/jpeg", 0.75);
      controller = new AbortController(); st.controller = controller;
      const response = await fetch("/api/face-expression", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
        body: JSON.stringify({ image }), cache: "no-store", signal: controller.signal
      });
      if (st.stopped || !st.stream) return;
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (response.status === 401) { setAn("Login required"); setRes("Please log in again to use facial-expression analysis."); }
        else if (response.status === 400) { setAn("Request rejected"); setRes(data.error || "The request was rejected. Refresh AURA and try again."); }
        else { setAn("Unavailable"); setRes(data.error || "The local expression API is unavailable."); }
        return;
      }
      if (!data.face_detected || !data.expressions?.length) {
        setAn("Face not found"); setRes(data.message || "No face detected. Try better lighting and face the camera."); return;
      }
      const results = data.expressions.map((item, index) => {
        const label = String(item.expression || "unknown");
        const score = Number(item.model_score);
        const scoreText = Number.isFinite(score) ? ` (normalized model score: ${score.toFixed(3)})` : "";
        return `Face ${index + 1}: ${label}${scoreText}`;
      });

      // Add only the first detected face to the in-memory graph. This does not
      // send emotion observations to the server or add them to chat/distress data.
      if (A.emotion && typeof A.emotion.addFaceObservation === "function") {
        const first = data.expressions[0];
        A.emotion.addFaceObservation({
          emotion: String(first.expression || "unknown"),
          model_score: Number(first.model_score),
          timestamp: Date.now()
        });
      }
      setAn("Expression estimates available");
      setRes(results.join(" | ") + ". These are estimates of visible facial patterns, not proof of actual emotion or a mental-health assessment.");
    } catch (error) {
      if (error.name === "AbortError" || st.stopped) return;
      setAn("Connection error");
      setRes("Could not reach the local AURA API. Make sure AURA is running and refresh the page if needed.");
    } finally {
      if (st.controller === controller) st.controller = null;
      st.busy = false;
    }
  }

  function togglePause() {
    if (!st.stream || st.stopped) return;
    st.paused = !st.paused;
    pauseB.textContent = st.paused ? "Resume analysis" : "Pause analysis";
    setCam(st.paused ? "Paused" : "Active"); setAn(st.paused ? "Paused" : "Running");
    if (st.paused) {
      if (st.controller) st.controller.abort();
      setRes("Analysis paused. The camera preview remains active.");
    } else { setRes("Resuming local facial-expression analysis..."); tick(); }
  }

  function stop(reason) {
    st.stopped = true; st.paused = false;
    if (st.timer) { clearInterval(st.timer); st.timer = null; }
    if (st.controller) { st.controller.abort(); st.controller = null; }
    if (st.stream) { st.stream.getTracks().forEach((track) => track.stop()); st.stream = null; }
    video.srcObject = null; video.hidden = true; ph.hidden = false; ph.textContent = "Camera is off.";
    setCam("Off"); setAn("Not running");
    setRes(reason || "Camera stopped. No new frames will be analyzed.");
    startB.disabled = false; stopB.disabled = true; pauseB.disabled = true; pauseB.textContent = "Pause analysis";
  }

  startB.addEventListener("click", start);
  stopB.addEventListener("click", () => stop());
  pauseB.addEventListener("click", togglePause);
  dlg.addEventListener("close", () => stop());
  window.addEventListener("pagehide", () => stop());
  if (logoutBtn) {
    const logoutForm = logoutBtn.closest("form");
    if (logoutForm) logoutForm.addEventListener("submit", () => stop());
  }
  A.camera = { stop, isActive: () => Boolean(st.stream && !st.stopped) };
})();
