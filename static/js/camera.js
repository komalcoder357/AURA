/* Webcam demo. Off by default. Local only: no frame is ever saved, uploaded or logged.
   There is NO expression model: this shows a preview and (if the browser has FaceDetector) a face count. */
(function () {
  const A = (window.Aura = window.Aura || {});
  const dlg = A.$("#dlgCam"), video = A.$("#camVideo"), ph = A.$("#camPlaceholder");
  const stateEl = A.$("#camState"), anEl = A.$("#camAnalysis"), resEl = A.$("#camResult");
  const startB = A.$("#camStart"), stopB = A.$("#camStop"), pauseB = A.$("#camPause");
  const st = { stream: null, starting: false, timer: null, detector: null, paused: false, busy: false };

  function setCam(t) { stateEl.textContent = "Camera: " + t; }
  function setAn(t) { anEl.textContent = "Analysis: " + t; }
  function setRes(t) { resEl.textContent = t; }

  async function start() {
    if (st.stream || st.starting) return;             // never two streams at once
    if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCam("Error"); return setRes("This browser can't open the camera here. Camera access needs HTTPS or localhost (http://127.0.0.1 or http://localhost).");
    }
    st.starting = true; startB.disabled = true; setCam("Requesting permission"); ph.textContent = "Waiting for your permission…";
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" }, audio: false });
      if (!dlg.open) { stream.getTracks().forEach((t) => t.stop()); return; }  // dialog closed while waiting
      st.stream = stream; video.srcObject = stream; video.hidden = false; ph.hidden = true;
      await video.play().catch(() => {});
      stopB.disabled = false; pauseB.disabled = false; st.paused = false; pauseB.textContent = "Pause analysis";
      stream.getVideoTracks().forEach((t) => t.addEventListener("ended", () => stop("The camera was disconnected.")));
      setCam("Active"); beginAnalysis();
    } catch (e) {
      const msg = { NotAllowedError: "Camera permission was denied. You can allow it in your browser's site settings and press Start again.",
        NotFoundError: "No camera was found on this device.", NotReadableError: "The camera is being used by another app. Close it and try again.",
        OverconstrainedError: "This camera doesn't support the requested settings." }[e.name] || "Couldn't start the camera (" + (e.name || "error") + ").";
      setCam("Error"); ph.hidden = false; ph.textContent = "Camera is off."; setRes(msg); startB.disabled = false;
    } finally { st.starting = false; }
  }

  function beginAnalysis() {
    if (!("FaceDetector" in window)) { setAn("Preview only"); return setRes("Preview only: this browser has no face-detection support and AURA includes no expression model, so no results are shown."); }
    setAn("Loading model");
    try { st.detector = new window.FaceDetector({ fastMode: true, maxDetectedFaces: 3 }); } catch (e) { setAn("Error"); return setRes("Face detection couldn't be started in this browser. Preview only."); }
    setAn("Detecting"); setRes("Looking for faces… (detection only: no emotion or expression is estimated)");
    st.timer = setInterval(tick, 800);                 // low frequency keeps CPU use small
  }
  async function tick() {
    if (st.paused || st.busy || !st.stream || video.readyState < 2 || document.hidden) return;
    st.busy = true;
    try {
      const faces = await st.detector.detect(video);
      if (!st.stream) return;
      if (!faces.length) { setAn("Face not found"); setRes("No face detected. Check lighting and make sure the camera isn't blocked."); }
      else { setAn("Detecting"); setRes(faces.length === 1 ? "1 face visible. (Face detection only; no emotion or expression is estimated.)" : faces.length + " faces visible. (Face detection only; no emotion or expression is estimated.)"); }
    } catch (e) { setAn("Error"); setRes("Face detection failed in this browser. Preview only."); clearInterval(st.timer); st.timer = null; }
    finally { st.busy = false; }
  }
  function togglePause() {
    if (!st.stream) return;
    st.paused = !st.paused; pauseB.textContent = st.paused ? "Resume analysis" : "Pause analysis";
    setCam(st.paused ? "Paused" : "Active"); if (st.paused) setAn("Not running"); else if (st.detector) setAn("Detecting");
    if (st.paused) setRes("Analysis paused.");
  }
  function stop(reason) {                               // releases every track and timer, on every path
    clearInterval(st.timer); st.timer = null; st.detector = null; st.paused = false;
    if (st.stream) { st.stream.getTracks().forEach((t) => t.stop()); st.stream = null; }
    video.srcObject = null; video.hidden = true; ph.hidden = false; ph.textContent = "Camera is off.";
    setCam("Off"); setAn("Not running"); setRes(reason || "No analysis yet.");
    startB.disabled = false; stopB.disabled = true; pauseB.disabled = true; pauseB.textContent = "Pause analysis";
  }
  startB.addEventListener("click", start);
  stopB.addEventListener("click", () => stop());
  pauseB.addEventListener("click", togglePause);
  dlg.addEventListener("close", () => stop());          // closing the window (button, Esc) stops the camera
  window.addEventListener("pagehide", () => stop());
  A.$("#logoutBtn").closest("form").addEventListener("submit", () => stop());
  A.camera = { stop, isActive: () => !!st.stream };
})();
