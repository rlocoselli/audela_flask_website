/* global echarts */

(function () {
  let _biModal = null;

  function ensureModal () {
    if (_biModal) return _biModal;
    const host = document.createElement('div');
    host.innerHTML = `
      <div class="modal fade" id="aiChatModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="aiChatModalTitle">Information</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body" id="aiChatModalBody"></div>
            <div class="modal-footer">
              <button type="button" class="btn btn-primary" data-bs-dismiss="modal">OK</button>
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
    m.title.textContent = title || 'Information';
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

  function renderMessage (log, role, text) {
    const msg = el('div', 'chat-msg ' + role);
    msg.textContent = String(text || '');
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
        p.textContent = 'Falha ao renderizar gráfico.';
        body.appendChild(p);
      }
    }
  }

  function boot () {
    const log = qs('#ai-log');
    const input = qs('#ai-input');
    const sendBtn = qs('#ai-send');
    const clearBtn = qs('#ai-clear');
    const questionSel = qs('#ai-question');
    const paramsEl = qs('#ai-params');
    const status = qs('#ai-status');

    if (!log || !input || !sendBtn || !questionSel) return;

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

    async function send () {
      const qid = Number(questionSel.value || 0);
      const msg = (input.value || '').trim();
      if (!qid) {
        if (window.uiToast) window.uiToast(window.t('Selecione uma pergunta'), { variant: 'danger' });
        else uiAlert(window.t('Selecione uma pergunta'), window.t('Validation'));
        return;
      }
      if (!msg) return;

      const params = parseJsonSafe(paramsEl ? paramsEl.value : '');
      if (params === null) {
        if (window.uiToast) window.uiToast('Parâmetros JSON inválidos.', { variant: 'danger' });
        else uiAlert('Parâmetros JSON inválidos.', window.t('Validation'));
        return;
      }

      renderMessage(log, 'user', msg);
      history.push({ role: 'user', content: msg });
      input.value = '';
      clearCharts();

      setStatus(window.t('Gerando resposta...'));

      const resp = await fetch('/app/api/ai/chat', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          ...(getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {})
        },
        body: JSON.stringify({ question_id: qid, message: msg, history: history, params: params || {} })
      });

      const payload = await resp.json().catch(() => ({}));
      if (!resp.ok || payload.error) {
        const err = payload.error || 'Erro';
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

    sendBtn.addEventListener('click', (e) => {
      e.preventDefault();
      send().catch((err) => {
        setStatus('');
        renderMessage(log, 'assistant', String(err || 'Erro'));
      });
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendBtn.click();
      }
    });

    // Hello
    renderMessage(log, 'assistant', 'Selecione uma pergunta e descreva o que você quer analisar.');
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
