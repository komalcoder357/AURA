(function () {
  const A = (window.Aura = window.Aura || {});
  const tpl = document.getElementById("mascot-template");
  // Public names -> CSS states
  const ALIAS = { thinking: "processing", success: "happy", celebrate: "happy", encouraging: "guiding", "password-shy": "shy",
    "theme-transition": "walking", "camera-off": "error", failure: "error" };
  function mount(el) {
    if (el.dataset.mounted || !tpl) return;
    el.classList.add("mascot");
    el.appendChild(tpl.content.firstElementChild.cloneNode(true));
    el.dataset.mounted = "1";
    if (!el.dataset.state) el.dataset.state = "idle";
  }
  function mountAll(root) { (root || document).querySelectorAll("[data-mascot]").forEach(mount); }
  function set(el, state) { if (el) el.dataset.state = ALIAS[state] || state; }
  // Play a transient state (e.g. happy) and then return to another
  function pulse(el, state, ms, back) {
    set(el, state);
    clearTimeout(el._pulse);
    el._pulse = setTimeout(() => set(el, back || "idle"), ms || 1400);
  }
  A.reducedMotion = A.reducedMotion || function () {
    return document.documentElement.dataset.motion === "reduced" || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  };
  A.mascot = { mount, mountAll, set, pulse };
  mountAll();
})();
