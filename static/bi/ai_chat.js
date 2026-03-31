/* global echarts */

(function () {
  let _biModal = null;
  const t = (window.t ? window.t : (s) => s);

  function ensureModal () {
    if (_biModal) return _biModal;
    const host = document.createElement('div');
    host.innerHTML = `
      <div class="modal fade" id="aiChatModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="aiChatModalTitle">${t('Information')}</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="${t('Close')}"></button>
            </div>
            <div class="modal-body" id="aiChatModalBody"></div>
            <div class="modal-footer">
              <button type="button" class="btn btn-primary" data-bs-dismiss="modal">${t('OK')}</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(host.firstElementChild);
    const el = document.getElementById('aiChatModal');
    _biModal = {
      title: document.getElementById('aiChatModalTitle'),
      body: document.getElementById('aiChatModalBody'),
      bs: new bootstrap.Modal(el)
    };
    return _biModal;
  }

  function uiAlert (message, title) {
    const m = ensureModal();
    m.title.textContent = title || t('Information');
    m.body.textContent = String(message || '');
    m.bs.show();
  }

  function qs (sel) { return document.querySelector(sel); }
  function el (tag, cls) { const e = document.createElement(tag); if (cls) e.className = cls; return e; }

  function getCsrfToken () {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  function parseJsonSafe (txt) {
    if (!txt || !String(txt).trim()) return {};
    try {
      const o = JSON.parse(txt);
      return (o && typeof o === 'object' && !Array.isArray(o)) ? o : null;
    } catch (e) {
      return null;
    }
  }

  async function fetchWithRetry (url, options, retries) {
    let lastError = null;
    const maxRetries = Number.isFinite(retries) ? retries : 1;
    for (let i = 0; i <= maxRetries; i += 1) {
      try {
        return await fetch(url, options);
      } catch (e) {
        lastError = e;
        if (i >= maxRetries) break;
        await new Promise(resolve => setTimeout(resolve, 450));
      }
    }
    throw lastError;
  }

  function renderMessage (log, role, text) {
    const msg = el('div', 'chat-msg ' + role);
    const safeText = String(text || '');

    if (role === 'assistant') {
      msg.classList.add('d-flex', 'flex-column', 'gap-1');

      const tools = el('div', 'd-flex justify-content-end');
      const speakBtn = el('button', 'btn btn-outline-secondary btn-sm js-tts-speak');
      speakBtn.type = 'button';
      speakBtn.title = t('Listen to explanation');
      speakBtn.setAttribute('aria-label', t('Listen to explanation'));
      speakBtn.setAttribute('data-tts-text', safeText);
      speakBtn.innerHTML = '<i class="bi bi-volume-up"></i>';
      tools.appendChild(speakBtn);

      const body = el('div');
      body.textContent = safeText;

      msg.appendChild(tools);
      msg.appendChild(body);
    } else {
      msg.textContent = safeText;
    }

    log.appendChild(msg);
    log.scrollTop = log.scrollHeight;
  }

  function clearCharts () {
    const wrap = qs('#ai-charts');
    if (!wrap) return;
    wrap.innerHTML = '';
    wrap.classList.remove('ai-chart-grid');
    wrap.classList.add('d-none');
  }

  function clearKpis () {
    const wrap = qs('#ai-kpis');
    if (!wrap) return;
    wrap.innerHTML = '';
    wrap.classList.add('d-none');
  }

  function renderKpis (payload) {
    const wrap = qs('#ai-kpis');
    if (!wrap) return;
    wrap.innerHTML = '';

    const profile = (payload && payload.profile && Array.isArray(payload.profile.columns))
      ? payload.profile.columns
      : [];
    const numericCols = profile.filter((c) => String(c.type || '').toLowerCase() === 'number').slice(0, 4);
    const rowCount = Number(payload && payload.result && payload.result.row_count) || 0;

    if (!numericCols.length && !rowCount) {
      wrap.classList.add('d-none');
      return;
    }

    const cards = [];
    if (rowCount > 0) {
      cards.push(
        `<div class="ai-kpi-card"><div class="ai-kpi-label">${t('Rows')}</div><div class="ai-kpi-value">${rowCount.toLocaleString()}</div><div class="ai-kpi-sub">${t('Current query')}</div></div>`
      );
    }

    numericCols.forEach((col) => {
      const name = String(col.name || t('Metric'));
      const avg = Number(col.avg);
      const min = Number(col.min);
      const max = Number(col.max);
      const fmt = (n) => Number.isFinite(n) ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '-';
      cards.push(
        `<div class="ai-kpi-card"><div class="ai-kpi-label">${name}</div><div class="ai-kpi-value">${fmt(avg)}</div><div class="ai-kpi-sub">${t('min')} ${fmt(min)} · ${t('max')} ${fmt(max)}</div></div>`
      );
    });

    if (!cards.length) {
      wrap.classList.add('d-none');
      return;
    }

    wrap.innerHTML = cards.join('');
    wrap.classList.remove('d-none');
  }

  function renderCharts (charts) {
    const wrap = qs('#ai-charts');
    if (!wrap) return;
    wrap.innerHTML = '';
    if (!Array.isArray(charts) || !charts.length) {
      wrap.classList.add('d-none');
      return;
    }

    wrap.classList.remove('d-none');
    wrap.classList.add('ai-chart-grid');

    for (const ch of charts.slice(0, 5)) {
      const title = ch.title || '';
      const opt = ch.echarts_option;
      const card = el('div', 'card border-0 shadow-sm ai-chart-card');
      card.style.borderRadius = '1rem';
      const body = el('div', 'card-body');
      const h = el('div', 'fw-semibold mb-2');
      h.textContent = title;
      const chartDiv = el('div');
      chartDiv.style.height = '320px';
      body.appendChild(h);
      body.appendChild(chartDiv);
      card.appendChild(body);
      wrap.appendChild(card);

      try {
        const chart = echarts.init(chartDiv);
        if (opt && typeof opt === 'object') chart.setOption(opt);
        window.addEventListener('resize', () => chart.resize());
      } catch (e) {
        const p = el('div', 'text-secondary');
        p.textContent = t('Failed to render chart.');
        body.appendChild(p);
      }
    }
  }

  function boot () {
    const log = qs('#ai-log');
    const input = qs('#ai-input');
    const sendBtn = qs('#ai-send');
    const createDashboardBtn = qs('#ai-create-dashboard');
    const createComparisonEl = qs('#ai-create-comparison');
    const clearBtn = qs('#ai-clear');
    const modeSel = qs('#ai-mode');
    const questionSel = qs('#ai-question');
    const sourceSel = qs('#ai-source');
    const paramsEl = qs('#ai-params');
    const questionWrap = qs('#ai-question-wrap');
    const sourceWrap = qs('#ai-source-wrap');
    const paramsWrap = qs('#ai-params-wrap');
    const status = qs('#ai-status');
    const loadingOverlay = qs('#aiLoadingOverlay');
    const loadingText = qs('#aiLoadingText');
    const denseToggle = qs('#ai-dense-toggle');

    if (!log || !input || !sendBtn || !questionSel) return;

    const query = new URLSearchParams(window.location.search || '');
    const createDashboardMode = query.get('create_dashboard') === '1';

    let history = [];
    const DENSE_PREF_KEY = 'aiChatDenseMode';

    function applyDenseMode (enabled) {
      document.body.classList.toggle('ai-dense-enabled', !!enabled);
      if (denseToggle) denseToggle.checked = !!enabled;
      try {
        window.localStorage.setItem(DENSE_PREF_KEY, enabled ? '1' : '0');
      } catch (e) {
        // Ignore storage errors.
      }
    }

    try {
      const saved = window.localStorage.getItem(DENSE_PREF_KEY);
      applyDenseMode(saved !== '0');
    } catch (e) {
      applyDenseMode(true);
    }

    if (denseToggle) {
      denseToggle.addEventListener('change', () => {
        applyDenseMode(!!denseToggle.checked);
      });
    }

    function setLoading (isLoading, text) {
      if (loadingOverlay) {
        loadingOverlay.classList.toggle('is-visible', !!isLoading);
      }
      if (loadingText && text) {
        loadingText.textContent = String(text);
      }
      if (sendBtn) sendBtn.disabled = !!isLoading;
      if (createDashboardBtn) createDashboardBtn.disabled = !!isLoading;
      if (input) input.disabled = !!isLoading;
    }

    function setStatus (s) {
      if (status) status.textContent = s || '';
    }

    function clearAll () {
      log.innerHTML = '';
      history = [];
      clearCharts();
      clearKpis();
      setStatus('');
      setLoading(false, '');
    }

    if (clearBtn) clearBtn.addEventListener('click', (e) => {
      e.preventDefault();
      clearAll();
    });

    function syncModeUi () {
      const mode = (modeSel?.value || 'question');
      if (questionWrap) questionWrap.classList.toggle('d-none', mode !== 'question');
      if (sourceWrap) sourceWrap.classList.toggle('d-none', mode !== 'source');
      if (paramsWrap) paramsWrap.classList.toggle('d-none', mode !== 'question');
    }

    if (modeSel) modeSel.addEventListener('change', syncModeUi);
    syncModeUi();

    async function send () {
      const mode = (modeSel?.value || 'question');
      const qid = Number(questionSel.value || 0);
      const sid = Number(sourceSel?.value || 0);
      const msg = (input.value || '').trim();
      if (mode === 'question') {
        if (!qid) {
          if (window.uiToast) window.uiToast(t('Select a question'), { variant: 'danger' });
          else uiAlert(t('Select a question'), t('Validation'));
          return;
        }
      } else {
        if (!sid) {
          if (window.uiToast) window.uiToast(t('Select a source.'), { variant: 'danger' });
          else uiAlert(t('Select a source.'), t('Validation'));
          return;
        }
      }
      if (!msg) return;

      let params = {};
      if (mode === 'question') {
        params = parseJsonSafe(paramsEl ? paramsEl.value : '');
        if (params === null) {
          if (window.uiToast) window.uiToast(t('Invalid JSON parameters.'), { variant: 'danger' });
          else uiAlert(t('Invalid JSON parameters.'), t('Validation'));
          return;
        }
      }

      renderMessage(log, 'user', msg);
      history.push({ role: 'user', content: msg });
      input.value = '';
      clearCharts();
      clearKpis();

      setStatus(t('Generating response...'));
      setLoading(true, t('Analyzing your request...'));

      const resp = await fetchWithRetry('/app/api/ai/chat', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          ...(getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {})
        },
        body: JSON.stringify({
          mode: mode,
          question_id: (mode === 'question') ? qid : null,
          source_id: (mode === 'source') ? sid : null,
          message: msg,
          history: history,
          params: params || {}
        })
      }, 1);

      const payload = await resp.json().catch(() => ({}));
      if (!resp.ok || payload.error) {
        const err = payload.error || t('Error');
        renderMessage(log, 'assistant', err);
        history.push({ role: 'assistant', content: err });
        setStatus('');
        setLoading(false, '');
        return;
      }

      const analysis = payload.analysis || payload.reply || '';
      renderMessage(log, 'assistant', analysis);
      history.push({ role: 'assistant', content: analysis });

      renderKpis(payload);
      const baseCharts = Array.isArray(payload.charts) ? payload.charts : [];
      const enriched = enrichChartsWithGauges(baseCharts, payload);
      renderCharts(enriched);
      setStatus('');
      setLoading(false, '');
    }

    function enrichChartsWithGauges (charts, payload) {
      const out = Array.isArray(charts) ? charts.slice(0, 8) : [];
      const profile = (payload && payload.profile && Array.isArray(payload.profile.columns))
        ? payload.profile.columns
        : [];
      const numericCols = profile.filter((c) => String(c.type || '').toLowerCase() === 'number');
      if (!numericCols.length) return out;

      const existingGaugeCount = out.filter((c) => {
        const opt = c && c.echarts_option;
        const series = (opt && Array.isArray(opt.series)) ? opt.series : [];
        return series.some((s) => String((s && s.type) || '').toLowerCase() === 'gauge');
      }).length;

      // Keep at least 2-3 gauges if possible.
      const needed = Math.max(0, 3 - existingGaugeCount);
      if (!needed) return out;

      const picked = numericCols.slice(0, needed);
      picked.forEach((col) => {
        const name = String(col.name || t('Metric'));
        const min = Number.isFinite(Number(col.min)) ? Number(col.min) : 0;
        const maxRaw = Number.isFinite(Number(col.max)) ? Number(col.max) : 100;
        const avgRaw = Number.isFinite(Number(col.avg)) ? Number(col.avg) : min;
        const max = maxRaw <= min ? (min + 100) : maxRaw;
        const avg = Math.min(max, Math.max(min, avgRaw));

        out.push({
          title: `${name} · ${t('Gauge')}`,
          echarts_option: {
            tooltip: { formatter: '{a}<br/>{b}: {c}' },
            series: [
              {
                type: 'gauge',
                min,
                max,
                detail: { formatter: '{value}' },
                axisLine: {
                  lineStyle: {
                    width: 16,
                    color: [
                      [0.5, '#22c55e'],
                      [0.8, '#f59e0b'],
                      [1, '#ef4444']
                    ]
                  }
                },
                progress: { show: true, width: 16 },
                data: [{ value: Number(avg.toFixed(2)), name }]
              }
            ]
          }
        });
      });
      return out.slice(0, 10);
    }

    async function createDashboardFromPrompt () {
      const mode = (modeSel?.value || 'question');
      const qid = Number(questionSel.value || 0);
      const sid = Number(sourceSel?.value || 0);
      const msg = (input.value || '').trim();
      const createComparison = !!(createComparisonEl && createComparisonEl.checked);

      if (!msg) {
        if (window.uiToast) window.uiToast(t('Type your dashboard request.'), { variant: 'danger' });
        else uiAlert(t('Type your dashboard request.'), t('Validation'));
        return;
      }

      if (mode === 'question' && !qid) {
        if (window.uiToast) window.uiToast(t('Select a question'), { variant: 'danger' });
        else uiAlert(t('Select a question'), t('Validation'));
        return;
      }

      if (mode === 'source' && !sid) {
        if (window.uiToast) window.uiToast(t('Select a source.'), { variant: 'danger' });
        else uiAlert(t('Select a source.'), t('Validation'));
        return;
      }

      setStatus(t('Creating dashboard automatically...'));
      setLoading(true, t('Creating dashboard...'));

      const resp = await fetchWithRetry('/app/api/ai/dashboard', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          ...(getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {})
        },
        body: JSON.stringify({
          message: msg,
          question_id: mode === 'question' ? qid : 0,
          source_id: mode === 'source' ? sid : 0,
          create_comparison: createComparison
        })
      }, 1);

      const payload = await resp.json().catch(() => ({}));
      if (!resp.ok || !payload.ok) {
        const err = payload.error || t('Failed to create dashboard.');
        renderMessage(log, 'assistant', err);
        setStatus('');
        setLoading(false, '');
        return;
      }

      const dashboard = (payload && payload.dashboard) ? payload.dashboard : {};
      const dashboardName = String(dashboard.name || t('Dashboard'));
      renderMessage(log, 'assistant', `${t('Dashboard created')}: ${dashboardName}`);

      const comparison = (payload && payload.comparison) ? payload.comparison : {};
      const comparisonDashboard = (payload && payload.comparison_dashboard) ? payload.comparison_dashboard : {};
      const comparisonUrl = String(comparisonDashboard.url || '').trim();
      if (comparison && comparison.created) {
        renderMessage(log, 'assistant', `${t('Comparison dashboard created')}: ${String(comparisonDashboard.name || t('Comparison'))}`);
      } else if (comparison && comparison.requested && comparison.error) {
        renderMessage(log, 'assistant', `${t('Main dashboard created. Comparison not created')}: ${comparison.error}`);
      }

      const goUrl = String(dashboard.url || '').trim();
      if (goUrl) {
        if (comparison && comparison.created && comparisonUrl) {
          try {
            window.open(comparisonUrl, '_blank', 'noopener');
          } catch (e) {
            // Ignore popup blockers.
          }
        }
        setStatus(t('Opening dashboard...'));
        window.location.href = goUrl;
        return;
      }

      setStatus('');
      setLoading(false, '');
    }

    sendBtn.addEventListener('click', (e) => {
      e.preventDefault();
      send().catch((err) => {
        setStatus('');
        setLoading(false, '');
        renderMessage(log, 'assistant', String(err || t('Error')));
      });
    });

    if (createDashboardBtn) {
      createDashboardBtn.addEventListener('click', (e) => {
        e.preventDefault();
        createDashboardFromPrompt().catch((err) => {
          setStatus('');
          setLoading(false, '');
          renderMessage(log, 'assistant', String(err || t('Error')));
        });
      });
    }

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendBtn.click();
      }
    });

    // Hello
    renderMessage(log, 'assistant', t('Select a question or a source and describe what you want to analyze.'));
    if (createDashboardMode) {
      setStatus(t('Describe your dashboard and click "Create dashboard".'));
      try {
        input.focus();
      } catch (e) {
        // Ignore focus errors.
      }
    }
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
