let password = sessionStorage.getItem("xixi-admin-password") || "";
const el = (id) => document.getElementById(id);

function headers(extra = {}) { return { "X-Admin-Password": password, ...extra }; }
function toast(message) { const node = el("toast"); node.textContent = message; node.classList.add("show"); setTimeout(() => node.classList.remove("show"), 2600); }
function formatSize(bytes) { if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`; return `${(bytes / 1024 / 1024).toFixed(1)} MB`; }

async function api(url, options = {}) {
  options.headers = headers(options.headers || {});
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "操作失败");
  return payload;
}

async function login(candidate) {
  password = candidate;
  await api("/api/admin/login", { method: "POST" });
  sessionStorage.setItem("xixi-admin-password", password);
  el("loginPanel").hidden = true;
  el("adminApp").hidden = false;
  await Promise.all([loadDocuments(), loadSettings(), loadVoiceSettings()]);
}

async function loadDocuments() {
  const payload = await api("/api/admin/documents");
  el("adminStats").textContent = `${payload.documents.length} 份资料 · ${payload.chunks} 个知识片段`;
  const list = el("documentList");
  list.replaceChildren();
  if (!payload.documents.length) { const empty = document.createElement("div"); empty.className = "empty"; empty.textContent = "还没有资料，请先上传教材。"; list.append(empty); return; }
  payload.documents.forEach((doc) => {
    const row = document.createElement("div"); row.className = "document";
    const info = document.createElement("div");
    const title = document.createElement("strong"); title.textContent = doc.filename;
    const meta = document.createElement("small"); meta.textContent = `${formatSize(doc.size)} · ${new Date(doc.modified * 1000).toLocaleString("zh-CN")}`;
    info.append(title, meta);
    const remove = document.createElement("button"); remove.type = "button"; remove.className = "danger"; remove.textContent = "删除";
    remove.addEventListener("click", async () => {
      if (!confirm(`确定删除“${doc.filename}”并重建索引吗？`)) return;
      try { await api(`/api/admin/documents/${doc.id}`, { method: "DELETE" }); toast("资料已删除"); await loadDocuments(); } catch (error) { toast(error.message); }
    });
    row.append(info, remove); list.append(row);
  });
}

async function loadSettings() {
  const data = await api("/api/admin/settings");
  el("baseUrl").value = data.base_url || "";
  el("model").value = data.model || "";
  el("apiKey").placeholder = data.api_key_set ? "已保存密钥，留空则不修改" : "输入 API Key";
}

async function loadVoiceSettings() {
  const data = await api("/api/admin/voice-settings");
  el("ttsUrl").value = data.service_url || "";
  el("ttsSpeed").value = data.speed ?? 0.96;
  el("browserFallback").checked = data.allow_browser_fallback !== false;
  populateSampleSelect("defaultSample", data.samples || [], "未选择", data.default_sample_id || "");
  populateSampleSelect("encourageSample", data.samples || [], "使用默认声音", data.style_sample_ids?.encourage || "");
  populateSampleSelect("correctSample", data.samples || [], "使用默认声音", data.style_sample_ids?.correct || "");
  populateSampleSelect("celebrateSample", data.samples || [], "使用默认声音", data.style_sample_ids?.celebrate || "");
  renderSamples(data.samples || []);
}

function populateSampleSelect(id, samples, emptyLabel, value) {
  const select = el(id);
  select.replaceChildren(new Option(emptyLabel, ""));
  samples.forEach((sample) => select.append(new Option(`${sample.style} · ${sample.transcript.slice(0, 32)}`, sample.id)));
  select.value = value;
}

function renderSamples(samples) {
  const list = el("sampleList");
  list.replaceChildren();
  if (!samples.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "还没有真人声音样本。";
    list.append(empty);
    return;
  }
  samples.forEach((sample) => {
    const row = document.createElement("div"); row.className = "document";
    const info = document.createElement("div");
    const title = document.createElement("strong"); title.textContent = `${sample.style} · ${sample.transcript}`;
    const meta = document.createElement("small"); meta.textContent = sample.filename;
    if (sample.source_url) {
      const source = document.createElement("a");
      source.href = sample.source_url;
      source.target = "_blank";
      source.rel = "noopener noreferrer";
      source.textContent = sample.source_title || "来源视频";
      meta.append(" · ", source);
      if (Number.isFinite(Number(sample.clip_start_seconds)) && Number.isFinite(Number(sample.clip_end_seconds))) {
        meta.append(`（${sample.clip_start_seconds}s–${sample.clip_end_seconds}s）`);
      }
    }
    info.append(title, meta);
    const remove = document.createElement("button"); remove.type = "button"; remove.className = "danger"; remove.textContent = "删除";
    remove.addEventListener("click", async () => {
      if (!confirm("确定删除这个声音样本吗？")) return;
      try { await api(`/api/admin/voice-samples/${sample.id}`, { method: "DELETE" }); toast("声音样本已删除"); await loadVoiceSettings(); } catch (error) { toast(error.message); }
    });
    row.append(info, remove); list.append(row);
  });
}

el("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault(); el("loginNotice").textContent = "";
  try { await login(el("password").value); } catch (error) { el("loginNotice").textContent = error.message; }
});
el("uploadForm").addEventListener("submit", async (event) => {
  event.preventDefault(); const file = el("fileInput").files[0]; if (!file) return;
  const data = new FormData(); data.append("file", file);
  try { toast("正在读取资料并重建索引…"); await api("/api/admin/documents", { method: "POST", body: data }); el("fileInput").value = ""; toast("资料已加入知识库"); await loadDocuments(); } catch (error) { toast(error.message); }
});
el("reindexButton").addEventListener("click", async () => { try { await api("/api/admin/reindex", { method: "POST" }); toast("索引已重建"); await loadDocuments(); } catch (error) { toast(error.message); } });
el("settingsForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/admin/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ base_url: el("baseUrl").value, model: el("model").value, api_key: el("apiKey").value }) });
    el("apiKey").value = ""; toast("模型设置已保存"); await loadSettings();
  } catch (error) { toast(error.message); }
});
el("voiceSettingsForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/admin/voice-settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        service_url: el("ttsUrl").value,
        default_sample_id: el("defaultSample").value,
        style_sample_ids: {
          encourage: el("encourageSample").value,
          correct: el("correctSample").value,
          celebrate: el("celebrateSample").value,
        },
        allow_browser_fallback: el("browserFallback").checked,
        speed: Number(el("ttsSpeed").value || 0.96),
        volume: 1.0,
      }),
    });
    toast("语音设置已保存");
  } catch (error) { toast(error.message); }
});
el("sampleForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = el("sampleFile").files[0];
  if (!file) return;
  const data = new FormData();
  data.append("file", file);
  data.append("transcript", el("sampleTranscript").value);
  data.append("style", el("sampleStyle").value);
  data.append("consent", String(el("sampleConsent").checked));
  try {
    await api("/api/admin/voice-samples", { method: "POST", body: data });
    el("sampleFile").value = ""; el("sampleTranscript").value = ""; el("sampleConsent").checked = false;
    toast("声音样本已保存"); await loadVoiceSettings();
  } catch (error) { toast(error.message); }
});
el("voiceTestForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const data = await api("/api/admin/voice-test", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: el("voiceTestText").value, sample_id: el("defaultSample").value }) });
    const audio = el("voicePreview"); audio.src = data.audio_url; audio.hidden = false; await audio.play();
  } catch (error) { toast(error.message); }
});

if (password) login(password).catch(() => sessionStorage.removeItem("xixi-admin-password"));
