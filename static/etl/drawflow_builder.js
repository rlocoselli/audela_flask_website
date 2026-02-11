const editor = new Drawflow(document.getElementById("drawflow"));
editor.start();

let _configModal = null;
let _dbSources = [];
let _apiSources = [];
let _workflows = [];

function _getBootstrapModal() {
  const el = document.getElementById("nodeConfigModal");
  if (!el) return null;
  if (!_configModal) _configModal = new bootstrap.Modal(el);
  return _configModal;
}

function _safeJsonParse(val, fallback) {
  if (val === null || val === undefined) return fallback;
  const s = String(val).trim();
  if (!s) return fallback;
  try { return JSON.parse(s); } catch (e) { return null; }
}

function _jsonPretty(obj) {
  try { return JSON.stringify(obj, null, 2); } catch(e) { return String(obj); }
}

function _defaultConfig(type) {
  if (type === "extract.http") return { api_source_id: "", path: "", method: "GET", headers: {}, params: {}, timeout: 30 };
  if (type === "extract.sql") return { query: "", db_source_id: "" };
  if (type === "transform.mapping") return { fields: {} };
  if (type === "load.warehouse") return {
    table: "", schema: "public", mode: "append",
    create_table_if_missing: true, add_columns_if_missing: true,
    warehouse_source_id: ""
  };
  return {};
}

function addNode(type) {
  const cfg = _defaultConfig(type);
  const nodeId = editor.addNode(
    type, 1, 1, 100, 100, type,
    { type: type, config: cfg },
    `<div>
        <strong>${type}</strong>
        <div style="font-size:11px;color:#666">Double-click to configure</div>
     </div>`
  );
  console.log("Node added:", nodeId);
}

