/* global echarts, $ */

// Minimal BI visualization layer:
// - ECharts for charts (bar/line/area/pie/scatter/gauge)
// - PivotTable.js for pivots
// - Client-side filters + drill-down (cross-filter)

window.BI = window.BI || {};

(function () {
  function safeJsonParse(elId, fallback) {
    const el = document.getElementById(elId);
    if (!el) return fallback;
    try {
      return JSON.parse(el.textContent || el.innerText || '');
    } catch (e) {
      return fallback;
    }
  }

  function indexOfCol(columns, name) {
    if (!columns || !name) return -1;
    return columns.findIndex(c => String(c) === String(name));
  }

  function applyFilters(data, filters) {
    if (!filters || !filters.length) return data;
    const cols = data.columns || [];
    const rows = data.rows || [];
    const out = [];
    for (const r of rows) {
      let ok = true;
      for (const f of filters) {
        const idx = indexOfCol(cols, f.field);
        if (idx < 0) continue;
        const v = r[idx];
        const op = f.op || 'eq';
        const rhs = f.value;

        if (op === 'eq') {
          if (String(v) !== String(rhs)) ok = false;
        } else if (op === 'contains') {
          if (String(v).toLowerCase().indexOf(String(rhs).toLowerCase()) === -1) ok = false;
        } else if (op === 'gt') {
          if (!(Number(v) > Number(rhs))) ok = false;
        } else if (op === 'lt') {
          if (!(Number(v) < Number(rhs))) ok = false;
        }
        if (!ok) break;
      }
      if (ok) out.push(r);
    }
    return { columns: cols, rows: out };
  }

  function toObjects(data) {
    const cols = data.columns || [];
    const rows = data.rows || [];
    return rows.map(r => {
      const o = {};
      cols.forEach((c, i) => { o[c] = r[i]; });
      return o;
    });
  }

  function renderTable(container, data) {
    const cols = data.columns || [];
    const rows = data.rows || [];
    let html = '<div style="overflow-x:auto;">';
    html += '<table class="table"><thead><tr>';
    for (const c of cols) html += `<th>${String(c)}</th>`;
    html += '</tr></thead><tbody>';
    for (const r of rows) {
      html += '<tr>';
      for (const v of r) html += `<td>${v === null || typeof v === 'undefined' ? '' : String(v)}</td>`;
      html += '</tr>';
    }
    html += '</tbody></table></div>';
    container.innerHTML = html;
  }

  function renderPivot(container, data, cfg) {
    if (typeof $ === 'undefined' || !$.pivotUtilities) {
      container.innerHTML = '<p>PivotTable.js não carregou.</p>';
      return;
    }
    const records = toObjects(data);
    const rows = cfg.pivot_rows ? [cfg.pivot_rows] : [];
    const cols = cfg.pivot_cols ? [cfg.pivot_cols] : [];

    // pivotUI is interactive.
    $(container).empty();
    $(container).pivotUI(records, {
      rows: rows,
      cols: cols,
      vals: cfg.pivot_val ? [cfg.pivot_val] : [],
      aggregatorName: cfg.aggregatorName || 'Count',
      rendererName: cfg.rendererName || 'Table'
    }, true);
  }

  function renderChart(container, data, cfg, onDrill) {
    if (typeof echarts === 'undefined') {
      container.innerHTML = '<p>ECharts não carregou.</p>';
      return;
    }
    // Dispose existing instance on this DOM node to avoid stale state
    try {
      const existing = echarts.getInstanceByDom(container);
      if (existing) existing.dispose();
    } catch (e) {}
    const chart = echarts.init(container);
    const cols = data.columns || [];
    const rows = data.rows || [];

    const type = cfg.type || 'table';
    const dim = cfg.dim;
    const metric = cfg.metric;
    const dimIdx = indexOfCol(cols, dim);
    const metIdx = indexOfCol(cols, metric);

    const x = [];
    const y = [];
    if (dimIdx >= 0 && metIdx >= 0) {
      for (const r of rows) {
        x.push(r[dimIdx]);
        y.push(Number(r[metIdx]));
      }
    }

    let option = {};
    if (type === 'bar' || type === 'line' || type === 'area') {
      option = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: x },
        yAxis: { type: 'value' },
        series: [{
          type: type === 'area' ? 'line' : type,
          areaStyle: type === 'area' ? {} : undefined,
          data: y
        }]
      };
    } else if (type === 'pie') {
      const items = x.map((name, i) => ({ name: String(name), value: y[i] }));
      option = {
        tooltip: { trigger: 'item' },
        series: [{ type: 'pie', radius: '70%', data: items }]
      };
    } else if (type === 'scatter') {
      option = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: x },
        yAxis: { type: 'value' },
        series: [{ type: 'scatter', data: y.map((v, i) => [i, v]) }]
      };
    } else if (type === 'gauge') {
      let value = 0;
      if (rows.length) {
        if (metIdx >= 0) value = Number(rows[0][metIdx]);
        else if (rows[0].length) value = Number(rows[0][0]);
      }
      option = {
        series: [{ type: 'gauge', detail: { formatter: '{value}' }, data: [{ value: value }] }]
      };
    } else {
      chart.dispose();
      renderTable(container, data);
      return;
    }

    chart.setOption(option);
    window.addEventListener('resize', () => chart.resize());

    // Drill-down
    if (cfg.drill && onDrill && dimIdx >= 0) {
      chart.off('click');
      chart.on('click', params => {
        const clickedVal = params.name;
        onDrill(cfg.drill, clickedVal);
      });
    }
  }

  // ----- Export helpers -----
  async function exportPdf(title, data) {
    const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    const resp = await fetch('/app/api/export/pdf', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'X-CSRFToken': token } : {})
      },
      body: JSON.stringify({ title: title, columns: data.columns || [], rows: data.rows || [] })
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      alert(err.error || 'Falha ao exportar PDF');
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (title || 'export') + '.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  // ----- Dashboard renderer -----
  function bootDashboard() {
    const cards = document.querySelectorAll('[data-bi-card="1"]');
    if (!cards.length) return;

    const state = window.BI_DASHBOARD_STATE || { filters: [] };
    window.BI_DASHBOARD_STATE = state;

    function rerender() {
      for (const card of cards) {
        const id = card.getAttribute('data-card-id');
        const data = safeJsonParse('data-' + id, { columns: [], rows: [] });
        const cfg = safeJsonParse('cfg-' + id, { type: 'table' });
        const viz = card.querySelector('.bi-viz');
        const filtered = applyFilters(data, state.filters);
        if (cfg.type === 'pivot') {
          renderPivot(viz, filtered, cfg);
        } else if (cfg.type === 'table') {
          renderTable(viz, filtered);
        } else {
          renderChart(viz, filtered, cfg, (field, value) => {
            state.filters = (state.filters || []).filter(f => f.field !== field);
            state.filters.push({ field: field, op: 'eq', value: value });
            renderFilterSummary();
            rerender();
          });
        }
      }
    }

    function renderFilterSummary() {
      const el = document.getElementById('bi-filter-summary');
      if (!el) return;
      const fs = state.filters || [];
      if (!fs.length) {
        el.innerHTML = '<em>(sem filtros)</em>';
        return;
      }
      el.innerHTML = fs.map((f, idx) => {
        return `<span style="display:inline-block;margin:0 .4em .4em 0;padding:.2em .5em;border:1px solid #ddd;border-radius:6px;">
          ${f.field} ${f.op} ${String(f.value)}
          <a href="#" data-rm="${idx}" style="margin-left:.5em;">×</a>
        </span>`;
      }).join('');
      el.querySelectorAll('a[data-rm]').forEach(a => {
        a.addEventListener('click', (e) => {
          e.preventDefault();
          const idx = Number(a.getAttribute('data-rm'));
          state.filters.splice(idx, 1);
          renderFilterSummary();
          rerender();
        });
      });
    }

    // filter controls
    const addBtn = document.getElementById('bi-add-filter');
    if (addBtn) {
      addBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const field = document.getElementById('bi-filter-field')?.value;
        const op = document.getElementById('bi-filter-op')?.value || 'eq';
        const val = document.getElementById('bi-filter-value')?.value;
        if (!field || typeof val === 'undefined' || val === null || String(val).trim() === '') return;
        state.filters.push({ field: field, op: op, value: val });
        renderFilterSummary();
        rerender();
      });
    }
    const clearBtn = document.getElementById('bi-clear-filters');
    if (clearBtn) {
      clearBtn.addEventListener('click', (e) => {
        e.preventDefault();
        state.filters = [];
        renderFilterSummary();
        rerender();
      });
    }

    // Build field list from union of columns
    const fieldSelect = document.getElementById('bi-filter-field');
    if (fieldSelect) {
      const fields = new Set();
      for (const card of cards) {
        const id = card.getAttribute('data-card-id');
        const data = safeJsonParse('data-' + id, { columns: [] });
        (data.columns || []).forEach(c => fields.add(c));
      }
      fieldSelect.innerHTML = '<option value="">--</option>' + Array.from(fields).map(f => `<option value="${String(f)}">${String(f)}</option>`).join('');
    }

    // Export (filtered) from first card by default
    const exportBtn = document.getElementById('bi-export-pdf');
    if (exportBtn) {
      exportBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        // merge rows? MVP: export first card
        const first = cards[0];
        const id = first.getAttribute('data-card-id');
        const data = safeJsonParse('data-' + id, { columns: [], rows: [] });
        const filtered = applyFilters(data, state.filters);
        await exportPdf(document.title || 'Dashboard', filtered);
      });
    }

    renderFilterSummary();
    rerender();
  }

  // ----- Question visualization page -----
  function bootQuestionViz() {
    const previewEl = document.getElementById('preview');
    if (!previewEl) return;

    const data = safeJsonParse('preview-data', { columns: [], rows: [] });
    const savedCfg = safeJsonParse('preview-cfg', {});

    const elType = document.getElementById('viz_type');
    const elDim = document.getElementById('viz_dim');
    const elMet = document.getElementById('viz_metric');
    const elDrill = document.getElementById('viz_drill');
    const elPR = document.getElementById('pivot_rows');
    const elPC = document.getElementById('pivot_cols');
    const elPV = document.getElementById('pivot_val');
    const hidden = document.getElementById('viz_config_json');

    function setIf(el, value) {
      if (!el || typeof value === 'undefined' || value === null) return;
      el.value = value;
    }
    setIf(elType, savedCfg.type);
    setIf(elDim, savedCfg.dim);
    setIf(elMet, savedCfg.metric);
    setIf(elDrill, savedCfg.drill);
    setIf(elPR, savedCfg.pivot_rows);
    setIf(elPC, savedCfg.pivot_cols);
    setIf(elPV, savedCfg.pivot_val);

    function currentCfg() {
      return {
        type: elType ? elType.value : 'table',
        dim: elDim ? elDim.value : '',
        metric: elMet ? elMet.value : '',
        drill: elDrill ? elDrill.value : '',
        pivot_rows: elPR ? elPR.value : '',
        pivot_cols: elPC ? elPC.value : '',
        pivot_val: elPV ? elPV.value : ''
      };
    }

    function render() {
      const cfg = currentCfg();
      previewEl.innerHTML = '';
      if (cfg.type === 'pivot') {
        renderPivot(previewEl, data, cfg);
      } else if (cfg.type === 'table') {
        renderTable(previewEl, data);
      } else {
        renderChart(previewEl, data, cfg, null);
      }
      if (hidden) hidden.value = JSON.stringify(cfg);
    }

    ['change', 'keyup'].forEach(evt => {
      [elType, elDim, elMet, elDrill, elPR, elPC, elPV].forEach(el => {
        if (el) el.addEventListener(evt, render);
      });
    });

    // Ensure form submission always carries the JSON
    const form = hidden?.closest('form');
    if (form) {
      form.addEventListener('submit', () => {
        if (hidden) hidden.value = JSON.stringify(currentCfg());
      });
    }

    render();
  }

  BI.applyFilters = applyFilters;
  BI.exportPdf = exportPdf;
  BI.renderViz = function(container, data, cfg, onDrill) {
    if (!container) return;
    try { console.debug('bi_viz.renderViz', { type: (cfg && cfg.type) || 'table', cols: (data && data.columns && data.columns.length) || 0, rows: (data && data.rows && data.rows.length) || 0 }); } catch (e) {}
    const type = (cfg && cfg.type) || 'table';
    container.innerHTML = '';
    if (type === 'pivot') {
      renderPivot(container, data, cfg);
    } else if (type === 'table' || !type) {
      renderTable(container, data);
    } else {
      renderChart(container, data, cfg, onDrill || null);
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    bootDashboard();
    bootQuestionViz();
  });
})();
