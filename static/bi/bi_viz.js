/* global echarts, $ */

// Minimal BI visualization layer:
// - ECharts for charts (bar/line/area/pie/scatter/gauge)
// - PivotTable.js for pivots
// - Client-side filters + drill-down (cross-filter)

window.BI = window.BI || {};

(function () {
  let _biModal = null;
  const t = (window.t ? window.t : (s) => s);

  function ensureModal () {
    if (_biModal) return _biModal;
    const host = document.createElement('div');
    host.innerHTML = `
      <div class="modal fade" id="biVizModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="biVizModalTitle">${t('Information')}</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="${t('Fechar')}"></button>
            </div>
            <div class="modal-body" id="biVizModalBody"></div>
            <div class="modal-footer">
              <button type="button" class="btn btn-primary" data-bs-dismiss="modal">${t('OK')}</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(host.firstElementChild);
    const el = document.getElementById('biVizModal');
    _biModal = {
      title: document.getElementById('biVizModalTitle'),
      body: document.getElementById('biVizModalBody'),
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

  function normGeoText(v) {
    return String(v || '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[.'`´’]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  const COUNTRY_ALIAS_MAP = {
    france: 'France',
    espagne: 'Spain', espana: 'Spain', spain: 'Spain',
    portugal: 'Portugal',
    allemagne: 'Germany', alemanha: 'Germany', germany: 'Germany', deutschland: 'Germany',
    italie: 'Italy', italia: 'Italy', italy: 'Italy',
    'royaume uni': 'United Kingdom', uk: 'United Kingdom', 'united kingdom': 'United Kingdom', england: 'United Kingdom',
    irlande: 'Ireland', ireland: 'Ireland',
    suisse: 'Switzerland', switzerland: 'Switzerland',
    belgique: 'Belgium', belgica: 'Belgium', belgium: 'Belgium',
    'pays bas': 'Netherlands', netherlands: 'Netherlands', hollande: 'Netherlands',
    luxembourg: 'Luxembourg',
    autriche: 'Austria', austria: 'Austria',
    pologne: 'Poland', polonia: 'Poland', poland: 'Poland',
    'republique tcheque': 'Czech Republic', 'czech republic': 'Czech Republic', tchequie: 'Czech Republic',
    slovaquie: 'Slovakia', slovakia: 'Slovakia',
    hongrie: 'Hungary', hungria: 'Hungary', hungary: 'Hungary',
    roumanie: 'Romania', romania: 'Romania',
    bulgarie: 'Bulgaria', bulgaria: 'Bulgaria',
    grece: 'Greece', grecia: 'Greece', greece: 'Greece',
    suede: 'Sweden', suedia: 'Sweden', sweden: 'Sweden',
    norvege: 'Norway', noruega: 'Norway', norway: 'Norway',
    danemark: 'Denmark', dinamarca: 'Denmark', denmark: 'Denmark',
    finlande: 'Finland', finlandia: 'Finland', finland: 'Finland',
    islande: 'Iceland', iceland: 'Iceland',
    russie: 'Russia', russia: 'Russia', 'federation de russie': 'Russia',
    ukraine: 'Ukraine',
    bielorussie: 'Belarus', belarus: 'Belarus',
    turquie: 'Turkey', turquia: 'Turkey', turkey: 'Turkey',
    maroc: 'Morocco', morocco: 'Morocco',
    algerie: 'Algeria', algeria: 'Algeria',
    tunisie: 'Tunisia', tunisia: 'Tunisia',
    egypte: 'Egypt', egypt: 'Egypt',
    'afrique du sud': 'South Africa', 'south africa': 'South Africa',
    nigeria: 'Nigeria',
    kenya: 'Kenya',
    'etats unis': 'United States of America', etatsunis: 'United States of America', usa: 'United States of America', 'u s a': 'United States of America', 'united states': 'United States of America',
    canada: 'Canada',
    mexique: 'Mexico', mexico: 'Mexico',
    bresil: 'Brazil', brasil: 'Brazil', brazil: 'Brazil',
    argentine: 'Argentina', argentina: 'Argentina',
    chili: 'Chile', chile: 'Chile',
    colombie: 'Colombia', colombia: 'Colombia',
    perou: 'Peru', peru: 'Peru',
    bolivie: 'Bolivia', bolivia: 'Bolivia',
    venezuela: 'Venezuela',
    equateur: 'Ecuador', ecuador: 'Ecuador',
    paraguay: 'Paraguay',
    uruguay: 'Uruguay',
    chine: 'China', china: 'China',
    japon: 'Japan', japan: 'Japan',
    'coree du sud': 'South Korea', 'south korea': 'South Korea',
    'coree du nord': 'North Korea', 'north korea': 'North Korea',
    inde: 'India', india: 'India',
    pakistan: 'Pakistan',
    bangladesh: 'Bangladesh',
    indonesie: 'Indonesia', indonesia: 'Indonesia',
    thailande: 'Thailand', thailand: 'Thailand',
    vietnam: 'Vietnam',
    malaisie: 'Malaysia', malaysia: 'Malaysia',
    philippines: 'Philippines',
    singapour: 'Singapore', singapore: 'Singapore',
    australie: 'Australia', australia: 'Australia',
    'nouvelle zelande': 'New Zealand', 'new zealand': 'New Zealand'
  };

  function canonicalCountryName(v) {
    const raw = String(v || '').trim();
    if (!raw) return '';
    const n = normGeoText(raw);
    return COUNTRY_ALIAS_MAP[n] || raw;
  }

  const IT_REGION_ALIAS_MAP = {
    abruzzo: 'Abruzzo',
    basilicata: 'Basilicata',
    calabria: 'Calabria',
    campania: 'Campania',
    'emilia romagna': 'Emilia-Romagna',
    'friuli venezia giulia': 'Friuli-Venezia Giulia',
    lazio: 'Lazio',
    liguria: 'Liguria',
    lombardia: 'Lombardy', lombardy: 'Lombardy',
    marche: 'Marche',
    molise: 'Molise',
    piemonte: 'Piedmont', piedmont: 'Piedmont',
    puglia: 'Apulia', apulia: 'Apulia',
    sardegna: 'Sardinia', sardinia: 'Sardinia',
    sicilia: 'Sicily', sicily: 'Sicily',
    toscana: 'Tuscany', tuscany: 'Tuscany',
    'trentino alto adige': 'Trentino-Alto Adige',
    umbria: 'Umbria',
    'valle d aosta': "Aosta Valley", "vallee d aoste": "Aosta Valley", 'aosta valley': 'Aosta Valley',
    veneto: 'Veneto'
  };

  const IT_REGION_CENTERS = {
    Abruzzo: [13.93, 42.35],
    Basilicata: [16.50, 40.64],
    Calabria: [16.25, 39.30],
    Campania: [14.80, 40.95],
    'Emilia-Romagna': [11.35, 44.50],
    'Friuli-Venezia Giulia': [13.00, 46.10],
    Lazio: [12.70, 41.90],
    Liguria: [8.95, 44.40],
    Lombardy: [9.95, 45.60],
    Marche: [13.00, 43.50],
    Molise: [14.70, 41.60],
    Piedmont: [7.90, 45.10],
    Apulia: [16.80, 41.10],
    Sardinia: [9.00, 40.10],
    Sicily: [14.10, 37.60],
    Tuscany: [11.10, 43.40],
    'Trentino-Alto Adige': [11.30, 46.50],
    Umbria: [12.50, 43.10],
    'Aosta Valley': [7.40, 45.73],
    Veneto: [12.20, 45.50]
  };

  const BR_STATE_ALIAS_MAP = {
    ac: 'Acre', acre: 'Acre',
    al: 'Alagoas', alagoas: 'Alagoas',
    ap: 'Amapa', amapa: 'Amapa', amapá: 'Amapa',
    am: 'Amazonas', amazonas: 'Amazonas',
    ba: 'Bahia', bahia: 'Bahia',
    ce: 'Ceara', ceara: 'Ceara', ceará: 'Ceara',
    df: 'Distrito Federal', 'distrito federal': 'Distrito Federal',
    es: 'Espirito Santo', 'espirito santo': 'Espirito Santo', 'espírito santo': 'Espirito Santo',
    go: 'Goias', goias: 'Goias', goiás: 'Goias',
    ma: 'Maranhao', maranhao: 'Maranhao', maranhão: 'Maranhao',
    mt: 'Mato Grosso', 'mato grosso': 'Mato Grosso',
    ms: 'Mato Grosso do Sul', 'mato grosso do sul': 'Mato Grosso do Sul',
    mg: 'Minas Gerais', 'minas gerais': 'Minas Gerais',
    pa: 'Para', para: 'Para', pará: 'Para',
    pb: 'Paraiba', paraiba: 'Paraiba', paraíba: 'Paraiba',
    pr: 'Parana', parana: 'Parana', paraná: 'Parana',
    pe: 'Pernambuco', pernambuco: 'Pernambuco',
    pi: 'Piaui', piaui: 'Piaui', piauí: 'Piaui',
    rj: 'Rio de Janeiro', 'rio de janeiro': 'Rio de Janeiro',
    rn: 'Rio Grande do Norte', 'rio grande do norte': 'Rio Grande do Norte',
    rs: 'Rio Grande do Sul', 'rio grande do sul': 'Rio Grande do Sul',
    ro: 'Rondonia', rondonia: 'Rondonia', rondônia: 'Rondonia',
    rr: 'Roraima', roraima: 'Roraima',
    sc: 'Santa Catarina', 'santa catarina': 'Santa Catarina',
    sp: 'Sao Paulo', 'sao paulo': 'Sao Paulo', 'são paulo': 'Sao Paulo',
    se: 'Sergipe', sergipe: 'Sergipe',
    to: 'Tocantins', tocantins: 'Tocantins'
  };

  const BR_STATE_CENTERS = {
    Acre: [-67.81, -9.97],
    Alagoas: [-35.74, -9.66],
    Amapa: [-51.07, 0.03],
    Amazonas: [-60.02, -3.10],
    Bahia: [-38.50, -12.97],
    Ceara: [-38.54, -3.73],
    'Distrito Federal': [-47.88, -15.79],
    'Espirito Santo': [-40.31, -20.32],
    Goias: [-49.25, -16.68],
    Maranhao: [-44.30, -2.53],
    'Mato Grosso': [-56.10, -15.60],
    'Mato Grosso do Sul': [-54.62, -20.47],
    'Minas Gerais': [-43.94, -19.92],
    Para: [-48.49, -1.45],
    Paraiba: [-34.88, -7.12],
    Parana: [-49.27, -25.43],
    Pernambuco: [-34.88, -8.05],
    Piaui: [-42.80, -5.09],
    'Rio de Janeiro': [-43.20, -22.90],
    'Rio Grande do Norte': [-35.21, -5.79],
    'Rio Grande do Sul': [-51.23, -30.03],
    Rondonia: [-63.90, -8.76],
    Roraima: [-60.67, 2.82],
    'Santa Catarina': [-48.55, -27.59],
    'Sao Paulo': [-46.63, -23.55],
    Sergipe: [-37.07, -10.91],
    Tocantins: [-48.33, -10.18]
  };

  const FR_DEPT_ALIAS_MAP = {
    '75': 'Paris', paris: 'Paris',
    '13': 'Bouches-du-Rhone', 'bouches du rhone': 'Bouches-du-Rhone', 'bouches-du-rhone': 'Bouches-du-Rhone',
    '69': 'Rhone', rhone: 'Rhone', rhône: 'Rhone',
    '59': 'Nord', nord: 'Nord',
    '33': 'Gironde', gironde: 'Gironde',
    '31': 'Haute-Garonne', 'haute garonne': 'Haute-Garonne',
    '44': 'Loire-Atlantique', 'loire atlantique': 'Loire-Atlantique',
    '34': 'Herault', herault: 'Herault', hérault: 'Herault',
    '06': 'Alpes-Maritimes', 'alpes maritimes': 'Alpes-Maritimes',
    '83': 'Var', var: 'Var',
    '76': 'Seine-Maritime', 'seine maritime': 'Seine-Maritime',
    '77': 'Seine-et-Marne', 'seine et marne': 'Seine-et-Marne',
    '78': 'Yvelines', yvelines: 'Yvelines',
    '91': 'Essonne', essonne: 'Essonne',
    '92': 'Hauts-de-Seine', 'hauts de seine': 'Hauts-de-Seine',
    '93': 'Seine-Saint-Denis', 'seine saint denis': 'Seine-Saint-Denis',
    '94': 'Val-de-Marne', 'val de marne': 'Val-de-Marne',
    '95': "Val-d'Oise", 'val d oise': "Val-d'Oise",
    '67': 'Bas-Rhin', 'bas rhin': 'Bas-Rhin',
    '68': 'Haut-Rhin', 'haut rhin': 'Haut-Rhin',
    '38': 'Isere', isere: 'Isere', isère: 'Isere',
    '74': 'Haute-Savoie', 'haute savoie': 'Haute-Savoie',
    '73': 'Savoie', savoie: 'Savoie',
    '2a': 'Corse-du-Sud', 'corse du sud': 'Corse-du-Sud',
    '2b': 'Haute-Corse', 'haute corse': 'Haute-Corse',
    '971': 'Guadeloupe', guadeloupe: 'Guadeloupe',
    '972': 'Martinique', martinique: 'Martinique',
    '973': 'Guyane', guyane: 'Guyane',
    '974': 'Reunion', reunion: 'Reunion', réunion: 'Reunion',
    '976': 'Mayotte', mayotte: 'Mayotte'
  };

  const FR_DEPT_CENTERS = {
    Paris: [2.35, 48.86],
    'Bouches-du-Rhone': [5.37, 43.30],
    Rhone: [4.84, 45.76],
    Nord: [3.06, 50.63],
    Gironde: [-0.58, 44.84],
    'Haute-Garonne': [1.44, 43.60],
    'Loire-Atlantique': [-1.55, 47.22],
    Herault: [3.88, 43.61],
    'Alpes-Maritimes': [7.26, 43.70],
    Var: [6.13, 43.12],
    'Seine-Maritime': [1.10, 49.44],
    'Seine-et-Marne': [2.70, 48.54],
    Yvelines: [2.13, 48.80],
    Essonne: [2.45, 48.62],
    'Hauts-de-Seine': [2.25, 48.89],
    'Seine-Saint-Denis': [2.45, 48.91],
    'Val-de-Marne': [2.47, 48.79],
    "Val-d'Oise": [2.10, 49.04],
    'Bas-Rhin': [7.75, 48.58],
    'Haut-Rhin': [7.36, 48.08],
    Isere: [5.72, 45.19],
    'Haute-Savoie': [6.12, 45.90],
    Savoie: [5.92, 45.57],
    'Corse-du-Sud': [8.74, 41.92],
    'Haute-Corse': [9.45, 42.70],
    Guadeloupe: [-61.55, 16.24],
    Martinique: [-61.02, 14.64],
    Guyane: [-53.13, 3.95],
    Reunion: [55.45, -20.88],
    Mayotte: [45.15, -12.78]
  };

  function canonicalByAlias(v, aliasMap) {
    const raw = String(v || '').trim();
    if (!raw) return '';
    const key = normGeoText(raw);
    return aliasMap[key] || raw;
  }

  function territoryGeoPoints(rows, keyIdx, metIdx, canonicalFn, centerMap, latIdx, lonIdx) {
    const agg = new Map();
    for (const r of rows) {
      if (!r || keyIdx < 0 || keyIdx >= r.length || metIdx < 0 || metIdx >= r.length) continue;
      const territory = canonicalFn(r[keyIdx]);
      const metric = Number(r[metIdx]);
      if (!territory || !Number.isFinite(metric)) continue;
      if (!agg.has(territory)) {
        agg.set(territory, { value: 0, latSum: 0, lonSum: 0, geoN: 0 });
      }
      const rec = agg.get(territory);
      rec.value += metric;
      if (latIdx >= 0 && lonIdx >= 0 && latIdx < r.length && lonIdx < r.length) {
        const lat = Number(r[latIdx]);
        const lon = Number(r[lonIdx]);
        if (Number.isFinite(lat) && Number.isFinite(lon)) {
          rec.latSum += lat;
          rec.lonSum += lon;
          rec.geoN += 1;
        }
      }
    }

    const points = [];
    for (const [name, rec] of agg.entries()) {
      let coord = centerMap[name] || null;
      if (!coord && rec.geoN > 0) {
        coord = [rec.lonSum / rec.geoN, rec.latSum / rec.geoN];
      }
      if (!coord) continue;
      points.push({ name, value: [coord[0], coord[1], Number(rec.value.toFixed(2))] });
    }
    return points;
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
    const srcRows = data.rows || [];
    const cfg = arguments[2] || {};

    function esc(v) {
      return String(v == null ? '' : v)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    function parseNum(v) {
      const n = Number(String(v == null ? '' : v).replace(',', '.'));
      return Number.isFinite(n) ? n : null;
    }

    function cmpValues(a, b) {
      const an = parseNum(a);
      const bn = parseNum(b);
      if (an != null && bn != null) return an - bn;
      return String(a == null ? '' : a).localeCompare(String(b == null ? '' : b), undefined, { numeric: true, sensitivity: 'base' });
    }

    const stateKey = container.getAttribute('data-table-state-key') || '';
    const allowedPageSizes = [10, 25, 50, 100, -1];
    const defaultPageSize = Number(cfg.table_page_size || cfg.page_size || 25);
    const state = {
      sortIndex: -1,
      sortDir: 'asc',
      page: 1,
      pageSize: allowedPageSizes.includes(defaultPageSize) ? defaultPageSize : 25
    };

    if (stateKey) {
      try {
        const raw = localStorage.getItem(stateKey);
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed && typeof parsed === 'object') {
            if (Number.isInteger(parsed.sortIndex)) state.sortIndex = parsed.sortIndex;
            if (parsed.sortDir === 'asc' || parsed.sortDir === 'desc') state.sortDir = parsed.sortDir;
            if (Number.isInteger(parsed.page) && parsed.page > 0) state.page = parsed.page;
            if (allowedPageSizes.includes(Number(parsed.pageSize))) state.pageSize = Number(parsed.pageSize);
          }
        }
      } catch (e) {}
    }

    function persistState() {
      if (!stateKey) return;
      try {
        localStorage.setItem(stateKey, JSON.stringify(state));
      } catch (e) {}
    }

    function processedRows() {
      const rows = srcRows.slice();
      if (state.sortIndex >= 0 && state.sortIndex < cols.length) {
        rows.sort((a, b) => cmpValues(a[state.sortIndex], b[state.sortIndex]));
        if (state.sortDir === 'desc') rows.reverse();
      }
      return rows;
    }

    function render() {
      const rows = processedRows();
      const total = rows.length;
      const pageSize = state.pageSize;
      const totalPages = pageSize === -1 ? 1 : Math.max(1, Math.ceil(total / pageSize));
      if (state.page > totalPages) state.page = totalPages;
      if (state.page < 1) state.page = 1;

      const start = pageSize === -1 ? 0 : (state.page - 1) * pageSize;
      const end = pageSize === -1 ? total : Math.min(total, start + pageSize);
      const pageRows = rows.slice(start, end);

      let html = '<div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mb-2">';
      html += `<div class="small text-secondary">${total} ${t('Linhas')}</div>`;
      html += '<div class="d-flex align-items-center gap-2">';
      html += `<label class="small text-secondary mb-0">${t('Tamanho da página')}</label>`;
      html += '<select class="form-select form-select-sm" data-table-pagesize style="width:auto;">';
      for (const ps of allowedPageSizes) {
        const lbl = ps === -1 ? t('Tudo') : String(ps);
        const sel = ps === pageSize ? ' selected' : '';
        html += `<option value="${ps}"${sel}>${lbl}</option>`;
      }
      html += '</select>';
      html += '</div></div>';

      html += '<div style="overflow-x:auto;">';
      html += '<table class="table table-sm align-middle"><thead><tr>';
      cols.forEach((c, idx) => {
        let icon = '';
        if (state.sortIndex === idx) icon = state.sortDir === 'asc' ? ' ▲' : ' ▼';
        html += `<th scope="col" data-sort-idx="${idx}" style="cursor:pointer; user-select:none;">${esc(c)}${icon}</th>`;
      });
      html += '</tr></thead><tbody>';
      for (const r of pageRows) {
        html += '<tr>';
        for (const v of r) html += `<td>${esc(v)}</td>`;
        html += '</tr>';
      }
      html += '</tbody></table></div>';

      html += '<div class="d-flex align-items-center justify-content-between flex-wrap gap-2">';
      html += `<div class="small text-secondary">${total === 0 ? '0' : (start + 1)}-${end} / ${total}</div>`;
      html += '<div class="btn-group btn-group-sm" role="group">';
      html += `<button type="button" class="btn btn-outline-secondary" data-page="prev" ${state.page <= 1 ? 'disabled' : ''}>${t('Anterior')}</button>`;
      html += `<button type="button" class="btn btn-outline-secondary" disabled>${state.page}/${totalPages}</button>`;
      html += `<button type="button" class="btn btn-outline-secondary" data-page="next" ${state.page >= totalPages ? 'disabled' : ''}>${t('Próximo')}</button>`;
      html += '</div></div>';

      container.innerHTML = html;

      container.querySelectorAll('th[data-sort-idx]').forEach(th => {
        th.addEventListener('click', () => {
          const idx = Number(th.getAttribute('data-sort-idx'));
          if (!Number.isInteger(idx)) return;
          if (state.sortIndex === idx) {
            state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
          } else {
            state.sortIndex = idx;
            state.sortDir = 'asc';
          }
          state.page = 1;
          persistState();
          render();
        });
      });

      const pageSizeSel = container.querySelector('[data-table-pagesize]');
      if (pageSizeSel) {
        pageSizeSel.addEventListener('change', () => {
          const v = Number(pageSizeSel.value);
          state.pageSize = allowedPageSizes.includes(v) ? v : 25;
          state.page = 1;
          persistState();
          render();
        });
      }

      const prevBtn = container.querySelector('button[data-page="prev"]');
      const nextBtn = container.querySelector('button[data-page="next"]');
      if (prevBtn) {
        prevBtn.addEventListener('click', () => {
          state.page = Math.max(1, state.page - 1);
          persistState();
          render();
        });
      }
      if (nextBtn) {
        nextBtn.addEventListener('click', () => {
          state.page = Math.min(totalPages, state.page + 1);
          persistState();
          render();
        });
      }
    }

    render();
  }

  function renderPivot(container, data, cfg) {
    if (typeof $ === 'undefined' || !$.pivotUtilities) {
      container.innerHTML = '<p>' + t('PivotTable.js não carregou.') + '</p>';
      return;
    }

    function ensurePivotThemeStyles() {
      if (document.getElementById('biPivotThemeStyles')) return;
      const style = document.createElement('style');
      style.id = 'biPivotThemeStyles';
      style.textContent = `
        .bi-pivot-host { width: 100%; }
        .bi-pivot-host .pvtUi { width: 100%; }
        .bi-pivot-host .pvtUi td,
        .bi-pivot-host .pvtUi th { vertical-align: middle; }
        .bi-pivot-host .pvtRendererArea {
          overflow: auto;
          max-height: min(68vh, 680px);
          border: 1px solid var(--bs-border-color);
          border-radius: .75rem;
          background: var(--bs-body-bg);
        }
        .bi-pivot-host .pvtTable {
          min-width: 100%;
          margin: 0;
          border-collapse: separate;
          border-spacing: 0;
          font-size: .89rem;
        }
        .bi-pivot-host .pvtTable thead th,
        .bi-pivot-host .pvtTable .pvtColLabel,
        .bi-pivot-host .pvtTable .pvtAxisLabel {
          position: sticky;
          top: 0;
          z-index: 3;
          background: var(--bs-tertiary-bg);
          border-bottom: 1px solid var(--bs-border-color);
        }
        .bi-pivot-host .pvtTable .pvtRowLabel {
          position: sticky;
          left: 0;
          z-index: 2;
          background: var(--bs-tertiary-bg);
        }
        .bi-pivot-host .pvtTable .pvtVal,
        .bi-pivot-host .pvtTable .pvtTotal,
        .bi-pivot-host .pvtTable .pvtGrandTotal {
          text-align: right;
          font-variant-numeric: tabular-nums;
        }
        .bi-pivot-host .pvtTable tbody tr:nth-child(even) td {
          background: color-mix(in srgb, var(--bs-tertiary-bg) 55%, transparent);
        }
        .bi-pivot-host .pvtTable tbody tr:hover td {
          background: color-mix(in srgb, var(--bs-info-bg-subtle) 48%, transparent);
        }
        .bi-pivot-host .pvtTotal,
        .bi-pivot-host .pvtGrandTotal {
          font-weight: 700;
        }
        .bi-pivot-host .pvtUi select,
        .bi-pivot-host .pvtUi input {
          min-height: calc(1.5em + .5rem + 2px);
          padding: .25rem .5rem;
          border: 1px solid var(--bs-border-color);
          border-radius: .375rem;
          background: var(--bs-body-bg);
          color: var(--bs-body-color);
          font-size: .875rem;
        }
      `;
      document.head.appendChild(style);
    }

    function decoratePivot(containerEl) {
      ensurePivotThemeStyles();
      containerEl.classList.add('bi-pivot-host');
      containerEl.querySelectorAll('.pvtTable').forEach(tbl => {
        tbl.classList.add('table', 'table-sm', 'table-hover', 'align-middle', 'mb-0');
      });
    }

    function observePivot(containerEl) {
      if (containerEl._biPivotObserver) {
        try { containerEl._biPivotObserver.disconnect(); } catch (e) {}
      }
      const obs = new MutationObserver(() => decoratePivot(containerEl));
      obs.observe(containerEl, { childList: true, subtree: true });
      containerEl._biPivotObserver = obs;
    }

    const records = toObjects(data);
    const rows = cfg.pivot_rows ? [cfg.pivot_rows] : [];
    const cols = cfg.pivot_cols ? [cfg.pivot_cols] : [];

    $(container).empty();
    $(container).pivotUI(records, {
      rows: rows,
      cols: cols,
      vals: cfg.pivot_val ? [cfg.pivot_val] : [],
      aggregatorName: cfg.aggregatorName || 'Count',
      rendererName: cfg.rendererName || 'Table'
    }, true);
    decoratePivot(container);
    observePivot(container);
  }

  function renderChart(container, data, cfg, onDrill) {
    if (typeof echarts === 'undefined') {
      container.innerHTML = '<p>' + t('ECharts não carregou.') + '</p>';
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
    const mapLevel = cfg.map_level || 'points';
    const dimIdx = indexOfCol(cols, dim);
    const metIdx = indexOfCol(cols, metric);

    const findGeoCol = (re) => cols.findIndex(c => re.test(String(c || '').toLowerCase()));
    const latIdx = findGeoCol(/^(lat|latitude|y_lat|coord_lat)$/);
    const lonIdx = findGeoCol(/^(lon|lng|longitude|long|x_lon|coord_lon)$/);

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
    } else if (type === 'kpi') {
      chart.dispose();
      let value = null;
      let label = metric || t('Métrica');
      if (rows.length) {
        if (metIdx >= 0) {
          value = rows[0][metIdx];
          label = cols[metIdx] || label;
        } else if (rows[0].length) {
          value = rows[0][0];
          label = cols[0] || label;
        }
      }
      const esc = (v) => String(v == null ? '' : v)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
      container.innerHTML = `
        <div class="d-flex align-items-center justify-content-center" style="min-height:300px;">
          <div class="text-center">
            <div class="text-secondary small mb-1">${esc(label)}</div>
            <div style="font-size: clamp(2rem, 6vw, 4rem); font-weight: 700; line-height: 1.1;">${esc(value == null ? '—' : value)}</div>
          </div>
        </div>
      `;
      return;
    } else if (type === 'map') {
      const hasGeo = latIdx >= 0 && lonIdx >= 0;

      if (mapLevel === 'country') {
        if (dimIdx < 0 || metIdx < 0) {
          chart.dispose();
          container.innerHTML = '<p class="small-muted">' + t('Map pays requer Dimensão (pays) et Métrica.') + '</p>';
          return;
        }
        const agg = new Map();
        for (const r of rows) {
          if (!r || dimIdx >= r.length || metIdx >= r.length) continue;
          const k = canonicalCountryName(r[dimIdx]);
          const v = Number(r[metIdx]);
          if (!k || !Number.isFinite(v)) continue;
          agg.set(k, (agg.get(k) || 0) + v);
        }
        const mapData = Array.from(agg.entries()).map(([name, value]) => ({ name, value: Number(value.toFixed(2)) }));
        if (!mapData.length) {
          chart.dispose();
          container.innerHTML = '<p class="small-muted">' + t('Sem dados válidos para map por pays.') + '</p>';
          return;
        }
        const vals = mapData.map(d => Number(d.value)).filter(v => Number.isFinite(v));
        const vmin = vals.length ? Math.min(...vals) : 0;
        const vmax = vals.length ? Math.max(...vals) : 1;
        option = {
          tooltip: { trigger: 'item' },
          visualMap: {
            min: vmin,
            max: vmax,
            text: [t('Alto'), t('Baixo')],
            realtime: false,
            calculable: true,
            left: 10,
            bottom: 10
          },
          series: [{
            type: 'map',
            map: 'world',
            roam: true,
            nameMap: cfg.nameMap || {},
            emphasis: { label: { show: false } },
            data: mapData
          }]
        };
      } else if (mapLevel === 'fr_departments' || mapLevel === 'it_regions' || mapLevel === 'br_states') {
        if (dimIdx < 0 || metIdx < 0) {
          chart.dispose();
          container.innerHTML = '<p class="small-muted">' + t('Map administratif requer Dimensão et Métrica.') + '</p>';
          return;
        }

        let aliasMap = FR_DEPT_ALIAS_MAP;
        let centers = FR_DEPT_CENTERS;
        let title = t('Départements France');
        if (mapLevel === 'it_regions') {
          aliasMap = IT_REGION_ALIAS_MAP;
          centers = IT_REGION_CENTERS;
          title = t('Régions Italie');
        } else if (mapLevel === 'br_states') {
          aliasMap = BR_STATE_ALIAS_MAP;
          centers = BR_STATE_CENTERS;
          title = t('États Brésil');
        }

        const points = territoryGeoPoints(
          rows,
          dimIdx,
          metIdx,
          (v) => canonicalByAlias(v, aliasMap),
          centers,
          latIdx,
          lonIdx
        );

        if (!points.length) {
          chart.dispose();
          container.innerHTML = '<p class="small-muted">' + t('Sem dados válidos para map administratif.') + '</p>';
          return;
        }

        option = {
          title: {
            text: title,
            left: 'center',
            top: 6,
            textStyle: { fontSize: 12, fontWeight: 600 }
          },
          tooltip: {
            trigger: 'item',
            formatter: (p) => `${p?.data?.name || ''}<br/>${t('Valor')}: ${Number(p?.data?.value?.[2] || 0).toFixed(2)}`
          },
          geo: {
            map: 'world',
            roam: true,
            emphasis: { label: { show: false } },
            itemStyle: { areaColor: '#f3f5f7', borderColor: '#9aa6b2' }
          },
          series: [{
            type: 'scatter',
            coordinateSystem: 'geo',
            data: points,
            symbolSize: (val) => {
              const raw = Number(val && val[2]);
              if (!Number.isFinite(raw)) return 12;
              return Math.max(10, Math.min(34, Math.sqrt(Math.abs(raw)) * 2.2));
            },
            emphasis: { scale: true }
          }]
        };
      } else if (mapLevel === 'continent') {
        if (dimIdx < 0 || metIdx < 0) {
          chart.dispose();
          container.innerHTML = '<p class="small-muted">' + t('Map continent requer Dimensão (continent) et Métrica.') + '</p>';
          return;
        }
        const norm = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim();
        const cMap = {
          europe: 'Europe', europa: 'Europe',
          asia: 'Asia', asie: 'Asia',
          africa: 'Africa', afrique: 'Africa',
          'north america': 'North America', 'n america': 'North America', 'amerique du nord': 'North America',
          'south america': 'South America', 's america': 'South America', 'amerique du sud': 'South America',
          oceania: 'Oceania', oceanie: 'Oceania',
          antarctica: 'Antarctica', antarctique: 'Antarctica'
        };
        const centers = {
          Europe: [10, 51],
          Asia: [90, 34],
          Africa: [20, 2],
          'North America': [-102, 42],
          'South America': [-60, -15],
          Oceania: [135, -25],
          Antarctica: [0, -78]
        };
        const agg = new Map();
        for (const r of rows) {
          if (!r || dimIdx >= r.length || metIdx >= r.length) continue;
          const rawName = String(r[dimIdx] ?? '').trim();
          const key = cMap[norm(rawName)] || rawName;
          const v = Number(r[metIdx]);
          if (!key || !Number.isFinite(v)) continue;
          agg.set(key, (agg.get(key) || 0) + v);
        }
        const points = [];
        for (const [name, value] of agg.entries()) {
          const coord = centers[name];
          if (!coord) continue;
          points.push({ name, value: [coord[0], coord[1], Number(value.toFixed(2))] });
        }
        if (!points.length) {
          chart.dispose();
          container.innerHTML = '<p class="small-muted">' + t('Sem dados válidos para map por continent.') + '</p>';
          return;
        }
        option = {
          tooltip: {
            trigger: 'item',
            formatter: (p) => `${p?.data?.name || ''}<br/>${t('Valor')}: ${Number(p?.data?.value?.[2] || 0).toFixed(2)}`
          },
          geo: {
            map: 'world',
            roam: true,
            emphasis: { label: { show: false } },
            itemStyle: { areaColor: '#f3f5f7', borderColor: '#9aa6b2' }
          },
          series: [{
            type: 'scatter',
            coordinateSystem: 'geo',
            data: points,
            symbolSize: (val) => {
              const raw = Number(val && val[2]);
              if (!Number.isFinite(raw)) return 12;
              return Math.max(10, Math.min(34, Math.sqrt(Math.abs(raw)) * 2.4));
            },
            emphasis: { scale: true }
          }]
        };
      } else {
        if (!hasGeo) {
          chart.dispose();
          container.innerHTML = '<p class="small-muted">' + t('Map points requer colunas lat/lon (latitude/longitude).') + '</p>';
          return;
        }

        const points = [];
        for (const r of rows) {
          if (!r || latIdx >= r.length || lonIdx >= r.length) continue;
          const lat = Number(r[latIdx]);
          const lon = Number(r[lonIdx]);
          if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
          const labelVal = dimIdx >= 0 && dimIdx < r.length ? r[dimIdx] : `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
          const metricVal = metIdx >= 0 && metIdx < r.length ? Number(r[metIdx]) : null;
          points.push({
            value: [lon, lat, Number.isFinite(metricVal) ? metricVal : 1],
            label: String(labelVal),
            metric: Number.isFinite(metricVal) ? metricVal : null
          });
        }

        if (!points.length) {
          chart.dispose();
          container.innerHTML = '<p class="small-muted">' + t('Sem coordenadas válidas para map.') + '</p>';
          return;
        }

        option = {
          tooltip: {
            trigger: 'item',
            formatter: (p) => {
              const d = p?.data || {};
              const lon = d?.value?.[0];
              const lat = d?.value?.[1];
              const met = d?.metric;
              const metLine = Number.isFinite(met) ? `<br/>${t('Valor')}: ${met}` : '';
              return `${d.label || ''}<br/>lon: ${lon}, lat: ${lat}${metLine}`;
            }
          },
          geo: {
            map: 'world',
            roam: true,
            emphasis: { label: { show: false } },
            itemStyle: { areaColor: '#f3f5f7', borderColor: '#9aa6b2' }
          },
          series: [{
            type: 'scatter',
            coordinateSystem: 'geo',
            symbolSize: (val) => {
              const raw = Number(val && val[2]);
              if (!Number.isFinite(raw)) return 10;
              return Math.max(8, Math.min(28, Math.sqrt(Math.abs(raw)) * 2.2));
            },
            data: points,
            emphasis: { scale: true }
          }]
        };
      }
    } else {
      chart.dispose();
      renderTable(container, data, cfg);
      return;
    }

    chart.setOption(option);
    window.addEventListener('resize', () => chart.resize());

    // Drill-down
    const drillField = cfg.drill || cfg.drill_field;
    if (drillField && onDrill && (dimIdx >= 0 || type === 'map')) {
      chart.off('click');
      chart.on('click', params => {
        let clickedVal = params?.name;
        if (type === 'map') {
          clickedVal = params?.data?.label || params?.data?.name || clickedVal;
        }
        if ((clickedVal === undefined || clickedVal === null || clickedVal === '') && Array.isArray(params?.value)) {
          const idx = Number(params.value[0]);
          if (Number.isInteger(idx) && idx >= 0 && idx < x.length) clickedVal = x[idx];
        }
        if (clickedVal === undefined || clickedVal === null || clickedVal === '') {
          clickedVal = params?.value;
        }
        onDrill(drillField, clickedVal);
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
      if (window.uiToast) window.uiToast(err.error || t('Falha ao exportar PDF'), { variant: 'danger' });
      else uiAlert(err.error || t('Falha ao exportar PDF'), t('Erreur'));
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

  async function exportXlsx(title, data, opts) {
    const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    const o = opts || {};
    const resp = await fetch('/app/api/export/xlsx', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'X-CSRFToken': token } : {})
      },
      body: JSON.stringify({
        title: title,
        columns: data.columns || [],
        rows: data.rows || [],
        add_chart: o.add_chart !== false
      })
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      if (window.uiToast) window.uiToast(err.error || t('Falha ao exportar XLSX'), { variant: 'danger' });
      else uiAlert(err.error || t('Falha ao exportar XLSX'), t('Erreur'));
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (title || 'export') + '.xlsx';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  // ----- Dashboard renderer -----
  window.BI.bootDashboard = function bootDashboard() {
    const cards = document.querySelectorAll('[data-bi-card="1"]');
    if (!cards.length) return;

    const storageKey = window.BI_DASHBOARD_FILTERS_KEY || '';
    const state = window.BI_DASHBOARD_STATE || { filters: [] };
    window.BI_DASHBOARD_STATE = state;

    if (storageKey && (!Array.isArray(state.filters) || !state.filters.length)) {
      try {
        const raw = localStorage.getItem(storageKey);
        const parsed = raw ? JSON.parse(raw) : null;
        if (parsed && Array.isArray(parsed.filters)) {
          state.filters = parsed.filters;
        }
      } catch (e) {}
    }

    function persistDashboardFilters() {
      if (!storageKey) return;
      try {
        localStorage.setItem(storageKey, JSON.stringify({ filters: state.filters || [] }));
      } catch (e) {}
    }

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
          viz.setAttribute('data-table-state-key', `bi.table.dashboard.${id}`);
          renderTable(viz, filtered, cfg);
        } else {
          renderChart(viz, filtered, cfg, (field, value) => {
            state.filters = (state.filters || []).filter(f => f.field !== field);
            state.filters.push({ field: field, op: 'eq', value: value });
            persistDashboardFilters();
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
        el.innerHTML = '<em>(' + t('Sem filtros.') + ')</em>';
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
          persistDashboardFilters();
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
        persistDashboardFilters();
        renderFilterSummary();
        rerender();
      });
    }
    const clearBtn = document.getElementById('bi-clear-filters');
    if (clearBtn) {
      clearBtn.addEventListener('click', (e) => {
        e.preventDefault();
        state.filters = [];
        persistDashboardFilters();
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
  };

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
        previewEl.setAttribute('data-table-state-key', `bi.table.preview.${window.location.pathname || 'default'}`);
        renderTable(previewEl, data, cfg);
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

  // public API
  window.BI.exportPdf = exportPdf;
  window.BI.exportXlsx = exportXlsx;

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
      renderTable(container, data, cfg);
    } else {
      renderChart(container, data, cfg, onDrill || null);
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    window.BI.bootDashboard();
    bootQuestionViz();
  });
})();