function _fetchJson(url, options) {
  return fetch(url, options).then(async (res) => {
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch(e) { data = { raw: text }; }
    if (!res.ok) {
      const msg = (data && (data.error || data.message)) ? (data.error || data.message) : `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data;
  });
}

// ---------------- Workflows ----------------

function getWorkflowName() {
  const el = document.getElementById("workflowName");
  const v = el ? el.value.trim() : "";
  return v || "workflow";
}
function setWorkflowName(name) {
  const el = document.getElementById("workflowName");
  if (el) el.value = name || "";
}

function refreshWorkflows() {
  _fetchJson("/etl/api/workflows", { method: "GET" })
    .then(data => {
      _workflows = data.workflows || [];
      const sel = document.getElementById("savedWorkflows");
      if (!sel) return;
      sel.innerHTML = "";
      if (!_workflows.length) {
        sel.innerHTML = `<option value="">(empty)</option>`;
        return;
      }
      _workflows.forEach(w => {
        const opt = document.createElement("option");
        opt.value = w.name;
        opt.textContent = w.name;
        sel.appendChild(opt);
      });
    })
    .catch(err => console.error("workflows:", err));
}

function loadSelectedWorkflow() {
  const sel = document.getElementById("savedWorkflows");
  const name = sel ? sel.value : "";
  if (!name) return;
  _fetchJson(`/etl/api/workflows/${encodeURIComponent(name)}`, { method: "GET" })
    .then(res => {
      setWorkflowName(res.name);
      if (res.kind === "drawflow") {
        editor.clear();
        editor.import(res.data);
      } else {
        const el = document.getElementById("etlPreview");
        if (el) el.textContent = _jsonPretty(res.data);
        alert("Loaded workflow definition (preview). For now, graphs load from Drawflow format.");
      }
    })
    .catch(err => alert("Load error: " + err.message));
}

// ---------------- Sources lists & tests ----------------

function refreshDbSources() {
  _fetchJson("/etl/api/sources/db", { method: "GET" })
    .then(data => {
      _dbSources = data.sources || [];
      const sel = document.getElementById("dbSourceSelect");
      if (sel) {
        sel.innerHTML = `<option value="">(none)</option>`;
        _dbSources.forEach(s => {
          const opt = document.createElement("option");
          opt.value = s.id;
          opt.textContent = `${s.name} (${s.type})`;
          sel.appendChild(opt);
        });
      }
    })
    .catch(err => console.error("db sources:", err));
}

function refreshApiSources() {
  _fetchJson("/etl/api/sources/api", { method: "GET" })
    .then(data => {
      _apiSources = data.sources || [];
      const sel = document.getElementById("apiSourceSelect");
      if (sel) {
        sel.innerHTML = `<option value="">(none)</option>`;
        _apiSources.forEach(s => {
          const opt = document.createElement("option");
          opt.value = s.id;
          opt.textContent = `${s.name}`;
          sel.appendChild(opt);
        });
      }
    })
    .catch(err => console.error("api sources:", err));
}

function testSelectedDbSource() {
  const sel = document.getElementById("dbSourceSelect");
  const id = sel ? sel.value : "";
  if (!id) return alert("Select a DB source");
  _fetchJson(`/etl/api/sources/db/${encodeURIComponent(id)}/test`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
    .then(res => {
      const el = document.getElementById("etlPreview");
      if (el) el.textContent = _jsonPretty(res);
      alert(res.ok ? "DB source OK" : "DB source failed");
    })
    .catch(err => alert("Test error: " + err.message));
}

function testSelectedApiSource() {
  const sel = document.getElementById("apiSourceSelect");
  const id = sel ? sel.value : "";
  if (!id) return alert("Select an API source");
  _fetchJson(`/etl/api/sources/api/${encodeURIComponent(id)}/test`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
    .then(res => {
      const el = document.getElementById("etlPreview");
      if (el) el.textContent = _jsonPretty(res);
      alert(res.ok ? "API source OK" : "API source failed");
    })
    .catch(err => alert("Test error: " + err.message));
}

function _dbOptionsHtml(selectedId) {
  const opts = [`<option value="">(none)</option>`]
    .concat(_dbSources.map(s => `<option value="${s.id}" ${String(s.id)===String(selectedId)?"selected":""}>${s.name} (${s.type})</option>`));
  return opts.join("");
}

function _apiOptionsHtml(selectedId) {
  const opts = [`<option value="">(none)</option>`]
    .concat(_apiSources.map(s => `<option value="${s.id}" ${String(s.id)===String(selectedId)?"selected":""}>${s.name}</option>`));
  return opts.join("");
}

// ---------------- Save/Run/Preview ----------------

function saveWorkflow() {
  const workflow = editor.export();
  workflow.name = getWorkflowName();

  _fetchJson("/etl/api/workflows", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(workflow)
  })
  .then(data => {
    refreshWorkflows();
    const el = document.getElementById("etlPreview");
    if (el) el.textContent = _jsonPretty(data);
    if (data.warning) alert("Saved graph. Warning: " + data.warning);
    else alert("Workflow saved successfully!");
  })
  .catch(err => alert("Error saving workflow: " + err.message));
}

function previewWorkflow() {
  const wf = editor.export();
  wf.name = getWorkflowName();

  _fetchJson("/etl/api/preview?limit=20", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(wf)
  })
  .then(data => {
    const el = document.getElementById("etlPreview");
    if (el) el.textContent = _jsonPretty(data.previews || data);
  })
  .catch(err => alert("Error previewing workflow: " + err.message));
}

function _setActiveStep(stepId) {
  // remove existing
  document.querySelectorAll(".drawflow-node.etl-active-step").forEach(n => n.classList.remove("etl-active-step"));
  if (!stepId) return;
  const el = document.getElementById("node-" + stepId);
  if (el) el.classList.add("etl-active-step");
}

async function runWorkflow() {
  const wf = editor.export();
  wf.name = getWorkflowName();

  const elPreview = document.getElementById("etlPreview");
  if (elPreview) elPreview.textContent = "Running...";

  _setActiveStep(null);

  const resp = await fetch("/etl/api/run_stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(wf)
  });

  if (!resp.ok) {
    const t = await resp.text();
    throw new Error(t || `HTTP ${resp.status}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buf = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    let idx;
    while ((idx = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 1);
      if (!line) continue;

      let msg;
      try { msg = JSON.parse(line); } catch(e) { continue; }

      if (msg.event === "step_start") {
        const stepId = (msg.step && msg.step.id) ? msg.step.id : null;
        _setActiveStep(stepId);
        if (elPreview) elPreview.textContent = `Running step: ${msg.step.type} (#${stepId})`;
      } else if (msg.event === "step_end") {
        const stepId = (msg.step && msg.step.id) ? msg.step.id : null;
        if (elPreview) elPreview.textContent = `Done step: ${msg.step.type} (#${stepId}) rows_out=${msg.rows_out}`;
      } else if (msg.event === "done") {
        _setActiveStep(null);
        if (elPreview) elPreview.textContent = _jsonPretty(msg.result);
      } else if (msg.event === "error") {
        _setActiveStep(null);
        if (elPreview) elPreview.textContent = "Error: " + msg.error;
        alert("Run error: " + msg.error);
      }
    }
  }
}

// ---------- Node config modal (double click) ----------

function _nodeIdFromElement(el) {
  if (!el || !el.id) return null;
  const m = el.id.match(/^node-(\d+)$/);
  return m ? m[1] : null;
}

document.getElementById("drawflow").addEventListener("dblclick", (e) => {
  const nodeEl = e.target.closest(".drawflow-node");
  if (!nodeEl) return;
  const nodeId = _nodeIdFromElement(nodeEl);
  if (!nodeId) return;
  openNodeConfig(nodeId);
});

function openNodeConfig(nodeId) {
  const node = editor.getNodeFromId(nodeId);
  if (!node) return;

  const type = node.name;
  const cfg = (node.data && node.data.config) ? node.data.config : _defaultConfig(type);

  const titleEl = document.getElementById("nodeConfigTitle");
  const idEl = document.getElementById("cfgNodeId");
  const formEl = document.getElementById("cfgForm");
  if (titleEl) titleEl.textContent = `${type} (#${nodeId})`;
  if (idEl) idEl.value = nodeId;

  let html = "";

  if (type === "extract.http") {
    html += `
      <div class="mb-3">
        <label class="form-label">API Source</label>
        <select class="form-select" id="cfg_api_source">
          ${_apiOptionsHtml(cfg.api_source_id)}
        </select>
        <div class="form-text">Select existing API source (optional). If set, URL is base_url + path.</div>
      </div>
      <div class="mb-3">
        <label class="form-label">Path (optional)</label>
        <input class="form-control" id="cfg_path" value="${cfg.path || ""}" placeholder="/v1/items or ?q=...">
      </div>
      <div class="row g-2">
        <div class="col-md-4">
          <label class="form-label">Method</label>
          <select class="form-select" id="cfg_method">
            ${["GET","POST","PUT","PATCH","DELETE"].map(m => `<option ${((cfg.method||"GET").toUpperCase()===m)?"selected":""}>${m}</option>`).join("")}
          </select>
        </div>
        <div class="col-md-4">
          <label class="form-label">Timeout (sec)</label>
          <input class="form-control" id="cfg_timeout" type="number" value="${cfg.timeout ?? 30}">
        </div>
      </div>
      <div class="mt-3">
        <label class="form-label">Headers override (JSON)</label>
        <textarea class="form-control" id="cfg_headers" rows="4" placeholder='{"Authorization":"Bearer ..."}'>${_jsonPretty(cfg.headers || {})}</textarea>
      </div>
      <div class="mt-3">
        <label class="form-label">Params override (JSON)</label>
        <textarea class="form-control" id="cfg_params" rows="4" placeholder='{"q":"Grenoble"}'>${_jsonPretty(cfg.params || {})}</textarea>
      </div>
    `;
  } else if (type === "extract.sql") {
    html += `
      <div class="mb-3">
        <label class="form-label">DB Source</label>
        <select class="form-select" id="cfg_db_source">
          ${_dbOptionsHtml(cfg.db_source_id)}
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label">SQL Query</label>
        <textarea class="form-control" id="cfg_query" rows="7" placeholder="SELECT * FROM ...">${cfg.query || ""}</textarea>
      </div>
    `;
  } else if (type === "transform.mapping") {
    html += `
      <div class="mb-3">
        <label class="form-label">Fields mapping (JSON)</label>
        <textarea class="form-control" id="cfg_fields" rows="10" placeholder='{"city":"$.name","temp":"$.main.temp"}'>${_jsonPretty(cfg.fields || {})}</textarea>
      </div>
    `;
  } else if (type === "load.warehouse") {
    html += `
      <div class="mb-3">
        <label class="form-label">Warehouse (DB Source)</label>
        <select class="form-select" id="cfg_wh_source">
          ${_dbOptionsHtml(cfg.warehouse_source_id)}
        </select>
      </div>
      <div class="row g-2">
        <div class="col-md-6">
          <label class="form-label">Schema</label>
          <input class="form-control" id="cfg_schema" value="${cfg.schema || "public"}">
        </div>
        <div class="col-md-6">
          <label class="form-label">Table</label>
          <input class="form-control" id="cfg_table" value="${cfg.table || ""}" placeholder="dwh_table_name">
        </div>
      </div>
      <div class="row g-2 mt-2">
        <div class="col-md-6">
          <label class="form-label">Mode</label>
          <select class="form-select" id="cfg_mode">
            <option ${((cfg.mode||"append")==="append")?"selected":""}>append</option>
          </select>
        </div>
      </div>
      <div class="form-check mt-3">
        <input class="form-check-input" type="checkbox" id="cfg_create" ${cfg.create_table_if_missing ? "checked" : ""}>
        <label class="form-check-label" for="cfg_create">Create table if missing</label>
      </div>
      <div class="form-check mt-2">
        <input class="form-check-input" type="checkbox" id="cfg_addcols" ${cfg.add_columns_if_missing ? "checked" : ""}>
        <label class="form-check-label" for="cfg_addcols">Add missing columns</label>
      </div>
    `;
  } else {
    html += `<div class="alert alert-warning">No config UI for type: ${type}</div>`;
  }

  if (formEl) formEl.innerHTML = html;

  const modal = _getBootstrapModal();
  if (modal) modal.show();
}

function saveNodeConfig() {
  const nodeId = document.getElementById("cfgNodeId").value;
  const node = editor.getNodeFromId(nodeId);
  if (!node) return;

  const type = node.name;
  let cfg = {};

  if (type === "extract.http") {
    const sel = document.getElementById("cfg_api_source");
    cfg.api_source_id = sel ? sel.value : "";
    cfg.path = document.getElementById("cfg_path").value.trim();
    cfg.method = document.getElementById("cfg_method").value.trim();
    cfg.timeout = parseInt(document.getElementById("cfg_timeout").value || "30", 10);
    const headers = _safeJsonParse(document.getElementById("cfg_headers").value, {});
    const params = _safeJsonParse(document.getElementById("cfg_params").value, {});
    if (headers === null) return alert("Headers JSON invalid");
    if (params === null) return alert("Params JSON invalid");
    cfg.headers = headers;
    cfg.params = params;
  } else if (type === "extract.sql") {
    const sel = document.getElementById("cfg_db_source");
    cfg.db_source_id = sel ? sel.value : "";
    cfg.query = document.getElementById("cfg_query").value;
  } else if (type === "transform.mapping") {
    const fields = _safeJsonParse(document.getElementById("cfg_fields").value, {});
    if (fields === null) return alert("Fields JSON invalid");
    cfg.fields = fields;
  } else if (type === "load.warehouse") {
    const sel = document.getElementById("cfg_wh_source");
    cfg.warehouse_source_id = sel ? sel.value : "";
    cfg.schema = document.getElementById("cfg_schema").value.trim() || "public";
    cfg.table = document.getElementById("cfg_table").value.trim();
    cfg.mode = document.getElementById("cfg_mode").value.trim() || "append";
    cfg.create_table_if_missing = document.getElementById("cfg_create").checked;
    cfg.add_columns_if_missing = document.getElementById("cfg_addcols").checked;
  }

  node.data = node.data || {};
  node.data.config = cfg;
  editor.updateNodeDataFromId(nodeId, node.data);

  const modal = _getBootstrapModal();
  if (modal) modal.hide();
}

// ---------------- init ----------------
function initEtlBuilder() {
  refreshWorkflows();
  refreshDbSources();
  refreshApiSources();

  const params = new URLSearchParams(window.location.search);
  const load = params.get("load");
  if (load) {
    _fetchJson(`/etl/api/workflows/${encodeURIComponent(load)}`, { method: "GET" })
      .then(res => {
        setWorkflowName(res.name);
        if (res.kind === "drawflow") {
          editor.clear();
          editor.import(res.data);
        }
      })
      .catch(err => console.error(err));
  }
}
document.addEventListener("DOMContentLoaded", initEtlBuilder);
