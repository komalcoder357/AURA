(function () {
  const A = (window.Aura = window.Aura || {});
  const token = document.querySelector('meta[name="csrf-token"]').content;
  A.$ = (s) => document.querySelector(s);
  A.csrf = token;

  function goLogin() { window.location.href = "/login"; }
  async function parse(res) {
    let data = null;
    try { data = await res.json(); } catch (e) { /* not JSON */ }
    if (res.status === 401) { goLogin(); throw new Error("Please log in."); }
    if (!res.ok) { const err = new Error((data && data.error) || "Request failed (" + res.status + ")."); err.status = res.status; throw err; }
    return data;
  }
  A.api = async function (path, opts) {
    opts = opts || {};
    const res = await fetch(path, {
      method: opts.method || "GET", credentials: "same-origin", signal: opts.signal,
      headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": token },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    return parse(res);
  };
  A.upload = async function (path, formData) {
    const res = await fetch(path, { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": token, Accept: "application/json" }, body: formData });
    return parse(res);
  };

  // NDJSON streaming of /api/chat/stream. handlers: onMeta, onDelta, onDone. Resolves when the stream ends.
  A.streamChat = async function (payload, handlers, signal) {
    const res = await fetch("/api/chat/stream", {
      method: "POST", credentials: "same-origin", signal,
      headers: { "Content-Type": "application/json", "X-CSRFToken": token },
      body: JSON.stringify(payload),
    });
    if (!res.ok) await parse(res);
    const reader = res.body.getReader(), dec = new TextDecoder();
    let buf = "", sawDone = false;
    function handleLine(line) {
      if (!line.trim()) return;
      const msg = JSON.parse(line);
      if (msg.type === "meta" && handlers.onMeta) handlers.onMeta(msg);
      else if (msg.type === "delta" && handlers.onDelta) handlers.onDelta(msg.text);
      else if (msg.type === "done") { sawDone = true; if (handlers.onDone) handlers.onDone(msg); }
    }
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n")) >= 0) { handleLine(buf.slice(0, i)); buf = buf.slice(i + 1); }
    }
    buf += dec.decode();
    handleLine(buf);
    if (!sawDone) throw new Error("The response was interrupted.");
  };

  let toastTimer = null;
  A.toast = function (msg) {
    const t = A.$("#toast");
    if (!t) return;
    t.textContent = msg; t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (t.hidden = true), 4500);
  };

  A.confirm = function (title, text, okLabel) {
    return new Promise((resolve) => {
      const d = A.$("#dlgConfirm");
      A.$("#confirmTitle").textContent = title;
      A.$("#confirmText").textContent = text;
      A.$("#confirmOk").textContent = okLabel || "Delete";
      d.returnValue = "";
      d.addEventListener("close", () => resolve(d.returnValue === "ok"), { once: true });
      d.showModal();
    });
  };

  // Dialog helper: remembers the opener so keyboard focus returns to it on close
  A.openDialog = function (id) {
    const d = A.$("#" + id);
    if (!d || d.open) return;
    const opener = document.activeElement;
    d.showModal();
    d.addEventListener("close", () => { if (opener && opener.focus && document.contains(opener)) opener.focus(); }, { once: true });
    d.dispatchEvent(new CustomEvent("aura:open"));
  };
  A.reducedMotion = function () {
    return document.documentElement.dataset.motion === "reduced" || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  };
})();
