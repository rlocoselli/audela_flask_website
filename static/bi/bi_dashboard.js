/* global GridStack, echarts */

(function () {
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
  }

  function resizeVizIn (cardEl) {
    // For ECharts: resize without re-render if possible.
    const viz = cardEl?.querySelector?.('.bi-viz');
    if (!viz) return;
    try {
      const inst = (typeof echarts !== 'undefined') ? echarts.getInstanceByDom(viz) : null;
      if (inst) inst.resize();
    } catch (e) {}
  }

  async function apiAddCard (dashboardId, questionId, params, vizType) {
  const statusEl = document.getElementById('addcard-status');
  if (statusEl) statusEl.textContent = window.t('Criando card...');
  // Optional: fetch sample data to infer dim/metric for charts
  let vizConfig = { type: vizType || 'table' };
  try {
    if (vizType && vizType !== 'table' && vizType !== 'pivot') {
      const resp = await fetch(`/app/api/questions/${questionId}/data`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ params: params || {} })
      });
      const data = await resp.json().catch(() => ({}));
      if (resp.ok && data && data.columns && data.rows) {
        const cols = data.columns;
        const rows = (data.rows || []).slice(0, 200);
        const inferred = cols.map((c, idx) => {
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
        const dim = inferred.find(x => !x.isNumber)?.name || cols[0];
        const met = inferred.find(x => x.isNumber)?.name || cols[0];
        if (dim) vizConfig.dimension = dim;
        if (met) vizConfig.metric = met;
      }
    }
  } catch (e) {}

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
  if (!resp2.ok) throw new Error(out.error || 'Request failed');
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
  if (!resp.ok) throw new Error(out.error || 'Request failed');
  return out;
}

function boot () {
    const gridEl = document.getElementById('dash-grid');
    if (!gridEl || typeof GridStack === 'undefined') return;

    hydrateGridItems();

    const dashboardId = Number(gridEl.getAttribute('data-dashboard-id') || 0);

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
          alert((data && data.error) ? data.error : window.t('Falha ao salvar layout.'));
          return;
        }
        alert(window.t('Layout salvo.'));
        setEditMode(false);
      });
    }

// Add-card builder (offcanvas)
const qSel = document.getElementById('addcard-question');
const qSearch = document.getElementById('addcard-search');
const typeSel = document.getElementById('addcard-type');
const paramsEl = document.getElementById('addcard-params');
const createBtn = document.getElementById('addcard-create');

function filterQuestions () {
  if (!qSel || !qSearch) return;
  const term = (qSearch.value || '').toLowerCase();
  Array.from(qSel.options).forEach((opt, idx) => {
    if (idx === 0) return;
    const showOpt = opt.textContent.toLowerCase().includes(term);
    opt.hidden = !showOpt;
  });
}
if (qSearch) qSearch.addEventListener('input', filterQuestions);

if (createBtn) {
  createBtn.addEventListener('click', async () => {
    const qid = Number(qSel?.value || 0);
    if (!qid) { alert(window.t('Selecione uma pergunta.')); return; }
    let params = {};
    if (paramsEl && paramsEl.value.trim()) {
      try { params = JSON.parse(paramsEl.value); } catch (e) { alert(window.t('Parâmetros JSON inválidos.')); return; }
    }
    const vizType = typeSel?.value || 'table';
    try {
      await apiAddCard(dashboardId, qid, params, vizType);
    } catch (e) {
      alert(String(e.message || e));
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
    if (!confirm(window.t('Remover card?'))) return;
    try {
      await apiDeleteCard(dashboardId, cardId);
      if (item) grid.removeWidget(item);
    } catch (err) {
      alert(String(err.message || err));
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
