// UI logic. Talks to the REST API; keeps no biometric data client-side beyond the
// in-flight capture. CSP-safe (external file).
"use strict";

const $ = (id) => document.getElementById(id);
const show = (elm, on) => { elm.hidden = !on; };

const state = {
  role: null,
  participants: [],
  selectedParticipant: null,
  conditionGroups: {},
  currentRun: null,
  trialTags: [],
  enrolFrames: [],
};

window.__cameras = [];
function makeCamera(videoEl) {
  const cam = new CameraController(videoEl);
  window.__cameras.push(cam);
  return cam;
}
const cams = {};

// ---- bootstrap / login ------------------------------------------------------
$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    const res = await API.post("/auth/login", {
      username: fd.get("username"),
      password: fd.get("password"),
    });
    API.csrf = res.csrf_token;
    state.role = res.user.role;
    $("whoami").textContent = `${res.user.username} (${res.user.role})`;
    show($("login-view"), false);
    show($("app-view"), true);
    await afterLogin();
  } catch (err) {
    $("login-error").textContent = err.message || "login failed";
  }
});

$("logout").addEventListener("click", async () => {
  try { await API.post("/auth/logout"); } catch (_) {}
  window.__cameras.forEach((c) => c.stop());
  location.reload();
});

async function afterLogin() {
  try {
    const eng = await API.get("/health/engine");
    if (eng.model && eng.model.name === "fake") {
      $("engine-banner").textContent =
        "Fake engine active: live webcam captures return 'no face'. Install the real engine " +
        "(pip install -e \".[engine]\") for real verification, or use a synthetic demo run for analysis.";
      show($("engine-banner"), true);
    }
  } catch (_) {}
  try { state.conditionGroups = await API.get("/settings").then((s) => s.condition_groups || {}); }
  catch (_) { state.conditionGroups = {
    lighting: ["normal", "bright", "dim", "backlit"], distance: ["near", "medium", "far"],
    glasses: ["on", "off"],
  }; }
  await loadParticipants();
  await loadRuns();
  populateTagSelectors();
}

// ---- tabs -------------------------------------------------------------------
document.querySelectorAll("#tabs button[data-tab]").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#tabs button[data-tab]").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".panel").forEach((p) => show(p, p.dataset.panel === btn.dataset.tab));
    window.__cameras.forEach((c) => c.stop());
  });
});

