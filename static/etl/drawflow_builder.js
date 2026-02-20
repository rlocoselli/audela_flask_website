const editor = new Drawflow(document.getElementById("drawflow"));
editor.start();
const t = (window.t ? window.t : (k) => k);


let _configModal = null;
let _dbSources = [];
let _apiSources = [];
let _workflows = [];
let _uiModal = null;
let _advancedEditors = {
  python: null,
  cleaning: null,
  notifyMessage: null,
};

function _getBootstrapModal() {
  const el = document.getElementById("nodeConfigModal");
  if (!el) return null;
  if (!_configModal) _configModal = new bootstrap.Modal(el);
  return _configModal;
}

function _getUiModal() {
  if (_uiModal) return _uiModal;
  const host = document.createElement("div");
  host.innerHTML = `
    <div class="modal fade" id="etlUiModal" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="etlUiModalTitle">Information</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body" id="etlUiModalBody"></div>
          <div class="modal-footer" id="etlUiModalFooter">
            <button type="button" class="btn btn-primary" data-bs-dismiss="modal">OK</button>
          </div>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(host.firstElementChild);
  const el = document.getElementById("etlUiModal");
  _uiModal = {
    el,
    title: document.getElementById("etlUiModalTitle"),
    body: document.getElementById("etlUiModalBody"),
    footer: document.getElementById("etlUiModalFooter"),
    bs: new bootstrap.Modal(el),
  };
  return _uiModal;
}

function _showMessageModal(message, title) {
  const m = _getUiModal();
  if (!m) return;
  m.title.textContent = title || "Information";
  m.body.textContent = String(message || "");
  m.footer.innerHTML = `<button type="button" class="btn btn-primary" data-bs-dismiss="modal">OK</button>`;
  m.bs.show();
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

function _escapeHtml(v) {
  return String(v ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function _destroyAdvancedEditors() {
  try {
    if (_advancedEditors.python && typeof _advancedEditors.python.toTextArea === "function") {
      _advancedEditors.python.toTextArea();
    }
  } catch (e) {}
  try {
    if (_advancedEditors.cleaning && typeof _advancedEditors.cleaning.toTextArea === "function") {
      _advancedEditors.cleaning.toTextArea();
    }
  } catch (e) {}
  try {
    if (_advancedEditors.notifyMessage && typeof _advancedEditors.notifyMessage.toTextArea === "function") {
      _advancedEditors.notifyMessage.toTextArea();
    }
  } catch (e) {}
  _advancedEditors = { python: null, cleaning: null, notifyMessage: null };
}

function _makeSimpleHintProvider(words) {
  return function(cm) {
    const cur = cm.getCursor();
    const token = cm.getTokenAt(cur);
    const from = CodeMirror.Pos(cur.line, token.start);
    const to = CodeMirror.Pos(cur.line, token.end);
    const raw = String(token.string || "");
    const q = raw.replace(/[^a-zA-Z0-9_:.{}]/g, "").toLowerCase();
    const list = (words || []).filter(w => !q || String(w).toLowerCase().includes(q));
    return { list, from, to };
  };
}

function _setupAdvancedEditors(type) {
  if (typeof CodeMirror === "undefined") return;

  if (type === "transform.python_advanced") {
    const ta = document.getElementById("cfg_py_code");
    if (!ta) return;
    const words = [
      "data", "rows", "meta", "ctx", "result", "table('staging')",
      "{{table:staging}}", "for", "if", "else", "return", "len", "sum",
      "sorted", "enumerate", "datetime", "json", "re"
    ];
    const cm = CodeMirror.fromTextArea(ta, {
      mode: "python",
      lineNumbers: true,
      matchBrackets: true,
      indentUnit: 4,
      extraKeys: {
        "Ctrl-Space": "autocomplete",
        "Cmd-Space": "autocomplete",
      },
      hintOptions: {
        hint: _makeSimpleHintProvider(words),
        completeSingle: false,
      }
    });
    cm.setSize("100%", 340);
    cm.on("inputRead", function(editor, change) {
      if (!change || change.origin === "setValue") return;
      const ch = (change.text && change.text[0]) ? change.text[0] : "";
      if (!/[A-Za-z_{.:]/.test(ch)) return;
      try { editor.showHint(); } catch (e) {}
    });
    _advancedEditors.python = cm;
    return;
  }

  if (type === "transform.cleaning_rules") {
    const ta = document.getElementById("cfg_clean_rules");
    if (!ta) return;
    const words = [
      '"type": "trim"', '"type": "normalize_nulls"', '"type": "case"',
      '"type": "regex_replace"', '"type": "cast"', '"type": "fillna"',
      '"type": "parse_date"', '"type": "clip"', '"fields": []',
      '"field": ""', '"mode": "lower"', '"pattern": ""', '"repl": ""',
      '"to": "int"', '"value": null', '"formats": ["%Y-%m-%d"]',
      '"output": "%Y-%m-%d"', '"min": 0', '"max": 100'
    ];
    const cm = CodeMirror.fromTextArea(ta, {
      mode: { name: "javascript", json: true },
      lineNumbers: true,
      matchBrackets: true,
      autoCloseBrackets: true,
      extraKeys: {
        "Ctrl-Space": "autocomplete",
        "Cmd-Space": "autocomplete",
      },
      hintOptions: {
        hint: _makeSimpleHintProvider(words),
        completeSingle: false,
      }
    });
    cm.setSize("100%", 260);
    cm.on("inputRead", function(editor, change) {
      if (!change || change.origin === "setValue") return;
      const ch = (change.text && change.text[0]) ? change.text[0] : "";
      if (!/[A-Za-z_"{]/.test(ch)) return;
      try { editor.showHint(); } catch (e) {}
    });
    _advancedEditors.cleaning = cm;
    return;
  }

  if (type === "notify.integration") {
    const ta = document.getElementById("cfg_notify_message");
    if (!ta) return;
    const words = [
      "{{workflow}}",
      "{{rows_count}}",
      "{{table:staging}}",
      "{{table:warehouse}}",
      "{{meta:last_scalar}}",
      "{{meta:last_cleaning}}",
      "{{meta:stop_reason}}",
      "ETL finished successfully",
      "ETL warning",
      "Please check logs"
    ];
    const cm = CodeMirror.fromTextArea(ta, {
      mode: "text/plain",
      lineNumbers: false,
      lineWrapping: true,
      extraKeys: {
        "Ctrl-Space": "autocomplete",
        "Cmd-Space": "autocomplete",
      },
      hintOptions: {
        hint: _makeSimpleHintProvider(words),
        completeSingle: false,
      }
    });
    cm.setSize("100%", 130);
    cm.on("inputRead", function(editor, change) {
      if (!change || change.origin === "setValue") return;
      const ch = (change.text && change.text[0]) ? change.text[0] : "";
      if (!/[A-Za-z_{:]/.test(ch)) return;
      try { editor.showHint(); } catch (e) {}
    });
    _advancedEditors.notifyMessage = cm;
  }
}

function _pythonAdvancedExampleSnippet(name) {
  const key = String(name || "").trim().toLowerCase();
  if (key === "normalize") {
    return `# Normalize current rows and keep selected columns
result = []
for row in (data or []):
    result.append({
        "id": row.get("id"),
        "email": str(row.get("email") or "").strip().lower(),
        "amount": float(row.get("amount") or 0),
    })`;
  }
  if (key === "aggregate") {
    return `# Aggregate current rows by category
agg = {}
for row in (data or []):
    k = row.get("category") or "unknown"
    agg[k] = agg.get(k, 0) + float(row.get("amount") or 0)

result = [{"category": k, "total": v} for k, v in agg.items()]`;
  }
  if (key === "tabledata") {
    return `# Read rows from meta.table_data (another step can write there)
rows_from_staging = (meta.get("table_data") or {}).get("staging", [])

# Merge with current data
merged = list(data or []) + list(rows_from_staging or [])
result = merged`;
  }
  if (key === "placeholder") {
    return `# Resolve SQL table name from placeholder and save meta info
table_name = {{table:staging}}
meta["debug_sql"] = f"SELECT count(*) AS c FROM {table_name}"

# Keep pipeline payload unchanged
result = data`;
  }
  return "result = data";
}

function _pythonToolSnippet(name) {
  const key = String(name || "").trim().toLowerCase();
  if (key === "debug_sql") {
    return `table_name = {{table:staging}}
meta["debug_sql"] = f"SELECT * FROM {table_name} LIMIT 20"`;
  }
  if (key === "debug_meta") {
    return `meta["debug_meta_keys"] = sorted(list((meta or {}).keys()))`;
  }
  if (key === "read_table_data") {
    return `rows_from_table = (meta.get("table_data") or {}).get("staging", [])`;
  }
  if (key === "write_table_data") {
    return `tables = meta.get("table_data") or {}
tables["cleaned"] = list(data or [])
meta["table_data"] = tables`;
  }
  if (key === "safe_numeric") {
    return `for row in (data or []):
    row["amount"] = float(row.get("amount") or 0)`;
  }
  if (key === "filter_rows") {
    return `result = [r for r in (data or []) if float(r.get("amount") or 0) > 0]`;
  }
  if (key === "keep_result") {
    return "result = data";
  }
  return "";
}

function _insertInPythonEditor(snippet) {
  const txt = String(snippet || "");
  if (!txt) return;
  if (_advancedEditors.python) {
    const cm = _advancedEditors.python;
    cm.focus();
    const cur = cm.getCursor();
    const line = cm.getLine(cur.line) || "";
    const prefix = (line.trim() ? "\n" : "");
    cm.replaceSelection(prefix + txt + "\n");
    return;
  }
  const ta = document.getElementById("cfg_py_code");
  if (!ta) return;
  const start = ta.selectionStart || 0;
  const end = ta.selectionEnd || 0;
  const before = ta.value.slice(0, start);
  const after = ta.value.slice(end);
  ta.value = before + txt + "\n" + after;
}

function _makeToolboxDraggable(box) {
  if (!box) return;
  const handle = box.querySelector("[data-py-toolbox-handle]");
  if (!handle) return;
  let dragging = false;
  let startX = 0;
  let startY = 0;
  let baseLeft = 0;
  let baseTop = 0;

  const onMove = (ev) => {
    if (!dragging) return;
    const x = ev.clientX || 0;
    const y = ev.clientY || 0;
    const dx = x - startX;
    const dy = y - startY;
    box.style.left = `${Math.max(8, baseLeft + dx)}px`;
    box.style.top = `${Math.max(56, baseTop + dy)}px`;
    box.style.right = "auto";
  };
  const onUp = () => {
    dragging = false;
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
  };

  handle.addEventListener("mousedown", (ev) => {
    ev.preventDefault();
    dragging = true;
    const rect = box.getBoundingClientRect();
    startX = ev.clientX || 0;
    startY = ev.clientY || 0;
    baseLeft = rect.left;
    baseTop = rect.top;
    box.style.position = "fixed";
    box.style.left = `${rect.left}px`;
    box.style.top = `${rect.top}px`;
    box.style.right = "auto";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}

function _bindPythonAdvancedToolbox() {
  const box = document.getElementById("cfg_py_toolbox");
  if (!box) return;

  _makeToolboxDraggable(box);

  box.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-py-tool]");
    if (!btn) return;
    const snippet = _pythonToolSnippet(btn.getAttribute("data-py-tool") || "");
    _insertInPythonEditor(snippet);
  });

  box.querySelectorAll("[data-py-tool]").forEach((el) => {
    el.setAttribute("draggable", "true");
    el.addEventListener("dragstart", (ev) => {
      const snippet = _pythonToolSnippet(el.getAttribute("data-py-tool") || "");
      ev.dataTransfer?.setData("text/plain", snippet);
      ev.dataTransfer.effectAllowed = "copy";
    });
  });

  if (_advancedEditors.python) {
    const wrap = _advancedEditors.python.getWrapperElement();
    wrap.addEventListener("dragover", (ev) => {
      ev.preventDefault();
      ev.dataTransfer.dropEffect = "copy";
    });
    wrap.addEventListener("drop", (ev) => {
      ev.preventDefault();
      const snippet = ev.dataTransfer?.getData("text/plain") || "";
      _insertInPythonEditor(snippet);
    });
  }
}

function _bindPythonAdvancedExamples() {
  const wrap = document.getElementById("cfg_py_examples");
  if (!wrap) return;
  wrap.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-py-example]");
    if (!btn) return;
    const name = btn.getAttribute("data-py-example") || "";
    const code = _pythonAdvancedExampleSnippet(name);
    if (_advancedEditors.python) {
      _advancedEditors.python.setValue(code);
      _advancedEditors.python.focus();
    } else {
      const ta = document.getElementById("cfg_py_code");
      if (ta) ta.value = code;
    }
  });
}

function _notifyToolSnippet(name) {
  const key = String(name || "").trim().toLowerCase();
  if (key === "rows_count") return "Rows count: {{rows_count}}";
  if (key === "workflow") return "Workflow: {{workflow}}";
  if (key === "table_staging") return "Staging table: {{table:staging}}";
  if (key === "table_warehouse") return "Warehouse table: {{table:warehouse}}";
  if (key === "last_scalar") return "Last scalar: {{meta:last_scalar}}";
  if (key === "debug_sql") return "Debug SQL: {{meta:debug_sql}}";
  if (key === "status_ok") return "✅ ETL finished successfully.";
  if (key === "status_warn") return "⚠️ ETL finished with warnings.";
  if (key === "status_fail") return "❌ ETL failed. Please check execution logs.";
  return "";
}

function _insertInNotifyMessageEditor(snippet) {
  const txt = String(snippet || "");
  if (!txt) return;
  if (_advancedEditors.notifyMessage) {
    const cm = _advancedEditors.notifyMessage;
    cm.focus();
    const cur = cm.getCursor();
    const line = cm.getLine(cur.line) || "";
    const prefix = (line.trim() ? "\n" : "");
    cm.replaceSelection(prefix + txt + "\n");
    return;
  }
  const ta = document.getElementById("cfg_notify_message");
  if (!ta) return;
  const start = ta.selectionStart || 0;
  const end = ta.selectionEnd || 0;
  const before = ta.value.slice(0, start);
  const after = ta.value.slice(end);
  ta.value = before + txt + "\n" + after;
}

function _bindNotifyMessageToolbox() {
  const box = document.getElementById("cfg_notify_toolbox");
  if (!box) return;

  _makeToolboxDraggable(box);

  box.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-notify-tool]");
    if (!btn) return;
    const snippet = _notifyToolSnippet(btn.getAttribute("data-notify-tool") || "");
    _insertInNotifyMessageEditor(snippet);
  });

  box.querySelectorAll("[data-notify-tool]").forEach((el) => {
    el.setAttribute("draggable", "true");
    el.addEventListener("dragstart", (ev) => {
      const snippet = _notifyToolSnippet(el.getAttribute("data-notify-tool") || "");
      ev.dataTransfer?.setData("text/plain", snippet);
      ev.dataTransfer.effectAllowed = "copy";
    });
  });

  if (_advancedEditors.notifyMessage) {
    const wrap = _advancedEditors.notifyMessage.getWrapperElement();
    wrap.addEventListener("dragover", (ev) => {
      ev.preventDefault();
      ev.dataTransfer.dropEffect = "copy";
    });
    wrap.addEventListener("drop", (ev) => {
      ev.preventDefault();
      const snippet = ev.dataTransfer?.getData("text/plain") || "";
      _insertInNotifyMessageEditor(snippet);
    });
  }
}

function _collectNotifyConfigFromForm() {
  const cfg = {};
  cfg.integration = (document.getElementById("cfg_notify_integration")?.value || "email").trim();
  cfg.enabled = !!document.getElementById("cfg_notify_enabled")?.checked;
  cfg.fail_on_error = !!document.getElementById("cfg_notify_fail")?.checked;
  cfg.subject = (document.getElementById("cfg_notify_subject")?.value || "ETL {{workflow}} done").trim();
  cfg.message = (document.getElementById("cfg_notify_message")?.value || "Rows: {{rows_count}}").trim();
  cfg.timeout = parseInt(document.getElementById("cfg_notify_timeout")?.value || "15", 10);
  cfg.to = (document.getElementById("cfg_notify_to")?.value || "").trim();
  cfg.sender = (document.getElementById("cfg_notify_sender")?.value || "").trim();
  cfg.as_html = !!document.getElementById("cfg_notify_html")?.checked;
  cfg.webhook_url = (document.getElementById("cfg_notify_webhook")?.value || "").trim();

  const headers = _safeJsonParse(document.getElementById("cfg_notify_headers")?.value || "{}", {});
  const payload = _safeJsonParse(document.getElementById("cfg_notify_payload")?.value || "{}", {});
  if (headers === null || typeof headers !== "object" || Array.isArray(headers)) {
    _showMessageModal("Headers JSON invalid (object expected)", "Validation");
    return null;
  }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    _showMessageModal("Payload JSON invalid (object expected)", "Validation");
    return null;
  }
  cfg.headers = headers;
  cfg.payload = payload;
  return cfg;
}

function _bindNotifyTestButton() {
  const btn = document.getElementById("cfg_notify_test");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    if (_advancedEditors.notifyMessage) {
      try { _advancedEditors.notifyMessage.save(); } catch (e) {}
    }
    const cfg = _collectNotifyConfigFromForm();
    if (!cfg) return;

    btn.disabled = true;
    const old = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Sending...';
    try {
      const data = await _fetchJson("/etl/api/notify/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          config: cfg,
          workflow: getWorkflowName(),
          sample_rows: [{ id: 1, status: "ok" }, { id: 2, status: "warning" }],
          last_scalar: 42,
          tables: { staging: "staging.sample_table", warehouse: "public.fact_sales" }
        })
      });
      if (data && data.ok) {
        _showMessageModal("Test notification sent successfully.", "Success");
      } else {
        _showMessageModal((data && (data.error || data.result?.error)) || "Notification test failed.", "Error");
      }
    } catch (e) {
      _showMessageModal(String(e.message || e), "Error");
    } finally {
      btn.disabled = false;
      btn.innerHTML = old;
    }
  });
}

function _defaultConfig(type) {
  if (type === "extract.http") return { api_source_id: "", path: "", method: "GET", headers: {}, params: {}, timeout: 30 };
  if (type === "extract.sql") return { query: "", db_source_id: "", result_mode: "rows", strict_scalar: true, scalar_key: "last_scalar" };
  if (type === "transform.mapping") return { fields: {} };
  if (type === "transform.cleaning_rules") return {
    presets: ["basic_text"],
    rules: [
      { type: "trim" },
      { type: "normalize_nulls" }
    ],
    deduplicate: { enabled: false, fields: [], keep: "first" }
  };
  if (type === "transform.python_advanced") return {
    input_mode: "current",
    input_table_key: "",
    output_table_key: "",
    code: "# data: list[dict] (or any structure from previous step)\n# meta: workflow metadata dict\n# Use table('staging') or {{table:staging}} in strings\nresult = data"
  };
  if (type === "transform.decision.scalar") return {
    source: "last_scalar",
    scalar_key: "",
    operator: "eq",
    value: "",
    on_true: "continue",
    on_false: "stop",
    message: "Scalar decision"
  };
  if (type === "load.warehouse") return {
    table: "", schema: "public", mode: "append",
    create_table_if_missing: true, add_columns_if_missing: true,
    warehouse_source_id: ""
  };
  if (type === "load.staging_table") return {
    table: "dataset",
    table_prefix: "stg_",
    schema: "staging",
    run_suffix: true,
    mode: "append",
    create_table_if_missing: true,
    add_columns_if_missing: true,
    warehouse_source_id: "",
    table_key: "staging"
  };
  if (type === "notify.integration") return {
    integration: "email",
    enabled: true,
    fail_on_error: false,
    to: "",
    sender: "",
    as_html: false,
    webhook_url: "",
    headers: {},
    payload: {},
    subject: "ETL {{workflow}} done",
    message: "Rows: {{rows_count}}\nTable: {{table:staging}}",
    timeout: 15
  };
  return {};
}

function _nodeHtml(type) {
  if (type === "transform.decision.scalar") {
    return `<div>
      <strong>${type}</strong>
      <div style="font-size:11px;color:#666">Double-click to configure</div>
      <div style="font-size:10px;color:#1f2937;margin-top:4px;display:flex;justify-content:space-between;gap:8px;">
        <span><b>↑ output_1</b> = TRUE</span>
        <span><b>↓ output_2</b> = FALSE</span>
      </div>
    </div>`;
  }
  return `<div>
      <strong>${type}</strong>
      <div style="font-size:11px;color:#666">Double-click to configure</div>
   </div>`;
}

function _normalizeDecisionNodeOutputs(drawflowPayload) {
  if (!drawflowPayload || !drawflowPayload.drawflow || !drawflowPayload.drawflow.Home || !drawflowPayload.drawflow.Home.data) {
    return drawflowPayload;
  }
  const nodes = drawflowPayload.drawflow.Home.data;
  Object.values(nodes).forEach((n) => {
    if (!n || n.name !== "transform.decision.scalar") return;
    n.outputs = n.outputs || {};
    if (!n.outputs.output_1) n.outputs.output_1 = { connections: [] };
    if (!n.outputs.output_2) n.outputs.output_2 = { connections: [] };
    n.html = _nodeHtml("transform.decision.scalar");
  });
  return drawflowPayload;
}

function addNode(type) {
  const cfg = _defaultConfig(type);
  const outputs = (type === "transform.decision.scalar") ? 2 : 1;
  const nodeId = editor.addNode(
    type, 1, outputs, 100, 100, type,
    { type: type, config: cfg },
    _nodeHtml(type)
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
        editor.import(_normalizeDecisionNodeOutputs(res.data));
      } else {
        const el = document.getElementById("etlPreview");
        if (el) el.textContent = _jsonPretty(res.data);
        _showMessageModal("Loaded workflow definition (preview). For now, graphs load from Drawflow format.", "Workflow loaded");
      }
    })
    .catch(err => _showMessageModal("Load error: " + err.message, "Error"));
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
  if (!id) return _showMessageModal("Select a DB source", "Validation");
  _fetchJson(`/etl/api/sources/db/${encodeURIComponent(id)}/test`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
    .then(res => {
      const el = document.getElementById("etlPreview");
      if (el) el.textContent = _jsonPretty(res);
      _showMessageModal(res.ok ? "DB source OK" : "DB source failed", "Source test");
    })
    .catch(err => _showMessageModal("Test error: " + err.message, "Error"));
}

function testSelectedApiSource() {
  const sel = document.getElementById("apiSourceSelect");
  const id = sel ? sel.value : "";
  if (!id) return _showMessageModal("Select an API source", "Validation");
  _fetchJson(`/etl/api/sources/api/${encodeURIComponent(id)}/test`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
    .then(res => {
      const el = document.getElementById("etlPreview");
      if (el) el.textContent = _jsonPretty(res);
      _showMessageModal(res.ok ? "API source OK" : "API source failed", "Source test");
    })
    .catch(err => _showMessageModal("Test error: " + err.message, "Error"));
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
    if (data.warning) _showMessageModal("Saved graph. Warning: " + data.warning, "Saved with warning");
    else _showMessageModal("Workflow saved successfully!", "Saved");
  })
  .catch(err => _showMessageModal("Error saving workflow: " + err.message, "Error"));
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
  .catch(err => _showMessageModal("Error previewing workflow: " + err.message, "Error"));
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
        _showMessageModal("Run error: " + msg.error, "Execution error");
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
  _destroyAdvancedEditors();

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

          <div class="row g-2 mt-1">
            <div class="col-md-4">
              <label class="form-label">${t("Result mode")}</label>
              <select class="form-select" id="cfg_result_mode">
                <option value="rows" ${((cfg.result_mode || "rows") === "rows") ? "selected" : ""}>rows</option>
                <option value="scalar" ${((cfg.result_mode || "rows") === "scalar") ? "selected" : ""}>scalar (1x1)</option>
              </select>
            </div>
            <div class="col-md-4">
              <label class="form-label">${t("Scalar key (meta)")}</label>
              <input class="form-control" id="cfg_scalar_key" value="${cfg.scalar_key || "last_scalar"}" placeholder="last_scalar">
            </div>
            <div class="col-md-4 d-flex align-items-end">
              <div class="form-check mb-2">
                <input class="form-check-input" type="checkbox" id="cfg_strict_scalar" ${cfg.strict_scalar !== false ? "checked" : ""}>
                <label class="form-check-label" for="cfg_strict_scalar">${t("Strict scalar (exactly 1 row/1 col)")}</label>
              </div>
            </div>
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
  } else if (type === "transform.cleaning_rules") {
    html += `
      <div class="mb-3">
        <label class="form-label">Presets (JSON array)</label>
        <input class="form-control" id="cfg_clean_presets" value='${_escapeHtml(_jsonPretty(cfg.presets || []))}' placeholder='["basic_text","email_standardization"]'>
        <div class="form-text">Available: basic_text, email_standardization, phone_digits, dates_iso</div>
      </div>
      <div class="mb-3">
        <label class="form-label">Rules (JSON array)</label>
        <textarea class="form-control" id="cfg_clean_rules" rows="10" placeholder='[{"type":"trim"},{"type":"normalize_nulls"}]'>${_jsonPretty(cfg.rules || [])}</textarea>
        <div class="form-text">Rule types: trim, normalize_nulls, case, regex_replace, cast, fillna, parse_date, clip</div>
      </div>
      <div class="border rounded-2 p-2">
        <div class="fw-semibold mb-2">Deduplicate</div>
        <div class="form-check mb-2">
          <input class="form-check-input" type="checkbox" id="cfg_clean_dedup_enabled" ${cfg.deduplicate && cfg.deduplicate.enabled ? "checked" : ""}>
          <label class="form-check-label" for="cfg_clean_dedup_enabled">Enable deduplication</label>
        </div>
        <div class="row g-2">
          <div class="col-md-8">
            <label class="form-label">Fields (comma separated)</label>
            <input class="form-control" id="cfg_clean_dedup_fields" value="${(cfg.deduplicate && Array.isArray(cfg.deduplicate.fields)) ? cfg.deduplicate.fields.join(',') : ''}" placeholder="id,email">
          </div>
          <div class="col-md-4">
            <label class="form-label">Keep</label>
            <select class="form-select" id="cfg_clean_dedup_keep">
              <option value="first" ${(!cfg.deduplicate || (cfg.deduplicate.keep || "first") === "first") ? "selected" : ""}>first</option>
              <option value="last" ${(cfg.deduplicate && (cfg.deduplicate.keep || "first") === "last") ? "selected" : ""}>last</option>
            </select>
          </div>
        </div>
      </div>
    `;
  } else if (type === "transform.python_advanced") {
    html += `
      <div class="row g-2">
        <div class="col-md-4">
          <label class="form-label">Input mode</label>
          <select class="form-select" id="cfg_py_input_mode">
            <option value="current" ${((cfg.input_mode || "current") === "current") ? "selected" : ""}>current</option>
            <option value="table" ${((cfg.input_mode || "current") === "table") ? "selected" : ""}>table_data key</option>
          </select>
        </div>
        <div class="col-md-4">
          <label class="form-label">Input table key</label>
          <input class="form-control" id="cfg_py_input_table_key" value="${_escapeHtml(cfg.input_table_key || "")}" placeholder="staging">
        </div>
        <div class="col-md-4">
          <label class="form-label">Output table key</label>
          <input class="form-control" id="cfg_py_output_table_key" value="${_escapeHtml(cfg.output_table_key || "")}" placeholder="cleaned">
        </div>
      </div>
      <div class="mt-3">
        <label class="form-label">Python code</label>
        <div id="cfg_py_editor_wrap" class="position-relative">
          <textarea class="form-control" id="cfg_py_code" rows="14" placeholder="result = data">${_escapeHtml(cfg.code || "result = data")}</textarea>
          <div id="cfg_py_toolbox" class="card shadow-sm" style="position:absolute; right:8px; top:36px; width:250px; z-index:8;">
            <div class="card-header py-1 px-2 small fw-semibold d-flex align-items-center justify-content-between" data-py-toolbox-handle style="cursor:move;">
              <span>🧰 Python tools</span>
              <span class="text-muted">drag</span>
            </div>
            <div class="card-body p-2">
              <div class="small text-muted mb-2">Drag and drop into editor or click to insert.</div>
              <div class="d-flex flex-wrap gap-1">
                <button type="button" class="btn btn-outline-secondary btn-sm" data-py-tool="debug_sql">debug_sql</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" data-py-tool="debug_meta">debug_meta</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" data-py-tool="read_table_data">read table_data</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" data-py-tool="write_table_data">write table_data</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" data-py-tool="safe_numeric">safe numeric</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" data-py-tool="filter_rows">filter rows</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" data-py-tool="keep_result">result=data</button>
              </div>
            </div>
          </div>
        </div>
        <div class="form-text">Available vars: data, rows, meta, ctx, table(name). Placeholder in code string: {{table:staging}}</div>
      </div>
      <div class="mt-3" id="cfg_py_examples">
        <div class="small fw-semibold mb-2">Examples</div>
        <div class="d-flex flex-wrap gap-2">
          <button type="button" class="btn btn-outline-secondary btn-sm" data-py-example="normalize">Normalize rows</button>
          <button type="button" class="btn btn-outline-secondary btn-sm" data-py-example="aggregate">Aggregate values</button>
          <button type="button" class="btn btn-outline-secondary btn-sm" data-py-example="tabledata">Get table_data</button>
          <button type="button" class="btn btn-outline-secondary btn-sm" data-py-example="placeholder">Use table placeholder</button>
        </div>
      </div>
    `;
  } else if (type === "transform.decision.scalar") {
    html += `
      <div class="row g-2">
        <div class="col-md-4">
          <label class="form-label d-flex align-items-center gap-1">
            <span>${t("Scalar source")}</span>
            <i class="bi bi-question-circle text-muted" title="last_scalar = prend la dernière valeur scalaire produite. meta_key = prend une valeur nommée dans meta.scalars (utiliser Scalar key)."></i>
          </label>
          <select class="form-select" id="cfg_dec_source">
            <option value="last_scalar" ${((cfg.source || "last_scalar") === "last_scalar") ? "selected" : ""}>last_scalar</option>
            <option value="meta_key" ${((cfg.source || "") === "meta_key") ? "selected" : ""}>meta key</option>
          </select>
          <div class="form-text">${t("last_scalar: dernière extraction scalar. meta_key: clé précise dans le dictionnaire scalars.")}</div>
        </div>
        <div class="col-md-4">
          <label class="form-label d-flex align-items-center gap-1">
            <span>${t("Scalar key")}</span>
            <i class="bi bi-question-circle text-muted" title="Utilisé uniquement si Scalar source = meta_key. Exemple: total_rows, avg_amount."></i>
          </label>
          <input class="form-control" id="cfg_dec_scalar_key" value="${cfg.scalar_key || ""}" placeholder="my_scalar">
        </div>
        <div class="col-md-4">
          <label class="form-label">${t("Operator")}</label>
          <select class="form-select" id="cfg_dec_operator">
            ${[
              ["eq", "eq (=)"], ["ne", "ne (!=)"], ["gt", "gt (>)"], ["gte", "gte (>=)"],
              ["lt", "lt (<)"], ["lte", "lte (<=)"], ["contains", "contains"], ["in", "in"],
              ["not_in", "not_in"], ["empty", "empty"], ["not_empty", "not_empty"],
              ["true", "true"], ["false", "false"]
            ].map(x => `<option value="${x[0]}" ${((cfg.operator || "eq") === x[0]) ? "selected" : ""}>${x[1]}</option>`).join("")}
          </select>
        </div>
      </div>
      <div class="row g-2 mt-1">
        <div class="col-md-6">
          <label class="form-label">${t("Compare value")}</label>
          <input class="form-control" id="cfg_dec_value" value="${(cfg.value ?? "")}" placeholder='10 ou [1,2,3]'>
          <div class="form-text">${t("JSON support: [1,2], true, 10.5")}</div>
        </div>
        <div class="col-md-3">
          <label class="form-label">${t("On true")}</label>
          <select class="form-select" id="cfg_dec_on_true">
            ${["continue", "stop", "error"].map(v => `<option value="${v}" ${((cfg.on_true || "continue") === v) ? "selected" : ""}>${v}</option>`).join("")}
          </select>
        </div>
        <div class="col-md-3">
          <label class="form-label">${t("On false")}</label>
          <select class="form-select" id="cfg_dec_on_false">
            ${["continue", "stop", "error"].map(v => `<option value="${v}" ${((cfg.on_false || "stop") === v) ? "selected" : ""}>${v}</option>`).join("")}
          </select>
        </div>
      </div>
      <div class="mt-2">
        <label class="form-label">${t("Message")}</label>
        <input class="form-control" id="cfg_dec_message" value="${cfg.message || "Scalar decision"}">
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
  } else if (type === "load.staging_table") {
    html += `
      <div class="mb-3">
        <label class="form-label">Warehouse (DB Source)</label>
        <select class="form-select" id="cfg_stg_source">
          ${_dbOptionsHtml(cfg.warehouse_source_id)}
        </select>
      </div>
      <div class="row g-2">
        <div class="col-md-6">
          <label class="form-label">Schema</label>
          <input class="form-control" id="cfg_stg_schema" value="${cfg.schema || "staging"}">
        </div>
        <div class="col-md-6">
          <label class="form-label">Base table name</label>
          <input class="form-control" id="cfg_stg_table" value="${cfg.table || "dataset"}" placeholder="orders_raw">
        </div>
      </div>
      <div class="row g-2 mt-2">
        <div class="col-md-4">
          <label class="form-label">Prefix</label>
          <input class="form-control" id="cfg_stg_prefix" value="${cfg.table_prefix || "stg_"}">
        </div>
        <div class="col-md-4">
          <label class="form-label">Mode</label>
          <select class="form-select" id="cfg_stg_mode">
            <option value="append" ${((cfg.mode||"append")==="append")?"selected":""}>append</option>
            <option value="replace" ${((cfg.mode||"append")==="replace")?"selected":""}>replace</option>
          </select>
        </div>
        <div class="col-md-4">
          <label class="form-label">Table key (meta.tables)</label>
          <input class="form-control" id="cfg_stg_key" value="${cfg.table_key || "staging"}" placeholder="staging">
        </div>
      </div>
      <div class="form-check mt-3">
        <input class="form-check-input" type="checkbox" id="cfg_stg_suffix" ${cfg.run_suffix !== false ? "checked" : ""}>
        <label class="form-check-label" for="cfg_stg_suffix">Append timestamp suffix</label>
      </div>
      <div class="form-check mt-2">
        <input class="form-check-input" type="checkbox" id="cfg_stg_create" ${cfg.create_table_if_missing !== false ? "checked" : ""}>
        <label class="form-check-label" for="cfg_stg_create">Create table if missing</label>
      </div>
      <div class="form-check mt-2">
        <input class="form-check-input" type="checkbox" id="cfg_stg_addcols" ${cfg.add_columns_if_missing !== false ? "checked" : ""}>
        <label class="form-check-label" for="cfg_stg_addcols">Add missing columns</label>
      </div>
    `;
  } else if (type === "notify.integration") {
    html += `
      <div class="row g-2">
        <div class="col-md-4">
          <label class="form-label">Integration</label>
          <select class="form-select" id="cfg_notify_integration">
            <option value="email" ${((cfg.integration || "email") === "email") ? "selected" : ""}>email (SMTP Audela)</option>
            <option value="teams" ${((cfg.integration || "") === "teams") ? "selected" : ""}>teams (webhook)</option>
            <option value="slack" ${((cfg.integration || "") === "slack") ? "selected" : ""}>slack (webhook)</option>
          </select>
        </div>
        <div class="col-md-4 d-flex align-items-end">
          <div class="form-check mb-2">
            <input class="form-check-input" type="checkbox" id="cfg_notify_enabled" ${cfg.enabled !== false ? "checked" : ""}>
            <label class="form-check-label" for="cfg_notify_enabled">Enabled</label>
          </div>
        </div>
        <div class="col-md-4 d-flex align-items-end">
          <div class="form-check mb-2">
            <input class="form-check-input" type="checkbox" id="cfg_notify_fail" ${cfg.fail_on_error ? "checked" : ""}>
            <label class="form-check-label" for="cfg_notify_fail">Fail workflow on error</label>
          </div>
        </div>
      </div>

      <div class="row g-2 mt-2">
        <div class="col-md-6">
          <label class="form-label">Subject</label>
          <input class="form-control" id="cfg_notify_subject" value="${_escapeHtml(cfg.subject || "ETL {{workflow}} done")}">
        </div>
        <div class="col-md-6">
          <label class="form-label">Timeout</label>
          <input class="form-control" id="cfg_notify_timeout" type="number" min="1" value="${Number(cfg.timeout || 15)}">
        </div>
      </div>

      <div class="mt-2">
        <label class="form-label">Message</label>
        <div id="cfg_notify_editor_wrap" class="position-relative">
          <textarea class="form-control" id="cfg_notify_message" rows="4">${_escapeHtml(cfg.message || "Rows: {{rows_count}}")}</textarea>
          <div id="cfg_notify_toolbox" class="card shadow-sm" style="position:absolute; right:8px; top:8px; width:260px; z-index:8;">
            <div class="card-header py-1 px-2 small fw-semibold d-flex align-items-center justify-content-between" data-py-toolbox-handle style="cursor:move;">
              <span>🔔 Message tools</span>
              <span class="text-muted">drag</span>
            </div>
            <div class="card-body p-2">
              <div class="small text-muted mb-2">Autocomplete + drag/drop snippets</div>
              <div class="d-flex flex-wrap gap-1">
                <button type="button" class="btn btn-outline-secondary btn-sm" data-notify-tool="workflow">workflow</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" data-notify-tool="rows_count">rows_count</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" data-notify-tool="table_staging">table:staging</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" data-notify-tool="table_warehouse">table:warehouse</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" data-notify-tool="last_scalar">meta:last_scalar</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" data-notify-tool="debug_sql">debug_sql</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" data-notify-tool="status_ok">status ok</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" data-notify-tool="status_warn">status warn</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" data-notify-tool="status_fail">status fail</button>
              </div>
            </div>
          </div>
        </div>
        <div class="form-text">Placeholders: {{workflow}}, {{rows_count}}, {{table:staging}}, {{meta:last_scalar}}, {{meta:debug_sql}}</div>
      </div>

      <div id="cfg_notify_email_box" class="border rounded-2 p-2 mt-3">
        <div class="fw-semibold mb-2">Email (SMTP)</div>
        <div class="row g-2">
          <div class="col-md-8">
            <label class="form-label">Recipients (comma separated)</label>
            <input class="form-control" id="cfg_notify_to" value="${_escapeHtml(cfg.to || "")}" placeholder="ops@company.com,data@company.com">
          </div>
          <div class="col-md-4">
            <label class="form-label">Sender (optional)</label>
            <input class="form-control" id="cfg_notify_sender" value="${_escapeHtml(cfg.sender || "")}" placeholder="noreply@audela.com">
          </div>
        </div>
        <div class="form-check mt-2">
          <input class="form-check-input" type="checkbox" id="cfg_notify_html" ${cfg.as_html ? "checked" : ""}>
          <label class="form-check-label" for="cfg_notify_html">Send body as HTML</label>
        </div>
      </div>

      <div id="cfg_notify_webhook_box" class="border rounded-2 p-2 mt-3">
        <div class="fw-semibold mb-2">Webhook (Teams / Slack)</div>
        <div class="mb-2">
          <label class="form-label">Webhook URL</label>
          <input class="form-control" id="cfg_notify_webhook" value="${_escapeHtml(cfg.webhook_url || "")}" placeholder="https://...">
        </div>
        <div class="mb-2">
          <label class="form-label">Headers (JSON, optional)</label>
          <textarea class="form-control" id="cfg_notify_headers" rows="3">${_jsonPretty(cfg.headers || {})}</textarea>
        </div>
        <div class="mb-0">
          <label class="form-label">Payload override (JSON, optional)</label>
          <textarea class="form-control" id="cfg_notify_payload" rows="4">${_jsonPretty(cfg.payload || {})}</textarea>
          <div class="form-text">If empty, default payload is generated from Subject + Message.</div>
        </div>
      </div>

      <div class="d-flex justify-content-end mt-3">
        <button type="button" class="btn btn-outline-primary btn-sm" id="cfg_notify_test">
          <i class="bi bi-send-check me-1"></i>Send test notification
        </button>
      </div>
    `;
  } else {
    html += `<div class="alert alert-warning">No config UI for type: ${type}</div>`;
  }

  if (formEl) formEl.innerHTML = html;

  if (type === "extract.sql") {
    _initExtractSqlUi();
  } else if (type === "transform.python_advanced" || type === "transform.cleaning_rules" || type === "notify.integration") {
    _setupAdvancedEditors(type);
    if (type === "transform.python_advanced") {
      _bindPythonAdvancedExamples();
      _bindPythonAdvancedToolbox();
    }
    if (type === "notify.integration") {
      _bindNotifyMessageToolbox();
      _bindNotifyTestButton();
    }
  }

  if (type === "notify.integration") {
    const integrationEl = document.getElementById("cfg_notify_integration");
    const emailBox = document.getElementById("cfg_notify_email_box");
    const webhookBox = document.getElementById("cfg_notify_webhook_box");
    const refreshNotifyMode = () => {
      const mode = (integrationEl?.value || "email").trim();
      if (emailBox) emailBox.style.display = (mode === "email") ? "" : "none";
      if (webhookBox) webhookBox.style.display = (mode === "teams" || mode === "slack") ? "" : "none";
    };
    integrationEl?.addEventListener("change", refreshNotifyMode);
    refreshNotifyMode();
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
  if (type === "transform.python_advanced" && _advancedEditors.python) {
    try { _advancedEditors.python.save(); } catch (e) {}
  }
  if (type === "transform.cleaning_rules" && _advancedEditors.cleaning) {
    try { _advancedEditors.cleaning.save(); } catch (e) {}
  }
  if (type === "notify.integration" && _advancedEditors.notifyMessage) {
    try { _advancedEditors.notifyMessage.save(); } catch (e) {}
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
    if (headers === null) return _showMessageModal("Headers JSON invalid", "Validation");
    if (params === null) return _showMessageModal("Params JSON invalid", "Validation");
    cfg.headers = headers;
    cfg.params = params;
  } else if (type === "extract.sql") {
    const sel = document.getElementById("cfg_db_source");
    cfg.db_source_id = sel ? sel.value : "";
    cfg.query = document.getElementById("cfg_query").value;
    cfg.result_mode = (document.getElementById("cfg_result_mode")?.value || "rows").trim();
    cfg.scalar_key = (document.getElementById("cfg_scalar_key")?.value || "last_scalar").trim();
    cfg.strict_scalar = !!document.getElementById("cfg_strict_scalar")?.checked;
  } else if (type === "transform.mapping") {
    const fields = _safeJsonParse(document.getElementById("cfg_fields").value, {});
    if (fields === null) return _showMessageModal("Fields JSON invalid", "Validation");
    cfg.fields = fields;
  } else if (type === "transform.cleaning_rules") {
    const presets = _safeJsonParse(document.getElementById("cfg_clean_presets").value, []);
    const rules = _safeJsonParse(document.getElementById("cfg_clean_rules").value, []);
    if (presets === null || !Array.isArray(presets)) return _showMessageModal("Presets JSON invalid (array expected)", "Validation");
    if (rules === null || !Array.isArray(rules)) return _showMessageModal("Rules JSON invalid (array expected)", "Validation");
    const dedupEnabled = !!document.getElementById("cfg_clean_dedup_enabled")?.checked;
    const dedupFieldsRaw = document.getElementById("cfg_clean_dedup_fields")?.value || "";
    const dedupFields = dedupFieldsRaw.split(",").map(s => s.trim()).filter(Boolean);
    const dedupKeep = (document.getElementById("cfg_clean_dedup_keep")?.value || "first").trim();
    cfg.presets = presets;
    cfg.rules = rules;
    cfg.deduplicate = {
      enabled: dedupEnabled,
      fields: dedupFields,
      keep: dedupKeep || "first"
    };
  } else if (type === "transform.python_advanced") {
    cfg.input_mode = (document.getElementById("cfg_py_input_mode")?.value || "current").trim();
    cfg.input_table_key = (document.getElementById("cfg_py_input_table_key")?.value || "").trim();
    cfg.output_table_key = (document.getElementById("cfg_py_output_table_key")?.value || "").trim();
    cfg.code = document.getElementById("cfg_py_code")?.value || "result = data";
  } else if (type === "transform.decision.scalar") {
    cfg.source = (document.getElementById("cfg_dec_source")?.value || "last_scalar").trim();
    cfg.scalar_key = (document.getElementById("cfg_dec_scalar_key")?.value || "").trim();
    cfg.operator = (document.getElementById("cfg_dec_operator")?.value || "eq").trim();
    cfg.value = (document.getElementById("cfg_dec_value")?.value || "").trim();
    cfg.on_true = (document.getElementById("cfg_dec_on_true")?.value || "continue").trim();
    cfg.on_false = (document.getElementById("cfg_dec_on_false")?.value || "stop").trim();
    cfg.message = (document.getElementById("cfg_dec_message")?.value || "Scalar decision").trim();
  } else if (type === "load.warehouse") {
    const sel = document.getElementById("cfg_wh_source");
    cfg.warehouse_source_id = sel ? sel.value : "";
    cfg.schema = document.getElementById("cfg_schema").value.trim() || "public";
    cfg.table = document.getElementById("cfg_table").value.trim();
    cfg.mode = document.getElementById("cfg_mode").value.trim() || "append";
    cfg.create_table_if_missing = document.getElementById("cfg_create").checked;
    cfg.add_columns_if_missing = document.getElementById("cfg_addcols").checked;
  } else if (type === "load.staging_table") {
    const sel = document.getElementById("cfg_stg_source");
    cfg.warehouse_source_id = sel ? sel.value : "";
    cfg.schema = document.getElementById("cfg_stg_schema")?.value?.trim() || "staging";
    cfg.table = document.getElementById("cfg_stg_table")?.value?.trim() || "dataset";
    cfg.table_prefix = document.getElementById("cfg_stg_prefix")?.value?.trim() || "stg_";
    cfg.mode = document.getElementById("cfg_stg_mode")?.value?.trim() || "append";
    cfg.table_key = document.getElementById("cfg_stg_key")?.value?.trim() || "staging";
    cfg.run_suffix = !!document.getElementById("cfg_stg_suffix")?.checked;
    cfg.create_table_if_missing = !!document.getElementById("cfg_stg_create")?.checked;
    cfg.add_columns_if_missing = !!document.getElementById("cfg_stg_addcols")?.checked;
  } else if (type === "notify.integration") {
    const notifyCfg = _collectNotifyConfigFromForm();
    if (!notifyCfg) return;
    cfg = notifyCfg;
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
          editor.import(_normalizeDecisionNodeOutputs(res.data));
        }
      })
      .catch(err => console.error(err));
  }
}
document.addEventListener("DOMContentLoaded", initEtlBuilder);
