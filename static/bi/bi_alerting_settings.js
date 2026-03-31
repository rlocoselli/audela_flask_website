(function () {
  const t = (window.t ? window.t : (s) => s);
  const AGG_FUNCS = ['SUM', 'AVG', 'COUNT', 'MIN', 'MAX', 'STDDEV'];
  const HORIZON_MODES = ['last_days', 'last_months', 'current_year', 'custom_range'];

  function onReady (fn) {
    if (window.onReady) return window.onReady(fn);
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn, { once: true });
    } else {
      fn();
    }
  }

  function escapeHtml (value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function normRule (rule) {
    const item = (rule && typeof rule === 'object') ? rule : {};
    const channels = Array.isArray(item.channels) ? item.channels : [];
    const indicatorRef = String(item.indicator_ref || '').trim();
    const ratioRef = String(item.ratio_ref || '').trim();
    const sourceRaw = String(item.source_kind || '').trim().toLowerCase();
    let sourceKind = 'question';
    if (sourceRaw === 'ratio' || sourceRaw === 'finance_ratio' || (ratioRef && sourceRaw !== 'question')) {
      sourceKind = 'ratio';
    } else if (sourceRaw === 'indicator' || sourceRaw === 'finance_indicator' || (indicatorRef && sourceRaw !== 'question')) {
      sourceKind = 'indicator';
    }
    const qid = Number(item.question_id || 0);
    const aggRaw = String(item.agg_func || '').toUpperCase();
    const agg = AGG_FUNCS.includes(aggRaw) ? aggRaw : 'AVG';
    const horizonRaw = String(item.horizon_mode || '').trim().toLowerCase();
    const horizonMode = HORIZON_MODES.includes(horizonRaw) ? horizonRaw : 'last_days';
    return {
      id: String(item.id || Math.random().toString(36).slice(2, 10)),
      enabled: Boolean(item.enabled),
      name: String(item.name || ''),
      source_kind: sourceKind,
      question_id: sourceKind === 'question' ? (Number.isFinite(qid) ? qid : 0) : 0,
      indicator_ref: sourceKind === 'indicator' ? indicatorRef : '',
      ratio_ref: sourceKind === 'ratio' ? ratioRef : '',
      metric_field: sourceKind === 'question' ? String(item.metric_field || '') : 'value',
      agg_func: sourceKind === 'question' ? agg : 'AVG',
      date_field: String(item.date_field || ''),
      horizon_mode: horizonMode,
      horizon_days: Number.isFinite(Number(item.horizon_days)) ? Math.max(1, Number(item.horizon_days)) : 30,
      horizon_months: Number.isFinite(Number(item.horizon_months)) ? Math.max(1, Number(item.horizon_months)) : 3,
      horizon_start: String(item.horizon_start || ''),
      horizon_end: String(item.horizon_end || ''),
      operator: ['>', '>=', '<', '<=', '==', '!='].includes(String(item.operator || '')) ? String(item.operator) : '>=',
      threshold: Number.isFinite(Number(item.threshold)) ? Number(item.threshold) : 0,
      severity: ['info', 'low', 'medium', 'high', 'critical'].includes(String(item.severity || '')) ? String(item.severity) : 'medium',
      sla_minutes: Number.isFinite(Number(item.sla_minutes)) ? Number(item.sla_minutes) : 60,
      channels: channels.filter((c) => ['email', 'slack', 'teams'].includes(String(c))),
      message_template: String(item.message_template || '')
    };
  }

  function normHorizonMode (value) {
    const mode = String(value || '').trim().toLowerCase();
    return HORIZON_MODES.includes(mode) ? mode : 'last_days';
  }

  function horizonModeLabel (mode) {
    if (mode === 'last_days') return t('Last X days');
    if (mode === 'last_months') return t('Últimos X meses');
    if (mode === 'current_year') return t('Ano atual');
    if (mode === 'custom_range') return t('Intervalo customizado');
    return mode;
  }

  function aggOptionsHtml (selected) {
    const current = String(selected || 'AVG').toUpperCase();
    const options = [
      { value: 'SUM', label: t('Soma') },
      { value: 'AVG', label: t('Média') },
      { value: 'COUNT', label: t('Contagem') },
      { value: 'MIN', label: t('Mínimo') },
      { value: 'MAX', label: t('Máximo') },
      { value: 'STDDEV', label: t('Desvio padrão') }
    ];
    return options
      .map((opt) => `<option value="${opt.value}" ${current === opt.value ? 'selected' : ''}>${escapeHtml(opt.label)}</option>`)
      .join('');
  }

  onReady(function () {
    const form = document.getElementById('alerting-form');
    const list = document.getElementById('alerting-rules-list');
    const empty = document.getElementById('alerting-empty');
    const addBtn = document.getElementById('alerting-add-rule');
    const hidden = document.getElementById('rules_json');
    const rawData = document.getElementById('alerting-rules-data');
    const metricsUrlTemplateEl = document.getElementById('alerting-metrics-url-template');
    const questionSource = document.getElementById('alerting-question-options');
    const indicatorSource = document.getElementById('alerting-indicator-options');
    const ratioSource = document.getElementById('alerting-ratio-options');
    if (!form || !list || !addBtn || !hidden || !rawData) return;

    let metricsUrlTemplate = '';
    try {
      metricsUrlTemplate = String(JSON.parse(metricsUrlTemplateEl?.textContent || '""') || '');
    } catch (e) {
      metricsUrlTemplate = '';
    }

    const questionOptions = questionSource
      ? Array.from(questionSource.querySelectorAll('option')).map((opt) => ({
          id: Number(opt.value || 0),
          name: String(opt.textContent || '').trim()
        })).filter((q) => Number.isFinite(q.id) && q.id > 0)
      : [];

    const indicatorOptions = indicatorSource
      ? Array.from(indicatorSource.querySelectorAll('option')).map((opt) => ({
          ref: String(opt.value || '').trim(),
          name: String(opt.textContent || '').trim()
        })).filter((item) => item.ref)
      : [];

    const ratioOptions = ratioSource
      ? Array.from(ratioSource.querySelectorAll('option')).map((opt) => ({
          ref: String(opt.value || '').trim(),
          name: String(opt.textContent || '').trim()
        })).filter((item) => item.ref)
      : [];

    function buildQuestionOptions (selectedId) {
      const selected = Number(selectedId || 0);
      const head = `<option value="">${escapeHtml(t('Selecione uma pergunta'))}</option>`;
      const body = questionOptions
        .map((q) => `<option value="${q.id}" ${selected === q.id ? 'selected' : ''}>${escapeHtml(q.name)}</option>`)
        .join('');
      return head + body;
    }

    function buildIndicatorOptions (selectedRef) {
      const selected = String(selectedRef || '').trim();
      const head = `<option value="">${escapeHtml(t('Selecione um indicador'))}</option>`;
      const body = indicatorOptions
        .map((item) => `<option value="${escapeHtml(item.ref)}" ${selected === item.ref ? 'selected' : ''}>${escapeHtml(item.name)}</option>`)
        .join('');
      return head + body;
    }

    function buildRatioOptions (selectedRef) {
      const selected = String(selectedRef || '').trim();
      const head = `<option value="">${escapeHtml(t('Selecione um ratio'))}</option>`;
      const body = ratioOptions
        .map((item) => `<option value="${escapeHtml(item.ref)}" ${selected === item.ref ? 'selected' : ''}>${escapeHtml(item.name)}</option>`)
        .join('');
      return head + body;
    }

    function metricsUrlForQuestion (questionId) {
      if (!metricsUrlTemplate) return '';
      return metricsUrlTemplate.replace('/0/', `/${String(questionId || 0)}/`);
    }

    const questionFieldsCache = new Map();

    function defaultQuestionFieldsInfo () {
      return {
        metric_fields: [],
        date_fields: [],
        horizons: HORIZON_MODES.slice()
      };
    }

    async function getQuestionFieldsInfo (questionId) {
      const qid = Number(questionId || 0);
      if (!Number.isFinite(qid) || qid <= 0) return defaultQuestionFieldsInfo();
      if (questionFieldsCache.has(qid)) return questionFieldsCache.get(qid) || defaultQuestionFieldsInfo();

      const url = metricsUrlForQuestion(qid);
      if (!url) return defaultQuestionFieldsInfo();

      try {
        const response = await fetch(url, {
          method: 'GET',
          headers: { Accept: 'application/json' }
        });
        if (!response.ok) return defaultQuestionFieldsInfo();

        const payload = await response.json();
        const scalarFields = Array.isArray(payload?.scalar_metric_fields) ? payload.scalar_metric_fields : [];
        const metricFields = Array.isArray(payload?.metric_fields) ? payload.metric_fields : [];
        const dateFields = Array.isArray(payload?.date_fields) ? payload.date_fields : [];
        const horizons = Array.isArray(payload?.horizons) ? payload.horizons : HORIZON_MODES;

        const uniqueMetrics = [];
        const seenMetric = new Set();
        scalarFields.concat(metricFields).forEach((item) => {
          const key = String(item || '').trim();
          if (!key || seenMetric.has(key)) return;
          seenMetric.add(key);
          uniqueMetrics.push(key);
        });

        const uniqueDates = [];
        const seenDate = new Set();
        dateFields.forEach((item) => {
          const key = String(item || '').trim();
          if (!key || seenDate.has(key)) return;
          seenDate.add(key);
          uniqueDates.push(key);
        });

        const cleanHorizons = Array.from(new Set(horizons
          .map((item) => String(item || '').trim().toLowerCase())
          .filter((item) => HORIZON_MODES.includes(item))));

        const info = {
          metric_fields: uniqueMetrics,
          date_fields: uniqueDates,
          horizons: cleanHorizons.length ? cleanHorizons : HORIZON_MODES.slice()
        };
        questionFieldsCache.set(qid, info);
        return info;
      } catch (e) {
        return defaultQuestionFieldsInfo();
      }
    }

    function setMetricFieldOptions (container, fields, currentValue) {
      const select = container.querySelector('.ar-metric');
      if (!select) return;

      const current = String(currentValue || '').trim();
      const values = Array.isArray(fields) ? fields.map((f) => String(f || '').trim()).filter(Boolean) : [];
      const base = [`<option value="">${escapeHtml(t('Selecione uma métrica'))}</option>`];
      values.forEach((field) => {
        base.push(`<option value="${escapeHtml(field)}">${escapeHtml(field)}</option>`);
      });

      if (current && !values.includes(current)) {
        base.push(`<option value="${escapeHtml(current)}">${escapeHtml(current)} ${escapeHtml(t('(atual)'))}</option>`);
      }

      select.innerHTML = base.join('');
      select.value = current || '';
    }

    function setDateFieldOptions (container, fields, currentValue) {
      const select = container.querySelector('.ar-date-field');
      if (!select) return;

      const current = String(currentValue || '').trim();
      const values = Array.isArray(fields) ? fields.map((f) => String(f || '').trim()).filter(Boolean) : [];
      const base = [`<option value="">${escapeHtml(t('Sem filtro de data'))}</option>`];
      values.forEach((field) => {
        base.push(`<option value="${escapeHtml(field)}">${escapeHtml(field)}</option>`);
      });

      if (current && !values.includes(current)) {
        base.push(`<option value="${escapeHtml(current)}">${escapeHtml(current)} ${escapeHtml(t('(atual)'))}</option>`);
      }

      select.innerHTML = base.join('');
      select.value = current || '';
    }

    function setHorizonModeOptions (container, modes, selectedValue) {
      const select = container.querySelector('.ar-horizon-mode');
      if (!select) return;

      const available = Array.isArray(modes) && modes.length
        ? modes.filter((item) => HORIZON_MODES.includes(String(item || '').trim().toLowerCase())).map((item) => String(item).trim().toLowerCase())
        : HORIZON_MODES.slice();
      const unique = Array.from(new Set(available.length ? available : HORIZON_MODES));
      const selected = normHorizonMode(selectedValue);
      select.innerHTML = unique
        .map((mode) => `<option value="${mode}" ${mode === selected ? 'selected' : ''}>${escapeHtml(horizonModeLabel(mode))}</option>`)
        .join('');
      select.value = selected;
    }

    function applyDateHorizonVisibility (container) {
      const sourceKind = String(container.querySelector('.ar-source')?.value || 'question').trim();
      const dateValue = String(container.querySelector('.ar-date-field')?.value || '').trim();
      const hasDateFilter = sourceKind === 'question' && Boolean(dateValue);
      const mode = normHorizonMode(container.querySelector('.ar-horizon-mode')?.value || 'last_days');

      container.querySelector('.ar-date-wrap')?.classList.toggle('d-none', sourceKind !== 'question');
      container.querySelector('.ar-horizon-mode-wrap')?.classList.toggle('d-none', !hasDateFilter);
      container.querySelector('.ar-horizon-days-wrap')?.classList.toggle('d-none', !hasDateFilter || mode !== 'last_days');
      container.querySelector('.ar-horizon-months-wrap')?.classList.toggle('d-none', !hasDateFilter || mode !== 'last_months');
      container.querySelector('.ar-horizon-start-wrap')?.classList.toggle('d-none', !hasDateFilter || mode !== 'custom_range');
      container.querySelector('.ar-horizon-end-wrap')?.classList.toggle('d-none', !hasDateFilter || mode !== 'custom_range');
    }

    async function refreshMetricFieldOptions (container, preferredMetric, preferredDate, preferredMode) {
      const sourceKind = String(container.querySelector('.ar-source')?.value || 'question').trim();
      if (sourceKind === 'indicator' || sourceKind === 'ratio') {
        setMetricFieldOptions(container, ['value'], 'value');
        setDateFieldOptions(container, [], '');
        setHorizonModeOptions(container, HORIZON_MODES, 'last_days');
        applyDateHorizonVisibility(container);
        return;
      }
      const questionEl = container.querySelector('.ar-question');
      const qid = Number(questionEl?.value || 0);
      const current = String(preferredMetric != null ? preferredMetric : (container.querySelector('.ar-metric')?.value || '')).trim();
      const currentDate = String(preferredDate != null ? preferredDate : (container.querySelector('.ar-date-field')?.value || '')).trim();
      const currentMode = String(preferredMode != null ? preferredMode : (container.querySelector('.ar-horizon-mode')?.value || 'last_days')).trim();
      if (!Number.isFinite(qid) || qid <= 0) {
        setMetricFieldOptions(container, [], current);
        setDateFieldOptions(container, [], currentDate);
        setHorizonModeOptions(container, HORIZON_MODES, currentMode);
        applyDateHorizonVisibility(container);
        return;
      }
      const info = await getQuestionFieldsInfo(qid);
      setMetricFieldOptions(container, info.metric_fields, current);
      setDateFieldOptions(container, info.date_fields, currentDate);
      setHorizonModeOptions(container, info.horizons, currentMode);
      applyDateHorizonVisibility(container);
    }

    function applySourceBehavior (container, preferredMetric, preferredDate, preferredMode) {
      const sourceKind = String(container.querySelector('.ar-source')?.value || 'question').trim();
      const questionWrap = container.querySelector('.ar-question-wrap');
      const indicatorWrap = container.querySelector('.ar-indicator-wrap');
      const ratioWrap = container.querySelector('.ar-ratio-wrap');
      const metricWrap = container.querySelector('.ar-metric-wrap');
      const aggWrap = container.querySelector('.ar-agg-wrap');
      const dateField = container.querySelector('.ar-date-field');
      const horizonMode = container.querySelector('.ar-horizon-mode');
      const horizonDays = container.querySelector('.ar-horizon-days');
      const horizonMonths = container.querySelector('.ar-horizon-months');
      const horizonStart = container.querySelector('.ar-horizon-start');
      const horizonEnd = container.querySelector('.ar-horizon-end');

      if (sourceKind === 'indicator') {
        questionWrap?.classList.add('d-none');
        metricWrap?.classList.add('d-none');
        aggWrap?.classList.add('d-none');
        indicatorWrap?.classList.remove('d-none');
        ratioWrap?.classList.add('d-none');
        if (dateField) dateField.value = '';
        if (horizonMode) horizonMode.value = 'last_days';
        if (horizonDays) horizonDays.value = '30';
        if (horizonMonths) horizonMonths.value = '3';
        if (horizonStart) horizonStart.value = '';
        if (horizonEnd) horizonEnd.value = '';
      } else if (sourceKind === 'ratio') {
        questionWrap?.classList.add('d-none');
        metricWrap?.classList.add('d-none');
        aggWrap?.classList.add('d-none');
        indicatorWrap?.classList.add('d-none');
        ratioWrap?.classList.remove('d-none');
        if (dateField) dateField.value = '';
        if (horizonMode) horizonMode.value = 'last_days';
        if (horizonDays) horizonDays.value = '30';
        if (horizonMonths) horizonMonths.value = '3';
        if (horizonStart) horizonStart.value = '';
        if (horizonEnd) horizonEnd.value = '';
      } else {
        questionWrap?.classList.remove('d-none');
        metricWrap?.classList.remove('d-none');
        aggWrap?.classList.remove('d-none');
        indicatorWrap?.classList.add('d-none');
        ratioWrap?.classList.add('d-none');
      }

      const scalarSource = (sourceKind === 'indicator' || sourceKind === 'ratio');
      const metricValue = scalarSource ? 'value' : preferredMetric;
      const dateValue = scalarSource ? '' : preferredDate;
      const modeValue = scalarSource ? 'last_days' : preferredMode;
      refreshMetricFieldOptions(container, metricValue, dateValue, modeValue);
      applyDateHorizonVisibility(container);
    }

    let initialRules = [];
    try {
      const parsed = JSON.parse(rawData.textContent || '[]');
      if (Array.isArray(parsed)) initialRules = parsed.map(normRule);
    } catch (e) {
      initialRules = [];
    }

    function renderEmpty () {
      if (!empty) return;
      empty.classList.toggle('d-none', list.querySelectorAll('.alert-rule-item').length > 0);
    }

    function makeRuleElement (rule) {
      const r = normRule(rule);
      const el = document.createElement('div');
      el.className = 'alert-rule-item border rounded-3 p-2';
      el.setAttribute('data-rule-id', r.id);
      el.innerHTML = `
        <div class="row g-2 align-items-end">
          <div class="col-6 col-md-1">
            <div class="form-check form-switch">
              <input class="form-check-input ar-enabled" type="checkbox" ${r.enabled ? 'checked' : ''}>
              <label class="form-check-label">${escapeHtml(t('Ativa'))}</label>
            </div>
          </div>
          <div class="col-12 col-md-2">
            <label class="form-label small mb-1">${escapeHtml(t('Nome'))}</label>
            <input class="form-control form-control-sm ar-name" type="text" value="${escapeHtml(r.name)}" placeholder="SLA API crítica">
          </div>
          <div class="col-6 col-md-2">
            <label class="form-label small mb-1">${escapeHtml(t('Tipo'))}</label>
            <select class="form-select form-select-sm ar-source">
              <option value="question" ${r.source_kind === 'question' ? 'selected' : ''}>${escapeHtml(t('Pergunta BI'))}</option>
              <option value="indicator" ${r.source_kind === 'indicator' ? 'selected' : ''}>${escapeHtml(t('Indicador BI'))}</option>
              <option value="ratio" ${r.source_kind === 'ratio' ? 'selected' : ''}>${escapeHtml(t('Ratio BI'))}</option>
            </select>
          </div>
          <div class="col-12 col-md-3 ar-question-wrap">
            <label class="form-label small mb-1">${escapeHtml(t('Pergunta BI'))}</label>
            <select class="form-select form-select-sm ar-question">
              ${buildQuestionOptions(r.question_id)}
            </select>
          </div>
          <div class="col-12 col-md-3 ar-indicator-wrap d-none">
            <label class="form-label small mb-1">${escapeHtml(t('Indicador BI'))}</label>
            <select class="form-select form-select-sm ar-indicator">
              ${buildIndicatorOptions(r.indicator_ref)}
            </select>
          </div>
          <div class="col-12 col-md-3 ar-ratio-wrap d-none">
            <label class="form-label small mb-1">${escapeHtml(t('Ratio BI'))}</label>
            <select class="form-select form-select-sm ar-ratio">
              ${buildRatioOptions(r.ratio_ref)}
            </select>
          </div>
          <div class="col-6 col-md-2 ar-metric-wrap">
            <label class="form-label small mb-1">${escapeHtml(t('Campo métrico'))}</label>
            <select class="form-select form-select-sm ar-metric"></select>
          </div>
          <div class="col-6 col-md-1 ar-agg-wrap">
            <label class="form-label small mb-1">${escapeHtml(t('Agregação'))}</label>
            <select class="form-select form-select-sm ar-agg">${aggOptionsHtml(r.agg_func)}</select>
          </div>
          <div class="col-12 col-md-2 ar-date-wrap">
            <label class="form-label small mb-1">${escapeHtml(t('Campo de data'))}</label>
            <select class="form-select form-select-sm ar-date-field"></select>
          </div>
          <div class="col-12 col-md-2 ar-horizon-mode-wrap d-none">
            <label class="form-label small mb-1">${escapeHtml(t('Horizonte temporal'))}</label>
            <select class="form-select form-select-sm ar-horizon-mode"></select>
          </div>
          <div class="col-6 col-md-1 ar-horizon-days-wrap d-none">
            <label class="form-label small mb-1">${escapeHtml(t('Dias'))}</label>
            <input class="form-control form-control-sm ar-horizon-days" type="number" min="1" value="${escapeHtml(r.horizon_days)}">
          </div>
          <div class="col-6 col-md-1 ar-horizon-months-wrap d-none">
            <label class="form-label small mb-1">${escapeHtml(t('Meses'))}</label>
            <input class="form-control form-control-sm ar-horizon-months" type="number" min="1" value="${escapeHtml(r.horizon_months)}">
          </div>
          <div class="col-6 col-md-2 ar-horizon-start-wrap d-none">
            <label class="form-label small mb-1">${escapeHtml(t('Início'))}</label>
            <input class="form-control form-control-sm ar-horizon-start" type="date" value="${escapeHtml(r.horizon_start)}">
          </div>
          <div class="col-6 col-md-2 ar-horizon-end-wrap d-none">
            <label class="form-label small mb-1">${escapeHtml(t('Fim'))}</label>
            <input class="form-control form-control-sm ar-horizon-end" type="date" value="${escapeHtml(r.horizon_end)}">
          </div>
          <div class="col-6 col-md-1">
            <label class="form-label small mb-1">${escapeHtml(t('Operador'))}</label>
            <select class="form-select form-select-sm ar-operator">
              ${['>', '>=', '<', '<=', '==', '!='].map((op) => `<option value="${op}" ${r.operator === op ? 'selected' : ''}>${op}</option>`).join('')}
            </select>
          </div>
          <div class="col-6 col-md-1">
            <label class="form-label small mb-1">${escapeHtml(t('Limiar'))}</label>
            <input class="form-control form-control-sm ar-threshold" type="number" step="any" value="${escapeHtml(r.threshold)}">
          </div>
          <div class="col-6 col-md-1">
            <label class="form-label small mb-1">${escapeHtml(t('SLA (min)'))}</label>
            <input class="form-control form-control-sm ar-sla" type="number" min="1" value="${escapeHtml(r.sla_minutes)}">
          </div>
          <div class="col-6 col-md-1">
            <label class="form-label small mb-1">${escapeHtml(t('Severidade'))}</label>
            <select class="form-select form-select-sm ar-severity">
              <option value="info" ${r.severity === 'info' ? 'selected' : ''}>${escapeHtml(t('Info'))}</option>
              <option value="low" ${r.severity === 'low' ? 'selected' : ''}>${escapeHtml(t('Baixa'))}</option>
              <option value="medium" ${r.severity === 'medium' ? 'selected' : ''}>${escapeHtml(t('Média'))}</option>
              <option value="high" ${r.severity === 'high' ? 'selected' : ''}>${escapeHtml(t('Alta'))}</option>
              <option value="critical" ${r.severity === 'critical' ? 'selected' : ''}>${escapeHtml(t('Crítica'))}</option>
            </select>
          </div>
          <div class="col-12 col-md-1 d-grid">
            <button class="btn btn-outline-danger btn-sm ar-remove" type="button">${escapeHtml(t('Remover'))}</button>
          </div>

          <div class="col-12 col-md-4">
            <label class="form-label small mb-1">${escapeHtml(t('Canais'))}</label>
            <div class="d-flex flex-wrap gap-2">
              <div class="form-check form-check-inline mb-0">
                <input class="form-check-input ar-channel" data-channel="email" type="checkbox" ${r.channels.includes('email') ? 'checked' : ''}>
                <label class="form-check-label small">E-mail</label>
              </div>
              <div class="form-check form-check-inline mb-0">
                <input class="form-check-input ar-channel" data-channel="slack" type="checkbox" ${r.channels.includes('slack') ? 'checked' : ''}>
                <label class="form-check-label small">Slack</label>
              </div>
              <div class="form-check form-check-inline mb-0">
                <input class="form-check-input ar-channel" data-channel="teams" type="checkbox" ${r.channels.includes('teams') ? 'checked' : ''}>
                <label class="form-check-label small">Teams</label>
              </div>
            </div>
          </div>

          <div class="col-12 col-md-8">
            <label class="form-label small mb-1">${escapeHtml(t('Mensagem'))}</label>
            <input class="form-control form-control-sm ar-message" type="text" value="${escapeHtml(r.message_template)}" placeholder="${escapeHtml(t('Se vazio, usa o template padrão.'))}">
          </div>
        </div>
      `;

      const removeBtn = el.querySelector('.ar-remove');
      removeBtn?.addEventListener('click', function () {
        el.remove();
        renderEmpty();
      });

      const questionSelect = el.querySelector('.ar-question');
      questionSelect?.addEventListener('change', function () {
        refreshMetricFieldOptions(el, '', '', 'last_days');
      });

      const dateFieldSelect = el.querySelector('.ar-date-field');
      dateFieldSelect?.addEventListener('change', function () {
        applyDateHorizonVisibility(el);
      });

      const horizonModeSelect = el.querySelector('.ar-horizon-mode');
      horizonModeSelect?.addEventListener('change', function () {
        applyDateHorizonVisibility(el);
      });

      const sourceSelect = el.querySelector('.ar-source');
      sourceSelect?.addEventListener('change', function () {
        applySourceBehavior(el, undefined, '', 'last_days');
      });

      applySourceBehavior(el, r.metric_field, r.date_field, r.horizon_mode);
      return el;
    }

    function addRule (rule) {
      list.appendChild(makeRuleElement(rule));
      renderEmpty();
    }

    function collectRules () {
      const rows = Array.from(list.querySelectorAll('.alert-rule-item'));
      return rows.map((row) => {
        const channels = Array.from(row.querySelectorAll('.ar-channel:checked')).map((ch) => String(ch.getAttribute('data-channel') || '').trim()).filter(Boolean);
        const sourceRaw = String(row.querySelector('.ar-source')?.value || 'question').trim().toLowerCase();
        const sourceKind = sourceRaw === 'ratio' ? 'ratio' : (sourceRaw === 'indicator' ? 'indicator' : 'question');
        return {
          id: String(row.getAttribute('data-rule-id') || ''),
          enabled: Boolean(row.querySelector('.ar-enabled')?.checked),
          name: String(row.querySelector('.ar-name')?.value || '').trim(),
          source_kind: sourceKind,
          question_id: sourceKind === 'question' ? Number(row.querySelector('.ar-question')?.value || 0) : 0,
          indicator_ref: sourceKind === 'indicator' ? String(row.querySelector('.ar-indicator')?.value || '').trim() : '',
          ratio_ref: sourceKind === 'ratio' ? String(row.querySelector('.ar-ratio')?.value || '').trim() : '',
          metric_field: sourceKind === 'question' ? String(row.querySelector('.ar-metric')?.value || '').trim() : 'value',
          agg_func: sourceKind === 'question' ? String(row.querySelector('.ar-agg')?.value || 'AVG').toUpperCase() : 'AVG',
          date_field: String(row.querySelector('.ar-date-field')?.value || '').trim(),
          horizon_mode: normHorizonMode(row.querySelector('.ar-horizon-mode')?.value || 'last_days'),
          horizon_days: Number(row.querySelector('.ar-horizon-days')?.value || 30),
          horizon_months: Number(row.querySelector('.ar-horizon-months')?.value || 3),
          horizon_start: String(row.querySelector('.ar-horizon-start')?.value || '').trim(),
          horizon_end: String(row.querySelector('.ar-horizon-end')?.value || '').trim(),
          operator: String(row.querySelector('.ar-operator')?.value || '>=').trim(),
          threshold: Number(row.querySelector('.ar-threshold')?.value || 0),
          sla_minutes: Number(row.querySelector('.ar-sla')?.value || 60),
          severity: String(row.querySelector('.ar-severity')?.value || 'medium').trim(),
          channels,
          message_template: String(row.querySelector('.ar-message')?.value || '').trim()
        };
      });
    }

    addBtn.addEventListener('click', function () {
      addRule({
        enabled: true,
        name: '',
        source_kind: 'question',
        question_id: 0,
        indicator_ref: '',
        ratio_ref: '',
        metric_field: '',
        agg_func: 'AVG',
        date_field: '',
        horizon_mode: 'last_days',
        horizon_days: 30,
        horizon_months: 3,
        horizon_start: '',
        horizon_end: '',
        operator: '>=',
        threshold: 0,
        severity: 'medium',
        sla_minutes: 60,
        channels: ['email'],
        message_template: ''
      });
    });

    form.addEventListener('submit', function (event) {
      const rules = collectRules();
      const invalidQuestion = rules.find((rule) => rule.enabled && rule.source_kind === 'question' && !(Number(rule.question_id) > 0));
      if (invalidQuestion) {
        event.preventDefault();
        window.alert(t('Selecione uma pergunta em cada regra ativa.'));
        return;
      }
      const invalidIndicator = rules.find((rule) => rule.enabled && rule.source_kind === 'indicator' && !String(rule.indicator_ref || '').trim());
      if (invalidIndicator) {
        event.preventDefault();
        window.alert(t('Selecione um indicador em cada regra ativa.'));
        return;
      }
      const invalidRatio = rules.find((rule) => rule.enabled && rule.source_kind === 'ratio' && !String(rule.ratio_ref || '').trim());
      if (invalidRatio) {
        event.preventDefault();
        window.alert(t('Selecione um ratio em cada regra ativa.'));
        return;
      }
      const invalidMetric = rules.find((rule) => rule.enabled && rule.source_kind === 'question' && !String(rule.metric_field || '').trim());
      if (invalidMetric) {
        event.preventDefault();
        window.alert(t('Selecione o campo métrico em cada regra ativa.'));
        return;
      }
      const invalidAgg = rules.find((rule) => rule.enabled && rule.source_kind === 'question' && !AGG_FUNCS.includes(String(rule.agg_func || '').toUpperCase()));
      if (invalidAgg) {
        event.preventDefault();
        window.alert(t('Selecione a agregação da métrica em cada regra ativa.'));
        return;
      }

      const invalidHorizonMode = rules.find((rule) => {
        if (!rule.enabled || rule.source_kind !== 'question') return false;
        if (!String(rule.date_field || '').trim()) return false;
        return !HORIZON_MODES.includes(normHorizonMode(rule.horizon_mode));
      });
      if (invalidHorizonMode) {
        event.preventDefault();
        window.alert(t('Selecione o modo de horizonte temporal em cada regra com campo de data.'));
        return;
      }

      const invalidHorizonDays = rules.find((rule) => {
        if (!rule.enabled || rule.source_kind !== 'question') return false;
        if (!String(rule.date_field || '').trim()) return false;
        return normHorizonMode(rule.horizon_mode) === 'last_days' && !(Number(rule.horizon_days) > 0);
      });
      if (invalidHorizonDays) {
        event.preventDefault();
        window.alert(t('Informe os dias do horizonte temporal.'));
        return;
      }

      const invalidHorizonMonths = rules.find((rule) => {
        if (!rule.enabled || rule.source_kind !== 'question') return false;
        if (!String(rule.date_field || '').trim()) return false;
        return normHorizonMode(rule.horizon_mode) === 'last_months' && !(Number(rule.horizon_months) > 0);
      });
      if (invalidHorizonMonths) {
        event.preventDefault();
        window.alert(t('Informe os meses do horizonte temporal.'));
        return;
      }

      const invalidHorizonRange = rules.find((rule) => {
        if (!rule.enabled || rule.source_kind !== 'question') return false;
        if (!String(rule.date_field || '').trim()) return false;
        if (normHorizonMode(rule.horizon_mode) !== 'custom_range') return false;
        const start = String(rule.horizon_start || '').trim();
        const end = String(rule.horizon_end || '').trim();
        if (!start || !end) return true;
        return end < start;
      });
      if (invalidHorizonRange) {
        event.preventDefault();
        window.alert(t('Informe início e fim válidos para o intervalo customizado.'));
        return;
      }
      hidden.value = JSON.stringify(rules);
    });

    if (initialRules.length) {
      initialRules.forEach(addRule);
    }
    renderEmpty();
  });
})();
