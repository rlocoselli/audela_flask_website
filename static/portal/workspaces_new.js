// Workspace Builder: quick join builder + autocomplete + AI draft

(function(){
  const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  const form = document.getElementById('ws-form');
  if (!form) return;

  const elDbSources = document.getElementById('ws-db-sources');
  const elSourceTags = document.getElementById('ws-source-tags');
  const elSourceCount = document.getElementById('ws-source-count');
  const elSelectAllSources = document.getElementById('ws-select-all-sources');
  const elClearSources = document.getElementById('ws-clear-sources');
  const elPickDbTables = document.getElementById('ws-pick-db-tables');
  const elDbTablesHidden = document.getElementById('ws-db-tables');
  const elDbTablesJsonHidden = document.getElementById('ws-db-tables-json');
  const elDbTableTags = document.getElementById('ws-db-table-tags');
  const elStarterSqlHidden = document.getElementById('ws-starter-sql');

  const elFileFilter = document.getElementById('ws-file-filter');
  const elFileFormatFilter = document.getElementById('ws-file-format-filter');
  const elFileSelectedOnly = document.getElementById('ws-file-selected-only');
  const elFilesCount = document.getElementById('ws-files-count');
  const elSelectAllFiles = document.getElementById('ws-select-all-files');
  const elClearFiles = document.getElementById('ws-clear-files');
  const filesTable = document.getElementById('ws-files-table');

  const elBaseTable = document.getElementById('ws-base-table');
  const elSuggestions = document.getElementById('ws-suggestions');
  const elRefreshSuggestions = document.getElementById('ws-refresh-suggestions');
  const elAddJoin = document.getElementById('ws-add-join');
  const joinsBody = document.querySelector('#ws-joins-table tbody');
  const elGenerateSql = document.getElementById('ws-generate-sql');
  const elAiSql = document.getElementById('ws-ai-sql');
  const elAiPrompt = document.getElementById('ws-ai-prompt');
  const elSqlPreview = document.getElementById('ws-sql-preview');

  // Modals
  const dbModalEl = document.getElementById('wsDbTablesModal');
  const dbModal = dbModalEl ? bootstrap.Modal.getOrCreateInstance(dbModalEl) : null;
  const elDbTableSearch = document.getElementById('ws-db-table-search');
  const elDbTableSourceFilter = document.getElementById('ws-db-table-source-filter');
  const elDbTableSelectedOnly = document.getElementById('ws-db-table-selected-only');
  const elDbTableCount = document.getElementById('ws-db-table-count');
  const elDbTableList = document.getElementById('ws-db-table-list');
  const elDbTableApply = document.getElementById('ws-db-table-apply');

  const schemaModalEl = document.getElementById('wsSchemaModal');
  const schemaModal = schemaModalEl ? bootstrap.Modal.getOrCreateInstance(schemaModalEl) : null;
  const elSchemaTitle = document.getElementById('ws-schema-title');
  const elSchemaBody = document.getElementById('ws-schema-body');

  // -----------------------------
  // State
  // -----------------------------

  const state = {
    dbSourceIds: [],
    dbSchemas: new Map(), // sourceId -> {sourceId, sourceName, tables:{nameLower:{name, columns:[]}}}
    selectedDbTables: [],
    fileSchemaCache: new Map(),
    joins: [], // {type, right, leftCol, rightCol}
  };

  // -----------------------------
  // Helpers
  // -----------------------------

  function sanitizeTableName(name){
    let n = String(name || '').trim().replace(/[^A-Za-z0-9_]/g, '_');
    if (!n) n = 't';
    if (/^\d/.test(n)) n = 't_' + n;
    return n;
  }

  function fetchJSON(url){
    return fetch(url, { credentials: 'same-origin' }).then(r => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }

  function postJSON(url, data){
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf,
        'X-CSRF-Token': csrf,
      },
      body: JSON.stringify(data || {}),
    }).then(r => r.json().then(j => ({ ok: r.ok, status: r.status, json: j })));
  }



  // Detect app prefix (dev uses /app)
  const APP_PREFIX = (window.location.pathname.startsWith('/app/') ? '/app' : (window.location.pathname.startsWith('/portal/') ? '/portal' : ''));
  function apiUrl(path){
    return APP_PREFIX + path;
  }
  function getSelectedFiles(){
    if (!filesTable) return [];
    const rows = filesTable.querySelectorAll('tbody tr[data-file-row="1"]');
    const out = [];
    rows.forEach(tr => {
      const chk = tr.querySelector('.ws-file-check');
      if (!chk || !chk.checked) return;
      const fileId = parseInt(tr.getAttribute('data-file-id') || '0', 10);
      const aliasInput = tr.querySelector('.ws-alias');
      const alias = sanitizeTableName(aliasInput ? aliasInput.value : ('file_' + fileId));
      out.push({ file_id: fileId, table: alias, ref: 'files.' + alias });
    });
    return out;
  }

  function getMaxRows(){
    const el = form.querySelector('input[name="max_rows"]');
    const v = parseInt(el?.value || '5000', 10);
    if (!isFinite(v)) return 5000;
    return Math.max(100, Math.min(v, 50000));
  }

  function getDbTables(){
    return state.selectedDbTables.map((x) => ({ ...x }));
  }

  function getSelectedDbSourceIds(){
    if (!elDbSources) return [];
    return Array.from(elDbSources.selectedOptions || [])
      .map((opt) => parseInt(opt.value || '0', 10))
      .filter((id) => Number.isFinite(id) && id > 0);
  }

  function renderDbSourceSelectionUI(){
    if (!elDbSources) return;
    const selectedOpts = Array.from(elDbSources.selectedOptions || []);

    if (elSourceCount) {
      elSourceCount.textContent = selectedOpts.length
        ? tformat('{n} source(s) selected', { n: selectedOpts.length })
        : window.t('No source selected');
    }

    if (elSourceTags) {
      elSourceTags.innerHTML = '';
      selectedOpts.forEach((opt) => {
        const sid = String(opt.value || '').trim();
        const lbl = String(opt.textContent || sid).trim();
        const tag = document.createElement('span');
        tag.className = 'ws-tag';
        tag.innerHTML = `<span>${escapeHtml(lbl)}</span>`;
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.innerHTML = '<i class="bi bi-x"></i>';
        btn.title = window.t('Remove');
        btn.addEventListener('click', () => {
          Array.from(elDbSources.options || []).forEach((o) => {
            if (String(o.value || '').trim() === sid) o.selected = false;
          });
          elDbSources.dispatchEvent(new Event('change', { bubbles: true }));
        });
        tag.appendChild(btn);
        elSourceTags.appendChild(tag);
      });
    }
  }

  function getVisibleFileRows(){
    if (!filesTable) return [];
    return Array.from(filesTable.querySelectorAll('tbody tr[data-file-row="1"]')).filter((tr) => tr.style.display !== 'none');
  }

  function populateFileFormatFilter(){
    if (!filesTable || !elFileFormatFilter) return;
    const rows = Array.from(filesTable.querySelectorAll('tbody tr[data-file-row="1"]'));
    const formats = Array.from(new Set(rows.map((tr) => String(tr.getAttribute('data-file-format') || '').trim()).filter(Boolean))).sort();
    const current = String(elFileFormatFilter.value || '');
    elFileFormatFilter.innerHTML = `<option value="">${escapeHtml(window.t('All formats'))}</option>`;
    formats.forEach((fmt) => {
      const opt = document.createElement('option');
      opt.value = fmt;
      opt.textContent = fmt.toUpperCase();
      elFileFormatFilter.appendChild(opt);
    });
    if (formats.includes(current)) {
      elFileFormatFilter.value = current;
    }
  }

  function applyFilesFilters(){
    if (!filesTable) return;
    const term = String(elFileFilter?.value || '').trim().toLowerCase();
    const fmt = String(elFileFormatFilter?.value || '').trim().toLowerCase();
    const selectedOnly = !!(elFileSelectedOnly && elFileSelectedOnly.checked);
    filesTable.querySelectorAll('tbody tr[data-file-row="1"]').forEach((tr) => {
      const name = String(tr.getAttribute('data-file-name') || '').toLowerCase();
      const format = String(tr.getAttribute('data-file-format') || '').toLowerCase();
      const chk = tr.querySelector('.ws-file-check');
      const isChecked = !!(chk && chk.checked);
      const matchesTerm = !term || name.includes(term);
      const matchesFmt = !fmt || format === fmt;
      const matchesSelected = !selectedOnly || isChecked;
      tr.style.display = (matchesTerm && matchesFmt && matchesSelected) ? '' : 'none';
    });
    renderFilesSelectionUI();
  }

  function populateDbSourceFilter(schemas){
    if (!elDbTableSourceFilter) return;
    const current = String(elDbTableSourceFilter.value || '');
    elDbTableSourceFilter.innerHTML = `<option value="">${escapeHtml(window.t('All sources'))}</option>`;
    const rows = Array.from((schemas || new Map()).values()).map((schema) => ({
      sourceId: Number(schema.sourceId || 0),
      sourceName: String(schema.sourceName || schema.sourceId || ''),
    })).filter((x) => x.sourceId > 0).sort((a, b) => a.sourceName.localeCompare(b.sourceName));
    rows.forEach((row) => {
      const opt = document.createElement('option');
      opt.value = String(row.sourceId);
      opt.textContent = row.sourceName;
      elDbTableSourceFilter.appendChild(opt);
    });
    if (Array.from(elDbTableSourceFilter.options).some((o) => o.value === current)) {
      elDbTableSourceFilter.value = current;
    }
  }

  function renderFilesSelectionUI(){
    if (!filesTable || !elFilesCount) return;
    const rows = getVisibleFileRows();
    const selected = rows.filter((tr) => {
      const chk = tr.querySelector('.ws-file-check');
      return !!(chk && chk.checked);
    }).length;
    const total = rows.length;
    if (!total) {
      elFilesCount.textContent = window.t('No file selected');
      return;
    }
    elFilesCount.textContent = tformat('{selected}/{total} file(s) selected', { selected, total });
  }

  function getSourceName(sourceId){
    if (!elDbSources || !sourceId) return String(sourceId || '');
    const opt = Array.from(elDbSources.options || []).find((o) => parseInt(o.value || '0', 10) === Number(sourceId));
    return String(opt?.textContent || sourceId).trim();
  }

  function setDbTables(tables){
    const normalized = [];
    const seen = new Set();
    (tables || []).forEach((x) => {
      if (x == null) return;
      if (typeof x === 'string') {
        const t = String(x || '').trim();
        if (!t) return;
        const sid = Number(state.dbSourceIds[0] || 0);
        if (!sid) return;
        const key = `${sid}::${t.toLowerCase()}`;
        if (seen.has(key)) return;
        seen.add(key);
        normalized.push({ source_id: sid, source_name: getSourceName(sid), table: t });
        return;
      }
      const sid = parseInt(String((x || {}).source_id || '0'), 10);
      const t = String((x || {}).table || '').trim();
      if (!sid || !t) return;
      const key = `${sid}::${t.toLowerCase()}`;
      if (seen.has(key)) return;
      seen.add(key);
      normalized.push({ source_id: sid, source_name: String((x || {}).source_name || getSourceName(sid)), table: t });
    });
    state.selectedDbTables = normalized.slice(0, 300);
    // Legacy fallback field (flat tables) remains for compatibility.
    elDbTablesHidden.value = state.selectedDbTables.map((x) => x.table).join(',');
    if (elDbTablesJsonHidden) {
      elDbTablesJsonHidden.value = JSON.stringify(state.selectedDbTables);
    }
    renderDbTableTags();
    refreshCatalog();
  }

  function renderDbTableTags(){
    if (!elDbTableTags) return;
    elDbTableTags.innerHTML = '';
    state.selectedDbTables.forEach((entry) => {
      const tname = String(entry.table || '');
      const sid = Number(entry.source_id || 0);
      if (!sid || !tname) return;
      const span = document.createElement('span');
      span.className = 'ws-tag';
      span.innerHTML = `<span class="ws-mono">db${escapeHtml(String(sid))}.${escapeHtml(sanitizeTableName(tname))}</span>`;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.innerHTML = '<i class="bi bi-x"></i>';
      btn.title = window.t('Remove');
      btn.onclick = () => setDbTables(state.selectedDbTables.filter(x => !(Number(x.source_id) === sid && String(x.table || '').toLowerCase() === tname.toLowerCase())));
      span.appendChild(btn);
      elDbTableTags.appendChild(span);
    });
  }

  function escapeHtml(s){
    return String(s||'').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
function toast(msg, variant){
    if (window.uiToast) window.uiToast(msg, { variant: variant || 'info' });
    else alert(msg);
  }

  function tformat(message, vars){
    if (typeof window.tf === 'function') {
      return window.tf(message, vars || {});
    }
    let out = String(message || '');
    Object.entries(vars || {}).forEach(([k, v]) => {
      out = out.replaceAll(`{${k}}`, String(v));
    });
    return out;
  }

  // -----------------------------
  // DB schema loading + modal
  // -----------------------------

  async function ensureDbSchemas(){
    const sourceIds = getSelectedDbSourceIds();
    state.dbSourceIds = sourceIds;
    const keep = new Set(sourceIds);
    Array.from(state.dbSchemas.keys()).forEach((id) => {
      if (!keep.has(Number(id))) state.dbSchemas.delete(id);
    });
    if (!sourceIds.length) return state.dbSchemas;

    for (const id of sourceIds) {
      if (state.dbSchemas.has(id)) continue;
      try {
        const meta = await fetchJSON(apiUrl(`/api/sources/${id}/schema`));
        if (meta && meta.error) {
          toast(meta.error, 'danger');
        }
        const tables = {};
        (meta.schemas || []).forEach(sc => {
          (sc.tables || []).forEach(t => {
            const name = String(t.name || '');
            const k = name.toLowerCase();
            const cols = (t.columns || []).map(c => String(c.name || '')).filter(Boolean);
            tables[k] = { name, columns: cols };
          });
        });
        state.dbSchemas.set(id, {
          sourceId: id,
          sourceName: getSourceName(id),
          tables,
        });
      } catch (e) {
        toast(window.t('Unable to load.'), 'danger');
      }
    }
    return state.dbSchemas;
  }

  function openDbTablesModal(){
    const ids = getSelectedDbSourceIds();
    if (!ids.length) {
      toast(window.t('Select at least one database source to list tables.'), 'info');
      return;
    }
    dbModal?.show();
    renderDbTablesList();
  }

  async function renderDbTablesList(){
    if (!elDbTableList) return;
    elDbTableList.innerHTML = `<div class="text-secondary small">${escapeHtml(window.t('Loading...'))}</div>`;
    const schemas = await ensureDbSchemas();
    if (!schemas || !schemas.size) {
      elDbTableList.innerHTML = `<div class="text-secondary small">${escapeHtml(window.t('Unable to load.'))}</div>`;
      return;
    }
    const term = String(elDbTableSearch?.value || '').trim().toLowerCase();
    const sourceFilter = String(elDbTableSourceFilter?.value || '').trim();
    const selectedOnly = !!(elDbTableSelectedOnly && elDbTableSelectedOnly.checked);
    populateDbSourceFilter(schemas);
    const all = [];
    Array.from(schemas.values()).forEach((schema) => {
      Object.values(schema.tables || {}).forEach((tbl) => {
        all.push({
          source_id: Number(schema.sourceId),
          source_name: String(schema.sourceName || schema.sourceId),
          table: String(tbl.name || ''),
          columns: Array.isArray(tbl.columns) ? tbl.columns : [],
        });
      });
    });
    const filtered = all.filter((x) => {
      const matchesTerm = !term || (`${x.source_name} ${x.table}`).toLowerCase().includes(term);
      const matchesSource = !sourceFilter || String(x.source_id) === sourceFilter;
      const isChecked = state.selectedDbTables.some((t) => Number(t.source_id) === Number(x.source_id) && String(t.table || '').toLowerCase() === String(x.table || '').toLowerCase());
      const matchesSelected = !selectedOnly || isChecked;
      return matchesTerm && matchesSource && matchesSelected;
    });

    if (elDbTableCount) {
      elDbTableCount.textContent = tformat('Showing {shown}/{total} table(s)', {
        shown: filtered.length,
        total: all.length,
      });
    }

    if (!filtered.length) {
      elDbTableList.innerHTML = `<div class="text-secondary small">${escapeHtml(window.t('No tables found.'))}</div>`;
      return;
    }

    elDbTableList.innerHTML = '';
    filtered.sort((a, b) => {
      if (a.source_id !== b.source_id) return a.source_id - b.source_id;
      return a.table.localeCompare(b.table);
    });
    filtered.slice(0, 700).forEach((row) => {
      const name = String(row.table || '');
      const sid = Number(row.source_id || 0);
      const sourceName = String(row.source_name || sid);
      const id = `tbl_${sid}_` + name.replace(/[^A-Za-z0-9_]/g,'_');
      const item = document.createElement('label');
      item.className = 'list-group-item d-flex align-items-start gap-2';
      const checked = state.selectedDbTables.some((x) => Number(x.source_id) === sid && String(x.table || '').toLowerCase() === name.toLowerCase());
      item.innerHTML = `
        <input class="form-check-input mt-1" type="checkbox" id="${escapeHtml(id)}" ${checked ? 'checked' : ''} data-db-source-id="${escapeHtml(String(sid))}" data-db-source-name="${escapeHtml(sourceName)}" data-db-table="${escapeHtml(name)}">
        <div class="flex-grow-1">
          <div class="fw-semibold ws-mono">db${escapeHtml(String(sid))}.${escapeHtml(sanitizeTableName(name))}</div>
          <div class="text-secondary small">${escapeHtml(sourceName)}</div>
          <div class="text-secondary small">${escapeHtml((row.columns || []).slice(0, 8).join(', '))}${(row.columns || []).length > 8 ? '…' : ''}</div>
        </div>
      `;
      elDbTableList.appendChild(item);
    });
  }

  function applyDbTablesFromModal(){
    const checks = elDbTableList?.querySelectorAll('input[data-db-table]') || [];
    const selected = [];
    checks.forEach(chk => {
      if (!chk.checked) return;
      selected.push({
        source_id: parseInt(chk.getAttribute('data-db-source-id') || '0', 10),
        source_name: String(chk.getAttribute('data-db-source-name') || ''),
        table: String(chk.getAttribute('data-db-table') || ''),
      });
    });
    setDbTables(selected);
    dbModal?.hide();
  }

  // -----------------------------
  // File schema modal
  // -----------------------------

  async function loadFileSchema(fileId){
    if (state.fileSchemaCache.has(fileId)) return state.fileSchemaCache.get(fileId);
    const schema = await fetchJSON(apiUrl(`/api/files/${fileId}/schema`));
    state.fileSchemaCache.set(fileId, schema || { columns: [] });
    return schema;
  }

  async function showFileSchema(fileId){
    try {
      const schema = await loadFileSchema(fileId);
      const rows = (schema.columns || []).map(c => `
        <div class="d-flex justify-content-between gap-3 py-1 border-bottom">
          <div class="ws-mono">${escapeHtml(c.name || '')}</div>
          <div class="text-secondary">${escapeHtml(c.type || '')}</div>
        </div>
      `).join('') || `<div class="text-secondary">${escapeHtml(window.t('No tables found.'))}</div>`;
      const tr = filesTable?.querySelector(`tr[data-file-id="${fileId}"]`);
      const fileName = tr?.getAttribute('data-file-name') || ('#' + fileId);
      elSchemaTitle.textContent = tformat('Schema: {name}', { name: fileName });
      elSchemaBody.innerHTML = rows;
      schemaModal?.show();
    } catch (e) {
      toast(window.t('Unable to load schema.'), 'danger');
    }
  }

  // -----------------------------
  // Catalog + autocomplete
  // -----------------------------

  async function buildCatalog(){
    const files = getSelectedFiles();
    const dbTables = getDbTables();
    const out = { tables: [] };

    // files
    for (const f of files) {
      let cols = [];
      try {
        const schema = await loadFileSchema(f.file_id);
        cols = (schema.columns || []).map(c => String(c.name || '')).filter(Boolean);
      } catch (_) {}
      out.tables.push({ ref: f.ref, kind: 'file', name: f.table, cols });
    }

    // db tables
    if (dbTables.length) {
      await ensureDbSchemas();
      dbTables.forEach((entry) => {
        const sid = Number(entry.source_id || 0);
        const tname = String(entry.table || '').trim();
        if (!sid || !tname) return;
        const safe = sanitizeTableName(tname);
        const schema = state.dbSchemas.get(sid);
        const cols = (schema?.tables?.[tname.toLowerCase()]?.columns || []);
        out.tables.push({ ref: `db${sid}.${safe}`, kind: 'db', name: safe, cols, source_id: sid });
      });
    }

    return out;
  }

  async function refreshCatalog(){
    const catalog = await buildCatalog();
    // Base table options
    elBaseTable.innerHTML = '';
    if (!catalog.tables.length) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = '(' + window.t('Select files/tables') + ')';
      elBaseTable.appendChild(opt);
    } else {
      catalog.tables.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.ref;
        opt.textContent = t.ref;
        elBaseTable.appendChild(opt);
      });
      if (!elBaseTable.value) elBaseTable.value = catalog.tables[0].ref;
    }

    // Re-render joins table options/columns
    renderJoinsRows(catalog);
    renderSuggestions(catalog);
  }

  function allTablesForSelect(catalog){
    return (catalog?.tables || []).map(t => t.ref);
  }

  function colsForTableRef(catalog, ref){
    const t = (catalog.tables || []).find(x => x.ref === ref);
    return t ? (t.cols || []) : [];
  }

  // -----------------------------
  // Join builder
  // -----------------------------

  function newJoinRow(pref){
    return {
      type: (pref?.type || 'INNER').toUpperCase(),
      right: pref?.right || '',
      leftCol: pref?.leftCol || '',
      rightCol: pref?.rightCol || '',
    };
  }

  function renderJoinsRows(catalog){
    if (!joinsBody) return;
    joinsBody.innerHTML = '';
    const tables = allTablesForSelect(catalog);
    state.joins.forEach((j, idx) => {
      const tr = document.createElement('tr');
      tr.setAttribute('data-join-idx', String(idx));

      // type
      const tdType = document.createElement('td');
      tdType.innerHTML = `
        <select class="form-select form-select-sm ws-join-type">
          <option value="INNER">INNER</option>
          <option value="LEFT">LEFT</option>
          <option value="RIGHT">RIGHT</option>
          <option value="FULL">FULL</option>
        </select>
      `;
      tdType.querySelector('select').value = j.type || 'INNER';

      // right table
      const tdTable = document.createElement('td');
      const opts = tables.map(t => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join('');
      tdTable.innerHTML = `<select class="form-select form-select-sm ws-join-right"><option value="">(${escapeHtml(window.t('Table'))})</option>${opts}</select>`;
      tdTable.querySelector('select').value = j.right || '';

      // left col
      const tdLeft = document.createElement('td');
      tdLeft.innerHTML = `<input class="form-control form-control-sm ws-join-left" placeholder="${escapeHtml(window.t('Column'))}" />`;
      tdLeft.querySelector('input').value = j.leftCol || '';

      // right col
      const tdRight = document.createElement('td');
      tdRight.innerHTML = `<input class="form-control form-control-sm ws-join-rightcol" placeholder="${escapeHtml(window.t('Column'))}" />`;
      tdRight.querySelector('input').value = j.rightCol || '';

      // remove
      const tdRm = document.createElement('td');
      tdRm.className = 'text-end';
      tdRm.innerHTML = `<button class="btn btn-outline-danger btn-sm" type="button" title="${escapeHtml(window.t('Remove'))}"><i class="bi bi-trash"></i></button>`;

      tr.appendChild(tdType);
      tr.appendChild(tdTable);
      tr.appendChild(tdLeft);
      tr.appendChild(tdRight);
      tr.appendChild(tdRm);
      joinsBody.appendChild(tr);

      // wire
      tdType.querySelector('select').addEventListener('change', (e) => { state.joins[idx].type = e.target.value; });
      tdTable.querySelector('select').addEventListener('change', (e) => { state.joins[idx].right = e.target.value; renderSuggestions(catalog); });
      tdLeft.querySelector('input').addEventListener('input', (e) => { state.joins[idx].leftCol = e.target.value; });
      tdRight.querySelector('input').addEventListener('input', (e) => { state.joins[idx].rightCol = e.target.value; });
      tdRm.querySelector('button').addEventListener('click', () => {
        state.joins.splice(idx, 1);
        refreshCatalog();
      });
    });

    // Autocomplete columns (jQuery UI)
    try {
      const baseRef = elBaseTable.value;
      const baseCols = colsForTableRef(catalog, baseRef);
      joinsBody.querySelectorAll('tr').forEach((tr, idx) => {
        const rightRef = state.joins[idx]?.right;
        const rightCols = colsForTableRef(catalog, rightRef);
        $(tr.querySelector('.ws-join-left')).autocomplete({ source: baseCols, minLength: 0 });
        $(tr.querySelector('.ws-join-rightcol')).autocomplete({ source: rightCols, minLength: 0 });
      });
    } catch (_) {}
  }

  // -----------------------------
  // Suggestions
  // -----------------------------

  function tableNameFromRef(ref){
    const s = String(ref || '');
    const parts = s.split('.');
    return (parts.length === 2) ? parts[1] : s;
  }

  function scoreJoin(aRef, aCols, bRef, bCols){
    const aName = tableNameFromRef(aRef).toLowerCase();
    const bName = tableNameFromRef(bRef).toLowerCase();
    const aSet = new Set(aCols.map(x => x.toLowerCase()));
    const bSet = new Set(bCols.map(x => x.toLowerCase()));

    // FK heuristic: <other>_id
    function fk(aSideName, aSideSet, bSideName, bSideSet){
      // a has b_id and b has id
      const cand = `${bSideName.replace(/s$/,'')}_id`;
      if (aSideSet.has(cand) && bSideSet.has('id')) return { leftCol: cand, rightCol: 'id', score: 0.92 };
      const cand2 = `${bSideName}_id`;
      if (aSideSet.has(cand2) && bSideSet.has('id')) return { leftCol: cand2, rightCol: 'id', score: 0.90 };
      return null;
    }

    // Try a->b then b->a
    const fk1 = fk(aName, aSet, bName, bSet);
    if (fk1) return { left: aRef, right: bRef, ...fk1 };
    const fk2 = fk(bName, bSet, aName, aSet);
    if (fk2) return { left: bRef, right: aRef, leftCol: fk2.leftCol, rightCol: fk2.rightCol, score: fk2.score };

    // Exact matching column names (excluding very generic)
    const inter = [];
    aSet.forEach(c => { if (bSet.has(c)) inter.push(c); });
    const generic = new Set(['id','date','created_at','updated_at','name']);
    const strong = inter.filter(c => !generic.has(c));
    if (strong.length) return { left: aRef, right: bRef, leftCol: strong[0], rightCol: strong[0], score: 0.75 };
    if (inter.includes('id')) return { left: aRef, right: bRef, leftCol: 'id', rightCol: 'id', score: 0.40 };
    return null;
  }

  function computeSuggestions(catalog){
    const tabs = catalog.tables || [];
    if (tabs.length < 2) return [];

    const base = elBaseTable.value;
    const out = [];
    for (let i=0;i<tabs.length;i++){
      for (let j=i+1;j<tabs.length;j++){
        const a = tabs[i], b = tabs[j];
        const sug = scoreJoin(a.ref, a.cols||[], b.ref, b.cols||[]);
        if (!sug) continue;
        // Prefer suggestions that involve base table
        let bias = 0;
        if (base && (sug.left===base || sug.right===base)) bias = 0.10;
        out.push({ ...sug, score: Math.min(1, (sug.score||0) + bias) });
      }
    }
    out.sort((x,y) => (y.score||0) - (x.score||0));
    // dedupe by signature
    const seen = new Set();
    return out.filter(s => {
      const k = `${s.left}|${s.right}|${s.leftCol}|${s.rightCol}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    }).slice(0, 12);
  }

  function renderSuggestions(catalog){
    if (!elSuggestions) return;
    elSuggestions.innerHTML = '';
    const sugs = computeSuggestions(catalog);
    if (!sugs.length) {
      elSuggestions.innerHTML = `<div class="text-secondary small">${escapeHtml(window.t('No suggestions available.'))}</div>`;
      return;
    }
    sugs.forEach((s) => {
      const item = document.createElement('div');
      item.className = 'list-group-item d-flex align-items-center justify-content-between gap-2';
      const text = `<div class="small"><span class="ws-mono">${escapeHtml(s.left)}</span> ↔ <span class="ws-mono">${escapeHtml(s.right)}</span><br><span class="text-secondary ws-mono">${escapeHtml(s.leftCol)} = ${escapeHtml(s.rightCol)}</span></div>`;
      item.innerHTML = `${text}<button class="btn btn-outline-primary btn-sm" type="button">${escapeHtml(window.t('Apply'))}</button>`;
      item.querySelector('button').addEventListener('click', () => applySuggestion(s));
      elSuggestions.appendChild(item);
    });
  }

  function applySuggestion(s){
    const base = elBaseTable.value || s.left;
    // Ensure base is the table that already exists, else set
    elBaseTable.value = base || s.left;

    let leftRef = base;
    let rightRef = (s.left === base) ? s.right : s.left;
    let leftCol = (s.left === base) ? s.leftCol : s.rightCol;
    let rightCol = (s.left === base) ? s.rightCol : s.leftCol;

    state.joins.push(newJoinRow({ type: 'INNER', right: rightRef, leftCol, rightCol }));
    refreshCatalog();
  }

  // -----------------------------
  // SQL generator
  // -----------------------------

  function qualifyCol(tableRef, col){
    const c = String(col || '').trim();
    if (!c) return '';
    if (c.includes('.')) return c; // already qualified
    return `${tableRef}.${c}`;
  }

  function buildSql(){
    const base = elBaseTable.value;
    if (!base) return '';
    const lines = [];
    lines.push(`SELECT *`);
    lines.push(`FROM ${base}`);
    state.joins.forEach(j => {
      if (!j.right) return;
      const type = (j.type || 'INNER').toUpperCase();
      const leftExpr = qualifyCol(base, j.leftCol);
      const rightExpr = qualifyCol(j.right, j.rightCol);
      if (leftExpr && rightExpr) {
        lines.push(`${type} JOIN ${j.right} ON ${leftExpr} = ${rightExpr}`);
      } else {
        lines.push(`${type} JOIN ${j.right}`);
      }
    });
    lines.push(`LIMIT 500`);
    return lines.join('\n');
  }

  function setSqlPreview(sql){
    elSqlPreview.value = sql || '';
    elStarterSqlHidden.value = (sql || '').trim();
  }

  // -----------------------------
  // Events
  // -----------------------------

  if (elPickDbTables) elPickDbTables.addEventListener('click', async () => {
    await ensureDbSchemas();
    openDbTablesModal();
  });

  if (elDbTableSearch) elDbTableSearch.addEventListener('input', renderDbTablesList);
  if (elDbTableSourceFilter) elDbTableSourceFilter.addEventListener('change', renderDbTablesList);
  if (elDbTableSelectedOnly) elDbTableSelectedOnly.addEventListener('change', renderDbTablesList);
  if (elDbTableApply) elDbTableApply.addEventListener('click', applyDbTablesFromModal);

  if (elDbSources) elDbSources.addEventListener('change', async () => {
    // reset tables when changing source
    state.selectedDbTables = [];
    elDbTablesHidden.value = '';
    if (elDbTablesJsonHidden) elDbTablesJsonHidden.value = '[]';
    renderDbTableTags();
    renderDbSourceSelectionUI();
    await ensureDbSchemas();
    refreshCatalog();
  });

  if (elSelectAllSources && elDbSources) {
    elSelectAllSources.addEventListener('click', () => {
      Array.from(elDbSources.options || []).forEach((opt) => { opt.selected = true; });
      elDbSources.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }

  if (elClearSources && elDbSources) {
    elClearSources.addEventListener('click', () => {
      Array.from(elDbSources.options || []).forEach((opt) => { opt.selected = false; });
      elDbSources.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }

  // File filter
  if (elFileFilter && filesTable) {
    elFileFilter.addEventListener('input', applyFilesFilters);
  }
  if (elFileFormatFilter) elFileFormatFilter.addEventListener('change', applyFilesFilters);
  if (elFileSelectedOnly) elFileSelectedOnly.addEventListener('change', applyFilesFilters);

  if (elSelectAllFiles) {
    elSelectAllFiles.addEventListener('click', () => {
      getVisibleFileRows().forEach((tr) => {
        const chk = tr.querySelector('.ws-file-check');
        if (chk) chk.checked = true;
      });
      renderFilesSelectionUI();
      refreshCatalog();
    });
  }

  if (elClearFiles) {
    elClearFiles.addEventListener('click', () => {
      getVisibleFileRows().forEach((tr) => {
        const chk = tr.querySelector('.ws-file-check');
        if (chk) chk.checked = false;
      });
      renderFilesSelectionUI();
      refreshCatalog();
    });
  }

  // File selection changes
  if (filesTable) {
    filesTable.addEventListener('change', (e) => {
      if (e.target.classList.contains('ws-file-check')) {
        applyFilesFilters();
        renderFilesSelectionUI();
        refreshCatalog();
      }
      if (e.target.classList.contains('ws-alias')) refreshCatalog();
    });
    filesTable.addEventListener('input', (e) => {
      if (e.target.classList.contains('ws-alias')) refreshCatalog();
    });
    filesTable.addEventListener('click', (e) => {
      const btn = e.target.closest('.ws-show-schema');
      if (!btn) return;
      const fid = parseInt(btn.getAttribute('data-file-id') || '0', 10);
      if (fid) showFileSchema(fid);
    });
  }

  // Base table affects autocomplete
  elBaseTable.addEventListener('change', refreshCatalog);

  if (elRefreshSuggestions) elRefreshSuggestions.addEventListener('click', refreshCatalog);

  if (elAddJoin) elAddJoin.addEventListener('click', async () => {
    const catalog = await buildCatalog();
    if ((catalog.tables || []).length < 2) {
      toast(window.t('Select at least two tables to suggest joins.'), 'info');
      return;
    }
    const tables = allTablesForSelect(catalog).filter(t => t !== elBaseTable.value);
    state.joins.push(newJoinRow({ right: tables[0] || '' }));
    refreshCatalog();
  });

  if (elGenerateSql) elGenerateSql.addEventListener('click', () => {
    const sql = buildSql();
    setSqlPreview(sql);
    toast(window.t('SQL generated.'), 'success');
  });

  if (elAiSql) elAiSql.addEventListener('click', async () => {
    const prompt = String(elAiPrompt.value || '').trim();
    if (!prompt) {
      toast(window.t('Describe your analysis.'), 'info');
      return;
    }
    const files = getSelectedFiles();
    const dbSourceIds = getSelectedDbSourceIds();
    const dbTables = getDbTables();

    const payload = {
      prompt,
      db_source_ids: dbSourceIds,
      db_source_id: dbSourceIds.length ? dbSourceIds[0] : null,
      db_tables: dbTables,
      files: files.map(x => ({ file_id: x.file_id, table: x.table })),
      max_rows: getMaxRows(),
    };

    toast(window.t('Loading...'), 'info');
    const res = await postJSON(apiUrl('/api/workspaces/draft_sql'), payload);
    if (!res.ok) {
      const err = res.json?.error || window.t('Unable to generate SQL.');
      toast(err, 'danger');
      return;
    }
    const sql = (res.json?.sql || '').trim();
    setSqlPreview(sql);
    const warnings = res.json?.warnings || [];
    if (warnings.length) toast(warnings.join(' / '), 'info');
    else toast(window.t('SQL generated.'), 'success');
  });

  // Persist starter_sql on submit
  form.addEventListener('submit', () => {
    // Keep hidden db_tables synchronized
    const dbTables = getDbTables();
    elDbTablesHidden.value = dbTables.map((x) => x.table).join(',');
    if (elDbTablesJsonHidden) {
      elDbTablesJsonHidden.value = JSON.stringify(dbTables);
    }
    elStarterSqlHidden.value = (elSqlPreview.value || '').trim();
  });

  // Initialize
  (async function init(){
    populateFileFormatFilter();
    renderDbTableTags();
    renderDbSourceSelectionUI();
    applyFilesFilters();
    renderFilesSelectionUI();
    await ensureDbSchemas();
    await refreshCatalog();
  })();
})();
