(function () {
  const t = (window.t ? window.t : (s) => s);
  const PREFS_KEY = 'bi.what_if.prefs.v1';
  const SCENARIOS_KEY = 'bi.what_if.saved_scenarios.v1';
  const DEFAULT_STRESS_TEXT = `[
  {"name":"Adverse","pct":-20,"prob":0.25},
  {"name":"Central","pct":0,"prob":0.5},
  {"name":"Optimiste","pct":15,"prob":0.25}
]`;

  function onReady (fn) {
    if (window.onReady) return window.onReady(fn);
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn, { once: true });
    } else {
      fn();
    }
  }

  function getCsrfToken () {
    const pageToken = document.getElementById('whatIfPage')?.getAttribute('data-csrf-token');
    if (pageToken) return pageToken;
    const metaToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    if (metaToken) return metaToken;
    const inputToken = document.querySelector('input[name="csrf_token"]')?.value;
    if (inputToken) return inputToken;
    return '';
  }

  function extractErrorMessage (rawText, parsedJson) {
    const data = (parsedJson && typeof parsedJson === 'object') ? parsedJson : {};
    const direct = String(data.error || data.message || '').trim();
    if (direct) return direct;

    const text = String(rawText || '').trim();
    if (!text) return t('Erro ao carregar.');
    const plain = text.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    if (/csrf token is missing/i.test(plain)) {
      return t('Sessão expirada ou token de segurança ausente. Recarregue a página e tente novamente.');
    }
    return plain || t('Erro ao carregar.');
  }

  function toNumber (value) {
    if (value === null || value === undefined) return null;
    if (typeof value === 'number') return Number.isFinite(value) ? value : null;
    let txt = String(value).trim();
    if (!txt) return null;

    txt = txt
      .replace(/\s+/g, '')
      .replace(/[€$£%]/g, '');

    const hasComma = txt.includes(',');
    const hasDot = txt.includes('.');
    if (hasComma && hasDot) {
      if (txt.lastIndexOf(',') > txt.lastIndexOf('.')) {
        txt = txt.replace(/\./g, '').replace(',', '.');
      } else {
        txt = txt.replace(/,/g, '');
      }
    } else if (hasComma && !hasDot) {
      txt = txt.replace(',', '.');
    }

    const n = Number(txt);
    return Number.isFinite(n) ? n : null;
  }

  function formatNumber (value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '0';
    return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  function formatPValue (value) {
    const p = Number(value);
    if (!Number.isFinite(p) || p < 0) return '0';
    if (p === 0) return '< 1e-308';
    if (p < 1e-4) return p.toExponential(2);
    return p.toLocaleString(undefined, { maximumFractionDigits: 6 });
  }

  function escapeHtml (value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function buildQuestionDataUrl (template, questionId) {
    const qid = String(questionId || '').trim();
    if (!qid) return '';
    const tpl = String(template || '/app/api/questions/0/data');
    try {
      const u = new URL(tpl, window.location.origin);
      if (/\/\d+\/data\/?$/.test(u.pathname)) {
        u.pathname = u.pathname.replace(/\/\d+\/data\/?$/, `/${qid}/data`);
        return `${u.pathname}${u.search}`;
      }
      return `/app/api/questions/${qid}/data`;
    } catch (e) {
      return tpl.replace(/\/\d+\/data\/?$/, `/${qid}/data`);
    }
  }

  function parseParams (raw) {
    const text = String(raw || '').trim();
    if (!text) return {};
    const parsed = JSON.parse(text);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error(t('Parâmetros devem ser um objeto JSON.'));
    }
    return parsed;
  }

  function inferColumns (rows, columns) {
    const cols = Array.isArray(columns) ? columns : [];
    const sample = Array.isArray(rows) ? rows.slice(0, 300) : [];
    return cols.map((name, idx) => {
      let numeric = 0;
      let nonEmpty = 0;
      for (const row of sample) {
        if (!Array.isArray(row) || idx >= row.length) continue;
        const value = row[idx];
        if (value === null || value === undefined || value === '') continue;
        nonEmpty += 1;
        if (toNumber(value) !== null) numeric += 1;
      }
      return {
        name,
        idx,
        numeric: nonEmpty > 0 ? (numeric / nonEmpty) >= 0.7 : false
      };
    });
  }

  function loadPrefs () {
    try {
      const raw = localStorage.getItem(PREFS_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
      return parsed;
    } catch (e) {
      return {};
    }
  }

  function savePrefs (prefs) {
    try {
      localStorage.setItem(PREFS_KEY, JSON.stringify(prefs || {}));
    } catch (e) {}
  }

  function loadScenarios () {
    try {
      const raw = localStorage.getItem(SCENARIOS_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
      return parsed;
    } catch (e) {
      return {};
    }
  }

  function saveScenarios (scenarios) {
    try {
      localStorage.setItem(SCENARIOS_KEY, JSON.stringify(scenarios || {}));
    } catch (e) {}
  }

  async function fetchScenariosFromServer (url) {
    const endpoint = String(url || '').trim();
    if (!endpoint) throw new Error(t('Endpoint scénarios indisponible.'));
    const res = await fetch(endpoint, {
      method: 'GET',
      credentials: 'same-origin',
      headers: { Accept: 'application/json' }
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data || data.ok === false) {
      throw new Error(String(data?.error || t('Erreur chargement scénarios.')));
    }
    return (data && typeof data.scenarios === 'object' && !Array.isArray(data.scenarios)) ? data.scenarios : {};
  }

  async function saveScenarioToServer (url, name, config) {
    const endpoint = String(url || '').trim();
    if (!endpoint) throw new Error(t('Endpoint scénarios indisponible.'));
    const csrf = getCsrfToken();
    const res = await fetch(endpoint, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...(csrf ? { 'X-CSRFToken': csrf, 'X-CSRF-Token': csrf } : {})
      },
      body: JSON.stringify({ name, config })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data || data.ok === false) {
      throw new Error(String(data?.error || t('Erreur sauvegarde scénario.')));
    }
    return (data && typeof data.scenarios === 'object' && !Array.isArray(data.scenarios)) ? data.scenarios : {};
  }

  async function deleteScenarioFromServer (url, name) {
    const endpoint = String(url || '').trim();
    if (!endpoint) throw new Error(t('Endpoint scénarios indisponible.'));
    const csrf = getCsrfToken();
    const res = await fetch(endpoint, {
      method: 'DELETE',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...(csrf ? { 'X-CSRFToken': csrf, 'X-CSRF-Token': csrf } : {})
      },
      body: JSON.stringify({ name })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data || data.ok === false) {
      throw new Error(String(data?.error || t('Erreur suppression scénario.')));
    }
    return (data && typeof data.scenarios === 'object' && !Array.isArray(data.scenarios)) ? data.scenarios : {};
  }

  function clamp (value, min, max) {
    const n = Number(value);
    if (!Number.isFinite(n)) return min;
    return Math.min(max, Math.max(min, n));
  }

  function mean (arr) {
    if (!Array.isArray(arr) || !arr.length) return 0;
    return arr.reduce((acc, v) => acc + v, 0) / arr.length;
  }

  function stdDev (arr, sample = true) {
    if (!Array.isArray(arr) || arr.length < 2) return 0;
    const m = mean(arr);
    const variance = arr.reduce((acc, v) => acc + ((v - m) ** 2), 0) / (sample ? (arr.length - 1) : arr.length);
    return Math.sqrt(Math.max(variance, 0));
  }

  function percentile (arr, p) {
    if (!Array.isArray(arr) || !arr.length) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const idx = clamp((p / 100) * (sorted.length - 1), 0, sorted.length - 1);
    const lo = Math.floor(idx);
    const hi = Math.ceil(idx);
    if (lo === hi) return sorted[lo];
    const w = idx - lo;
    return (sorted[lo] * (1 - w)) + (sorted[hi] * w);
  }

  function randomNormal () {
    let u = 0;
    let v = 0;
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  function randomTriangular (min, mode, max) {
    const u = Math.random();
    const c = (mode - min) / (max - min);
    if (u < c) {
      return min + Math.sqrt(u * (max - min) * (mode - min));
    }
    return max - Math.sqrt((1 - u) * (max - min) * (max - mode));
  }

  function drawShockMultiplier (distribution, volatilityPct) {
    const v = Math.max(0, Number(volatilityPct) || 0) / 100;
    if (v === 0) return 1;
    if (distribution === 'uniform') {
      return 1 + ((Math.random() * 2 - 1) * v);
    }
    if (distribution === 'triangular') {
      return 1 + randomTriangular(-v, 0, v);
    }
    return 1 + (randomNormal() * v);
  }

  function erfApprox (x) {
    const sign = x < 0 ? -1 : 1;
    const ax = Math.abs(x);
    const a1 = 0.254829592;
    const a2 = -0.284496736;
    const a3 = 1.421413741;
    const a4 = -1.453152027;
    const a5 = 1.061405429;
    const p = 0.3275911;
    const tVal = 1 / (1 + p * ax);
    const y = 1 - (((((a5 * tVal + a4) * tVal) + a3) * tVal + a2) * tVal + a1) * tVal * Math.exp(-ax * ax);
    return sign * y;
  }

  function normalCdf (x) {
    return 0.5 * (1 + erfApprox(x / Math.sqrt(2)));
  }

  function normalizeStressScenarios (rawText) {
    const txt = String(rawText || '').trim() || DEFAULT_STRESS_TEXT;
    let parsed;
    try {
      parsed = JSON.parse(txt);
    } catch (e) {
      throw new Error(t('JSON de stress invalide.'));
    }
    if (!Array.isArray(parsed) || !parsed.length) {
      throw new Error(t('Le stress test attend une liste de scénarios.'));
    }
    const clean = parsed.slice(0, 20).map((item, idx) => {
      const label = String(item?.name || `${t('Scénario')} ${idx + 1}`).trim();
      const pct = clamp(toNumber(item?.pct) ?? 0, -99.9, 500);
      const prob = Math.max(0, toNumber(item?.prob) ?? 0);
      return { name: label || `${t('Scénario')} ${idx + 1}`, pct, prob };
    });
    const sumProb = clean.reduce((acc, s) => acc + s.prob, 0);
    if (sumProb <= 0) {
      const p = 1 / clean.length;
      return clean.map((s) => ({ ...s, prob: p }));
    }
    return clean.map((s) => ({ ...s, prob: s.prob / sumProb }));
  }

  function buildSimulationRows (rows, metricField, dimField) {
    const out = [];
    for (const row of rows || []) {
      if (!Array.isArray(row)) continue;
      const metricValue = toNumber(row[metricField.idx]);
      if (metricValue === null) continue;
      const keyRaw = dimField ? row[dimField.idx] : t('Não agrupado');
      const key = (keyRaw === null || keyRaw === undefined || keyRaw === '') ? t('Não agrupado') : String(keyRaw);
      out.push({ key, metric: metricValue });
    }
    return out;
  }

  function addToMap (map, key, value) {
    map.set(key, (map.get(key) || 0) + value);
  }

  function baseGroupStats (simRows) {
    const groups = new Map();
    let baseTotal = 0;
    for (const row of simRows) {
      baseTotal += row.metric;
      if (!groups.has(row.key)) groups.set(row.key, { key: row.key, rows: 0, base: 0 });
      const item = groups.get(row.key);
      item.rows += 1;
      item.base += row.metric;
    }
    return { groups, baseTotal };
  }

  function hypothesisTestTwoSample (baseSample, simSample) {
    const n1 = baseSample.length;
    const n2 = simSample.length;
    if (n1 < 2 || n2 < 2) return null;
    const m1 = mean(baseSample);
    const m2 = mean(simSample);
    const s1 = stdDev(baseSample);
    const s2 = stdDev(simSample);
    const se = Math.sqrt((s1 ** 2) / n1 + (s2 ** 2) / n2);
    if (!Number.isFinite(se) || se <= 0) return null;
    const z = (m2 - m1) / se;
    const p = 2 * (1 - normalCdf(Math.abs(z)));
    return {
      z,
      p,
      m1,
      m2,
      se,
      significant: p < 0.05,
      summary: p < 0.05
        ? t('Différence statistiquement significative (p < 0,05).')
        : t('Différence non significative au seuil 5%.')
    };
  }

  function hypothesisTestOneSample (nullMean, sample) {
    const n = sample.length;
    if (n < 2) return null;
    const m = mean(sample);
    const s = stdDev(sample);
    const se = s / Math.sqrt(n);
    if (!Number.isFinite(se) || se <= 0) return null;
    const z = (m - nullMean) / se;
    const p = 2 * (1 - normalCdf(Math.abs(z)));
    return {
      z,
      p,
      m,
      nullMean,
      se,
      significant: p < 0.05,
      summary: p < 0.05
        ? t('La moyenne simulée diffère significativement de la base (p < 0,05).')
        : t('Aucune différence significative détectée au seuil 5%.')
    };
  }

  function buildExplanation (method, distribution, runs) {
    if (method === 'stress') {
      return t('Stress test: chaque scénario applique un choc (%) et une probabilité; le résultat principal est la valeur attendue pondérée par les probabilités.');
    }
    if (method === 'montecarlo') {
      return `${t('Monte Carlo:')} ${Number(runs) || 0} ${t('tirages aléatoires selon une loi')} ${distribution || 'normal'} ${t('pour estimer la distribution des résultats (P5/P50/P95).')}`;
    }
    return t('Déterministe: applique une variation fixe (%) puis un delta constant sur chaque ligne.');
  }

  onReady(function () {
    const page = document.getElementById('whatIfPage');
    if (!page) return;

    const elError = document.getElementById('whatIfError');
    const selQuestion = document.getElementById('wf-question');
    const txtParams = document.getElementById('wf-params');
    const selMetric = document.getElementById('wf-metric');
    const selDim = document.getElementById('wf-dim');
    const inpPct = document.getElementById('wf-pct');
    const inpDelta = document.getElementById('wf-delta');
    const selMethod = document.getElementById('wf-method');
    const selDist = document.getElementById('wf-dist');
    const inpVol = document.getElementById('wf-vol');
    const inpRuns = document.getElementById('wf-runs');
    const txtStressJson = document.getElementById('wf-stress-json');
    const chkHypothesis = document.getElementById('wf-hypothesis');
    const inpScenarioName = document.getElementById('wf-scenario-name');
    const selSavedScenarios = document.getElementById('wf-saved-scenarios');
    const btnSaveScenario = document.getElementById('wf-save-scenario');
    const btnLoadScenario = document.getElementById('wf-load-scenario');
    const btnDeleteScenario = document.getElementById('wf-delete-scenario');
    const selSort = document.getElementById('wf-sort');
    const btnLoad = document.getElementById('wf-load');
    const btnRun = document.getElementById('wf-run');

    const resultsCard = document.getElementById('wf-results-card');
    const kpiBase = document.getElementById('wf-kpi-base');
    const kpiSim = document.getElementById('wf-kpi-sim');
    const kpiDiff = document.getElementById('wf-kpi-diff');
    const kpiDiffPct = document.getElementById('wf-kpi-diff-pct');
    const thDim = document.getElementById('wf-th-dim');
    const tbody = document.getElementById('wf-tbody');
    const limitNote = document.getElementById('wf-limit-note');
    const explanationBox = document.getElementById('wf-explanation');
    const advancedTbody = document.getElementById('wf-advanced-tbody');
    const monteCarloHistBox = document.getElementById('wf-mc-hist-box');
    const monteCarloHistWrap = document.getElementById('wf-mc-hist-wrap');
    const monteCarloHistCanvas = document.getElementById('wf-mc-hist-canvas');
    const monteCarloHistMeta = document.getElementById('wf-mc-hist-meta');
    const monteCarloHistTooltip = document.getElementById('wf-mc-hist-tooltip');
    const hypothesisBox = document.getElementById('wf-hypothesis-box');
    const hypothesisSummary = document.getElementById('wf-hypothesis-summary');
    const hypothesisTbody = document.getElementById('wf-hypothesis-tbody');

    const state = {
      columns: [],
      rows: [],
      fields: [],
      savedScenarios: {},
      monteCarloChartData: null,
      monteCarloHoverBin: -1
    };

    const prefs = loadPrefs();
    if (inpPct && Number.isFinite(Number(prefs.pct))) inpPct.value = String(prefs.pct);
    if (inpDelta && Number.isFinite(Number(prefs.delta))) inpDelta.value = String(prefs.delta);
    if (selMethod && ['deterministic', 'stress', 'montecarlo'].includes(String(prefs.method || ''))) selMethod.value = String(prefs.method);
    if (selDist && ['normal', 'uniform', 'triangular'].includes(String(prefs.dist || ''))) selDist.value = String(prefs.dist);
    if (inpVol && Number.isFinite(Number(prefs.vol))) inpVol.value = String(prefs.vol);
    if (inpRuns && Number.isFinite(Number(prefs.runs))) inpRuns.value = String(prefs.runs);
    if (txtStressJson && typeof prefs.stressJson === 'string' && prefs.stressJson.trim()) txtStressJson.value = prefs.stressJson;
    if (chkHypothesis && typeof prefs.hypothesis === 'boolean') chkHypothesis.checked = prefs.hypothesis;
    if (selSort && ['impact_desc', 'base_desc', 'sim_desc', 'key_asc'].includes(String(prefs.sort || ''))) {
      selSort.value = String(prefs.sort);
    }

    function persistCurrentPrefs () {
      savePrefs({
        pct: toNumber(inpPct?.value) ?? 0,
        delta: toNumber(inpDelta?.value) ?? 0,
        method: String(selMethod?.value || 'deterministic'),
        dist: String(selDist?.value || 'normal'),
        vol: toNumber(inpVol?.value) ?? 10,
        runs: clamp(toNumber(inpRuns?.value) ?? 1000, 100, 5000),
        stressJson: String(txtStressJson?.value || '').trim() || DEFAULT_STRESS_TEXT,
        hypothesis: !!chkHypothesis?.checked,
        sort: String(selSort?.value || 'impact_desc')
      });
    }

    function setMethodUi () {
      const method = String(selMethod?.value || 'deterministic');
      const monte = method === 'montecarlo';
      const stress = method === 'stress';
      if (selDist) selDist.disabled = !monte;
      if (inpVol) inpVol.disabled = !monte;
      if (inpRuns) inpRuns.disabled = !monte;
      if (txtStressJson) txtStressJson.disabled = !stress;
    }

    function scenarioSnapshot () {
      return {
        question: String(selQuestion?.value || '').trim(),
        metric: String(selMetric?.value || '').trim(),
        dim: String(selDim?.value || '').trim(),
        params: String(txtParams?.value || '{}'),
        pct: toNumber(inpPct?.value) ?? 0,
        delta: toNumber(inpDelta?.value) ?? 0,
        method: String(selMethod?.value || 'deterministic'),
        dist: String(selDist?.value || 'normal'),
        vol: toNumber(inpVol?.value) ?? 10,
        runs: clamp(toNumber(inpRuns?.value) ?? 1000, 100, 5000),
        stressJson: String(txtStressJson?.value || '').trim() || DEFAULT_STRESS_TEXT,
        hypothesis: !!chkHypothesis?.checked,
        sort: String(selSort?.value || 'impact_desc')
      };
    }

    function applyScenarioSnapshot (cfg) {
      if (!cfg || typeof cfg !== 'object') return;
      if (selQuestion && typeof cfg.question === 'string') selQuestion.value = cfg.question;
      if (txtParams && typeof cfg.params === 'string') txtParams.value = cfg.params;
      if (inpPct && Number.isFinite(Number(cfg.pct))) inpPct.value = String(cfg.pct);
      if (inpDelta && Number.isFinite(Number(cfg.delta))) inpDelta.value = String(cfg.delta);
      if (selMethod && ['deterministic', 'stress', 'montecarlo'].includes(String(cfg.method || ''))) selMethod.value = String(cfg.method);
      if (selDist && ['normal', 'uniform', 'triangular'].includes(String(cfg.dist || ''))) selDist.value = String(cfg.dist);
      if (inpVol && Number.isFinite(Number(cfg.vol))) inpVol.value = String(cfg.vol);
      if (inpRuns && Number.isFinite(Number(cfg.runs))) inpRuns.value = String(clamp(cfg.runs, 100, 5000));
      if (txtStressJson && typeof cfg.stressJson === 'string' && cfg.stressJson.trim()) txtStressJson.value = cfg.stressJson;
      if (chkHypothesis && typeof cfg.hypothesis === 'boolean') chkHypothesis.checked = cfg.hypothesis;
      if (selSort && ['impact_desc', 'base_desc', 'sim_desc', 'key_asc'].includes(String(cfg.sort || ''))) selSort.value = String(cfg.sort);
      setMethodUi();
    }

    function renderSavedScenarioOptions () {
      if (!selSavedScenarios) return;
      const names = Object.keys(state.savedScenarios || {}).sort((a, b) => a.localeCompare(b));
      const options = [`<option value="">—</option>`];
      for (const name of names) {
        options.push(`<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`);
      }
      selSavedScenarios.innerHTML = options.join('');
    }

    async function refreshSavedScenarios () {
      const endpoint = String(page?.dataset?.scenariosUrl || '').trim();
      try {
        const serverScenarios = await fetchScenariosFromServer(endpoint);
        state.savedScenarios = serverScenarios;
        saveScenarios(serverScenarios);
      } catch (e) {
        state.savedScenarios = loadScenarios();
      }
      renderSavedScenarioOptions();
    }

    function showError (message) {
      if (!elError) return;
      elError.classList.remove('d-none');
      elError.textContent = message || t('Erro ao carregar.');
    }

    function hideError () {
      if (!elError) return;
      elError.classList.add('d-none');
      elError.textContent = '';
    }

    function setBusy (busy) {
      if (btnLoad) btnLoad.disabled = !!busy;
      if (btnRun) btnRun.disabled = !!busy;
    }

    function resetFields () {
      if (selMetric) {
        selMetric.innerHTML = '';
        selMetric.disabled = true;
      }
      if (selDim) {
        selDim.innerHTML = '';
        selDim.disabled = true;
      }
    }

    function clearAdvancedOutput () {
      if (explanationBox) explanationBox.textContent = '';
      if (advancedTbody) advancedTbody.innerHTML = '';
      if (monteCarloHistMeta) monteCarloHistMeta.textContent = '';
      if (monteCarloHistBox) monteCarloHistBox.classList.add('d-none');
      if (monteCarloHistTooltip) monteCarloHistTooltip.classList.add('d-none');
      state.monteCarloChartData = null;
      state.monteCarloHoverBin = -1;
      if (hypothesisSummary) hypothesisSummary.textContent = '';
      if (hypothesisTbody) hypothesisTbody.innerHTML = '';
      if (hypothesisBox) hypothesisBox.classList.toggle('d-none', !chkHypothesis?.checked);
    }

    function drawMonteCarloHistogram (hoverBinIndex = -1) {
      if (!monteCarloHistCanvas || !state.monteCarloChartData) return;

      const chartData = state.monteCarloChartData;
      const bins = chartData.bins || [];
      if (!bins.length) return;

      const css = getComputedStyle(document.documentElement);
      const colorPrimary = (css.getPropertyValue('--bs-primary') || '').trim() || '#0d6efd';
      const colorSecondary = (css.getPropertyValue('--bs-secondary-color') || '').trim() || '#6c757d';
      const colorBorder = (css.getPropertyValue('--bs-border-color') || '').trim() || '#dee2e6';
      const colorDanger = (css.getPropertyValue('--bs-danger') || '').trim() || '#dc3545';
      const colorSuccess = (css.getPropertyValue('--bs-success') || '').trim() || '#198754';
      const colorWarning = (css.getPropertyValue('--bs-warning') || '').trim() || '#ffc107';
      const colorBody = (css.getPropertyValue('--bs-body-bg') || '').trim() || '#ffffff';

      const dpr = Math.max(1, Math.floor(window.devicePixelRatio || 1));
      const widthCss = Math.max(360, Math.floor(monteCarloHistCanvas.clientWidth || 700));
      const heightCss = Math.max(180, Math.floor(monteCarloHistCanvas.clientHeight || 220));
      monteCarloHistCanvas.width = widthCss * dpr;
      monteCarloHistCanvas.height = heightCss * dpr;

      const ctx = monteCarloHistCanvas.getContext('2d');
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, widthCss, heightCss);

      const padLeft = 44;
      const padRight = 12;
      const padTop = 20;
      const padBottom = 30;
      const chartW = Math.max(10, widthCss - padLeft - padRight);
      const chartH = Math.max(10, heightCss - padTop - padBottom);
      const chartX = padLeft;
      const chartY = padTop;
      const maxBin = Math.max(1, ...bins.map((b) => b.count));
      const bandW = chartW / bins.length;
      const barGap = Math.min(2, Math.max(1, bandW * 0.08));
      const barW = Math.max(1, bandW - (2 * barGap));

      chartData.layout = {
        left: chartX,
        top: chartY,
        width: chartW,
        height: chartH,
        bandW,
        barW,
        maxBin
      };

      ctx.fillStyle = colorBody;
      ctx.fillRect(chartX, chartY, chartW, chartH);

      ctx.strokeStyle = colorBorder;
      ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i += 1) {
        const y = chartY + Math.round((i / 4) * chartH) + 0.5;
        ctx.beginPath();
        ctx.moveTo(chartX, y);
        ctx.lineTo(chartX + chartW, y);
        ctx.stroke();
      }

      ctx.fillStyle = colorSecondary;
      ctx.font = '11px sans-serif';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillText('0', chartX - 6, chartY + chartH);
      ctx.fillText(formatNumber(maxBin / 2), chartX - 6, chartY + (chartH / 2));
      ctx.fillText(formatNumber(maxBin), chartX - 6, chartY);

      for (let i = 0; i < bins.length; i += 1) {
        const bin = bins[i];
        const h = (bin.count / maxBin) * chartH;
        const x = chartX + (i * bandW) + barGap;
        const y = chartY + chartH - h;
        bin.drawX = x;
        bin.drawY = y;
        bin.drawW = barW;
        bin.drawH = h;

        const isHover = i === hoverBinIndex;
        ctx.fillStyle = colorPrimary;
        ctx.globalAlpha = isHover ? 0.85 : 0.48;
        ctx.fillRect(x, y, barW, h);
        if (isHover) {
          ctx.globalAlpha = 1;
          ctx.strokeStyle = colorPrimary;
          ctx.lineWidth = 1;
          ctx.strokeRect(x + 0.5, y + 0.5, Math.max(0, barW - 1), Math.max(0, h - 1));
        }
      }
      ctx.globalAlpha = 1;

      const valueToX = (val) => {
        if (!Number.isFinite(Number(val))) return null;
        const ratio = (Number(val) - chartData.minVal) / chartData.range;
        return chartX + (Math.max(0, Math.min(1, ratio)) * chartW);
      };

      const drawMarker = (value, color, label, dashed = false) => {
        const x = valueToX(value);
        if (x === null) return;
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        if (dashed) ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.moveTo(x, chartY);
        ctx.lineTo(x, chartY + chartH);
        ctx.stroke();
        ctx.restore();

        ctx.fillStyle = color;
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        ctx.fillText(label, x, chartY - 2);
      };

      drawMarker(chartData.p10, colorWarning, 'P10', true);
      drawMarker(chartData.p50, colorSecondary, 'P50', true);
      drawMarker(chartData.p90, colorSuccess, 'P90', true);
      drawMarker(chartData.baseTotal, colorDanger, t('Base'), false);

      ctx.strokeStyle = colorBorder;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(chartX, chartY + chartH + 0.5);
      ctx.lineTo(chartX + chartW, chartY + chartH + 0.5);
      ctx.stroke();

      ctx.fillStyle = colorSecondary;
      ctx.font = '11px sans-serif';
      ctx.textBaseline = 'top';
      ctx.textAlign = 'left';
      ctx.fillText(formatNumber(chartData.minVal), chartX, chartY + chartH + 6);
      ctx.textAlign = 'right';
      ctx.fillText(formatNumber(chartData.maxVal), chartX + chartW, chartY + chartH + 6);

      if (monteCarloHistMeta) {
        monteCarloHistMeta.textContent = `${t('Base')}: ${formatNumber(chartData.baseTotal)} · P10: ${formatNumber(chartData.p10)} · P50: ${formatNumber(chartData.p50)} · P90: ${formatNumber(chartData.p90)} · ${t('Moyenne simulée')}: ${formatNumber(chartData.meanVal)} · ${t('Runs Monte Carlo')}: ${chartData.values.length}`;
      }
    }

    function renderMonteCarloHistogram (totals, baseTotal) {
      if (!monteCarloHistBox || !monteCarloHistCanvas) return;
      if (!Array.isArray(totals) || totals.length < 2) {
        monteCarloHistBox.classList.add('d-none');
        if (monteCarloHistMeta) monteCarloHistMeta.textContent = '';
        if (monteCarloHistTooltip) monteCarloHistTooltip.classList.add('d-none');
        state.monteCarloChartData = null;
        state.monteCarloHoverBin = -1;
        return;
      }

      const values = totals.filter((v) => Number.isFinite(Number(v))).map((v) => Number(v));
      if (values.length < 2) {
        monteCarloHistBox.classList.add('d-none');
        if (monteCarloHistMeta) monteCarloHistMeta.textContent = '';
        if (monteCarloHistTooltip) monteCarloHistTooltip.classList.add('d-none');
        state.monteCarloChartData = null;
        state.monteCarloHoverBin = -1;
        return;
      }

      monteCarloHistBox.classList.remove('d-none');

      const minVal = Math.min(...values);
      const maxVal = Math.max(...values);
      const range = Math.max(1e-9, maxVal - minVal);
      const binsCount = 20;
      const binWidth = range / binsCount;
      const bins = Array.from({ length: binsCount }, (_, i) => {
        const from = minVal + (i * binWidth);
        const to = i === binsCount - 1 ? maxVal : minVal + ((i + 1) * binWidth);
        return { from, to, count: 0 };
      });

      for (const v of values) {
        const idx = Math.max(0, Math.min(binsCount - 1, Math.floor((v - minVal) / binWidth)));
        bins[idx].count += 1;
      }

      state.monteCarloChartData = {
        values,
        bins,
        minVal,
        maxVal,
        range,
        baseTotal: Number(baseTotal || 0),
        p10: percentile(values, 10),
        p50: percentile(values, 50),
        p90: percentile(values, 90),
        meanVal: mean(values),
        layout: null
      };
      state.monteCarloHoverBin = -1;
      if (monteCarloHistTooltip) monteCarloHistTooltip.classList.add('d-none');

      drawMonteCarloHistogram(-1);
    }

    if (monteCarloHistCanvas) {
      monteCarloHistCanvas.addEventListener('mousemove', function (event) {
        const chartData = state.monteCarloChartData;
        const layout = chartData?.layout;
        if (!chartData || !layout) return;

        const rect = monteCarloHistCanvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        const inChart = (
          x >= layout.left &&
          x <= (layout.left + layout.width) &&
          y >= layout.top &&
          y <= (layout.top + layout.height)
        );

        if (!inChart) {
          if (state.monteCarloHoverBin !== -1) {
            state.monteCarloHoverBin = -1;
            drawMonteCarloHistogram(-1);
          }
          if (monteCarloHistTooltip) monteCarloHistTooltip.classList.add('d-none');
          return;
        }

        const idx = Math.max(0, Math.min(chartData.bins.length - 1, Math.floor((x - layout.left) / layout.bandW)));
        if (idx !== state.monteCarloHoverBin) {
          state.monteCarloHoverBin = idx;
          drawMonteCarloHistogram(idx);
        }

        if (!monteCarloHistTooltip) return;
        const bin = chartData.bins[idx];
        if (!bin) return;

        monteCarloHistTooltip.innerHTML = `${formatNumber(bin.from)} → ${formatNumber(bin.to)}<br>${t('Runs Monte Carlo')}: ${formatNumber(bin.count)}`;
        monteCarloHistTooltip.classList.remove('d-none');

        const hostRect = (monteCarloHistWrap || monteCarloHistBox).getBoundingClientRect();
        let left = event.clientX - hostRect.left + 10;
        let top = event.clientY - hostRect.top - 6;
        left = Math.min(left, Math.max(4, hostRect.width - monteCarloHistTooltip.offsetWidth - 6));
        top = Math.min(Math.max(4, top), Math.max(4, hostRect.height - monteCarloHistTooltip.offsetHeight - 4));
        monteCarloHistTooltip.style.left = `${left}px`;
        monteCarloHistTooltip.style.top = `${top}px`;
      });

      monteCarloHistCanvas.addEventListener('mouseleave', function () {
        if (state.monteCarloHoverBin !== -1) {
          state.monteCarloHoverBin = -1;
          drawMonteCarloHistogram(-1);
        }
        if (monteCarloHistTooltip) monteCarloHistTooltip.classList.add('d-none');
      });

      window.addEventListener('resize', function () {
        if (!state.monteCarloChartData) return;
        drawMonteCarloHistogram(state.monteCarloHoverBin);
      });
    }

    function fillSelectors () {
      resetFields();
      const numericFields = state.fields.filter((f) => f.numeric);

      if (!numericFields.length) {
        showError(t('Nenhuma coluna numérica encontrada.'));
        return;
      }

      if (selMetric) {
        selMetric.innerHTML = numericFields
          .map((f) => `<option value="${escapeHtml(f.name)}">${escapeHtml(f.name)}</option>`)
          .join('');
        selMetric.disabled = false;
      }

      if (selDim) {
        const options = [`<option value="">${t('Não agrupado')}</option>`];
        for (const f of state.fields) {
          options.push(`<option value="${escapeHtml(f.name)}">${escapeHtml(f.name)}</option>`);
        }
        selDim.innerHTML = options.join('');
        selDim.disabled = false;
      }
    }

    async function loadData () {
      hideError();
      if (resultsCard) resultsCard.classList.add('d-none');
      clearAdvancedOutput();

      const questionId = String(selQuestion?.value || '').trim();
      if (!questionId) {
        showError(t('Selecione uma pergunta.'));
        resetFields();
        state.columns = [];
        state.rows = [];
        state.fields = [];
        return false;
      }

      let params = {};
      try {
        params = parseParams(txtParams?.value || '{}');
      } catch (e) {
        showError(e.message || t('Parâmetros inválidos.'));
        return false;
      }

      const endpoint = buildQuestionDataUrl(page.dataset.questionUrlTemplate, questionId);
      if (!endpoint) {
        showError(t('Erro ao carregar.'));
        return false;
      }

      setBusy(true);
      try {
        const csrf = getCsrfToken();
        const res = await fetch(endpoint, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            ...(csrf ? { 'X-CSRFToken': csrf, 'X-CSRF-Token': csrf } : {})
          },
          body: JSON.stringify({ params })
        });
        const raw = await res.text();
        let data = {};
        try {
          data = raw ? JSON.parse(raw) : {};
        } catch (e) {
          data = {};
        }
        if (!res.ok) {
          throw new Error(extractErrorMessage(raw, data));
        }

        state.columns = Array.isArray(data.columns) ? data.columns : [];
        state.rows = Array.isArray(data.rows) ? data.rows : [];
        if (!state.columns.length || !state.rows.length) {
          state.fields = [];
          resetFields();
          showError(t('Sem dados para simulação.'));
          return false;
        }

        state.fields = inferColumns(state.rows, state.columns);
        fillSelectors();
        return true;
      } catch (err) {
        resetFields();
        showError(err && err.message ? err.message : t('Erro ao carregar.'));
        return false;
      } finally {
        setBusy(false);
      }
    }

    function runSimulation () {
      hideError();
      const metric = String(selMetric?.value || '').trim();
      if (!metric) {
        showError(t('Selecione uma métrica numérica.'));
        return;
      }

      const metricField = state.fields.find((f) => f.name === metric);
      if (!metricField) {
        showError(t('Selecione uma métrica numérica.'));
        return;
      }

      const dim = String(selDim?.value || '').trim();
      const dimField = dim ? state.fields.find((f) => f.name === dim) : null;
      const pct = toNumber(inpPct?.value);
      const delta = toNumber(inpDelta?.value);
      const method = String(selMethod?.value || 'deterministic');
      const distribution = String(selDist?.value || 'normal');
      const volatility = clamp(toNumber(inpVol?.value) ?? 10, 0, 500);
      const runs = Math.round(clamp(toNumber(inpRuns?.value) ?? 1000, 100, 5000));
      const sortMode = String(selSort?.value || 'impact_desc');
      const pctFactor = 1 + ((pct === null ? 0 : pct) / 100);
      const addDelta = (delta === null ? 0 : delta);

      const simRows = buildSimulationRows(state.rows, metricField, dimField);
      if (!simRows.length) {
        showError(t('Sem dados para simulação.'));
        return;
      }
      const baseSample = simRows.map((r) => r.metric);
      const { groups: baseGroups, baseTotal } = baseGroupStats(simRows);
      const expectedGroupSims = new Map();
      let simulatedTotal = 0;
      const advancedRows = [];
      let hypothesis = null;
      let simSample = [];
      let monteCarloTotals = null;

      if (method === 'stress') {
        let scenarios;
        try {
          scenarios = normalizeStressScenarios(txtStressJson?.value || DEFAULT_STRESS_TEXT);
        } catch (err) {
          showError(err?.message || t('JSON de stress invalide.'));
          return;
        }

        let expectedShockPct = 0;
        const scenarioTotals = [];
        for (const scenario of scenarios) {
          expectedShockPct += scenario.pct * scenario.prob;
          let scenarioTotal = 0;
          const sFactor = 1 + (((pct === null ? 0 : pct) + scenario.pct) / 100);
          for (const row of simRows) {
            const sim = (row.metric * sFactor) + addDelta;
            scenarioTotal += sim;
            addToMap(expectedGroupSims, row.key, sim * scenario.prob);
          }
          scenarioTotals.push({ name: scenario.name, prob: scenario.prob, total: scenarioTotal });
          advancedRows.push({
            label: `${scenario.name} (${formatNumber(scenario.prob * 100)}%)`,
            value: scenarioTotal,
            details: `${t('Choc')} ${formatNumber(scenario.pct)}%`
          });
        }
        simulatedTotal = scenarioTotals.reduce((acc, s) => acc + (s.total * s.prob), 0);
        simSample = simRows.map((row) => (row.metric * (1 + (((pct === null ? 0 : pct) + expectedShockPct) / 100))) + addDelta);
        const lossProb = scenarioTotals.filter((s) => s.total < baseTotal).reduce((acc, s) => acc + s.prob, 0) * 100;
        advancedRows.unshift({
          label: t('Valeur attendue (pondérée)'),
          value: simulatedTotal,
          details: `${t('Probabilité de baisse vs base')}: ${formatNumber(lossProb)}%`
        });
      } else if (method === 'montecarlo') {
        const totals = [];
        const groupSums = new Map();
        for (const key of baseGroups.keys()) groupSums.set(key, 0);

        for (let run = 0; run < runs; run += 1) {
          let runTotal = 0;
          const runGroup = new Map();
          for (const row of simRows) {
            const center = (row.metric * pctFactor) + addDelta;
            const shock = drawShockMultiplier(distribution, volatility);
            const sim = center * shock;
            runTotal += sim;
            addToMap(runGroup, row.key, sim);
          }
          totals.push(runTotal);
          for (const [key, value] of runGroup.entries()) {
            addToMap(groupSums, key, value);
          }
        }

        simulatedTotal = mean(totals);
        monteCarloTotals = totals;
        simSample = totals;
        for (const [key, value] of groupSums.entries()) {
          expectedGroupSims.set(key, value / runs);
        }
        const p5 = percentile(totals, 5);
        const p50 = percentile(totals, 50);
        const p95 = percentile(totals, 95);
        const lossProb = (totals.filter((v) => v < baseTotal).length / totals.length) * 100;
        advancedRows.push({ label: 'P5', value: p5, details: t('Scénario prudent') });
        advancedRows.push({ label: 'P50', value: p50, details: t('Médiane') });
        advancedRows.push({ label: 'P95', value: p95, details: t('Scénario favorable') });
        advancedRows.push({
          label: t('Probabilité de baisse vs base'),
          value: lossProb,
          details: '%'
        });
        advancedRows.push({
          label: t('Écart-type des runs'),
          value: stdDev(totals),
          details: t('Dispersion des résultats simulés')
        });
      } else {
        for (const row of simRows) {
          const sim = (row.metric * pctFactor) + addDelta;
          simulatedTotal += sim;
          addToMap(expectedGroupSims, row.key, sim);
          simSample.push(sim);
        }
        advancedRows.push({
          label: t('Hypothèse centrale'),
          value: simulatedTotal,
          details: `${t('Variation')} ${formatNumber(pct ?? 0)}% + ${t('Delta')} ${formatNumber(addDelta)}`
        });
      }

      const mergedGroups = Array.from(baseGroups.values()).map((baseItem) => ({
        key: baseItem.key,
        rows: baseItem.rows,
        base: baseItem.base,
        sim: expectedGroupSims.get(baseItem.key) || 0
      }));

      const ordered = mergedGroups.sort((a, b) => {
        const aDiff = a.sim - a.base;
        const bDiff = b.sim - b.base;
        if (sortMode === 'base_desc') return b.base - a.base;
        if (sortMode === 'sim_desc') return b.sim - a.sim;
        if (sortMode === 'key_asc') return String(a.key).localeCompare(String(b.key));
        return Math.abs(bDiff) - Math.abs(aDiff);
      });
      const limited = ordered.slice(0, 300);

      const diff = simulatedTotal - baseTotal;
      const diffPct = baseTotal !== 0 ? (diff / baseTotal) * 100 : 0;

      if (kpiBase) kpiBase.textContent = formatNumber(baseTotal);
      if (kpiSim) kpiSim.textContent = formatNumber(simulatedTotal);
      if (kpiDiff) kpiDiff.textContent = formatNumber(diff);
      if (kpiDiffPct) kpiDiffPct.textContent = `${formatNumber(diffPct)}%`;
      if (thDim) thDim.textContent = t('Dimensão');

      if (tbody) {
        tbody.innerHTML = limited.map((item) => {
          const deltaRow = item.sim - item.base;
          return `
            <tr>
              <td>${escapeHtml(item.key)}</td>
              <td class="text-end">${formatNumber(item.rows)}</td>
              <td class="text-end">${formatNumber(item.base)}</td>
              <td class="text-end">${formatNumber(item.sim)}</td>
              <td class="text-end ${deltaRow >= 0 ? 'text-success' : 'text-danger'}">${formatNumber(deltaRow)}</td>
            </tr>
          `;
        }).join('');
      }

      if (limitNote) limitNote.classList.toggle('d-none', ordered.length <= 300);

      if (explanationBox) {
        const expl = String(buildExplanation(method, distribution, runs) || '').trim();
        explanationBox.textContent = expl || t('Analyse avancée: résultats déterministes/probabilistes, dispersion et significativité statistique.');
      }

      if (!advancedRows.length) {
        advancedRows.push({
          label: t('Valeur simulée'),
          value: simulatedTotal,
          details: t('Aucun indicateur avancé disponible pour cette configuration.')
        });
      }

      if (advancedTbody) {
        advancedTbody.innerHTML = advancedRows.map((row) => `
          <tr>
            <td>${escapeHtml(String(row.label || ''))}</td>
            <td class="text-end">${formatNumber(row.value)}</td>
            <td class="text-end">${escapeHtml(String(row.details || ''))}</td>
          </tr>
        `).join('');
      }

      if (method === 'montecarlo') {
        renderMonteCarloHistogram(monteCarloTotals, baseTotal);
      } else if (monteCarloHistBox) {
        monteCarloHistBox.classList.add('d-none');
        if (monteCarloHistMeta) monteCarloHistMeta.textContent = '';
        if (monteCarloHistTooltip) monteCarloHistTooltip.classList.add('d-none');
        state.monteCarloChartData = null;
        state.monteCarloHoverBin = -1;
      }

      if (chkHypothesis?.checked) {
        if (method === 'montecarlo') {
          hypothesis = hypothesisTestOneSample(baseTotal, simSample);
        } else {
          hypothesis = hypothesisTestTwoSample(baseSample, simSample);
        }
      }

      if (hypothesisBox) hypothesisBox.classList.toggle('d-none', !chkHypothesis?.checked);
      if (hypothesisSummary) {
        hypothesisSummary.textContent = hypothesis
          ? hypothesis.summary
          : t('Pas assez de variance/données pour calculer un test fiable.');
      }
      if (hypothesisTbody) {
        if (hypothesis) {
          const rows = [
            [t('Statistique z'), hypothesis.z, '', 'number'],
            ['p-value', hypothesis.p, hypothesis.significant ? t('Significatif à 5%') : t('Non significatif à 5%'), 'pvalue'],
            [t('Erreur standard'), hypothesis.se, '', 'number']
          ];
          if (method === 'montecarlo') {
            rows.push([t('Moyenne simulée'), hypothesis.m, '', 'number']);
            rows.push([t('Moyenne nulle (base)'), hypothesis.nullMean, '', 'number']);
          } else {
            rows.push([t('Moyenne base'), hypothesis.m1, '', 'number']);
            rows.push([t('Moyenne simulée'), hypothesis.m2, '', 'number']);
          }
          hypothesisTbody.innerHTML = rows.map((r) => {
            const valueText = r[3] === 'pvalue' ? formatPValue(r[1]) : formatNumber(r[1]);
            return `
            <tr>
              <td>${escapeHtml(String(r[0]))}</td>
              <td class="text-end">${escapeHtml(String(valueText))}</td>
              <td class="text-end">${escapeHtml(String(r[2]))}</td>
            </tr>
          `;
          }).join('');
        } else {
          hypothesisTbody.innerHTML = '';
        }
      }

      if (resultsCard) resultsCard.classList.remove('d-none');
      persistCurrentPrefs();
    }

    btnLoad?.addEventListener('click', loadData);

    selQuestion?.addEventListener('change', async function () {
      state.columns = [];
      state.rows = [];
      state.fields = [];
      await loadData();
    });

    selSort?.addEventListener('change', function () {
      persistCurrentPrefs();
      if (state.rows.length) runSimulation();
    });
    selMethod?.addEventListener('change', function () {
      setMethodUi();
      persistCurrentPrefs();
      if (state.rows.length) runSimulation();
    });
    inpPct?.addEventListener('change', persistCurrentPrefs);
    inpDelta?.addEventListener('change', persistCurrentPrefs);
    selDist?.addEventListener('change', persistCurrentPrefs);
    inpVol?.addEventListener('change', persistCurrentPrefs);
    inpRuns?.addEventListener('change', persistCurrentPrefs);
    txtStressJson?.addEventListener('change', persistCurrentPrefs);
    chkHypothesis?.addEventListener('change', function () {
      persistCurrentPrefs();
      if (state.rows.length) runSimulation();
    });

    btnSaveScenario?.addEventListener('click', async function () {
      const name = String(inpScenarioName?.value || '').trim();
      if (!name) {
        showError(t('Donnez un nom au scénario avant sauvegarde.'));
        return;
      }
      const snapshot = scenarioSnapshot();
      const endpoint = String(page?.dataset?.scenariosUrl || '').trim();
      try {
        const serverScenarios = await saveScenarioToServer(endpoint, name, snapshot);
        state.savedScenarios = serverScenarios;
        saveScenarios(serverScenarios);
      } catch (err) {
        const localScenarios = loadScenarios();
        localScenarios[name] = snapshot;
        state.savedScenarios = localScenarios;
        saveScenarios(localScenarios);
      }
      renderSavedScenarioOptions();
      if (selSavedScenarios) selSavedScenarios.value = name;
      hideError();
    });

    btnLoadScenario?.addEventListener('click', async function () {
      const selected = String(selSavedScenarios?.value || '').trim();
      if (!selected) {
        showError(t('Sélectionnez un scénario enregistré.'));
        return;
      }
      const cfg = (state.savedScenarios || {})[selected];
      if (!cfg) {
        showError(t('Scénario introuvable.'));
        return;
      }
      applyScenarioSnapshot(cfg);
      persistCurrentPrefs();
      const loaded = await loadData();
      if (!loaded) return;
      if (selMetric && cfg.metric) selMetric.value = String(cfg.metric);
      if (selDim && typeof cfg.dim === 'string') selDim.value = cfg.dim;
      runSimulation();
    });

    btnDeleteScenario?.addEventListener('click', async function () {
      const selected = String(selSavedScenarios?.value || '').trim();
      if (!selected) {
        showError(t('Sélectionnez un scénario à supprimer.'));
        return;
      }
      const endpoint = String(page?.dataset?.scenariosUrl || '').trim();
      try {
        const serverScenarios = await deleteScenarioFromServer(endpoint, selected);
        state.savedScenarios = serverScenarios;
        saveScenarios(serverScenarios);
      } catch (err) {
        const localScenarios = loadScenarios();
        if (Object.prototype.hasOwnProperty.call(localScenarios, selected)) {
          delete localScenarios[selected];
          state.savedScenarios = localScenarios;
          saveScenarios(localScenarios);
        }
      }
      renderSavedScenarioOptions();
      hideError();
    });

    btnRun?.addEventListener('click', async function () {
      if (!state.rows.length) {
        const loaded = await loadData();
        if (!loaded) return;
      }
      runSimulation();
    });

    setMethodUi();
    refreshSavedScenarios();
    clearAdvancedOutput();
  });
})();
