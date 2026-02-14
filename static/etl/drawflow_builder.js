const editor = new Drawflow(document.getElementById("drawflow"));
editor.start();
const t = (window.t ? window.t : (k) => k);


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
    .concat(_dbSources.map(s => `<option value="${s.id}" data-dbtype="${s.type}" ${String(s.id)===String(selectedId)?"selected":""}>${s.name} (${s.type})</option>`));
  return opts.join("");
}

function _apiOptionsHtml(selectedId) {
  const opts = [`<option value="">(none)</option>`]
    .concat(_apiSources.map(s => `<option value="${s.id}" ${String(s.id)===String(selectedId)?"selected":""}>${s.name}</option>`));
  return opts.join("");
}


// -------------------------------
// extract.sql modal (CodeMirror + NL -> SQL + Query Builder)
// -------------------------------
let _extractSqlUi = {
  cm: null,
  schemaMeta: null,
  tablesMap: {},
  tablesFlat: [],
  currentDbType: "",
  qb: null,
  _onInputRead: null,
};

function _destroyExtractSqlUi() {
  try {
    if (_extractSqlUi.cm && typeof _extractSqlUi.cm.toTextArea === "function") {
      _extractSqlUi.cm.toTextArea();
    }
  } catch (e) {}
  _extractSqlUi = {
    cm: null,
    schemaMeta: null,
    tablesMap: {},
    tablesFlat: [],
    currentDbType: "",
    qb: null,
    _onInputRead: null,
  };
}

function _getCsrfToken() {
  const el = document.querySelector('meta[name="csrf-token"]');
  return el ? el.getAttribute("content") : "";
}

