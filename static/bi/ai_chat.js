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
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="${t('Fechar')}"></button>
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
      speakBtn.title = t('Ouvir explicação');
      speakBtn.setAttribute('aria-label', t('Ouvir explicação'));
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
    wrap.classList.add('d-none');
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

    for (const ch of charts.slice(0, 5)) {
      const title = ch.title || '';
      const opt = ch.echarts_option;
      const card = el('div', 'card border-0 shadow-sm mb-3');
      card.style.borderRadius = '1rem';
      const body = el('div', 'card-body');
      const h = el('div', 'fw-semibold mb-2');
      h.textContent = title;
      const chartDiv = el('div');
      chartDiv.style.height = '360px';
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
        p.textContent = t('Falha ao renderizar gráfico.');
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

    if (!log || !input || !sendBtn || !questionSel) return;

    const query = new URLSearchParams(window.location.search || '');
    const createDashboardMode = query.get('create_dashboard') === '1';

    let history = [];

    function setStatus (s) {
      if (status) status.textContent = s || '';
    }

    function clearAll () {
      log.innerHTML = '';
      history = [];
      clearCharts();
      setStatus('');
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
          if (window.uiToast) window.uiToast(t('Selecione uma pergunta'), { variant: 'danger' });
          else uiAlert(t('Selecione uma pergunta'), t('Validação'));
          return;
        }
      } else {
        if (!sid) {
          if (window.uiToast) window.uiToast(t('Selecione uma fonte.'), { variant: 'danger' });
          else uiAlert(t('Selecione uma fonte.'), t('Validação'));
          return;
        }
      }
      if (!msg) return;

      let params = {};
      if (mode === 'question') {
        params = parseJsonSafe(paramsEl ? paramsEl.value : '');
        if (params === null) {
          if (window.uiToast) window.uiToast(t('Parâmetros JSON inválidos.'), { variant: 'danger' });
          else uiAlert(t('Parâmetros JSON inválidos.'), t('Validação'));
          return;
        }
      }

      renderMessage(log, 'user', msg);
      history.push({ role: 'user', content: msg });
      input.value = '';
      clearCharts();

      setStatus(t('Gerando resposta...'));

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
        const err = payload.error || t('Erro');
        renderMessage(log, 'assistant', err);
        history.push({ role: 'assistant', content: err });
        setStatus('');
        return;
      }

      const analysis = payload.analysis || payload.reply || '';
      renderMessage(log, 'assistant', analysis);
      history.push({ role: 'assistant', content: analysis });

      renderCharts(payload.charts || []);
      setStatus('');
    }

    async function createDashboardFromPrompt () {
      const mode = (modeSel?.value || 'question');
      const qid = Number(questionSel.value || 0);
      const sid = Number(sourceSel?.value || 0);
      const msg = (input.value || '').trim();
      const createComparison = !!(createComparisonEl && createComparisonEl.checked);

      if (!msg) {
        if (window.uiToast) window.uiToast(t('Digite o pedido do dashboard.'), { variant: 'danger' });
        else uiAlert(t('Digite o pedido do dashboard.'), t('Validação'));
        return;
      }

      if (mode === 'question' && !qid) {
        if (window.uiToast) window.uiToast(t('Selecione uma pergunta'), { variant: 'danger' });
        else uiAlert(t('Selecione uma pergunta'), t('Validação'));
        return;
      }

      if (mode === 'source' && !sid) {
        if (window.uiToast) window.uiToast(t('Selecione uma fonte.'), { variant: 'danger' });
        else uiAlert(t('Selecione uma fonte.'), t('Validação'));
        return;
      }

      setStatus(t('Criando dashboard automaticamente...'));

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
        const err = payload.error || t('Erro ao criar dashboard.');
        renderMessage(log, 'assistant', err);
        setStatus('');
        return;
      }

      const dashboard = (payload && payload.dashboard) ? payload.dashboard : {};
      const dashboardName = String(dashboard.name || t('Dashboard'));
      renderMessage(log, 'assistant', `${t('Dashboard criado')}: ${dashboardName}`);

      const comparison = (payload && payload.comparison) ? payload.comparison : {};
      const comparisonDashboard = (payload && payload.comparison_dashboard) ? payload.comparison_dashboard : {};
      const comparisonUrl = String(comparisonDashboard.url || '').trim();
      if (comparison && comparison.created) {
        renderMessage(log, 'assistant', `${t('Dashboard comparativo criado')}: ${String(comparisonDashboard.name || t('Comparativo'))}`);
      } else if (comparison && comparison.requested && comparison.error) {
        renderMessage(log, 'assistant', `${t('Dashboard principal criado. Comparativo não criado')}: ${comparison.error}`);
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
        setStatus(t('Abrindo dashboard...'));
        window.location.href = goUrl;
        return;
      }

      setStatus('');
    }

    sendBtn.addEventListener('click', (e) => {
      e.preventDefault();
      send().catch((err) => {
        setStatus('');
        renderMessage(log, 'assistant', String(err || t('Erro')));
      });
    });

    if (createDashboardBtn) {
      createDashboardBtn.addEventListener('click', (e) => {
        e.preventDefault();
        createDashboardFromPrompt().catch((err) => {
          setStatus('');
          renderMessage(log, 'assistant', String(err || t('Erro')));
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
      setStatus(t('Describe your dashboard and click "Créer dashboard".'));
      try {
        input.focus();
      } catch (e) {
        // Ignore focus errors.
      }
    }
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
