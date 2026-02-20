/* global BI */
(function () {
  let _biModal = null;

  function ensureModal () {
    if (_biModal) return _biModal;
    const host = document.createElement('div');
    host.innerHTML = `
      <div class="modal fade" id="biExploreModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="biExploreModalTitle">Information</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body" id="biExploreModalBody"></div>
            <div class="modal-footer">
              <button type="button" class="btn btn-primary" data-bs-dismiss="modal">OK</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(host.firstElementChild);
    const el = document.getElementById('biExploreModal');
    _biModal = {
      title: document.getElementById('biExploreModalTitle'),
      body: document.getElementById('biExploreModalBody'),
      bs: new bootstrap.Modal(el)
    };
    return _biModal;
  }

  function uiAlert (message, title) {
    const m = ensureModal();
    m.title.textContent = title || 'Information';
    m.body.textContent = String(message || '');
    m.bs.show();
  }

  function getCsrfToken () {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  function qs (s) { return document.querySelector(s); }

  function parseParams () {
    const txt = qs('#ex-params')?.value || '';
    if (!txt.trim()) return {};
    try {
      const o = JSON.parse(txt);
      return (o && typeof o === 'object' && !Array.isArray(o)) ? o : null;
    } catch (e) {
      return null;
    }
  }

  function inferTypes (data) {
    const cols = data.columns || [];
    const rows = (data.rows || []).slice(0, 200);
    const out = cols.map((c, idx) => {
      let num = 0; let non = 0;
      for (const r of rows) {
        if (!r || idx >= r.length) continue;
        const v = r[idx];
        if (v === null || v === undefined || v === '') continue;
        non++;
        if (!isNaN(Number(v))) num++;
      }
      return { name: c, isNumber: non ? (num / non) >= 0.7 : false };
    });
    return out;
  }

  function fillSelect (sel, options, selected) {
    if (!sel) return;
    sel.innerHTML = '';
    for (const o of options) {
      const opt = document.createElement('option');
      opt.value = o;
      opt.textContent = o;
      if (selected && selected === o) opt.selected = true;
      sel.appendChild(opt);
    }
  }

  function cfgFromUi () {
    const type = qs('#ex-type')?.value || 'table';
    const dim = qs('#ex-dim')?.value || '';
    const met = qs('#ex-met')?.value || '';
    const aggFunc = qs('#ex-agg-func')?.value || '';
    const drill = qs('#ex-drill')?.value || '';
    const cfg = { type };
    if (type !== 'table' && type !== 'pivot') {
      if (dim) cfg.dim = dim;
      if (met) cfg.metric = met;
      if (aggFunc) cfg.agg = { func: aggFunc, metric: met, dim: dim };
      if (drill) cfg.drill_field = drill;
    }
    if (type === 'pivot') {
      cfg.pivot_rows = qs('#ex-pr')?.value || '';
      cfg.pivot_cols = qs('#ex-pc')?.value || '';
      cfg.pivot_val = qs('#ex-pv')?.value || '';
    }
    if (type === 'gauge') {
      if (met) cfg.metric = met;
    }
    return cfg;
  }

  function setStatus (msg) {
    const el = qs('#ex-status');
    if (el) el.textContent = msg || '';
  }

  function render (raw, filters) {
    const container = qs('#ex-viz');
    if (!container || !raw) return;
    if (!window.BI || !window.BI.renderViz) {
      container.innerHTML = '<p style="color: #999;">Carregando visualizador...</p>';
      return;
    }
    const data = (filters && filters.length) ? BI.applyFilters(raw, filters) : raw;
    const cfg = cfgFromUi();
    BI.renderViz(container, data, cfg, (drillField, value) => {
      if (!drillField) return;
      filters.push({ field: drillField, op: 'eq', value: value });
      render(raw, filters);
      renderFiltersSummary(filters);
    });
  }

  function renderFiltersSummary (filters) {
    const el = qs('#ex-filter-summary');
    if (!el) return;
    if (!filters.length) { el.innerHTML = '<span class="small-muted">' + window.t('Sem filtros.') + '</span>'; return; }
    el.innerHTML = filters.map((f, i) =>
      `<span class="badge text-bg-secondary me-1">${f.field} ${f.op} ${f.value} <a href="#" data-rm="${i}" class="link-light ms-1" style="text-decoration:none;">×</a></span>`
    ).join(' ');
    el.querySelectorAll('[data-rm]').forEach(a => {
      a.addEventListener('click', (e) => {
        e.preventDefault();
        const idx = Number(a.getAttribute('data-rm'));
        filters.splice(idx, 1);
        renderFiltersSummary(filters);
      });
    });
  }

  async function fetchData (questionId, params) {
    const resp = await fetch(`/app/api/questions/${questionId}/data`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...(getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {})
      },
      body: JSON.stringify({ params: params || {} })
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.error || 'Request failed');
    return data;
  }

  async function saveViz (questionId, cfg) {
    const resp = await fetch(`/app/api/questions/${questionId}/viz`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...(getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {})
      },
      body: JSON.stringify({ viz_config: cfg })
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.error || 'Request failed');
    return data;
  }

  async function addToDashboard (dashboardId, questionId, cfg) {
    const resp = await fetch(`/app/api/dashboards/${dashboardId}/cards`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...(getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {})
      },
      body: JSON.stringify({ question_id: questionId, viz_config: cfg })
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.error || 'Request failed');
    return data;
  }

  function boot () {
    const qSel = qs('#ex-question');
    if (!qSel) return;

    const dimSel = qs('#ex-dim');
    const metSel = qs('#ex-met');
    const drillSel = qs('#ex-drill');
    const pr = qs('#ex-pr'); const pc = qs('#ex-pc'); const pv = qs('#ex-pv');
    const typeSel = qs('#ex-type');
    const refreshBtn = qs('#ex-refresh');
    const saveBtn = qs('#ex-save');
    const dashSel = qs('#ex-dashboard');
    const addDashBtn = qs('#ex-add-dash');

    const filterField = qs('#ex-filter-field');
    const filterOp = qs('#ex-filter-op');
    const filterValue = qs('#ex-filter-value');
    const addFilterBtn = qs('#ex-add-filter');
    const clearFiltersBtn = qs('#ex-clear-filters');

    let raw = null;
    const filters = [];

    function fillColumns (data) {
      const inferred = inferTypes(data);
      const allCols = inferred.map(x => x.name);
      const dimCols = inferred.filter(x => !x.isNumber).map(x => x.name);
      const metCols = inferred.filter(x => x.isNumber).map(x => x.name);
      fillSelect(dimSel, allCols);
      fillSelect(drillSel, [''].concat(allCols));
      fillSelect(metSel, allCols);
      fillSelect(pr, allCols);
      fillSelect(pc, allCols);
      fillSelect(pv, allCols);
      fillSelect(filterField, allCols);

      // Pick defaults
      const d0 = dimCols[0] || allCols[0] || '';
      const m0 = metCols[0] || allCols[0] || '';
      if (dimSel && d0) dimSel.value = d0;
      if (metSel && m0) metSel.value = m0;
      if (pr && d0) pr.value = d0;
      if (pv && m0) pv.value = m0;
    }

    async function refresh () {
      const qid = Number(qSel.value || 0);
      if (!qid) return;
      const params = parseParams();
      if (params === null) {
        if (window.uiToast) window.uiToast(window.t('Parâmetros JSON inválidos.'), { variant: 'danger' });
        else uiAlert(window.t('Parâmetros JSON inválidos.'), window.t('Validation'));
        return;
      }
      setStatus(window.t('Carregando...'));
      try {
        // include aggregation info if present
        const cfg = cfgFromUi();
        const agg = cfg.agg || null;
        raw = await (async () => {
          const resp = await fetch(`/app/api/questions/${qid}/data`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
              'Content-Type': 'application/json',
              ...(getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {})
            },
            body: JSON.stringify({ params: params || {}, agg: agg })
          });
          const data = await resp.json().catch(() => ({}));
          if (!resp.ok) throw new Error(data.error || 'Request failed');
          return data;
        })();
        fillColumns(raw);
        filters.length = 0;
        renderFiltersSummary(filters);
        setStatus(window.t('OK'));
        // If dataset is empty, show a helpful message in the preview
        if (!raw || !raw.rows || raw.rows.length === 0) {
          const container = qs('#ex-viz');
          if (container) container.innerHTML = '<p class="small-muted">' + window.t('Sem linhas retornadas.') + '</p>';
        } else {
          console.debug('bi_explore: rendering preview', { columns: raw.columns && raw.columns.length, rows: raw.rows && raw.rows.length, cfg: cfgFromUi() });
          render(raw, filters);
        }
      } catch (e) {
        setStatus(window.t('Erro'));
        if (window.uiToast) window.uiToast(String(e.message || e), { variant: 'danger' });
        else uiAlert(String(e.message || e), window.t('Erreur'));
      }
    }

    function onTypeChange () {
      const pivotBox = qs('#ex-pivot-box');
      const type = typeSel.value;
      if (pivotBox) pivotBox.style.display = (type === 'pivot') ? '' : 'none';
      if (raw) render(raw, filters);
    }

    // Sync visual type picker buttons (if present)
    const vtBtns = Array.from(document.querySelectorAll('.viz-type-picker .vt-btn'));
    if (vtBtns.length) {
      const setActiveBtn = (type) => {
        vtBtns.forEach(b => {
          const t = b.getAttribute('data-type');
          const active = (t === type);
          b.classList.toggle('active', active);
          b.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
      };
      // initialize
      setActiveBtn(typeSel.value || 'table');
      vtBtns.forEach(b => {
        b.addEventListener('click', (e) => {
          const t = b.getAttribute('data-type');
          if (!t) return;
          if (typeSel) typeSel.value = t;
          setActiveBtn(t);
          // Log the action and force a redraw of the preview if data already loaded
          console.debug('viz-type-picker: clicked', t, { cfg: cfgFromUi() });
          try {
            if (raw) {
              // call onTypeChange which toggles pivot box and triggers render
              onTypeChange();
              // also ensure we explicitly re-render with current filters
              render(raw, filters);
            }
          } catch (err) {
            console.error('viz-type-picker: render error', err);
          }
        });
      });
    }

    qSel.addEventListener('change', refresh);
    if (refreshBtn) refreshBtn.addEventListener('click', refresh);
    if (typeSel) typeSel.addEventListener('change', onTypeChange);
    [dimSel, metSel, drillSel, pr, pc, pv].forEach(el => {
      if (el) el.addEventListener('change', () => { if (raw) render(raw, filters); });
    });

    if (addFilterBtn) addFilterBtn.addEventListener('click', () => {
      if (!raw) return;
      const f = filterField.value;
      const op = filterOp.value;
      const v = filterValue.value;
      if (!f || v === undefined || v === null || v === '') return;
      filters.push({ field: f, op: op, value: v });
      renderFiltersSummary(filters);
      render(raw, filters);
    });
    if (clearFiltersBtn) clearFiltersBtn.addEventListener('click', () => {
      filters.length = 0;
      renderFiltersSummary(filters);
      if (raw) render(raw, filters);
    });

    if (saveBtn) saveBtn.addEventListener('click', async () => {
      const qid = Number(qSel.value || 0);
      if (!qid) return;
      try {
        await saveViz(qid, cfgFromUi());
        if (window.uiToast) window.uiToast(window.t('Visualização salva.'), { variant: 'success' });
        else uiAlert(window.t('Visualização salva.'), window.t('Succès'));
      } catch (e) {
        if (window.uiToast) window.uiToast(String(e.message || e), { variant: 'danger' });
        else uiAlert(String(e.message || e), window.t('Erreur'));
      }
    });

    if (addDashBtn) addDashBtn.addEventListener('click', async () => {
      const qid = Number(qSel.value || 0);
      const did = Number(dashSel?.value || 0);
      if (!qid || !did) return;
      try {
        await addToDashboard(did, qid, cfgFromUi());
        if (window.uiToast) window.uiToast(window.t('Card adicionado ao dashboard.'), { variant: 'success' });
        else uiAlert(window.t('Card adicionado ao dashboard.'), window.t('Succès'));
      } catch (e) {
        if (window.uiToast) window.uiToast(String(e.message || e), { variant: 'danger' });
        else uiAlert(String(e.message || e), window.t('Erreur'));
      }
    });

    onTypeChange();

    // Auto-select and load first question if available
    if (qSel && qSel.options.length > 1) {
      const firstOptionWithValue = Array.from(qSel.options).find((opt, idx) => idx > 0 && opt.value);
      if (firstOptionWithValue) {
        qSel.value = firstOptionWithValue.value;
        refresh();
      }
    }
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