function _sqlLiteral(val) {
  const v = String(val ?? "").trim();
  if (!v) return "''";
  const numLike = /^[+-]?\d+(\.\d+)?$/.test(v);
  if (numLike) return v;
  return "'" + v.replace(/'/g, "''") + "'";
}

function _sqlLikeLiteral(val) {
  const v = String(val ?? "").trim();
  if (!v) return "''";
  const esc = v.replace(/'/g, "''");
  if (esc.includes("%")) return "'" + esc + "'";
  return "'%" + esc + "%'";
}

function _sqlLimitClause(dbType, limitValue) {
  const db = String(dbType || "").toLowerCase();
  const lim = parseInt(limitValue || "0", 10);
  if (!lim || lim <= 0) return { selectPrefix: "", suffix: "" };

  if (db.includes("sqlserver") || db.includes("mssql")) {
    return { selectPrefix: `TOP ${lim} `, suffix: "" };
  }
  return { selectPrefix: "", suffix: ` LIMIT ${lim}` };
}

function _buildTablesMap(meta) {
  const tables = {};
  const flat = [];
  if (!meta || !meta.schemas) return { tables, flat };

  meta.schemas.forEach(s => {
    const schemaName = s.name || "";
    (s.tables || []).forEach(t => {
      const tableName = t.name || "";
      const key = schemaName ? `${schemaName}.${tableName}` : tableName;
      flat.push(key);
      tables[key] = {};
      (t.columns || []).forEach(c => {
        if (c && c.name) tables[key][c.name] = c.type || "";
      });
    });
  });

  return { tables, flat };
}

function _setSchemaHtml(container, meta) {
  if (!container) return;
  if (!meta || !meta.schemas) {
    container.innerHTML = `<div class="text-muted small">(sem metadados)</div>`;
    return;
  }

  let html = "";
  meta.schemas.forEach(s => {
    const schemaName = s.name || "";
    html += `<div class="mb-2"><div class="fw-semibold">${schemaName || "public"}</div>`;
    (s.tables || []).forEach(t => {
      const tableName = t.name || "";
      const fullName = schemaName ? `${schemaName}.${tableName}` : tableName;
      html += `<details class="ms-2 mb-1">
        <summary class="cursor-pointer">
          <button type="button" class="btn btn-link p-0 text-decoration-none" data-ins="${fullName}">${tableName}</button>
        </summary>
        <div class="ms-2 mt-1">`;
      (t.columns || []).forEach(c => {
        const col = c.name || "";
        const typ = c.type ? ` <span class="text-muted">(${c.type})</span>` : "";
        html += `<div class="d-flex justify-content-between align-items-center gap-2">
          <button type="button" class="btn btn-link p-0 text-decoration-none small" data-ins="${col}">${col}</button>
          <span class="small text-muted">${typ}</span>
        </div>`;
      });
      html += `</div></details>`;
    });
    html += `</div>`;
  });
  container.innerHTML = html;
}

function _insertTextIntoEditor(text) {
  const ta = document.getElementById("cfg_query");
  if (_extractSqlUi.cm) {
    _extractSqlUi.cm.focus();
    _extractSqlUi.cm.replaceSelection(text);
    return;
  }
  if (!ta) return;
  const start = ta.selectionStart || 0;
  const end = ta.selectionEnd || 0;
  const before = ta.value.slice(0, start);
  const after = ta.value.slice(end);
  ta.value = before + text + after;
  const pos = start + text.length;
  ta.setSelectionRange(pos, pos);
  ta.focus();
}

function _refreshAutocomplete() {
  if (!_extractSqlUi.cm || typeof CodeMirror === "undefined") return;

  _extractSqlUi.cm.setOption("hintOptions", { tables: _extractSqlUi.tablesMap });

  // (re)attach inputRead handler
  try {
    if (_extractSqlUi._onInputRead) _extractSqlUi.cm.off("inputRead", _extractSqlUi._onInputRead);
  } catch (e) {}

  const handler = function(cm, change) {
    if (!change || change.origin === "setValue") return;
    // Don't autocomplete after deleting
    if (change.text && change.text.length === 1 && change.text[0] === "") return;

    const cur = cm.getCursor();
    const token = cm.getTokenAt(cur);
    const ch = (change.text && change.text[0]) ? change.text[0] : "";
    const trigger = /^[A-Za-z0-9_\.]$/.test(ch) || (token && token.string && token.string.length >= 2);
    if (!trigger) return;

    try {
      cm.showHint({ completeSingle: false });
    } catch (e) {}
  };

  _extractSqlUi._onInputRead = handler;
  _extractSqlUi.cm.on("inputRead", handler);
}

async function _loadExtractSqlSchema() {
  const sel = document.getElementById("cfg_db_source");
  const schemaEl = document.getElementById("cfg_schema");
  if (!sel || !schemaEl) return;

  const sourceId = sel.value;
  if (!sourceId) {
    schemaEl.innerHTML = `<div class="text-muted small">${t("Selecione uma fonte.")}</div>`;
    _extractSqlUi.schemaMeta = null;
    _extractSqlUi.tablesMap = {};
    _extractSqlUi.tablesFlat = [];
    _refreshAutocomplete();
    _refreshQueryBuilder();
    return;
  }

  // current db type (from option attribute)
  const opt = sel.options[sel.selectedIndex];
  _extractSqlUi.currentDbType = opt ? (opt.getAttribute("data-dbtype") || "") : "";

  schemaEl.innerHTML = `<div class="text-muted small">${t("Carregando...")}</div>`;
  try {
    const resp = await fetch(`/app/api/sources/${encodeURIComponent(sourceId)}/schema`, {
      headers: { "Accept": "application/json" }
    });
    const meta = await resp.json();
    _extractSqlUi.schemaMeta = meta;
    const built = _buildTablesMap(meta);
    _extractSqlUi.tablesMap = built.tables;
    _extractSqlUi.tablesFlat = built.flat;

    _setSchemaHtml(schemaEl, meta);
    _refreshAutocomplete();
    _refreshQueryBuilder();
  } catch (e) {
    schemaEl.innerHTML = `<div class="text-danger small">${String(e)}</div>`;
  }
}

function _refreshQueryBuilder() {
  const tableSel = document.getElementById("cfg_qb_table");
  const colsWrap = document.getElementById("cfg_qb_columns");
  const fField = document.getElementById("cfg_qb_filter_field");
  const fList = document.getElementById("cfg_qb_filter_list");
  if (!tableSel || !colsWrap || !fField || !fList) return;

  if (!_extractSqlUi.qb) {
    _extractSqlUi.qb = { table: "", columns: new Set(), filters: [] };
  }

  // Populate table options once or when schema changes
  const current = tableSel.value;
  tableSel.innerHTML = `<option value="">--</option>` + (_extractSqlUi.tablesFlat || []).map(tn => {
    const sel = (tn === current) ? "selected" : "";
    return `<option value="${tn}" ${sel}>${tn}</option>`;
  }).join("");

  const tableName = tableSel.value || _extractSqlUi.qb.table || "";
  _extractSqlUi.qb.table = tableName;

  const colsObj = _extractSqlUi.tablesMap[tableName] || {};
  const colNames = Object.keys(colsObj);

  // Columns checkboxes
  colsWrap.innerHTML = colNames.length ? colNames.map(cn => {
    const checked = _extractSqlUi.qb.columns.has(cn) ? "checked" : "";
    return `<label class="form-check form-check-inline me-2">
      <input class="form-check-input" type="checkbox" data-col="${cn}" ${checked}>
      <span class="form-check-label small">${cn}</span>
    </label>`;
  }).join("") : `<div class="text-muted small">(sem colunas)</div>`;

  // Filter field options
  const fCur = fField.value;
  fField.innerHTML = `<option value="">--</option>` + colNames.map(cn => {
    const sel = (cn === fCur) ? "selected" : "";
    return `<option value="${cn}" ${sel}>${cn}</option>`;
  }).join("");

  // Filters list
  if (!_extractSqlUi.qb.filters.length) {
    fList.innerHTML = `<span class="text-muted">${t("Sem filtros.")}</span>`;
  } else {
    fList.innerHTML = _extractSqlUi.qb.filters.map((f, idx) => {
      const txt = `${f.field} ${f.op} ${f.value}`;
      return `<div class="d-flex align-items-center justify-content-between gap-2">
        <code class="small">${txt}</code>
        <button type="button" class="btn btn-outline-danger btn-sm py-0" data-filter-rm="${idx}">&times;</button>
      </div>`;
    }).join("");
  }
}

function _buildSqlFromQueryBuilder() {
  const tableSel = document.getElementById("cfg_qb_table");
  const limitEl = document.getElementById("cfg_qb_limit");
  if (!_extractSqlUi.qb || !tableSel) return "";

  const table = tableSel.value || _extractSqlUi.qb.table;
  if (!table) return "";

  const cols = Array.from(_extractSqlUi.qb.columns || []);
  const colList = cols.length ? cols.join(", ") : "*";
  const limit = limitEl ? (limitEl.value || "") : "";
  const lim = _sqlLimitClause(_extractSqlUi.currentDbType, limit);

  let sql = `SELECT ${lim.selectPrefix}${colList} FROM ${table}`;

  const whereParts = [];
  (_extractSqlUi.qb.filters || []).forEach(f => {
    if (!f.field || !f.op) return;
    const op = String(f.op).toLowerCase();
    let rhs;
    if (op === "like") rhs = _sqlLikeLiteral(f.value);
    else rhs = _sqlLiteral(f.value);
    whereParts.push(`${f.field} ${f.op} ${rhs}`);
  });
  if (whereParts.length) sql += ` WHERE ${whereParts.join(" AND ")}`;

  sql += lim.suffix;
  return sql;
}

function _initExtractSqlUi() {
  _destroyExtractSqlUi();

  const textarea = document.getElementById("cfg_query");
  const sel = document.getElementById("cfg_db_source");
  const schemaEl = document.getElementById("cfg_schema");
  if (!textarea || !sel) return;

  // CodeMirror
  if (typeof CodeMirror !== "undefined") {
    _extractSqlUi.cm = CodeMirror.fromTextArea(textarea, {
      mode: "text/x-sql",
      lineNumbers: true,
      matchBrackets: true,
      indentWithTabs: false,
      smartIndent: true,
      extraKeys: {
        "Ctrl-Space": "autocomplete",
        "Cmd-Space": "autocomplete",
      },
    });
    _extractSqlUi.cm.setSize("100%", 320);
  }

  // Schema click insert
  if (schemaEl) {
    schemaEl.addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-ins]");
      if (!btn) return;
      ev.preventDefault();
      const txt = btn.getAttribute("data-ins") || "";
      if (!txt) return;
      _insertTextIntoEditor(txt);
    });
  }

  // DB source change -> reload schema
  sel.addEventListener("change", () => _loadExtractSqlSchema());

  // Reload schema button
  const btnReload = document.getElementById("cfg_reload_schema");
  if (btnReload) btnReload.addEventListener("click", () => _loadExtractSqlSchema());

  // NLQ -> SQL
  const nlqBtn = document.getElementById("cfg_nlq_generate");
  const nlqText = document.getElementById("cfg_nlq_text");
  const nlqWarn = document.getElementById("cfg_nlq_warnings");
  if (nlqBtn && nlqText) {
    nlqBtn.addEventListener("click", async () => {
      const prompt = (nlqText.value || "").trim();
      if (!prompt) return;
      if (!sel.value) {
        if (nlqWarn) nlqWarn.textContent = t("Selecione uma fonte.");
        return;
      }
      if (nlqWarn) nlqWarn.textContent = t("Carregando...");

      try {
        const resp = await fetch("/app/api/nlq", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": _getCsrfToken(),
            "Accept": "application/json",
          },
          body: JSON.stringify({ source_id: sel.value, text: prompt }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || resp.statusText);

        const sql = data.sql || "";
        if (_extractSqlUi.cm) _extractSqlUi.cm.setValue(sql);
        else textarea.value = sql;

        const warnList = (data.warnings || []).filter(Boolean);
        if (nlqWarn) nlqWarn.textContent = warnList.length ? warnList.join(" • ") : "";
      } catch (e) {
        if (nlqWarn) nlqWarn.textContent = String(e);
      }
    });
  }

  // Query Builder events
  const tableSel = document.getElementById("cfg_qb_table");
  const colsWrap = document.getElementById("cfg_qb_columns");
  const fField = document.getElementById("cfg_qb_filter_field");
  const fOp = document.getElementById("cfg_qb_filter_op");
  const fVal = document.getElementById("cfg_qb_filter_value");
  const btnAddFilter = document.getElementById("cfg_qb_add_filter");
  const btnGen = document.getElementById("cfg_qb_generate");
  const filterList = document.getElementById("cfg_qb_filter_list");

  if (tableSel) tableSel.addEventListener("change", () => {
    if (!_extractSqlUi.qb) _extractSqlUi.qb = { table: "", columns: new Set(), filters: [] };
    _extractSqlUi.qb.table = tableSel.value || "";
    _refreshQueryBuilder();
  });

  if (colsWrap) colsWrap.addEventListener("change", (ev) => {
    const cb = ev.target.closest("input[data-col]");
    if (!cb) return;
    const col = cb.getAttribute("data-col");
    if (!col) return;
    if (!_extractSqlUi.qb) _extractSqlUi.qb = { table: "", columns: new Set(), filters: [] };
    if (cb.checked) _extractSqlUi.qb.columns.add(col);
    else _extractSqlUi.qb.columns.delete(col);
  });

  if (btnAddFilter) btnAddFilter.addEventListener("click", () => {
    const field = fField ? fField.value : "";
    const op = fOp ? fOp.value : "=";
    const value = fVal ? fVal.value : "";
    if (!field || value === "") return;

    if (!_extractSqlUi.qb) _extractSqlUi.qb = { table: "", columns: new Set(), filters: [] };
    _extractSqlUi.qb.filters.push({ field, op, value });
    if (fVal) fVal.value = "";
    _refreshQueryBuilder();
  });

  if (filterList) filterList.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-filter-rm]");
    if (!btn) return;
    const idx = parseInt(btn.getAttribute("data-filter-rm") || "-1", 10);
    if (idx < 0) return;
    if (_extractSqlUi.qb && _extractSqlUi.qb.filters) {
      _extractSqlUi.qb.filters.splice(idx, 1);
      _refreshQueryBuilder();
    }
  });

  if (btnGen) btnGen.addEventListener("click", () => {
    const sql = _buildSqlFromQueryBuilder();
    if (!sql) return;
    if (_extractSqlUi.cm) _extractSqlUi.cm.setValue(sql);
    else textarea.value = sql;
  });

  // Initial schema load
  _loadExtractSqlSchema().then(() => {
    _refreshAutocomplete();
  });
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
  if (type === "extract.sql" && _extractSqlUi && _extractSqlUi.cm) {
    try { _extractSqlUi.cm.save(); } catch (e) {}
  }
  const cfg = (node.data && node.data.config) ? node.data.config : _defaultConfig(type);

  _destroyExtractSqlUi();

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
      <div class="row g-3">
        <div class="col-md-8">
          <div class="mb-3">
            <label class="form-label">${t("Fonte de dados")}</label>
            <select class="form-select" id="cfg_db_source">
              ${_dbOptionsHtml(cfg.db_source_id)}
            </select>
          </div>

          <div class="mb-3">
            <label class="form-label">${t("Linguagem humana")}</label>
            <div class="d-flex gap-2 flex-wrap">
              <input class="form-control" id="cfg_nlq_text" placeholder="${t("ex: total vendas por mês")}">
              <button type="button" class="btn btn-outline-primary" id="cfg_nlq_generate">${t("Gerar SQL")}</button>
            </div>
            <div id="cfg_nlq_warnings" class="form-text mt-1"></div>
          </div>

          <details class="mb-3">
            <summary class="fw-semibold cursor-pointer">
              ${t("Query Builder")}
              <span class="text-muted">— ${t("montar SELECT com ajuda da estrutura")}</span>
            </summary>
            <div class="border rounded-3 p-3 mt-2">
              <div class="row g-2">
                <div class="col-md-6">
                  <label class="form-label">${t("Tabela")}</label>
                  <select class="form-select" id="cfg_qb_table">
                    <option value="">--</option>
                  </select>
                </div>
                <div class="col-md-6">
                  <label class="form-label">${t("Limite")}</label>
                  <input class="form-control" id="cfg_qb_limit" type="number" min="0" placeholder="100">
                </div>
              </div>

              <div class="mt-3">
                <label class="form-label">${t("Colunas")}</label>
                <div id="cfg_qb_columns" class="d-flex flex-wrap gap-2"></div>
              </div>

              <div class="mt-3">
                <label class="form-label">${t("Filtros")}</label>
                <div class="row g-2">
                  <div class="col-md-5">
                    <select class="form-select" id="cfg_qb_filter_field">
                      <option value="">--</option>
                    </select>
                  </div>
                  <div class="col-md-2">
                    <select class="form-select" id="cfg_qb_filter_op">
                      <option value="=">=</option>
                      <option value=">">&gt;</option>
                      <option value="<">&lt;</option>
                      <option value=">=">&gt;=</option>
                      <option value="<=">&lt;=</option>
                      <option value="like">LIKE</option>
                    </select>
                  </div>
                  <div class="col-md-5">
                    <input class="form-control" id="cfg_qb_filter_value" placeholder="...">
                  </div>
                </div>
                <div class="d-flex gap-2 mt-2 flex-wrap">
                  <button type="button" class="btn btn-outline-secondary btn-sm" id="cfg_qb_add_filter">${t("Adicionar filtro")}</button>
                  <button type="button" class="btn btn-primary btn-sm" id="cfg_qb_generate">${t("Gerar SQL no editor")}</button>
                </div>
                <div id="cfg_qb_filter_list" class="small text-muted mt-2"></div>
              </div>
            </div>
          </details>

          <div class="mb-2">
            <label class="form-label">SQL</label>
            <textarea class="form-control" id="cfg_query" rows="9" placeholder="${t("SELECT ...")}">${cfg.query || ""}</textarea>
          </div>
        </div>

        <div class="col-md-4">
          <div class="border rounded-3 p-2 bg-body">
            <div class="d-flex align-items-center justify-content-between">
              <div class="fw-semibold">${t("Estrutura")}</div>
              <button type="button" class="btn btn-outline-secondary btn-sm" id="cfg_reload_schema" title="${t("Atualizar")}"><i class="bi bi-arrow-repeat"></i></button>
            </div>
            <div id="cfg_schema" class="bi-schema mt-2" style="max-height: 460px; overflow:auto; font-size:.9rem;"></div>
          </div>
        </div>
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

  if (type === "extract.sql") {
    _initExtractSqlUi();
  }

  const modal = _getBootstrapModal();
  if (modal) modal.show();
}

function saveNodeConfig() {
  const nodeId = document.getElementById("cfgNodeId").value;
  const node = editor.getNodeFromId(nodeId);
  if (!node) return;

  const type = node.name;
  if (type === "extract.sql" && _extractSqlUi && _extractSqlUi.cm) {
    try { _extractSqlUi.cm.save(); } catch (e) {}
  }
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
