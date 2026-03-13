/* global GridStack, echarts */

(function () {
  let _biModal = null;
  const t = (window.t ? window.t : (s) => s);

  function ensureModal () {
    if (_biModal) return _biModal;
    const host = document.createElement('div');
    host.innerHTML = `
      <div class="modal fade" id="biUiModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="biUiModalTitle">${t('Information')}</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="${t('Fechar')}"></button>
            </div>
            <div class="modal-body" id="biUiModalBody"></div>
            <div class="modal-footer" id="biUiModalFooter"></div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(host.firstElementChild);
    const el = document.getElementById('biUiModal');
    _biModal = {
      el,
      title: document.getElementById('biUiModalTitle'),
      body: document.getElementById('biUiModalBody'),
      footer: document.getElementById('biUiModalFooter'),
      bs: new bootstrap.Modal(el)
    };
    return _biModal;
  }

  function uiAlert (message, title) {
    const m = ensureModal();
    m.title.textContent = title || t('Information');
    m.body.textContent = String(message || '');
    m.footer.innerHTML = `<button type="button" class="btn btn-primary" data-bs-dismiss="modal">${t('OK')}</button>`;
    m.bs.show();
  }

  function uiConfirm (message, title) {
    const m = ensureModal();
    m.title.textContent = title || t('Confirmation');
    m.body.textContent = String(message || '');
    m.footer.innerHTML = `
      <button type="button" class="btn btn-outline-secondary" data-ui-no>${t('Cancel')}</button>
      <button type="button" class="btn btn-primary" data-ui-yes>${t('Confirm')}</button>
    `;
    return new Promise(resolve => {
      const yes = m.footer.querySelector('[data-ui-yes]');
      const no = m.footer.querySelector('[data-ui-no]');
      let settled = false;
      const done = (v) => {
        if (settled) return;
        settled = true;
        resolve(v);
      };
      yes?.addEventListener('click', () => { m.bs.hide(); done(true); }, { once: true });
      no?.addEventListener('click', () => { m.bs.hide(); done(false); }, { once: true });
      m.el.addEventListener('hidden.bs.modal', () => done(false), { once: true });
      m.bs.show();
    });
  }

  function getCsrfToken () {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  function show (el) { if (el) el.classList.remove('d-none'); }
  function hide (el) { if (el) el.classList.add('d-none'); }

  function hydrateGridItems () {
    const grid = document.getElementById('dash-grid');
    const tpl = document.getElementById('dash-cards-template');
    if (!grid || !tpl) return;
    // Only hydrate once
    if (grid.children.length) return;
    const frag = tpl.content.cloneNode(true);
    grid.appendChild(frag);
    // After hydration, boot the visualization renderer
    if (window.BI && window.BI.bootDashboard) {
      setTimeout(() => window.BI.bootDashboard(), 50);
    }
  }

  function resizeVizIn (cardEl) {
    // For ECharts: resize without re-render if possible.
    const viz = cardEl?.querySelector('.bi-viz');
    if (!viz) return;
    try {
      const inst = (typeof echarts !== 'undefined') ? echarts.getInstanceByDom(viz) : null;
      if (inst) inst.resize();
    } catch (e) {}
  }

  function inferTypes (data) {
    const cols = (data && data.columns) ? data.columns : [];
    const rows = ((data && data.rows) ? data.rows : []).slice(0, 200);
    return cols.map((c, idx) => {
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
  }

  async function apiAddCard (dashboardId, questionId, params, vizType, vizOptions, sourceKind, ratioRef) {
  const statusEl = document.getElementById('addcard-status');
  if (statusEl) statusEl.textContent = window.t('Criando card...');
  const mode = String(sourceKind || 'question').toLowerCase() === 'ratio' ? 'ratio' : 'question';

  if (mode === 'ratio') {
    const type = ['kpi', 'gauge'].includes(String(vizType || '').toLowerCase()) ? String(vizType || '').toLowerCase() : 'gauge';
    const vizConfig = {
      type,
      metric: 'value',
      source_kind: 'ratio',
      ratio_ref: String(ratioRef || '').trim()
    };
    const resp = await fetch(`/app/api/dashboards/${dashboardId}/cards`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...(getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {})
      },
      body: JSON.stringify({ source_kind: 'ratio', ratio_ref: ratioRef, question_id: 0, viz_config: vizConfig })
    });
    const out = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(out.error || t('Falha na requisição.'));
    if (statusEl) statusEl.textContent = window.t('Card criado. Recarregando...');
    window.location.reload();
    return;
  }

  // Optional: fetch sample data to infer dim/metric for charts
  let vizConfig = { type: vizType || 'table' };
  const opts = (vizOptions && typeof vizOptions === 'object') ? vizOptions : {};
  const preferredDim = String(opts.dim || '').trim();
  const preferredMetric = String(opts.metric || '').trim();
  let preferredAgg = String(opts.aggFunc || '').trim().toUpperCase();
  if (!['COUNT_ROWS', 'SUM', 'AVG', 'COUNT', 'MIN', 'MAX', 'STDDEV'].includes(preferredAgg)) preferredAgg = '';
  let detectedDim = preferredDim;
  let detectedMetric = preferredMetric;
  try {
    if (vizType && vizType !== 'table' && vizType !== 'pivot' && vizType !== 'text') {
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
      if (resp.ok && data && data.columns && data.rows) {
        const cols = data.columns || [];
        const inferred = inferTypes(data);
        const autoDim = inferred.find(x => !x.isNumber)?.name || cols[0] || '';
        const autoMet = inferred.find(x => x.isNumber)?.name || cols[0] || '';
        detectedDim = detectedDim || autoDim;
        detectedMetric = detectedMetric || autoMet;
      }
    }
  } catch (e) {}

  if (detectedDim) vizConfig.dim = detectedDim;
  if (detectedMetric) vizConfig.metric = detectedMetric;

  const needsAgg = ['bar', 'line', 'area', 'pie', 'scatter', 'gauge', 'kpi'].includes(vizType);
  if (vizType === 'kpi' && !preferredAgg) preferredAgg = detectedMetric ? 'SUM' : 'COUNT_ROWS';
  if (needsAgg && preferredAgg && (detectedMetric || preferredAgg === 'COUNT_ROWS')) {
    vizConfig.agg = {
      func: preferredAgg,
      metric: detectedMetric || '',
      dim: detectedDim || ''
    };
  }

  const resp2 = await fetch(`/app/api/dashboards/${dashboardId}/cards`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...(getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {})
    },
    body: JSON.stringify({ question_id: questionId, viz_config: vizConfig })
  });
  const out = await resp2.json().catch(() => ({}));
  if (!resp2.ok) throw new Error(out.error || t('Falha na requisição.'));
  if (statusEl) statusEl.textContent = window.t('Card criado. Recarregando...');
  // simplest: reload to render server-side with data + cfg
  window.location.reload();
}

async function apiDeleteCard (dashboardId, cardId) {
  const resp = await fetch(`/app/api/dashboards/${dashboardId}/cards/${cardId}`, {
    method: 'DELETE',
    credentials: 'same-origin',
    headers: { ...(getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {}) }
  });
  const out = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(out.error || t('Falha na requisição.'));
  return out;
}

function boot () {
    const gridEl = document.getElementById('dash-grid');
    if (!gridEl || typeof GridStack === 'undefined') return;

    hydrateGridItems();

    const dashboardId = Number(gridEl.getAttribute('data-dashboard-id') || 0);
    window.BI_DASHBOARD_FILTERS_KEY = dashboardId ? `bi.dashboard.${dashboardId}.filters` : 'bi.dashboard.filters';

    const grid = GridStack.init({
      float: true,
      margin: 10,
      cellHeight: 80,
      disableOneColumnMode: false,
      resizable: { handles: 'all' },
      draggable: { handle: '.card-head' }
    }, gridEl);

    // View mode by default
    grid.disable();

    const btnEdit = document.getElementById('layout-edit');
    const btnSave = document.getElementById('layout-save');
    const btnCancel = document.getElementById('layout-cancel');
    const btnAdd = document.getElementById('layout-add-card');

    function initFloatingFiltersPanel () {
      const panel = document.getElementById('bi-floating-filters');
      if (!panel) return;

      const head = document.getElementById('bi-floating-filters-head');
      const toggleBtn = document.getElementById('bi-floating-filters-toggle');
      const collapseBtn = document.getElementById('bi-floating-filters-collapse');
      const dockBtn = document.getElementById('bi-floating-filters-dock');
      const keyCollapsed = 'bi.filters.collapsed';

      function setCollapsed (on) {
        panel.classList.toggle('is-collapsed', !!on);
        try { localStorage.setItem(keyCollapsed, on ? '1' : '0'); } catch (e) {}
        if (collapseBtn) {
          const icon = collapseBtn.querySelector('i');
          if (icon) icon.className = on ? 'bi bi-chevron-up' : 'bi bi-chevron-down';
        }
      }

      function toggleVisible () {
        panel.style.display = panel.style.display === 'none' ? '' : 'none';
      }

      function dockDefault () {
        panel.style.left = '';
        panel.style.top = '';
        panel.style.right = '18px';
      }

      if (toggleBtn && !toggleBtn._biBound) {
        toggleBtn._biBound = true;
        toggleBtn.addEventListener('click', (e) => {
          e.preventDefault();
          toggleVisible();
        });
      }
      if (collapseBtn && !collapseBtn._biBound) {
        collapseBtn._biBound = true;
        collapseBtn.addEventListener('click', (e) => {
          e.preventDefault();
          setCollapsed(!panel.classList.contains('is-collapsed'));
        });
      }
      if (dockBtn && !dockBtn._biBound) {
        dockBtn._biBound = true;
        dockBtn.addEventListener('click', (e) => {
          e.preventDefault();
          dockDefault();
        });
      }

      try {
        setCollapsed(localStorage.getItem(keyCollapsed) === '1');
      } catch (e) {
        setCollapsed(false);
      }

      if (!head) return;

      let dragging = false;
      let startX = 0;
      let startY = 0;
      let origLeft = 0;
      let origTop = 0;

      function onMove (clientX, clientY) {
        if (!dragging) return;
        const dx = clientX - startX;
        const dy = clientY - startY;
        const w = panel.offsetWidth || 320;
        const h = panel.offsetHeight || 180;
        const maxLeft = Math.max(8, window.innerWidth - w - 8);
        const maxTop = Math.max(8, window.innerHeight - h - 8);
        let nextLeft = origLeft + dx;
        let nextTop = origTop + dy;
        nextLeft = Math.max(8, Math.min(maxLeft, nextLeft));
        nextTop = Math.max(8, Math.min(maxTop, nextTop));
        panel.style.left = `${nextLeft}px`;
        panel.style.top = `${nextTop}px`;
        panel.style.right = 'auto';
      }

      function stopDrag () {
        dragging = false;
        document.body.classList.remove('user-select-none');
      }

      if (!head._biBound) {
        head._biBound = true;
        head.addEventListener('mousedown', (e) => {
          if (window.matchMedia('(max-width: 991.98px)').matches) return;
          if (e.button !== 0) return;
          if (e.target && e.target.closest('button,input,select,textarea,a,label')) return;
          const rect = panel.getBoundingClientRect();
          dragging = true;
          startX = e.clientX;
          startY = e.clientY;
          origLeft = rect.left;
          origTop = rect.top;
          document.body.classList.add('user-select-none');
          e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => onMove(e.clientX, e.clientY));
        document.addEventListener('mouseup', stopDrag);
      }
    }

    initFloatingFiltersPanel();

    function setEditMode (on) {
      if (on) {
        grid.enable();
        document.querySelectorAll('[data-card-remove="1"]').forEach(x => x.classList.remove('d-none'));
        hide(btnEdit);
        show(btnSave);
        show(btnCancel);
        show(btnAdd);
      } else {
        grid.disable();
        document.querySelectorAll('[data-card-remove="1"]').forEach(x => x.classList.add('d-none'));
        show(btnEdit);
        hide(btnSave);
        hide(btnCancel);
        hide(btnAdd);
      }
    }

    if (btnEdit) {
      btnEdit.addEventListener('click', () => setEditMode(true));
    }
    if (btnCancel) {
      btnCancel.addEventListener('click', () => window.location.reload());
    }

    if (btnSave) {
      btnSave.addEventListener('click', async () => {
        if (!dashboardId) return;
        const nodes = grid.engine?.nodes || [];
        const payload = nodes.map(n => {
          const el = n.el;
          const cardId = Number(el?.getAttribute('data-card-id') || 0);
          return { card_id: cardId, x: n.x, y: n.y, w: n.w, h: n.h };
        }).filter(x => x.card_id);

        const resp = await fetch(`/app/api/dashboards/${dashboardId}/layout`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            ...(getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {})
          },
          body: JSON.stringify({ items: payload })
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          if (window.uiToast) window.uiToast((data && data.error) ? data.error : t('Falha ao salvar layout.'), { variant: 'danger' });
          else uiAlert((data && data.error) ? data.error : t('Falha ao salvar layout.'), t('Erro'));
          return;
        }
        if (window.uiToast) window.uiToast(t('Layout salvo.'), { variant: 'success' });
        else uiAlert(t('Layout salvo.'), t('Sucesso'));
        setEditMode(false);
      });
    }

// Add-card builder (offcanvas)
const sourceSel = document.getElementById('addcard-source');
const qSel = document.getElementById('addcard-question');
const qSearch = document.getElementById('addcard-search');
const qSearchWrap = document.getElementById('addcard-search-wrap');
const qWrap = document.getElementById('addcard-question-wrap');
const ratioSel = document.getElementById('addcard-ratio');
const ratioSearch = document.getElementById('addcard-ratio-search');
const ratioSearchWrap = document.getElementById('addcard-ratio-search-wrap');
const ratioWrap = document.getElementById('addcard-ratio-wrap');
const typeSel = document.getElementById('addcard-type');
const dimSel = document.getElementById('addcard-dim');
const metSel = document.getElementById('addcard-met');
const aggSel = document.getElementById('addcard-agg');
const dimWrap = document.getElementById('addcard-dim-wrap');
const metWrap = document.getElementById('addcard-met-wrap');
const aggWrap = document.getElementById('addcard-agg-wrap');
const paramsEl = document.getElementById('addcard-params');
const paramsWrap = document.getElementById('addcard-params-wrap');
const createBtn = document.getElementById('addcard-create');

function currentSourceKind () {
  return String(sourceSel?.value || 'question').toLowerCase() === 'ratio' ? 'ratio' : 'question';
}

function parseParamsInput () {
  if (!paramsEl || !paramsEl.value.trim()) return {};
  return JSON.parse(paramsEl.value);
}

function fillSelect (el, values) {
  if (!el) return;
  const current = el.value || '';
  el.innerHTML = `<option value="">${t('Auto')}</option>`;
  for (const v of values || []) {
    const opt = document.createElement('option');
    opt.value = String(v);
    opt.textContent = String(v);
    el.appendChild(opt);
  }
  if (current) {
    el.value = current;
    if (el.value !== current) el.value = '';
  }
}

function updateFieldVisibility () {
  const sourceKind = currentSourceKind();
  const isQuestion = sourceKind === 'question';
  const isRatio = sourceKind === 'ratio';
  const type = typeSel ? typeSel.value : 'table';
  if (qSearchWrap) qSearchWrap.style.display = isQuestion ? '' : 'none';
  if (qWrap) qWrap.style.display = isQuestion ? '' : 'none';
  if (ratioSearchWrap) ratioSearchWrap.style.display = isRatio ? '' : 'none';
  if (ratioWrap) ratioWrap.style.display = isRatio ? '' : 'none';

  if (isRatio && typeSel && !['kpi', 'gauge'].includes(type)) {
    typeSel.value = 'gauge';
  }

  const showDim = isQuestion && type !== 'table' && type !== 'pivot' && type !== 'gauge' && type !== 'kpi';
  const showMet = isQuestion && type !== 'table' && type !== 'pivot';
  const showAgg = isQuestion && ['bar', 'line', 'area', 'pie', 'scatter', 'gauge', 'kpi'].includes(type);
  if (dimWrap) dimWrap.style.display = showDim ? '' : 'none';
  if (metWrap) metWrap.style.display = showMet ? '' : 'none';
  if (aggWrap) aggWrap.style.display = showAgg ? '' : 'none';
  if (paramsWrap) paramsWrap.style.display = isQuestion ? '' : 'none';
}

async function loadQuestionFields () {
  if (currentSourceKind() !== 'question') return;
  const qid = Number(qSel?.value || 0);
  if (!qid) {
    fillSelect(dimSel, []);
    fillSelect(metSel, []);
    return;
  }
  const statusEl = document.getElementById('addcard-status');
  try {
    const params = parseParamsInput();
    if (statusEl) statusEl.textContent = t('Carregando campos...');
    const resp = await fetch(`/app/api/questions/${qid}/data`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...(getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {})
      },
      body: JSON.stringify({ params: params || {} })
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.error || t('Falha na requisição.'));
    const inferred = inferTypes(data);
    const cols = inferred.map(x => x.name);
    const numericCols = inferred.filter(x => x.isNumber).map(x => x.name);
    fillSelect(dimSel, cols);
    fillSelect(metSel, cols);
    if (numericCols.length && metSel && !metSel.value) metSel.value = numericCols[0];
    if (statusEl) statusEl.textContent = t('Campos atualizados.');
  } catch (e) {
    if (statusEl) statusEl.textContent = String(e.message || e || '');
  }
}

function filterQuestions () {
  if (!qSel || !qSearch) return;
  const term = (qSearch.value || '').toLowerCase();
  Array.from(qSel.options).forEach((opt, idx) => {
    if (idx === 0) return;
    const showOpt = opt.textContent.toLowerCase().includes(term);
    opt.hidden = !showOpt;
  });
}

function filterRatios () {
  if (!ratioSel || !ratioSearch) return;
  const term = (ratioSearch.value || '').toLowerCase();
  Array.from(ratioSel.options).forEach((opt, idx) => {
    if (idx === 0) return;
    const showOpt = opt.textContent.toLowerCase().includes(term);
    opt.hidden = !showOpt;
  });
}
if (qSearch) qSearch.addEventListener('input', filterQuestions);
if (ratioSearch) ratioSearch.addEventListener('input', filterRatios);
if (qSel) qSel.addEventListener('change', loadQuestionFields);
if (typeSel) typeSel.addEventListener('change', updateFieldVisibility);
if (sourceSel) sourceSel.addEventListener('change', () => {
  updateFieldVisibility();
  if (currentSourceKind() === 'question') loadQuestionFields();
});

if (paramsEl) {
  let _paramsTimer = null;
  paramsEl.addEventListener('input', () => {
    if (_paramsTimer) clearTimeout(_paramsTimer);
    _paramsTimer = setTimeout(() => {
      loadQuestionFields();
    }, 500);
  });
}

updateFieldVisibility();

if (createBtn) {
  createBtn.addEventListener('click', async () => {
    const sourceKind = currentSourceKind();
    let qid = 0;
    let params = {};
    let ratioRef = '';

    if (sourceKind === 'question') {
      qid = Number(qSel?.value || 0);
      if (!qid) {
        if (window.uiToast) window.uiToast(t('Selecione uma pergunta.'), { variant: 'danger' }); else uiAlert(t('Selecione uma pergunta.'), t('Validação'));
        return;
      }
      try {
        params = parseParamsInput();
      } catch (e) {
        if (window.uiToast) window.uiToast(t('Parâmetros JSON inválidos.'), { variant: 'danger' }); else uiAlert(t('Parâmetros JSON inválidos.'), t('Validação'));
        return;
      }
    } else {
      ratioRef = String(ratioSel?.value || '').trim();
      if (!ratioRef) {
        if (window.uiToast) window.uiToast(t('Selecione um ratio BI.'), { variant: 'danger' }); else uiAlert(t('Selecione um ratio BI.'), t('Validação'));
        return;
      }
    }

    const vizType = typeSel?.value || 'table';
    if (sourceKind === 'ratio' && !['kpi', 'gauge'].includes(vizType)) {
      if (window.uiToast) window.uiToast(t('Para ratio, selecione KPI ou Gauge.'), { variant: 'danger' }); else uiAlert(t('Para ratio, selecione KPI ou Gauge.'), t('Validação'));
      return;
    }
    const vizOptions = {
      dim: dimSel?.value || '',
      metric: metSel?.value || '',
      aggFunc: aggSel?.value || ''
    };
    try {
      await apiAddCard(dashboardId, qid, params, vizType, vizOptions, sourceKind, ratioRef);
    } catch (e) {
      if (window.uiToast) window.uiToast(String(e.message || e), { variant: 'danger' }); else uiAlert(String(e.message || e), t('Erro'));
    }
  });
}

// Delete cards (only visible in edit mode)
document.querySelectorAll('[data-card-remove="1"]').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    const item = btn.closest('.grid-stack-item');
    const cardId = Number(item?.getAttribute('data-card-id') || 0);
    if (!cardId) return;
    const ok = await uiConfirm(t('Remover card?'), t('Confirmação'));
    if (!ok) return;
    try {
      await apiDeleteCard(dashboardId, cardId);
      if (item) grid.removeWidget(item);
    } catch (err) {
      if (window.uiToast) window.uiToast(String(err.message || err), { variant: 'danger' }); else uiAlert(String(err.message || err), t('Erro'));
    }
  });
});

    // Resize charts on resize events
    grid.on('resizestop', (_event, el) => {
      resizeVizIn(el);
    });
    grid.on('dragstop', (_event, el) => {
      // no-op
    });

    // Also resize charts once after layout
    setTimeout(() => {
      Array.from(gridEl.querySelectorAll('[data-bi-card="1"]')).forEach(resizeVizIn);
    }, 250);
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
