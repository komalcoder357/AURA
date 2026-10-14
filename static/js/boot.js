/* Tiny blocking script: applies the locally remembered look before first paint on pages where the server
   does not know the user (landing, login, register). Logged-in pages are rendered with the account's saved theme. */
(function () {
  try {
    const h = document.documentElement;
    if (h.dataset.server !== "1") {
      const t = localStorage.getItem("aura.theme"), m = localStorage.getItem("aura.mode");
      if (t) h.dataset.theme = t;
      if (m) h.dataset.mode = m;
    }
    if (localStorage.getItem("aura.motion") === "reduced") h.dataset.motion = "reduced";
  } catch (e) { /* storage unavailable: defaults apply */ }
})();
