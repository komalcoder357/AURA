(function () {
  const A = (window.Aura = window.Aura || {});
  const list = A.$("#memList");

  async function refresh() {
    const r = await A.api("/api/memory");
    A.$("#memEnabled").checked = r.enabled;
    list.textContent = "";
    if (!r.items.length) { const li = document.createElement("li"); li.className = "muted"; li.textContent = "Nothing saved yet."; list.appendChild(li); }
    r.items.forEach((m) => {
      const li = document.createElement("li");
      const t = document.createElement("span"); t.textContent = m.content; t.dir = "auto";
      const b = document.createElement("button"); b.type = "button"; b.textContent = "Delete";
      b.setAttribute("aria-label", "Delete memory: " + m.content);
      b.addEventListener("click", async () => { await A.api("/api/memory/" + m.id, { method: "DELETE" }); refresh(); });
      li.appendChild(t); li.appendChild(b); list.appendChild(li);
    });
  }
  A.$("#dlgMemory").addEventListener("aura:open", () => refresh().catch((e) => A.toast(e.message)));
  A.$("#memAdd").addEventListener("click", async () => {
    const inp = A.$("#memInput");
    if (!inp.value.trim()) return;
    try { await A.api("/api/memory", { method: "POST", body: { content: inp.value } }); inp.value = ""; refresh(); } catch (e) { A.toast(e.message); }
  });
  A.$("#memEnabled").addEventListener("change", async (e) => {
    try { await A.api("/api/settings", { method: "PATCH", body: { memory_enabled: e.target.checked } }); A.settings.data.memory_enabled = e.target.checked; }
    catch (err) { A.toast(err.message); e.target.checked = !e.target.checked; }
  });
  A.$("#memClear").addEventListener("click", async () => {
    if (await A.confirm("Clear saved memory?", "This removes every saved memory item. Your conversations are not affected.", "Clear memory")) {
      await A.api("/api/memory", { method: "DELETE" }); A.openDialog("dlgMemory");
    }
  });
  A.$("#chatsClear").addEventListener("click", async () => {
    if (await A.confirm("Delete all chats?", "This permanently deletes every conversation and its messages. Saved memory is not affected.", "Delete all")) {
      await A.api("/api/conversations", { method: "DELETE" });
      A.chat.reset(); A.app.refreshConversations(); A.$("#dlgMemory").close();
    }
  });

  // Analytics: stored data and measured timings only
  const body = A.$("#anBody");
  function section(title) { const h = document.createElement("h3"); h.textContent = title; body.appendChild(h); }
  function bars(obj, labelMap) {
    const keys = Object.keys(obj);
    if (!keys.length) { const p = document.createElement("p"); p.className = "muted small"; p.textContent = "No data."; body.appendChild(p); return; }
    const max = Math.max.apply(null, keys.map((k) => obj[k]));
    const wrap = document.createElement("div"); wrap.className = "bars";
    keys.forEach((k) => {
      const row = document.createElement("div"); row.className = "bar-row";
      const l = document.createElement("span"); l.textContent = (labelMap && labelMap[k]) || k;
      const bar = document.createElement("span"); bar.className = "bar"; const fill = document.createElement("span"); fill.className = "bar-fill"; bar.appendChild(fill);
      const n = document.createElement("b"); n.textContent = obj[k];
      row.appendChild(l); row.appendChild(bar); row.appendChild(n); wrap.appendChild(row);
      fill.style.width = Math.round((obj[k] / max) * 100) + "%";
    });
    body.appendChild(wrap);
  }
  async function loadAnalytics() {
    body.textContent = "Loading…";
    try {
      const r = await A.api("/api/analytics?days=" + encodeURIComponent(A.$("#anDays").value));
      body.textContent = "";
      if (!r.user_messages) { const p = document.createElement("p"); p.className = "muted"; p.textContent = "No messages in this period yet."; body.appendChild(p); return; }
      const p = document.createElement("p"); p.textContent = r.user_messages + " messages sent in the last " + r.days + " days."; body.appendChild(p);
      section("Activity by day"); bars(r.activity_by_day);
      section("Emotion labels (model estimates)"); bars(r.emotion_estimates);
      section("Reply sources"); bars(r.reply_sources, { gemini: "Gemini", fallback: "Fallback", partial: "Interrupted", safety_template: "Safety template" });
      section("Provider errors"); bars(r.provider_errors);
      section("AI reply time");
      const l = r.latency_ms, q = document.createElement("p");
      q.textContent = l.count ? "Average " + l.average + " ms · median " + l.median + " ms · slowest " + l.max + " ms (" + l.count + " Gemini replies)" : "No measured Gemini replies yet.";
      body.appendChild(q);
    } catch (e) { body.textContent = "Couldn't load analytics: " + e.message; }
  }
  A.$("#dlgAnalytics").addEventListener("aura:open", loadAnalytics);
  A.$("#anDays").addEventListener("change", loadAnalytics);
  A.memory = {};
})();
