const state = {
  sessionId: null,
  study: null,
  meta: null,
  mermaidN: 0,
  mermaid: null,
  project: "",
  scenario: "restudy",
  format: "long",
};

async function mermaidApi() {
  if (state.mermaid) return state.mermaid;
  const mod = await import("https://cdn.jsdelivr.net/npm/mermaid@11.6.0/dist/mermaid.esm.min.mjs");
  const mermaid = mod.default;
  mermaid.initialize({
    startOnLoad: false,
    theme: "base",
    securityLevel: "strict",
    themeVariables: {
      fontFamily: "Public Sans, sans-serif",
      primaryColor: "#fff7ed",
      primaryTextColor: "#1c1914",
      primaryBorderColor: "#b45309",
      lineColor: "#5f584e",
      secondaryColor: "#f4f0e4",
      tertiaryColor: "#ffffff",
    },
  });
  state.mermaid = mermaid;
  return mermaid;
}

const $ = (id) => document.getElementById(id);

function fmt(n, digits = 1) {
  if (n == null || n === "") return "-";
  const v = Number(n);
  if (Number.isNaN(v)) return String(n);
  return v.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function pct(n) {
  if (n == null || n === "") return "-";
  const v = Number(n);
  if (Number.isNaN(v)) return String(n);
  return `${(v * 100).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/"/g, "&quot;");
}

function findRow(list, key, value) {
  return (list || []).find((row) => row[key] === value) || null;
}

function setTechnical(on) {
  document.body.classList.toggle("technical", on);
  try {
    localStorage.setItem("p4-technical", on ? "1" : "0");
  } catch (_) {
    /* ignore */
  }
}

function setDockSize(size) {
  const dock = $("dock");
  dock.dataset.size = size;
  document.body.classList.toggle("dock-min", size === "min");
  document.body.classList.toggle("dock-max", size === "max");
}

function setPhase() {
  const reading = Boolean(state.study && state.study.markdown);
  document.body.classList.toggle("reading", reading);
  $("summary-bar").hidden = !reading;
  $("help-panel").hidden = !reading;
  $("dock").hidden = !reading;
  if (!reading) {
    document.body.classList.remove("editing");
    setDockSize("mid");
  }
}

function renderPicks() {
  const meta = state.meta || {};
  $("project-picks").innerHTML = (meta.projects || [])
    .map((p) => {
      const on = p.project_key === state.project ? " on" : "";
      return `<button type="button" class="pick${on}" data-pick="project" data-value="${esc(p.project_key)}">
        <strong>${esc(p.label)}</strong>
        <span class="sum">${esc(p.summary)}</span>
        <span class="tech">${esc(p.project_key)}</span>
      </button>`;
    })
    .join("");

  $("scenario-picks").innerHTML = (meta.scenarios || [])
    .map((s) => {
      const on = s.name === state.scenario ? " on" : "";
      return `<button type="button" class="pick${on}" data-pick="scenario" data-value="${esc(s.name)}">
        <strong>${esc(s.label)}</strong>
        <span class="sum">${esc(s.summary)}</span>
        <span class="expect">What to expect: ${esc(s.expect)}</span>
        <span class="tech">${esc(s.name)}. ${esc(s.detail || s.note || "")}</span>
      </button>`;
    })
    .join("");

  $("format-picks").innerHTML = (meta.formats || [])
    .map((f) => {
      const on = f.name === state.format ? " on" : "";
      return `<button type="button" class="pick${on}" data-pick="format" data-value="${esc(f.name)}">
        <strong>${esc(f.label)}</strong>
        <span class="sum">${esc(f.summary)}</span>
        <span class="expect">What to expect: ${esc(f.expect)}</span>
        <span class="tech">${esc(f.name)}</span>
      </button>`;
    })
    .join("");

  syncMapToggle();
}

function syncMapToggle() {
  const row = findRow((state.meta || {}).formats, "name", state.format) || {};
  const box = $("want-diagram");
  const wrap = $("map-wrap");
  if (state.format === "diagram") {
    box.checked = true;
    box.disabled = true;
    wrap.classList.add("disabled");
    return;
  }
  if (row.allows_map === false) {
    box.checked = false;
    box.disabled = true;
    wrap.classList.add("disabled");
    return;
  }
  box.disabled = false;
  wrap.classList.remove("disabled");
}

function renderHelp() {
  const meta = state.meta || {};
  const projectItems = (meta.projects || [])
    .map((p) => `<dt>${esc(p.label)}</dt><dd>${esc(p.summary)}</dd>`)
    .join("");
  const scenarioItems = (meta.scenarios || [])
    .map((s) => `<dt>${esc(s.label)}</dt><dd>${esc(s.summary)} ${esc(s.expect)}</dd>`)
    .join("");
  const formatItems = (meta.formats || [])
    .map((f) => `<dt>${esc(f.label)}</dt><dd>${esc(f.summary)} ${esc(f.expect)}</dd>`)
    .join("");
  $("help-body").innerHTML = `
    <h3>Projects</h3>
    <p>${esc((meta.guides || {}).project || "")}</p>
    <dl>${projectItems}</dl>
    <h3>What-ifs</h3>
    <p>${esc((meta.guides || {}).what_if || "")}</p>
    <dl>${scenarioItems}</dl>
    <h3>Briefing shapes</h3>
    <p>${esc((meta.guides || {}).format || "")}</p>
    <dl>${formatItems}</dl>`;
}

function renderSummary() {
  const p = findRow((state.meta || {}).projects, "project_key", state.project);
  const s = findRow((state.meta || {}).scenarios, "name", state.scenario);
  const f = findRow((state.meta || {}).formats, "name", state.format);
  $("summary-text").textContent = [
    p && p.label,
    s && s.label,
    f && f.label,
  ].filter(Boolean).join("  |  ");
}

function renderSuggestions() {
  const chats = ((state.meta || {}).examples || []).filter((e) => e.kind === "chat");
  $("suggestions").innerHTML = chats
    .map((e) => `<button type="button" data-q="${esc(e.question)}">${esc(e.label)}</button>`)
    .join("");
}

async function renderScoreboard() {
  if (!state.project || !state.scenario) return;
  const res = await fetch(
    `/api/stack?project_key=${encodeURIComponent(state.project)}&scenario=${encodeURIComponent(state.scenario)}`,
  );
  const data = await res.json();
  if (!res.ok || data.error) {
    $("scoreboard").innerHTML = `<p class="gloss">${esc(data.message || "Could not load the card.")}</p>`;
    return;
  }
  const gs = data.gold_stack || {};
  const cb = gs.catboost || {};
  const p2 = gs.platinum2 || {};
  $("scoreboard").innerHTML = `<div class="strip">
    <div class="metric">
      <dt>Chance it withdraws within 12 months</dt>
      <dd>${pct(cb.p_quit_12m)}</dd>
      <p class="gloss">A ranking score, not a verdict that the project will quit.</p>
      <p class="gloss tech-only">CatBoost 12-month P(quit).</p>
    </div>
    <div class="metric">
      <dt>If this what-if applied</dt>
      <dd>${pct(cb.p_quit_under_scenario)}</dd>
      <p class="gloss">What the ranking would be if this what-if were already true.</p>
      <p class="gloss tech-only">Delta ${pct(cb.delta_p_quit)}.</p>
    </div>
    <div class="metric">
      <dt>Nearby delayed capacity</dt>
      <dd>${fmt(p2.delayed_mw_now, 0)} MW</dd>
      <p class="gloss">Queue crowding nearby, not this plant's in-service date.</p>
    </div>
  </div>`;
}

function stripMermaid(md) {
  return (md || "").replace(/```mermaid[\s\S]*?```/g, "").trim();
}

function renderMarkdown(md) {
  const html = marked.parse(stripMermaid(md || ""), { gfm: true });
  $("note").innerHTML = DOMPurify.sanitize(html);
}

async function renderMap(src) {
  const panel = $("map-panel");
  const canvas = $("map-canvas");
  if (!src) {
    panel.hidden = true;
    canvas.innerHTML = "";
    return;
  }
  panel.hidden = false;
  state.mermaidN += 1;
  try {
    const mermaid = await mermaidApi();
    const { svg } = await mermaid.render(`p4map-${state.mermaidN}`, src);
    canvas.innerHTML = svg;
  } catch (err) {
    canvas.innerHTML = `<pre>${esc(src)}</pre><p class="gloss">${esc(String(err))}</p>`;
  }
}

function renderLimits(study) {
  const box = $("limits");
  const claims = (study && study.do_not_claim) || [];
  const gaps = (study && study.gaps) || [];
  if (!study || !study.markdown) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  const extra = claims.length
    ? `<ul class="tech-only">${claims.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>`
    : "";
  const gapLine = gaps.length
    ? `<p>Not covered by a BPM clause: ${esc(gaps.join("; "))}.</p>`
    : "";
  box.innerHTML = `<h3>Limits of this briefing</h3>
    <p>This restates MISO procedure. It is not a legal opinion and not a compliance score. It does not forecast months of COD delay.</p>
    ${gapLine}${extra}`;
  box.hidden = false;
}

function showStudy(study) {
  state.study = study;
  const empty = $("study-empty");
  if (!study || !study.markdown) {
    empty.hidden = false;
    $("note").hidden = true;
    $("raw-wrap").hidden = true;
    $("map-panel").hidden = true;
    $("format-btn").disabled = true;
    setChatEnabled(false);
    renderLimits(null);
    setPhase();
    return;
  }
  empty.hidden = true;
  $("note").hidden = false;
  $("raw-wrap").hidden = false;
  $("format-btn").disabled = false;
  $("raw-md").textContent = study.markdown || "";
  renderMarkdown(study.markdown || "");
  renderMap(study.mermaid);
  renderLimits(study);
  renderSummary();
  setChatEnabled(true);
  setPhase();
}

function setChatEnabled(on) {
  $("followup").disabled = !on;
  $("chat-btn").disabled = !on;
}

function renderThread(messages) {
  const ol = $("messages");
  const rows = (messages || []).filter((m) => m.role !== "system");
  if (!rows.length) {
    ol.innerHTML = `<li class="msg empty">Questions refer to the briefing above. They do not write a new one.</li>`;
    return;
  }
  ol.innerHTML = "";
  for (const m of rows) {
    const li = document.createElement("li");
    li.className = `msg ${m.role === "user" ? "user" : "bot"}`;
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = m.role === "user" ? "You" : "Briefing";
    li.appendChild(who);
    if (m.role === "assistant" && m.markdown) {
      const wrap = document.createElement("div");
      wrap.innerHTML = DOMPurify.sanitize(marked.parse(stripMermaid(m.markdown), { gfm: true }));
      li.appendChild(wrap);
    } else {
      li.append(m.text || "");
    }
    ol.appendChild(li);
  }
  ol.scrollTop = ol.scrollHeight;
}

function setBusy(on, label) {
  document.body.classList.toggle("busy", on);
  $("study-btn").disabled = on;
  $("format-btn").disabled = on || !state.study;
  $("chat-btn").disabled = on || !state.study;
  $("status").textContent = on ? (label || "Working...") : "";
}

function clearStudy() {
  state.sessionId = null;
  state.study = null;
  showStudy(null);
  renderThread([]);
  $("status").textContent = "";
}

function explainNetworkError(err) {
  const msg = String(err || "");
  if (/failed to fetch|networkerror|load failed/i.test(msg)) {
    return "Cannot reach the briefing server. Open http://127.0.0.1:8765/ and keep python scripts/serve_platinum4_ui.py running.";
  }
  return msg;
}

async function post(mode, extra = {}) {
  let res;
  try {
    res = await fetch("/api/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode,
        session_id: state.sessionId,
        project_key: state.project,
        scenario: state.scenario,
        format: state.format,
        want_diagram: $("want-diagram").checked,
        split: "val",
        ...extra,
      }),
    });
  } catch (err) {
    throw new Error(explainNetworkError(err));
  }
  const view = await res.json().catch(() => null);
  if (!view) {
    throw new Error("The server returned an empty response. Try Write briefing again.");
  }
  return view;
}

async function generateStudy() {
  setBusy(true, "Writing briefing...");
  try {
    const view = await post("study", { focus: $("focus").value, reset: true });
    if (view.error) {
      $("status").textContent = view.message || view.error_code || "Briefing failed";
      return;
    }
    state.sessionId = view.session_id;
    $("status").textContent = "";
    document.body.classList.remove("editing");
    showStudy(view.study);
    renderThread(view.messages);
  } catch (err) {
    $("status").textContent = err.message || explainNetworkError(err);
  } finally {
    setBusy(false);
  }
}

async function applyFormat() {
  if (!state.study) return;
  setBusy(true, "Changing layout...");
  try {
    const view = await post("reformat");
    if (view.error) {
      $("status").textContent = view.message || "Could not change layout";
      return;
    }
    state.sessionId = view.session_id;
    $("status").textContent = "";
    showStudy(view.study);
    renderThread(view.messages);
  } catch (err) {
    $("status").textContent = err.message || explainNetworkError(err);
  } finally {
    setBusy(false);
  }
}

async function sendChat(question) {
  const q = (question || $("followup").value).trim();
  if (!q) return;
  if (!state.study) {
    $("status").textContent = "Write a briefing first.";
    return;
  }
  setBusy(true, "Answering...");
  try {
    const view = await post("chat", { question: q });
    if (view.error) {
      $("status").textContent = view.message || view.error_code || "Question failed";
      return;
    }
    state.sessionId = view.session_id;
    $("status").textContent = "";
    showStudy(view.study);
    renderThread(view.messages);
    $("followup").value = "";
    if ($("dock").dataset.size === "min") setDockSize("mid");
  } catch (err) {
    $("status").textContent = err.message || explainNetworkError(err);
  } finally {
    setBusy(false);
  }
}

function onPick(kind, value) {
  if (kind === "project") {
    if (state.project !== value) {
      state.project = value;
      clearStudy();
    }
  } else if (kind === "scenario") {
    if (state.scenario !== value) {
      state.scenario = value;
      clearStudy();
    }
  } else if (kind === "format") {
    state.format = value;
    syncMapToggle();
    renderSummary();
  }
  renderPicks();
  renderScoreboard();
}

async function boot() {
  const meta = await (await fetch("/api/meta")).json();
  state.meta = meta;
  const guides = meta.guides || {};
  if (guides.project) $("guide-project").textContent = guides.project;
  if (guides.what_if) $("guide-what-if").textContent = guides.what_if;
  if (guides.format) $("guide-format").textContent = guides.format;
  state.project = (meta.projects[0] || {}).project_key || "";
  state.scenario = "restudy";
  state.format = "long";
  try {
    if (localStorage.getItem("p4-technical") === "1") {
      $("tech-toggle").checked = true;
      setTechnical(true);
    }
  } catch (_) {
    /* ignore */
  }
  renderPicks();
  renderHelp();
  renderSuggestions();
  renderSummary();
  $("tech-toggle").addEventListener("change", (e) => setTechnical(e.target.checked));
  $("setup-panel").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-pick]");
    if (!btn) return;
    onPick(btn.dataset.pick, btn.dataset.value);
  });
  $("setup-form").addEventListener("submit", (e) => {
    e.preventDefault();
    generateStudy();
  });
  $("format-btn").addEventListener("click", applyFormat);
  $("edit-setup-btn").addEventListener("click", () => {
    document.body.classList.add("editing");
    $("setup-panel").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  $("chat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    sendChat();
  });
  $("suggestions").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-q]");
    if (!btn) return;
    sendChat(btn.dataset.q);
  });
  $("dock-min").addEventListener("click", () => setDockSize("min"));
  $("dock-mid").addEventListener("click", () => setDockSize("mid"));
  $("dock-max").addEventListener("click", () => setDockSize("max"));
  showStudy(null);
  renderThread([]);
  await renderScoreboard();
}

boot().catch((err) => {
  $("status").textContent = explainNetworkError(err);
});
