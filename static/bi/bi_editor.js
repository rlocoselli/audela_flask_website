/* global CodeMirror */

// BI SQL Editor helper:
// - CodeMirror SQL editor with schema-based autocomplete
// - Schema explorer (tables/columns)
// - Query Builder that generates SQL + bind parameters (:param)
// - Natural language -> SQL integration (/app/api/nlq)

(function () {
  function qs (sel) { return document.querySelector(sel); }
  function qsa (sel) { return Array.from(document.querySelectorAll(sel)); }

  function getCsrfToken () {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  function sanitizeParam (s) {
    const x = String(s || '').trim().toLowerCase().replace(/[^a-z0-9_]+/g, '_');
    if (!x) return 'p';
    if (/^[0-9]/.test(x)) return 'p_' + x;
    return x;
  }

  function parseJsonSafe (txt) {
    if (!txt || !String(txt).trim()) return {};
    try {
      const o = JSON.parse(txt);
      return (o && typeof o === 'object' && !Array.isArray(o)) ? o : {};
    } catch (e) {
      return null;
    }
  }

  function extractBindParams (sql) {
    const out = new Set();
    const re = /:([A-Za-z_][A-Za-z0-9_]*)/g;
    let m;
    while ((m = re.exec(sql)) !== null) {
      out.add(m[1]);
    }
    return Array.from(out);
  }

  function setSchemaHtml (container, meta) {
    if (!container) return;
    if (!meta || !meta.schemas) {
      container.innerHTML = '<em>(sem metadados)</em>';
      return;
    }
    let html = '';
    for (const sc of meta.schemas) {
      html += `<details open><summary><strong>${String(sc.name || 'schema')}</strong></summary>`;
      for (const t of (sc.tables || [])) {
        const tq = sc.name ? `${String(sc.name)}.${String(t.name)}` : String(t.name);
        html += `<div class="tbl"><button type="button" class="btn btn-link p-0" data-ins="${tq}"><strong>${String(t.name)}</strong></button></div>`;
        const cols = (t.columns || []).map(c => {
          const cn = String(c.name);
          const ins = `${tq}.${cn}`;
          return `<button type="button" class="btn btn-link p-0" data-ins="${ins}">${cn}</button> <span style="color:#777;">(${String(c.type)})</span>`;
        });
        html += `<div class="cols">${cols.join('<br/>') || '<em>(sem colunas)</em>'}</div>`;
      }
      html += '</details>';
    }
    container.innerHTML = html;
  }

  function buildTablesMap (meta) {
    const tables = {}; // { tableName: [col1, col2] }
    const flat = []; // [{name, columns, schema}]
    if (!meta || !meta.schemas) return { tables, flat };
    for (const sc of meta.schemas) {
      for (const t of (sc.tables || [])) {
        const cols = (t.columns || []).map(c => c.name).filter(Boolean);
        tables[t.name] = cols;
        if (sc.name) { tables[`${sc.name}.${t.name}`] = cols; }
        flat.push({ name: t.name, columns: cols, schema: sc.name });
      }
    }
    return { tables, flat };
  }

  function sqlLimitClause (dbType, limit) {
    const n = Number(limit || 0);
    if (!n || n <= 0) return { selectPrefix: '', suffix: '' };
    const t = String(dbType || '').toLowerCase();
    if (t.includes('sqlserver') || t.includes('mssql')) {
      return { selectPrefix: `TOP ${n} `, suffix: '' };
    }
    if (t.includes('oracle')) {
      return { selectPrefix: '', suffix: ` FETCH FIRST ${n} ROWS ONLY` };
    }
    // postgres / mysql / sqlite
    return { selectPrefix: '', suffix: ` LIMIT ${n}` };
  }

  function boot () {
    const textarea = qs('#sql_text');
    if (!textarea || typeof CodeMirror === 'undefined') return;

    const form = qs('#sql-form');
    const paramsEl = qs('#params_json');
    const schemaEl = qs('#schema');
    const sourceSel = qs('#source_id');
    const nlqText = qs('#nlq-text');
    const nlqBtn = qs('#nlq-generate');
    const nlqWarn = qs('#nlq-warnings');

    // Query Builder elements
    const qbTable = qs('#qb-table');
    const qbLimit = qs('#qb-limit');
    const qbColsWrap = qs('#qb-columns');
    const qbFilterField = qs('#qb-filter-field');
    const qbFilterOp = qs('#qb-filter-op');
    const qbFilterValue = qs('#qb-filter-value');
    const qbAddFilter = qs('#qb-add-filter');
    const qbFilterList = qs('#qb-filter-list');
    const qbGenerate = qs('#qb-generate');

    const cm = CodeMirror.fromTextArea(textarea, {
      mode: 'text/x-sql',
      lineNumbers: true,
      lineWrapping: true,
      autofocus: false,
      extraKeys: {
        'Ctrl-Space': 'autocomplete',
        'Cmd-Space': 'autocomplete',
        'Cmd-Space': 'autocomplete',
        'Ctrl-Enter': () => form?.requestSubmit?.(),
        'Cmd-Enter': () => form?.requestSubmit?.()
      }
    });

    // Current schema state
    let schemaMeta = null;
    let tablesMap = {}; // {table: [cols]}
    let tablesFlat = []; // [{name, columns}]
    let currentDbType = '';

    // QB state
    const qbState = {
      table: '',
      columns: new Set(),
      filters: [] // {field, op, param, suggestedValue}
    };

    function setEditorSql (sql) {
      cm.setValue(sql || '');
      cm.focus();
    }

    function setParamsObject (obj) {
      if (!paramsEl) return;
      paramsEl.value = JSON.stringify(obj || {}, null, 2);
    }

    function getParamsObject () {
      if (!paramsEl) return {};
      const parsed = parseJsonSafe(paramsEl.value);
      return parsed === null ? null : parsed;
    }

    function ensureParamsForSql (sql) {
      if (!paramsEl) return;
      const parsed = getParamsObject();
      if (parsed === null) return; // invalid JSON; keep as is
      const keys = extractBindParams(sql || '');
      for (const k of keys) {
        // tenant_id is injected by backend; still okay to display but not required
        if (!(k in parsed)) parsed[k] = '';
      }
      setParamsObject(parsed);
    }

    // --- Autocomplete wiring ---
    function refreshAutocomplete () {
      cm.setOption('hintOptions', {
        tables: tablesMap
      });
      // Auto trigger on dot or after typing a few chars
      cm.off('inputRead');
      cm.on('inputRead', (instance, change) => {
        const ch = change.text && change.text[0];
        if (ch === '.' || ch === '_' || /[A-Za-z]/.test(ch)) {
          CodeMirror.commands.autocomplete(instance, null, { completeSingle: false });
        }
      });
    }

    // Click-to-insert from schema explorer
if (schemaEl) {
  schemaEl.addEventListener('click', (e) => {
    const btn = e.target?.closest?.('[data-ins]');
    if (!btn) return;
    e.preventDefault();
    const txt = btn.getAttribute('data-ins') || '';
    if (!txt) return;
    cm.replaceSelection(txt);
    cm.focus();
  });
}
// --- Schema load ---
    async function loadSchema () {
      const sourceId = sourceSel?.value;
      if (!sourceId) {
        schemaMeta = null;
        tablesMap = {};
        tablesFlat = [];
        setSchemaHtml(schemaEl, null);
        if (qbTable) qbTable.innerHTML = '<option value="">--</option>';
        refreshAutocomplete();
        return;
      }

      // detect db type from selected option
      const opt = sourceSel.options[sourceSel.selectedIndex];
      currentDbType = opt?.dataset?.dbtype || '';

      schemaEl.innerHTML = '<em>Loading…</em>';
      const resp = await fetch(`/app/api/sources/${sourceId}/schema`, { credentials: 'same-origin' });
      if (!resp.ok) {
        schemaEl.innerHTML = '<em>(falha ao carregar esquema)</em>';
        return;
      }
      schemaMeta = await resp.json();
      setSchemaHtml(schemaEl, schemaMeta);
      const built = buildTablesMap(schemaMeta);
      tablesMap = built.tables;
      tablesFlat = built.flat;
      refreshAutocomplete();
      refreshQueryBuilderTables();
    }

    // --- Query Builder ---
    function refreshQueryBuilderTables () {
      if (!qbTable) return;
      const options = ['<option value="">--</option>']
        .concat(tablesFlat.map(t => `<option value="${String(t.name)}">${String(t.name)}</option>`));
      qbTable.innerHTML = options.join('');
      qbState.table = '';
      qbState.columns = new Set();
      qbState.filters = [];
      renderQB();
    }

    function currentTableCols () {
      if (!qbState.table) return [];
      return tablesMap[qbState.table] || [];
    }

    function renderQB () {
      const cols = currentTableCols();

      // columns checklist
      if (qbColsWrap) {
        qbColsWrap.innerHTML = cols.map(c => {
          const checked = qbState.columns.has(c) ? 'checked' : '';
          return `<label style="display:inline-flex;align-items:center;gap:.35em;">
            <input type="checkbox" data-col="${String(c)}" ${checked} /> ${String(c)}
          </label>`;
        }).join('') || '<em>(selecione uma tabela)</em>';

        qsa('#qb-columns input[type=checkbox]').forEach(chk => {
          chk.addEventListener('change', () => {
            const c = chk.getAttribute('data-col');
            if (!c) return;
            if (chk.checked) qbState.columns.add(c);
            else qbState.columns.delete(c);
          });
        });
      }

      // filter field options
      if (qbFilterField) {
        qbFilterField.innerHTML = '<option value="">--</option>' + cols.map(c => `<option value="${String(c)}">${String(c)}</option>`).join('');
      }

      // filter list
      if (qbFilterList) {
        if (!qbState.filters.length) {
          qbFilterList.innerHTML = '<em>(sem filtros)</em>';
        } else {
          qbFilterList.innerHTML = qbState.filters.map((f, i) => {
            return `<div style="margin:.2em 0; padding:.35em .5em; border:1px solid #eee; border-radius:8px;">
              <code>${f.field} ${f.op} :${f.param}</code>
              <a href="#" data-rm="${i}" style="float:right;">×</a>
            </div>`;
          }).join('');
          qsa('#qb-filter-list a[data-rm]').forEach(a => {
            a.addEventListener('click', (e) => {
              e.preventDefault();
              const idx = Number(a.getAttribute('data-rm'));
              qbState.filters.splice(idx, 1);
              renderQB();
            });
          });
        }
      }
    }

    function qbGenerateSql () {
      const table = qbState.table;
      if (!table) return { sql: '', params: {} };

      const cols = Array.from(qbState.columns);
      const limitN = Number(qbLimit?.value || 0);
      const limitSpec = sqlLimitClause(currentDbType, limitN);
      const selectCols = cols.length ? cols.map(c => c).join(', ') : '*';
      let sql = `SELECT ${limitSpec.selectPrefix}${selectCols} FROM ${table}`;

      const params = {};

      // Auto tenant filter if column exists
      const tableCols = currentTableCols().map(c => String(c).toLowerCase());
      const hasTenant = tableCols.includes('tenant_id');
      const filters = [...qbState.filters];
      if (hasTenant) {
        // keep it first; backend injects tenant_id value
        filters.unshift({ field: 'tenant_id', op: '=', param: 'tenant_id', suggestedValue: '' });
      }

      if (filters.length) {
        const clauses = [];
        for (const f of filters) {
          const op = String(f.op || '=').toUpperCase();
          const p = f.param;
          clauses.push(`${f.field} ${op} :${p}`);
          if (p !== 'tenant_id') {
            params[p] = (typeof f.suggestedValue !== 'undefined') ? f.suggestedValue : '';
          }
        }
        sql += ' WHERE ' + clauses.join(' AND ');
      }

      sql += limitSpec.suffix;
      return { sql, params };
    }

    // --- Event handlers ---
    if (sourceSel) {
      sourceSel.addEventListener('change', loadSchema);
    }

    if (qbTable) {
      qbTable.addEventListener('change', () => {
        qbState.table = qbTable.value;
        qbState.columns = new Set();
        qbState.filters = [];
        renderQB();
      });
    }

    if (qbAddFilter) {
      qbAddFilter.addEventListener('click', (e) => {
        e.preventDefault();
        const field = qbFilterField?.value;
        const op = qbFilterOp?.value || '=';
        const raw = qbFilterValue?.value;
        if (!field) return;

        const base = sanitizeParam(field);
        const idx = qbState.filters.filter(f => f.param.startsWith(base)).length + 1;
        const param = `${base}_${idx}`;
        let suggested = raw;
        if (String(op).toUpperCase() === 'LIKE' && raw && raw.indexOf('%') === -1) {
          suggested = `%${raw}%`;
        }
        qbState.filters.push({ field, op, param, suggestedValue: suggested });
        if (qbFilterValue) qbFilterValue.value = '';
        renderQB();
      });
    }

    if (qbGenerate) {
      qbGenerate.addEventListener('click', (e) => {
        e.preventDefault();
        const gen = qbGenerateSql();
        if (!gen.sql) return;
        setEditorSql(gen.sql);

        // merge parameters (keep what the user already typed)
        const current = getParamsObject();
        if (current !== null) {
          const merged = { ...current, ...gen.params };
          // remove tenant_id if user had it; backend injects anyway
          delete merged.tenant_id;
          setParamsObject(merged);
        }
        ensureParamsForSql(gen.sql);
      });
    }

    if (nlqBtn) {
      nlqBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        const sourceId = sourceSel?.value;
        const text = nlqText?.value || '';
        if (!sourceId) return;
        if (nlqWarn) nlqWarn.innerHTML = '';
        const resp = await fetch('/app/api/nlq', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            ...(getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {})
          },
          body: JSON.stringify({ source_id: Number(sourceId), text })
        });
        const payload = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          if (nlqWarn) nlqWarn.innerHTML = `<span style="color:#b00;">${payload.error || 'Erro'}</span>`;
          return;
        }
        setEditorSql(payload.sql || '');
        ensureParamsForSql(payload.sql || '');
        if (nlqWarn && payload.warnings && payload.warnings.length) {
          nlqWarn.innerHTML = payload.warnings.map(w => `<div style="color:#a60;">• ${String(w)}</div>`).join('');
        }
      });
    }

    // Validate params JSON on submit
    if (form) {
      form.addEventListener('submit', (e) => {
        const parsed = getParamsObject();
        if (parsed === null) {
          e.preventDefault();
          if (window.uiToast) window.uiToast('Parâmetros JSON inválidos. Corrija antes de executar.', { variant: 'danger' });
          else alert('Parâmetros JSON inválidos. Corrija antes de executar.');
          return;
        }
        // Keep params in sync with SQL placeholders
        ensureParamsForSql(cm.getValue());
      });
    }

    // Initial load
    loadSchema().catch(() => {});
    renderQB();
    refreshAutocomplete();
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
