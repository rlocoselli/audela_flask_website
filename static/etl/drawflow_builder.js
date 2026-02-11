const editor = new Drawflow(document.getElementById("drawflow"));
editor.start();

let _configModal = null;

function _getBootstrapModal() {
  const el = document.getElementById("nodeConfigModal");
  if (!el) return null;
  if (!_configModal) {
    _configModal = new bootstrap.Modal(el);
  }
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
  if (type === "extract.http") {
    return { url: "", method: "GET", headers: {}, params: {}, timeout: 30 };
  }
  if (type === "extract.sql") {
    return { query: "", connection_name: "" };
  }
  if (type === "transform.mapping") {
    return { fields: {} };
  }
  if (type === "load.warehouse") {
    return {
      table: "",
      schema: "public",
      mode: "append",
      create_table_if_missing: true,
      add_columns_if_missing: true,
      connection_name: ""
    };
  }
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

function saveWorkflow() {
  const workflow = editor.export();
  _fetchJson("/etl/api/workflows", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(workflow)
  })
  .then(data => {
    alert("Workflow saved successfully!");
    console.log(data);
  })
  .catch(err => {
    console.error(err);
    alert("Error saving workflow: " + err.message);
  });
}

function runWorkflow() {
  const wf = editor.export();
  _fetchJson("/etl/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(wf)
  })
  .then(data => {
    console.log("Run result:", data);
    alert("Workflow executed.");
  })
  .catch(err => {
    console.error(err);
    alert("Error executing workflow: " + err.message);
  });
}

function previewWorkflow() {
  const wf = editor.export();
  _fetchJson("/etl/api/preview?limit=20", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(wf)
  })
  .then(data => {
    console.log("Preview:", data);
    const el = document.getElementById("etlPreview");
    if (el) el.textContent = _jsonPretty(data.previews || data);
  })
  .catch(err => {
    console.error(err);
    alert("Error previewing workflow: " + err.message);
  });
}

// ---------- Node config modal (double click) ----------

function _nodeIdFromElement(el) {
  // drawflow nodes have id like "node-3"
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

  // Build a simple form depending on type
  let html = "";

  if (type === "extract.http") {
    html += `
      <div class="mb-3">
        <label class="form-label">URL</label>
        <input class="form-control" id="cfg_url" value="${cfg.url || ""}" placeholder="https://api.example.com/endpoint">
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
        <label class="form-label">Headers (JSON)</label>
        <textarea class="form-control" id="cfg_headers" rows="4" placeholder='{"Authorization":"Bearer ..."}'>${_jsonPretty(cfg.headers || {})}</textarea>
      </div>
      <div class="mt-3">
        <label class="form-label">Params (JSON)</label>
        <textarea class="form-control" id="cfg_params" rows="4" placeholder='{"q":"Grenoble"}'>${_jsonPretty(cfg.params || {})}</textarea>
      </div>
    `;
  } else if (type === "extract.sql") {
    html += `
      <div class="mb-3">
        <label class="form-label">SQL Query</label>
        <textarea class="form-control" id="cfg_query" rows="6" placeholder="SELECT * FROM ...">${cfg.query || ""}</textarea>
      </div>
      <div class="mb-3">
        <label class="form-label">Connection name (optional)</label>
        <input class="form-control" id="cfg_conn" value="${cfg.connection_name || ""}" placeholder="warehouse / source_db ...">
        <div class="form-text">Connection catalog is available via /etl/api/connections (MVP: validated if exists).</div>
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
        <div class="col-md-6">
          <label class="form-label">Connection name (optional)</label>
          <input class="form-control" id="cfg_conn" value="${cfg.connection_name || ""}" placeholder="warehouse">
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
    cfg.url = document.getElementById("cfg_url").value.trim();
    cfg.method = document.getElementById("cfg_method").value.trim();
    cfg.timeout = parseInt(document.getElementById("cfg_timeout").value || "30", 10);
    const headers = _safeJsonParse(document.getElementById("cfg_headers").value, {});
    const params = _safeJsonParse(document.getElementById("cfg_params").value, {});
    if (headers === null) return alert("Headers JSON invalid");
    if (params === null) return alert("Params JSON invalid");
    cfg.headers = headers;
    cfg.params = params;
  } else if (type === "extract.sql") {
    cfg.query = document.getElementById("cfg_query").value;
    cfg.connection_name = document.getElementById("cfg_conn").value.trim();
  } else if (type === "transform.mapping") {
    const fields = _safeJsonParse(document.getElementById("cfg_fields").value, {});
    if (fields === null) return alert("Fields JSON invalid");
    cfg.fields = fields;
  } else if (type === "load.warehouse") {
    cfg.schema = document.getElementById("cfg_schema").value.trim() || "public";
    cfg.table = document.getElementById("cfg_table").value.trim();
    cfg.mode = document.getElementById("cfg_mode").value.trim() || "append";
    cfg.connection_name = document.getElementById("cfg_conn").value.trim();
    cfg.create_table_if_missing = document.getElementById("cfg_create").checked;
    cfg.add_columns_if_missing = document.getElementById("cfg_addcols").checked;
  }

  // update node data
  node.data = node.data || {};
  node.data.config = cfg;
  editor.updateNodeDataFromId(nodeId, node.data);

  const modal = _getBootstrapModal();
  if (modal) modal.hide();
}
