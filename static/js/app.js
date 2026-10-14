(function () {
  const A = (window.Aura = window.Aura || {});
  const app = A.$("#app"), backdrop = A.$("#backdrop"), list = A.$("#convList"), ctx = A.$("#ctxMenu");
  const searchInput = A.$("#searchInput"), searchClear = A.$("#searchClear");
  const mobile = window.matchMedia("(max-width: 900px)");
  let conversations = [], activeId = null, ctxTarget = null, pressTimer = null, searchSeq = 0, searchTimer = null, searching = false;

  /* ---------- layout ---------- */
  function syncAria() {
    const sb = String(app.dataset.sidebar === "open");
    A.$("#sidebarToggle").setAttribute("aria-expanded", sb); A.$("#sidebarOpen").setAttribute("aria-expanded", sb);
    A.$("#panelToggle").setAttribute("aria-expanded", String(app.dataset.panel === "open"));
    backdrop.hidden = !(mobile.matches && (app.dataset.sidebar === "open" || app.dataset.panel === "open"));
  }
  function setLayout(which, open) {
    app.dataset[which] = open ? "open" : "closed";
    if (mobile.matches && open) app.dataset[which === "sidebar" ? "panel" : "sidebar"] = "closed";
    syncAria();
    if (!mobile.matches) { try { localStorage.setItem("aura.layout." + which, open ? "open" : "closed"); } catch (e) {} }
  }
  const toggle = (which) => setLayout(which, app.dataset[which] !== "open");
  function initLayout() {
    if (mobile.matches) { app.dataset.sidebar = "closed"; app.dataset.panel = "closed"; }
    else {
      let s = "open", p = "closed";
      try { s = localStorage.getItem("aura.layout.sidebar") || s; p = localStorage.getItem("aura.layout.panel") || p; } catch (e) {}
      app.dataset.sidebar = s; app.dataset.panel = p;
    }
    syncAria();
  }
  mobile.addEventListener("change", initLayout);
  A.$("#sidebarToggle").addEventListener("click", () => toggle("sidebar"));
  A.$("#sidebarOpen").addEventListener("click", () => toggle("sidebar"));
  A.$("#panelToggle").addEventListener("click", () => toggle("panel"));
  backdrop.addEventListener("click", () => { app.dataset.sidebar = "closed"; app.dataset.panel = "closed"; syncAria(); });

  /* ---------- conversation list ---------- */
  function highlight(text, q) {
    const frag = document.createDocumentFragment();
    const i = q ? text.toLowerCase().indexOf(q.toLowerCase()) : -1;
    if (i < 0) { frag.appendChild(document.createTextNode(text)); return frag; }
    frag.appendChild(document.createTextNode(text.slice(0, i)));
    const m = document.createElement("mark"); m.textContent = text.slice(i, i + q.length); frag.appendChild(m);
    frag.appendChild(document.createTextNode(text.slice(i + q.length)));
    return frag;
  }
  function group(title, items) {
    if (!items.length) return;
    const h = document.createElement("div"); h.className = "conv-group"; h.textContent = title; list.appendChild(h);
    items.forEach((c) => list.appendChild(item(c)));
  }
  function item(c, q) {
    const row = document.createElement("div");
    row.className = "conv-item" + (c.id === activeId ? " active" : "");
    const open = document.createElement("button");
    open.type = "button"; open.className = "conv-open";
    const top = document.createElement("span"); top.className = "conv-row";
    if (c.pinned) { const p = document.createElement("span"); p.className = "pin-mark"; p.textContent = "📌"; p.setAttribute("aria-label", "Pinned"); top.appendChild(p); }
    const t = document.createElement("span"); t.className = "conv-title"; t.dir = "auto";
    if (q) t.appendChild(highlight(c.title, q)); else t.textContent = c.title;
    top.appendChild(t); open.appendChild(top);
    if (q && c.snippet && c.match === "message") { const s = document.createElement("span"); s.className = "conv-snippet"; s.dir = "auto"; s.appendChild(highlight(c.snippet, q)); open.appendChild(s); }
    if (c.id === activeId) open.setAttribute("aria-current", "true");
    open.addEventListener("click", () => openConversation(c.id));
    row.appendChild(open);
    if (!q) {
      const more = document.createElement("button");
      more.type = "button"; more.className = "conv-more"; more.textContent = "⋯"; more.setAttribute("aria-label", "Options for " + c.title);
      more.addEventListener("click", (e) => { e.stopPropagation(); const r = more.getBoundingClientRect(); showCtx(c, r.left, r.bottom); });
      row.addEventListener("contextmenu", (e) => { e.preventDefault(); showCtx(c, e.clientX, e.clientY); });
      row.addEventListener("touchstart", (e) => { const p = e.touches[0]; pressTimer = setTimeout(() => showCtx(c, p.clientX, p.clientY), 550); }, { passive: true });
      ["touchend", "touchmove", "touchcancel"].forEach((n) => row.addEventListener(n, () => clearTimeout(pressTimer), { passive: true }));
      row.appendChild(more);
    }
    return row;
  }
  function note(text) { const p = document.createElement("p"); p.className = "muted conv-empty"; p.textContent = text; list.appendChild(p); }
  function render() {
    if (searching) return;
    list.textContent = "";
    if (!conversations.length) return note("Your conversations will appear here.");
    group("Pinned", conversations.filter((c) => c.pinned));
    group("Recent", conversations.filter((c) => !c.pinned));
  }
  async function refreshConversations() {
    try {
      conversations = (await A.api("/api/conversations")).conversations;
      if (A.chat.state.conversationId) activeId = A.chat.state.conversationId;
      render();
    } catch (e) { A.toast(e.message); }
  }
  async function openConversation(id) {
    try { await A.chat.load(id); activeId = id; try { localStorage.setItem("aura.lastConversation", id); } catch (e) {} searching ? runSearch() : render(); if (mobile.matches) setLayout("sidebar", false); }
    catch (e) { A.toast(e.message); }
  }
  A.$("#newChat").addEventListener("click", () => {
    A.chat.reset(); activeId = null; try { localStorage.removeItem("aura.lastConversation"); } catch (e) {}
    searching ? runSearch() : render(); A.$("#input").focus(); if (mobile.matches) setLayout("sidebar", false);
  });

  /* ---------- search (database only; never sent to the AI) ---------- */
  async function runSearch() {
    const q = searchInput.value.trim(), seq = ++searchSeq;
    if (!q) { searching = false; searchClear.hidden = true; return render(); }
    searching = true; searchClear.hidden = false; list.textContent = ""; note("Searching…");
    try {
      const r = await A.api("/api/search?q=" + encodeURIComponent(q));
      if (seq !== searchSeq) return;            // a newer search replaced this one
      list.textContent = "";
      if (!r.results.length) return note("No chats match “" + q + "”.");
      r.results.forEach((c) => list.appendChild(item(c, q)));
    } catch (e) { if (seq === searchSeq) { list.textContent = ""; note("Search failed: " + e.message); } }
  }
  searchInput.addEventListener("input", () => { clearTimeout(searchTimer); searchClear.hidden = !searchInput.value; searchTimer = setTimeout(runSearch, 250); });
  searchInput.addEventListener("keydown", (e) => { if (e.key === "Escape" && searchInput.value) { e.preventDefault(); clearSearch(); } });
  function clearSearch() { searchInput.value = ""; searchSeq++; searching = false; searchClear.hidden = true; render(); searchInput.focus(); }
  searchClear.addEventListener("click", clearSearch);

  /* ---------- context menu ---------- */
  function showCtx(c, x, y) {
    ctxTarget = c;
    A.$("#ctxMenu [data-act=pin]").textContent = c.pinned ? "Unpin" : "Pin";
    ctx.hidden = false;
    const w = ctx.offsetWidth, h = ctx.offsetHeight;
    ctx.style.left = Math.max(8, Math.min(x, window.innerWidth - w - 8)) + "px";
    ctx.style.top = Math.max(8, Math.min(y, window.innerHeight - h - 8)) + "px";
    ctx.querySelector("button").focus();
  }
  const hideMenus = () => { ctx.hidden = true; };
  document.addEventListener("click", (e) => { if (!e.target.closest(".menu, .conv-more")) hideMenus(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideMenus(); });
  ctx.addEventListener("click", async (e) => {
    const act = e.target.dataset.act, c = ctxTarget;
    if (!act || !c) return;
    hideMenus();
    try {
      if (act === "pin") await A.api("/api/conversations/" + c.id, { method: "PATCH", body: { pinned: !c.pinned } });
      if (act === "rename") {
        const d = A.$("#dlgRename"), inp = A.$("#renameInput");
        inp.value = c.title; d.returnValue = ""; d.showModal();
        d.addEventListener("close", async () => {
          if (d.returnValue === "ok" && inp.value.trim()) {
            try { await A.api("/api/conversations/" + c.id, { method: "PATCH", body: { title: inp.value } }); if (c.id === activeId) A.$("#chatTitle").textContent = inp.value.trim(); refreshConversations(); }
            catch (err) { A.toast(err.message); }
          }
        }, { once: true });
        return;
      }
      if (act === "delete") {
        if (!(await A.confirm("Delete this conversation?", "Its messages and analysis are permanently deleted. Saved memory is not affected.", "Delete"))) return;
        await A.api("/api/conversations/" + c.id, { method: "DELETE" });
        if (c.id === activeId) { A.chat.reset(); activeId = null; try { localStorage.removeItem("aura.lastConversation"); } catch (e2) {} }
      }
      refreshConversations();
    } catch (err) { A.toast(err.message); }
  });

  /* ---------- dialogs ---------- */
  document.querySelectorAll("[data-open]").forEach((b) => b.addEventListener("click", () => {
    hideMenus();
    const id = b.dataset.open, current = b.closest("dialog");
    if (current && current.id !== id) current.close();
    A.openDialog(id);
  }));
  document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));

  A.app = { refreshConversations };
  initLayout();
  A.settings.load().catch((e) => A.toast(e.message));
  A.emotion.reset();
  refreshConversations().then(() => {          // restore the last open conversation after a refresh
    let last = null; try { last = localStorage.getItem("aura.lastConversation"); } catch (e) {}
    if (last && conversations.some((c) => c.id === last)) openConversation(last);
  });
})();