// ---- participants & enrolment ----------------------------------------------
async function loadParticipants() {
  const data = await API.get("/participants");
  state.participants = data.items;
  const tbody = $("participant-table").querySelector("tbody");
  tbody.innerHTML = "";
  for (const p of data.items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${p.subject_code}</td><td>${p.status}</td><td></td>` +
      `<td><button data-pid="${p.id}">select</button></td>`;
    tr.querySelector("button").addEventListener("click", () => selectParticipant(p));
    tbody.appendChild(tr);
  }
  refreshParticipantSelectors();
}

$("participant-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    await API.post("/participants", { subject_code: fd.get("subject_code") });
    e.target.reset();
    await loadParticipants();
  } catch (err) { alert(err.message); }
});

function selectParticipant(p) {
  state.selectedParticipant = p;
  state.enrolFrames = [];
  $("frame-count").textContent = "0";
  $("enrol-target").textContent = `Selected: ${p.subject_code} (${p.status})`;
  $("btn-consent").disabled = false;
  $("btn-cam-start").disabled = false;
  $("btn-enrol").disabled = true;
  $("btn-capture-frame").disabled = true;
}

$("btn-consent").addEventListener("click", async () => {
  if (!state.selectedParticipant) return;
  const text = $("consent-text").textContent;
  const sha = await sha256Hex(text);
  try {
    await API.post(`/participants/${state.selectedParticipant.id}/consent`, {
      consent_version: "v1.0",
      consent_text_sha256: sha,
      purposes: ["research_face_verification_eval"],
      accepted: true,
    });
    $("enrol-result").textContent = "Consent recorded.";
  } catch (err) { alert(err.message); }
});

$("btn-cam-start").addEventListener("click", async () => {
  cams.enrol = cams.enrol || makeCamera($("enrol-video"));
  try {
    await cams.enrol.start();
    $("btn-capture-frame").disabled = false;
    $("enrol-guidance").textContent = "Camera on. Capture 3-10 frames.";
  } catch (_) {
    $("enrol-guidance").textContent = "Camera permission denied.";
  }
});

$("btn-capture-frame").addEventListener("click", () => {
  if (!cams.enrol) return;
  state.enrolFrames.push({ image_b64: cams.enrol.capture() });
  $("frame-count").textContent = String(state.enrolFrames.length);
  $("btn-enrol").disabled = state.enrolFrames.length < 3;
});

$("btn-enrol").addEventListener("click", async () => {
  if (!state.selectedParticipant) return;
  try {
    const res = await API.post(`/participants/${state.selectedParticipant.id}/enrolment`, {
      frames: state.enrolFrames, replace: false,
    });
    $("enrol-result").textContent =
      `Enrolled ${res.accepted} template(s); ${res.rejected.length} rejected.`;
    state.enrolFrames = [];
    $("frame-count").textContent = "0";
    $("btn-enrol").disabled = true;
    await loadParticipants();
  } catch (err) { $("enrol-result").textContent = `Error: ${err.message}`; }
});

// ---- verify -----------------------------------------------------------------
function refreshParticipantSelectors() {
  const opts = state.participants
    .map((p) => `<option value="${p.id}" data-code="${p.subject_code}">${p.subject_code}</option>`)
    .join("");
  for (const id of ["verify-select", "probe-select", "claimed-select"]) {
    const sel = $(id);
    if (sel) sel.innerHTML = opts;
  }
  updateGroundTruth();
}

$("btn-verify-cam").addEventListener("click", async () => {
  cams.verify = cams.verify || makeCamera($("verify-video"));
  try { await cams.verify.start(); } catch (_) { alert("camera permission denied"); }
});

$("btn-verify-go").addEventListener("click", async () => {
  if (!cams.verify || !cams.verify.stream) { alert("start the camera first"); return; }
  const pid = Number($("verify-select").value);
  const box = $("verify-result");
  try {
    const res = await API.post("/verify", { claimed_participant_id: pid, image_b64: cams.verify.capture() });
    box.className = `result ${res.decision}`;
    box.textContent = `${res.decision.toUpperCase()} - score ${res.score.toFixed(3)} (threshold ${res.threshold.toFixed(3)})`;
  } catch (err) {
    box.className = "result fta";
    box.textContent = `${err.code || "error"}: ${err.message}`;
  }
});

// ---- trials -----------------------------------------------------------------
async function loadRuns() {
  const data = await API.get("/runs");
  const list = $("run-list");
  list.innerHTML = "";
  const sel = $("analysis-run");
  sel.innerHTML = "";
  for (const r of data.items) {
    const li = document.createElement("li");
    li.innerHTML = `<button data-rid="${r.id}">${r.name}</button> <span class="muted small">${r.status}, ${r.trial_count} trials</span>`;
    li.querySelector("button").addEventListener("click", () => {
      state.currentRun = r;
      $("trial-run").textContent = `Run: ${r.name} (${r.status})`;
    });
    list.appendChild(li);
    sel.innerHTML += `<option value="${r.id}">${r.name}</option>`;
  }
}

$("run-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try { await API.post("/runs", { name: fd.get("name") }); e.target.reset(); await loadRuns(); }
  catch (err) { alert(err.message); }
});

function updateGroundTruth() {
  const probe = $("probe-select");
  const claimed = $("claimed-select");
  if (!probe || !claimed || !probe.selectedOptions.length) return;
  const gt = probe.value === claimed.value ? "genuine" : "impostor";
  $("ground-truth").textContent = `Ground truth: ${gt}`;
}
["probe-select", "claimed-select"].forEach((id) => {
  const el = $(id);
  if (el) el.addEventListener("change", updateGroundTruth);
});

function populateTagSelectors() {
  const g = $("tag-group");
  g.innerHTML = Object.keys(state.conditionGroups).map((k) => `<option>${k}</option>`).join("");
  const updateValues = () => {
    const vals = state.conditionGroups[g.value] || [];
    $("tag-value").innerHTML = vals.map((v) => `<option>${v}</option>`).join("");
  };
  g.addEventListener("change", updateValues);
  updateValues();
}

$("btn-add-tag").addEventListener("click", () => {
  const tag = `${$("tag-group").value}:${$("tag-value").value}`;
  if (!state.trialTags.includes(tag)) state.trialTags.push(tag);
  renderTagChips();
});

function renderTagChips() {
  $("tag-chips").innerHTML = state.trialTags
    .map((t) => `<span class="chip" data-tag="${t}">${t} x</span>`).join("");
  $("tag-chips").querySelectorAll(".chip").forEach((c) =>
    c.addEventListener("click", () => {
      state.trialTags = state.trialTags.filter((t) => t !== c.dataset.tag);
      renderTagChips();
    }));
}

$("btn-trial-cam").addEventListener("click", async () => {
  cams.trial = cams.trial || makeCamera($("trial-video"));
  try { await cams.trial.start(); } catch (_) { alert("camera permission denied"); }
});

$("btn-trial-go").addEventListener("click", async () => {
  if (!state.currentRun) { alert("select a run"); return; }
  if (!cams.trial || !cams.trial.stream) { alert("start the camera first"); return; }
  const probeCode = $("probe-select").selectedOptions[0].dataset.code;
  const claimedCode = $("claimed-select").selectedOptions[0].dataset.code;
  try {
    const res = await API.post(`/runs/${state.currentRun.id}/trials`, {
      probe_label: probeCode, claimed_label: claimedCode,
      image_b64: cams.trial.capture(), condition_tags: state.trialTags.slice(),
    });
    $("trial-result").textContent =
      `Recorded: ${res.ground_truth} -> ${res.outcome}` +
      (res.score != null ? ` (score ${res.score.toFixed(3)})` : "") +
      (res.warnings.length ? ` [${res.warnings.join(", ")}]` : "");
    await loadRuns();
  } catch (err) { $("trial-result").textContent = `Error: ${err.message}`; }
});

// ---- analysis ---------------------------------------------------------------
$("btn-analyse").addEventListener("click", async () => {
  const runId = $("analysis-run").value;
  if (!runId) return;
  const thrInput = $("analysis-threshold").value;
  const q = thrInput ? `?threshold=${thrInput}` : "";
  try {
    const m = await API.get(`/runs/${runId}/metrics${q}`);
    renderMetrics(m);
    const sweep = await API.get(`/runs/${runId}/sweep`);
    drawSweep($("sweep-canvas"), sweep);
    const eer = sweep.eer.interpolated;
    $("eer-box").textContent = eer
      ? `EER ${(eer.value * 100).toFixed(1)}% at threshold ${eer.threshold.toFixed(3)} (interpolated).`
      : `EER not available (${sweep.eer.reason || "insufficient data"}).`;
    $("export-links").innerHTML =
      `<a href="/api/runs/${runId}/export/trials.csv">trials.csv</a> ` +
      `<a href="/api/runs/${runId}/export/metrics.csv">metrics.csv</a> ` +
      `<a href="/api/runs/${runId}/export/sweep.csv">sweep.csv</a>`;
  } catch (err) { alert(err.message); }
});

function fmtPct(v) { return v == null ? "n/a" : `${(v * 100).toFixed(1)}%`; }
function renderMetrics(m) {
  const tile = (label, val, ci) =>
    `<div class="metric"><span class="muted small">${label}</span><b>${val}</b>` +
    (ci ? `<span class="muted small">95% ${fmtPct(ci[0])}-${fmtPct(ci[1])}</span>` : "") + `</div>`;
  $("metrics-box").innerHTML =
    tile("FAR", fmtPct(m.far), m.far_ci95) +
    tile("FRR", fmtPct(m.frr), m.frr_ci95) +
    tile("GAR", fmtPct(m.gar), m.gar_ci95) +
    tile("Accuracy", fmtPct(m.accuracy)) +
    tile("Balanced", fmtPct(m.balanced_accuracy)) +
    tile("Genuine n", m.n_genuine) +
    tile("Impostor n", m.n_impostor) +
    tile("FTA", fmtPct(m.fta_rate)) +
    (m.warnings && m.warnings.length ? `<div class="metric"><span class="muted small">warnings</span><b>!</b><span class="small">${m.warnings.join(", ")}</span></div>` : "");
}

// ---- admin ------------------------------------------------------------------
async function loadSettings() {
  try {
    const s = await API.get("/settings");
    $("settings-box").innerHTML = Object.entries(s)
      .map(([k, v]) => `<div class="small"><code>${k}</code> = ${JSON.stringify(v)}</div>`).join("");
    if (s.operating_threshold != null) $("set-threshold").value = s.operating_threshold;
  } catch (err) { $("settings-box").textContent = err.message; }
}

$("btn-set-threshold").addEventListener("click", async () => {
  try {
    await API.put("/settings/operating_threshold", {
      value: Number($("set-threshold").value), reason: $("set-reason").value || "manual",
    });
    await loadSettings();
    alert("threshold updated");
  } catch (err) { alert(err.message); }
});

$("btn-audit-verify").addEventListener("click", async () => {
  try {
    const r = await API.get("/audit/verify");
    $("audit-status").textContent = r.valid
      ? `Chain OK (${r.events} events).` : `BROKEN at id ${r.first_broken_id}.`;
  } catch (err) { $("audit-status").textContent = err.message; }
});

$("btn-retention").addEventListener("click", async () => {
  try {
    const r = await API.post("/admin/retention/run?dry_run=true");
    $("retention-status").textContent =
      `Dry run: ${r.debug_frames_deleted} frames, ${r.templates_deleted} templates would be deleted.`;
  } catch (err) { $("retention-status").textContent = err.message; }
});

// Load admin data when the admin tab is first opened.
document.querySelector('#tabs button[data-tab="admin"]').addEventListener("click", loadSettings);

// ---- utils ------------------------------------------------------------------
async function sha256Hex(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}
