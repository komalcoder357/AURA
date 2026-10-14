/* Login / sign-up: password eye toggles, field validation, JSON submit, and the mascot's reactions.
   The mascot never blocks the form: it only reflects focus and results. */
(function () {
  const form = document.getElementById("authForm"), mascot = document.getElementById("authMascot");
  if (!form) return;
  const A = window.Aura, kind = form.dataset.kind, errBox = document.getElementById("formError"), btn = document.getElementById("submitBtn");
  const token = document.querySelector('meta[name="csrf-token"]').content;
  const set = (s) => A.mascot.set(mascot, s);
  const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  let revealed = new Set(), focused = null, busy = false;

  function resting() {
    if (focused && (focused.type === "password" || focused.dataset.wasPassword) && !revealed.has(focused.id)) return set("shy");
    if (focused) return set("attentive");
    set(kind === "register" ? "guiding" : "idle");
  }
  set("greeting");
  setTimeout(() => { if (!focused && !busy) resting(); }, 2800);   // wave hello, then settle (guide on sign-up)

  form.querySelectorAll("input").forEach((inp) => {
    if (inp.type === "password") inp.dataset.wasPassword = "1";
    inp.addEventListener("focus", () => { focused = inp; resting(); });
    inp.addEventListener("blur", () => { focused = null; setTimeout(() => { if (!focused && !busy) resting(); }, 60); });
    inp.addEventListener("input", () => clearField(inp));
  });
  document.querySelectorAll("[data-pw-toggle]").forEach((b) => b.addEventListener("click", () => {
    const inp = document.getElementById(b.dataset.pwToggle), show = inp.type === "password";
    inp.type = show ? "text" : "password";                         // the user's choice always wins
    show ? revealed.add(inp.id) : revealed.delete(inp.id);
    b.setAttribute("aria-pressed", String(show)); b.setAttribute("aria-label", show ? "Hide password" : "Show password");
    b.querySelector(".eye-on").hidden = show; b.querySelector(".eye-off").hidden = !show;
    inp.focus(); focused = inp; resting();
  }));

  function fieldErr(name, msg) {
    const span = document.getElementById("err-" + name), inp = document.getElementById(name);
    if (span) span.textContent = msg || ""; if (inp) { if (msg) inp.setAttribute("aria-invalid", "true"); else inp.removeAttribute("aria-invalid"); }
  }
  function clearField(inp) { fieldErr(inp.name, ""); }
  function showError(msg) { errBox.textContent = msg; errBox.hidden = !msg; }
  function validate(v) {
    const e = {};
    if (kind === "register") {
      if (!v.display_name.trim()) e.display_name = "Enter a display name.";
      if (!EMAIL.test(v.email)) e.email = "Enter a valid email address.";
      if (v.password.length < 8 || !/[A-Za-z]/.test(v.password) || !/\d/.test(v.password)) e.password = "Use at least 8 characters with a letter and a number.";
      if (v.password !== v.confirm_password) e.confirm_password = "The two passwords don't match.";
    } else {
      if (!v.email.trim()) e.email = "Enter your email.";
      if (!v.password) e.password = "Enter your password.";
    }
    return e;
  }
  form.addEventListener("submit", async (ev) => {
    if (!window.fetch) return;                                      // no fetch: normal form POST still works
    ev.preventDefault();
    if (busy) return;                                               // no duplicate submissions
    const v = {}; new FormData(form).forEach((val, k) => { if (k !== "csrf_token") v[k] = String(val); });
    ["display_name", "email", "password", "confirm_password"].forEach((n) => fieldErr(n, ""));
    showError("");
    const errs = validate(v);
    if (Object.keys(errs).length) {
      Object.keys(errs).forEach((n) => fieldErr(n, errs[n])); showError("Please fix the highlighted fields.");
      set("concerned"); const first = form.querySelector('[aria-invalid="true"]'); if (first) first.focus(); return;
    }
    busy = true; btn.disabled = true; const label = btn.textContent; btn.textContent = kind === "login" ? "Signing in…" : "Creating account…";
    try {
      const res = await fetch(form.action, { method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": token }, body: JSON.stringify(v) });
      let data = {}; try { data = await res.json(); } catch (e) {}
      if (res.ok && data.ok) {
        set("happy"); btn.textContent = kind === "login" ? "Welcome back!" : "Welcome to AURA!";
        setTimeout(() => { window.location.href = data.redirect || "/"; }, A.reducedMotion() ? 50 : 900);
        return;
      }
      Object.keys(data.field_errors || {}).forEach((n) => fieldErr(n, data.field_errors[n]));
      showError(data.error || "Something went wrong. Please try again.");
      set("concerned"); setTimeout(() => { if (!busy) resting(); }, 2600);
    } catch (e) { showError("Couldn't reach the server. Check your connection and try again."); set("concerned"); }
    busy = false; btn.disabled = false; btn.textContent = label;
    setTimeout(() => { if (!focused) resting(); }, 2600);
  });
})();
