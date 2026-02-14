// Workspace Builder: quick join builder + autocomplete + AI draft

(function(){
  const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  const form = document.getElementById('ws-form');
  if (!form) return;

  const elDbSource = document.getElementById('ws-db-source');
  const elPickDbTables = document.getElementById('ws-pick-db-tables');
  const elDbTablesHidden = document.getElementById('ws-db-tables');
  const elDbTableTags = document.getElementById('ws-db-table-tags');
  const elStarterSqlHidden = document.getElementById('ws-starter-sql');

  const elFileFilter = document.getElementById('ws-file-filter');
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
    dbSourceId: null,
    dbSchema: null, // { tables: {nameLower: {name, columns:[...]}} }
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
    return state.selectedDbTables.slice();
  }

  function setDbTables(tables){
    const clean = (tables || []).map(x => String(x||'').trim()).filter(Boolean);
    state.selectedDbTables = Array.from(new Set(clean)).slice(0, 200);
    elDbTablesHidden.value = state.selectedDbTables.join(',');
    renderDbTableTags();
    refreshCatalog();
  }

  function renderDbTableTags(){
    if (!elDbTableTags) return;
    elDbTableTags.innerHTML = '';
    state.selectedDbTables.forEach((tname) => {
      const span = document.createElement('span');
      span.className = 'ws-tag';
      span.innerHTML = `<span class="ws-mono">db.${escapeHtml(sanitizeTableName(tname))}</span>`;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.innerHTML = '<i class="bi bi-x"></i>';
      btn.title = window.t('Remover');
      btn.onclick = () => setDbTables(state.selectedDbTables.filter(x => x !== tname));
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

  // -----------------------------
  // DB schema loading + modal
  // -----------------------------

  async function ensureDbSchema(){
    const id = (elDbSource && elDbSource.value) ? parseInt(elDbSource.value, 10) : 0;
    state.dbSourceId = id || null;
    state.dbSchema = null;
    if (!id) return null;
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
      state.dbSchema = { tables };
      return state.dbSchema;
    } catch (e) {
      toast(window.t('Erro ao carregar.'), 'danger');
      return null;
    }
  }

  function openDbTablesModal(){
    const id = (elDbSource && elDbSource.value) ? elDbSource.value : '';
    if (!id) {
      toast(window.t('Selecione uma fonte de banco para listar tabelas.'), 'info');
      return;
    }
    dbModal?.show();
    renderDbTablesList();
  }

  async function renderDbTablesList(){
    if (!elDbTableList) return;
    elDbTableList.innerHTML = `<div class="text-secondary small">${escapeHtml(window.t('Carregando...'))}</div>`;
    const schema = state.dbSchema || await ensureDbSchema();
    if (!schema) {
      elDbTableList.innerHTML = `<div class="text-secondary small">${escapeHtml(window.t('Erro ao carregar.'))}</div>`;
      return;
    }
    const term = String(elDbTableSearch?.value || '').trim().toLowerCase();
    const all = Object.values(schema.tables)
      .map(x => x.name)
      .sort((a,b) => a.localeCompare(b));
    const filtered = term ? all.filter(n => n.toLowerCase().includes(term)) : all;
    if (!filtered.length) {
      elDbTableList.innerHTML = `<div class="text-secondary small">${escapeHtml(window.t('Nenhuma tabela encontrada.'))}</div>`;
      return;
    }

    elDbTableList.innerHTML = '';
    filtered.slice(0, 400).forEach(name => {
      const id = 'tbl_' + name.replace(/[^A-Za-z0-9_]/g,'_');
      const item = document.createElement('label');
      item.className = 'list-group-item d-flex align-items-start gap-2';
      const checked = state.selectedDbTables.includes(name);
      item.innerHTML = `
        <input class="form-check-input mt-1" type="checkbox" id="${escapeHtml(id)}" ${checked ? 'checked' : ''} data-db-table="${escapeHtml(name)}">
        <div class="flex-grow-1">
          <div class="fw-semibold ws-mono">db.${escapeHtml(sanitizeTableName(name))}</div>
          <div class="text-secondary small">${escapeHtml((state.dbSchema.tables[name.toLowerCase()]?.columns || []).slice(0, 8).join(', '))}${(state.dbSchema.tables[name.toLowerCase()]?.columns || []).length > 8 ? '…' : ''}</div>
        </div>
      `;
      elDbTableList.appendChild(item);
    });
  }

  function applyDbTablesFromModal(){
    const checks = elDbTableList?.querySelectorAll('input[data-db-table]') || [];
    const selected = [];
    checks.forEach(chk => {
      if (chk.checked) selected.push(chk.getAttribute('data-db-table'));
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
      `).join('') || `<div class="text-secondary">${escapeHtml(window.t('Nenhuma tabela encontrada.'))}</div>`;
      const tr = filesTable?.querySelector(`tr[data-file-id="${fileId}"]`);
      const fileName = tr?.getAttribute('data-file-name') || ('#' + fileId);
      elSchemaTitle.textContent = window.tf('Schema: {name}', { name: fileName });
      elSchemaBody.innerHTML = rows;
      schemaModal?.show();
    } catch (e) {
      toast(window.t('Falha ao carregar schema.'), 'danger');
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
      const schema = state.dbSchema || await ensureDbSchema();
      dbTables.forEach(tn => {
        const safe = sanitizeTableName(tn);
        const cols = (schema?.tables?.[tn.toLowerCase()]?.columns || []);
        out.tables.push({ ref: 'db.' + safe, kind: 'db', name: safe, cols });
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
      opt.textContent = '(' + window.t('Selecione arquivos/tabelas') + ')';
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
      tdTable.innerHTML = `<select class="form-select form-select-sm ws-join-right"><option value="">(${escapeHtml(window.t('Tabela'))})</option>${opts}</select>`;
      tdTable.querySelector('select').value = j.right || '';

      // left col
      const tdLeft = document.createElement('td');
      tdLeft.innerHTML = `<input class="form-control form-control-sm ws-join-left" placeholder="${escapeHtml(window.t('Coluna'))}" />`;
      tdLeft.querySelector('input').value = j.leftCol || '';

      // right col
      const tdRight = document.createElement('td');
      tdRight.innerHTML = `<input class="form-control form-control-sm ws-join-rightcol" placeholder="${escapeHtml(window.t('Coluna'))}" />`;
      tdRight.querySelector('input').value = j.rightCol || '';

      // remove
      const tdRm = document.createElement('td');
      tdRm.className = 'text-end';
      tdRm.innerHTML = `<button class="btn btn-outline-danger btn-sm" type="button" title="${escapeHtml(window.t('Remover'))}"><i class="bi bi-trash"></i></button>`;

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
      elSuggestions.innerHTML = `<div class="text-secondary small">${escapeHtml(window.t('Nenhuma sugestão disponível.'))}</div>`;
      return;
    }
    sugs.forEach((s) => {
      const item = document.createElement('div');
      item.className = 'list-group-item d-flex align-items-center justify-content-between gap-2';
      const text = `<div class="small"><span class="ws-mono">${escapeHtml(s.left)}</span> ↔ <span class="ws-mono">${escapeHtml(s.right)}</span><br><span class="text-secondary ws-mono">${escapeHtml(s.leftCol)} = ${escapeHtml(s.rightCol)}</span></div>`;
      item.innerHTML = `${text}<button class="btn btn-outline-primary btn-sm" type="button">${escapeHtml(window.t('Aplicar'))}</button>`;
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
    await ensureDbSchema();
    openDbTablesModal();
  });

  if (elDbTableSearch) elDbTableSearch.addEventListener('input', renderDbTablesList);
  if (elDbTableApply) elDbTableApply.addEventListener('click', applyDbTablesFromModal);

  if (elDbSource) elDbSource.addEventListener('change', async () => {
    // reset tables when changing source
    state.selectedDbTables = [];
    elDbTablesHidden.value = '';
    renderDbTableTags();
    await ensureDbSchema();
    refreshCatalog();
  });

  // File filter
  if (elFileFilter && filesTable) {
    elFileFilter.addEventListener('input', () => {
      const term = String(elFileFilter.value || '').trim().toLowerCase();
      filesTable.querySelectorAll('tbody tr[data-file-row="1"]').forEach(tr => {
        const name = (tr.getAttribute('data-file-name') || '').toLowerCase();
        tr.style.display = (!term || name.includes(term)) ? '' : 'none';
      });
    });
  }

  // File selection changes
  if (filesTable) {
    filesTable.addEventListener('change', (e) => {
      if (e.target.classList.contains('ws-file-check')) refreshCatalog();
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
      toast(window.t('Selecione pelo menos duas tabelas para sugerir joins.'), 'info');
      return;
    }
    const tables = allTablesForSelect(catalog).filter(t => t !== elBaseTable.value);
    state.joins.push(newJoinRow({ right: tables[0] || '' }));
    refreshCatalog();
  });

  if (elGenerateSql) elGenerateSql.addEventListener('click', () => {
    const sql = buildSql();
    setSqlPreview(sql);
    toast(window.t('SQL gerado.'), 'success');
  });

  if (elAiSql) elAiSql.addEventListener('click', async () => {
    const prompt = String(elAiPrompt.value || '').trim();
    if (!prompt) {
      toast(window.t('Descreva sua análise.'), 'info');
      return;
    }
    const files = getSelectedFiles();
    const dbSourceId = (elDbSource && elDbSource.value) ? parseInt(elDbSource.value, 10) : 0;
    const dbTables = getDbTables();

    const payload = {
      prompt,
      db_source_id: dbSourceId || null,
      db_tables: dbTables,
      files: files.map(x => ({ file_id: x.file_id, table: x.table })),
      max_rows: getMaxRows(),
    };

    toast(window.t('Carregando...'), 'info');
    const res = await postJSON(apiUrl('/api/workspaces/draft_sql'), payload);
    if (!res.ok) {
      const err = res.json?.error || window.t('Falha ao gerar SQL.');
      toast(err, 'danger');
      return;
    }
    const sql = (res.json?.sql || '').trim();
    setSqlPreview(sql);
    const warnings = res.json?.warnings || [];
    if (warnings.length) toast(warnings.join(' / '), 'info');
    else toast(window.t('SQL gerado.'), 'success');
  });

  // Persist starter_sql on submit
  form.addEventListener('submit', () => {
    // Keep hidden db_tables synchronized
    elDbTablesHidden.value = getDbTables().join(',');
    elStarterSqlHidden.value = (elSqlPreview.value || '').trim();
  });

  // Initialize
  (async function init(){
    renderDbTableTags();
    await ensureDbSchema();
    await refreshCatalog();
  })();
})();
