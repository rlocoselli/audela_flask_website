/* global echarts */

(function () {
  function qs (s) { return document.querySelector(s); }
  function el (tag, cls) { const x = document.createElement(tag); if (cls) x.className = cls; return x; }
  const t = window.t ? window.t : (s) => s;

  function csrfToken () {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  async function fetchJson (url, options) {
    const resp = await fetch(url, options);
    const payload = await resp.json().catch(() => ({}));
    if (!resp.ok || payload.error || payload.ok === false) {
      throw new Error(payload.error || t('Request failed.'));
    }
    return payload;
  }

  function downloadBlob (blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'download.bin';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1200);
  }

  function addMessage (log, role, text) {
    const m = el('div', `studio-msg ${role}`);
    m.textContent = String(text || '');
    log.appendChild(m);
    log.scrollTop = log.scrollHeight;
  }

  function renderCharts (charts) {
    const wrap = qs('#studioChartsWrap');
    const host = qs('#studioCharts');
    if (!wrap || !host) return;
    host.innerHTML = '';
    if (!Array.isArray(charts) || !charts.length) {
      wrap.style.display = 'none';
      return;
    }

    wrap.style.display = '';
    for (const ch of charts.slice(0, 6)) {
      const card = el('div', 'studio-chart-card');
      const h = el('div', 'fw-semibold small mb-2');
      h.textContent = String(ch.title || 'Chart');
      const c = el('div');
      c.style.height = '290px';
      card.appendChild(h);
      card.appendChild(c);
      host.appendChild(card);

      try {
        const inst = echarts.init(c);
        const opt = ch && ch.echarts_option;
        if (opt && typeof opt === 'object') inst.setOption(opt);
        window.addEventListener('resize', () => inst.resize());
      } catch (e) {
        c.textContent = t('Chart rendering failed.');
      }
    }
  }

  function fileLabel (f) {
    const cols = Array.isArray(f.columns) ? f.columns : [];
    const preview = cols.length ? ` (${cols.slice(0, 4).join(', ')})` : '';
    return `${String(f.name || 'file')} [${String(f.file_format || '')}]${preview}`;
  }

  // ---------------------------------------------------------------
  // Template definitions for each export format
  // ---------------------------------------------------------------
  const EXPORT_TEMPLATES = {
    pdf: [
      {
        id: 'executive',
        name: 'Executive Report',
        desc: 'Branded cover header, KPI highlights and full data table.',
        keywords: 'executive premium report branded',
        icon: { bg: '#0c63e7', paths: [
          '<rect x="4" y="4" width="36" height="44" rx="3" fill="white" opacity=".12"/>',
          '<rect x="4" y="4" width="36" height="44" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="8" y="12" width="28" height="3" rx="1.5" fill="white"/>',
          '<rect x="8" y="18" width="20" height="2" rx="1" fill="white" opacity=".7"/>',
          '<rect x="8" y="23" width="28" height="2" rx="1" fill="white" opacity=".5"/>',
          '<rect x="8" y="28" width="28" height="2" rx="1" fill="white" opacity=".5"/>',
          '<rect x="8" y="33" width="24" height="2" rx="1" fill="white" opacity=".5"/>',
          '<rect x="8" y="38" width="28" height="2" rx="1" fill="white" opacity=".5"/>',
        ] }
      },
      {
        id: 'report',
        name: 'Standard Report',
        desc: 'Clean A4 layout with header strip and striped table rows.',
        keywords: 'standard report clean table',
        icon: { bg: '#475569', paths: [
          '<rect x="4" y="4" width="36" height="44" rx="3" fill="white" opacity=".12"/>',
          '<rect x="4" y="4" width="36" height="44" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="4" y="4" width="36" height="8" rx="3" fill="white" opacity=".2"/>',
          '<rect x="8" y="7" width="18" height="2" rx="1" fill="white"/>',
          '<rect x="8" y="16" width="28" height="2" rx="1" fill="white" opacity=".7"/>',
          '<rect x="8" y="20" width="28" height="2" rx="1" fill="white" opacity=".45"/>',
          '<rect x="8" y="24" width="28" height="2" rx="1" fill="white" opacity=".7"/>',
          '<rect x="8" y="28" width="28" height="2" rx="1" fill="white" opacity=".45"/>',
          '<rect x="8" y="32" width="28" height="2" rx="1" fill="white" opacity=".7"/>',
        ] }
      },
      {
        id: 'compact',
        name: 'Compact Table',
        desc: 'Dense layout, maximum rows per page, reduced margins.',
        keywords: 'compact dense table minimal margins',
        icon: { bg: '#64748b', paths: [
          '<rect x="4" y="4" width="36" height="44" rx="3" fill="white" opacity=".1"/>',
          '<rect x="4" y="4" width="36" height="44" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="6" y="8" width="32" height="1.5" rx=".75" fill="white" opacity=".8"/>',
          '<rect x="6" y="12" width="32" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="6" y="16" width="32" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="6" y="20" width="32" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="6" y="24" width="32" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="6" y="28" width="32" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="6" y="32" width="32" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="6" y="36" width="32" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="6" y="40" width="32" height="1.5" rx=".75" fill="white" opacity=".5"/>',
        ] }
      },
      {
        id: 'confidential',
        name: 'Confidential',
        desc: 'Red-accent header with confidentiality notice and timestamp.',
        keywords: 'confidential private restricted red warning executive',
        icon: { bg: '#b91c1c', paths: [
          '<rect x="4" y="4" width="36" height="44" rx="3" fill="white" opacity=".1"/>',
          '<rect x="4" y="4" width="36" height="44" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="4" y="4" width="36" height="7" rx="3" fill="white" opacity=".18"/>',
          '<text x="22" y="10" text-anchor="middle" font-size="5" font-weight="bold" fill="white">CONF.</text>',
          '<rect x="8" y="16" width="28" height="2" rx="1" fill="white" opacity=".6"/>',
          '<rect x="8" y="21" width="28" height="2" rx="1" fill="white" opacity=".45"/>',
          '<rect x="8" y="26" width="28" height="2" rx="1" fill="white" opacity=".45"/>',
          '<rect x="8" y="31" width="28" height="2" rx="1" fill="white" opacity=".45"/>',
        ] }
      },
      {
        id: 'annual',
        name: 'Annual Review',
        desc: 'Two-column layout, year-over-year comparison table, large cover title.',
        keywords: 'annual review yearly comparison two-column landscape',
        icon: { bg: '#1e3a5f', paths: [
          '<rect x="4" y="4" width="36" height="44" rx="3" fill="white" opacity=".1"/>',
          '<rect x="4" y="4" width="36" height="44" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="4" y="4" width="36" height="10" rx="3" fill="white" opacity=".2"/>',
          '<text x="22" y="12" text-anchor="middle" font-size="5.5" font-weight="bold" fill="white">2025</text>',
          '<rect x="5" y="18" width="15" height="2" rx="1" fill="white" opacity=".6"/>',
          '<rect x="5" y="22" width="15" height="2" rx="1" fill="white" opacity=".4"/>',
          '<rect x="5" y="26" width="15" height="2" rx="1" fill="white" opacity=".4"/>',
          '<rect x="5" y="30" width="15" height="2" rx="1" fill="white" opacity=".4"/>',
          '<rect x="24" y="18" width="15" height="2" rx="1" fill="white" opacity=".6"/>',
          '<rect x="24" y="22" width="15" height="2" rx="1" fill="white" opacity=".4"/>',
          '<rect x="24" y="26" width="15" height="2" rx="1" fill="white" opacity=".4"/>',
          '<rect x="24" y="30" width="15" height="2" rx="1" fill="white" opacity=".4"/>',
          '<line x1="21" y1="16" x2="21" y2="34" stroke="white" stroke-width=".8" opacity=".3"/>',
        ] }
      },
      {
        id: 'narrative',
        name: 'Narrative Brief',
        desc: 'Prose-first format: text summary with embedded callouts, minimal tables.',
        keywords: 'narrative story brief prose text callout memo',
        icon: { bg: '#4338ca', paths: [
          '<rect x="4" y="4" width="36" height="44" rx="3" fill="white" opacity=".1"/>',
          '<rect x="4" y="4" width="36" height="44" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="8" y="8" width="28" height="3" rx="1.5" fill="white" opacity=".85"/>',
          '<rect x="8" y="14" width="28" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="8" y="18" width="22" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="4" y="22" width="3" height="14" rx="1.5" fill="white" opacity=".6"/>',
          '<rect x="10" y="23" width="26" height="1.5" rx=".75" fill="white" opacity=".45"/>',
          '<rect x="10" y="27" width="26" height="1.5" rx=".75" fill="white" opacity=".45"/>',
          '<rect x="10" y="31" width="20" height="1.5" rx=".75" fill="white" opacity=".45"/>',
          '<rect x="8" y="38" width="28" height="1.5" rx=".75" fill="white" opacity=".4"/>',
          '<rect x="8" y="42" width="20" height="1.5" rx=".75" fill="white" opacity=".4"/>',
        ] }
      },
      {
        id: 'landscape',
        name: 'Landscape Wide',
        desc: 'Wide A4 landscape format, side-by-side table and bar chart.',
        keywords: 'landscape wide horizontal chart table visual',
        icon: { bg: '#0891b2', paths: [
          '<rect x="2" y="8" width="40" height="28" rx="3" fill="white" opacity=".1"/>',
          '<rect x="2" y="8" width="40" height="28" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="8" width="40" height="6" rx="3" fill="white" opacity=".2"/>',
          '<rect x="4" y="18" width="18" height="1.5" rx=".75" fill="white" opacity=".6"/>',
          '<rect x="4" y="22" width="18" height="1.5" rx=".75" fill="white" opacity=".4"/>',
          '<rect x="4" y="26" width="18" height="1.5" rx=".75" fill="white" opacity=".4"/>',
          '<rect x="4" y="30" width="18" height="1.5" rx=".75" fill="white" opacity=".4"/>',
          '<rect x="26" y="18" width="4" height="14" rx="1" fill="white" opacity=".7"/>',
          '<rect x="32" y="21" width="4" height="11" rx="1" fill="white" opacity=".7"/>',
          '<rect x="38" y="24" width="4" height="8" rx="1" fill="white" opacity=".7"/>',
        ] }
      },
      {
        id: 'regulatory',
        name: 'Regulatory Annex',
        desc: 'Compliance-focused layout with controls, risk notes and annex table.',
        keywords: 'regulatory compliance risk annex controls audit',
        icon: { bg: '#0f766e', paths: [
          '<rect x="4" y="4" width="36" height="44" rx="3" fill="white" opacity=".1"/>',
          '<rect x="4" y="4" width="36" height="44" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="4" y="4" width="36" height="8" rx="3" fill="white" opacity=".2"/>',
          '<rect x="8" y="8" width="14" height="2" rx="1" fill="white" opacity=".85"/>',
          '<rect x="8" y="16" width="22" height="1.5" rx=".75" fill="white" opacity=".55"/>',
          '<rect x="8" y="20" width="22" height="1.5" rx=".75" fill="white" opacity=".45"/>',
          '<rect x="8" y="24" width="22" height="1.5" rx=".75" fill="white" opacity=".45"/>',
          '<rect x="8" y="30" width="8" height="8" rx="1.5" fill="white" opacity=".2"/>',
          '<path d="M10 34 L12 36 L15 32" stroke="white" stroke-width="1.2" fill="none"/>',
          '<rect x="20" y="30" width="16" height="1.5" rx=".75" fill="white" opacity=".45"/>',
          '<rect x="20" y="34" width="12" height="1.5" rx=".75" fill="white" opacity=".45"/>',
          '<rect x="20" y="38" width="14" height="1.5" rx=".75" fill="white" opacity=".45"/>',
        ] }
      }
    ],
    xlsx: [
      {
        id: 'modern',
        name: 'Modern Analytics',
        desc: 'Summary sheet, data bars on numerics, bar chart tab.',
        excelTemplate: 'modern',
        icon: { bg: '#1f7a4a', paths: [
          '<rect x="2" y="3" width="40" height="46" rx="3" fill="white" opacity=".1"/>',
          '<rect x="2" y="3" width="40" height="46" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="5" y="6" width="34" height="6" rx="2" fill="white" opacity=".2"/>',
          '<rect x="5" y="15" width="20" height="3" rx="1.5" fill="white" opacity=".8"/>',
          '<rect x="5" y="20" width="14" height="3" rx="1.5" fill="white" opacity=".6"/>',
          '<rect x="5" y="25" width="28" height="3" rx="1.5" fill="white" opacity=".6"/>',
          '<rect x="5" y="30" width="10" height="3" rx="1.5" fill="white" opacity=".6"/>',
          '<rect x="5" y="35" width="24" height="3" rx="1.5" fill="white" opacity=".6"/>',
        ] }
      },
      {
        id: 'executive',
        name: 'Executive Workbook',
        desc: 'Slate palette, KPI summary tab first, pivot, conditional formatting.',
        excelTemplate: 'executive',
        icon: { bg: '#3a4a63', paths: [
          '<rect x="2" y="3" width="40" height="46" rx="3" fill="white" opacity=".1"/>',
          '<rect x="2" y="3" width="40" height="46" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="3" width="40" height="7" rx="3" fill="white" opacity=".18"/>',
          '<rect x="6" y="5.5" width="22" height="2" rx="1" fill="white"/>',
          '<rect x="5" y="14" width="34" height="2" rx="1" fill="white" opacity=".7"/>',
          '<rect x="5" y="19" width="26" height="2" rx="1" fill="white" opacity=".5"/>',
          '<rect x="5" y="24" width="34" height="2" rx="1" fill="white" opacity=".5"/>',
          '<rect x="5" y="29" width="20" height="2" rx="1" fill="white" opacity=".5"/>',
          '<rect x="5" y="34" width="34" height="2" rx="1" fill="white" opacity=".5"/>',
        ] }
      },
      {
        id: 'clean',
        name: 'Clean Table',
        desc: 'Minimal formatting, raw data with column headers. No extras.',
        excelTemplate: 'clean',
        icon: { bg: '#94a3b8', paths: [
          '<rect x="4" y="4" width="36" height="44" rx="3" fill="white" opacity=".1"/>',
          '<rect x="4" y="4" width="36" height="44" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="4" y="4" width="36" height="6" rx="3" fill="white" opacity=".2"/>',
          '<line x1="4" y1="16" x2="40" y2="16" stroke="white" stroke-width=".8" opacity=".4"/>',
          '<line x1="4" y1="22" x2="40" y2="22" stroke="white" stroke-width=".8" opacity=".4"/>',
          '<line x1="4" y1="28" x2="40" y2="28" stroke="white" stroke-width=".8" opacity=".4"/>',
          '<line x1="4" y1="34" x2="40" y2="34" stroke="white" stroke-width=".8" opacity=".4"/>',
          '<line x1="18" y1="10" x2="18" y2="48" stroke="white" stroke-width=".8" opacity=".4"/>',
          '<line x1="32" y1="10" x2="32" y2="48" stroke="white" stroke-width=".8" opacity=".4"/>',
        ] }
      },
      {
        id: 'dashboard',
        name: 'Dashboard Ready',
        desc: 'Named ranges, chart-ready layout, formatted for PowerBI import.',
        excelTemplate: 'clean',
        keywords: 'dashboard powerbi data analytics',
        icon: { bg: '#0c63e7', paths: [
          '<rect x="2" y="3" width="40" height="46" rx="3" fill="white" opacity=".1"/>',
          '<rect x="2" y="3" width="40" height="46" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="5" y="7" width="16" height="12" rx="2" fill="white" opacity=".2"/>',
          '<rect x="25" y="7" width="16" height="12" rx="2" fill="white" opacity=".2"/>',
          '<rect x="8" y="26" width="4" height="14" rx="1" fill="white" opacity=".8"/>',
          '<rect x="14" y="22" width="4" height="18" rx="1" fill="white" opacity=".7"/>',
          '<rect x="20" y="30" width="4" height="10" rx="1" fill="white" opacity=".7"/>',
          '<rect x="26" y="20" width="4" height="20" rx="1" fill="white" opacity=".7"/>',
          '<rect x="32" y="25" width="4" height="15" rx="1" fill="white" opacity=".7"/>',
        ] }
      },
      {
        id: 'financial',
        name: 'Financial Statements',
        desc: 'P&L and Balance sheet tabs with formula-ready totals and subtotals.',
        excelTemplate: 'executive',
        keywords: 'financial statements P&L balance sheet accounting',
        icon: { bg: '#0f4c2a', paths: [
          '<rect x="2" y="3" width="40" height="46" rx="3" fill="white" opacity=".1"/>',
          '<rect x="2" y="3" width="40" height="46" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="3" width="40" height="7" rx="3" fill="white" opacity=".2"/>',
          '<rect x="4" y="5.5" width="16" height="2" rx="1" fill="white"/>',
          '<rect x="5" y="14" width="34" height="2" rx="1" fill="white" opacity=".7"/>',
          '<rect x="5" y="19" width="34" height="1.5" rx="1" fill="white" opacity=".4"/>',
          '<rect x="5" y="23" width="34" height="1.5" rx="1" fill="white" opacity=".4"/>',
          '<rect x="5" y="27" width="28" height="1.5" rx="1" fill="white" opacity=".6" />',
          '<rect x="5" y="31" width="34" height="2" rx="1" fill="white" opacity=".7"/>',
          '<rect x="5" y="35" width="34" height="1.5" rx="1" fill="white" opacity=".4"/>',
          '<rect x="5" y="39" width="34" height="1.5" rx="1" fill="white" opacity=".4"/>',
        ] }
      },
      {
        id: 'pivot',
        name: 'Pivot Matrix',
        desc: 'Cross-tab pivot sheet with totals per row/column and conditional formatting.',
        excelTemplate: 'modern',
        keywords: 'pivot matrix cross-tab aggregation',
        icon: { bg: '#6d28d9', paths: [
          '<rect x="2" y="3" width="40" height="46" rx="3" fill="white" opacity=".1"/>',
          '<rect x="2" y="3" width="40" height="46" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="3" width="40" height="7" rx="3" fill="white" opacity=".2"/>',
          '<rect x="2" y="10" width="12" height="38" rx="0" fill="white" opacity=".1"/>',
          '<rect x="2" y="10" width="40" height="5" rx="0" fill="white" opacity=".1"/>',
          '<line x1="14" y1="10" x2="14" y2="48" stroke="white" stroke-width=".8" opacity=".3"/>',
          '<line x1="26" y1="10" x2="26" y2="48" stroke="white" stroke-width=".8" opacity=".3"/>',
          '<line x1="2" y1="15" x2="42" y2="15" stroke="white" stroke-width=".8" opacity=".3"/>',
          '<line x1="2" y1="22" x2="42" y2="22" stroke="white" stroke-width=".8" opacity=".3"/>',
          '<line x1="2" y1="29" x2="42" y2="29" stroke="white" stroke-width=".8" opacity=".3"/>',
          '<line x1="2" y1="36" x2="42" y2="36" stroke="white" stroke-width=".8" opacity=".3"/>',
        ] }
      },
      {
        id: 'scorecard',
        name: 'Scorecard',
        desc: 'KPI scorecard with target, actual, RAG status and trend sparklines.',
        excelTemplate: 'executive',
        keywords: 'scorecard KPI RAG status red amber green targets',
        icon: { bg: '#92400e', paths: [
          '<rect x="2" y="3" width="40" height="46" rx="3" fill="white" opacity=".1"/>',
          '<rect x="2" y="3" width="40" height="46" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="5" y="7" width="34" height="5" rx="2" fill="white" opacity=".2"/>',
          '<rect x="5" y="15" width="16" height="5" rx="2" fill="white" opacity=".25"/>',
          '<rect x="5" y="23" width="16" height="5" rx="2" fill="white" opacity=".25"/>',
          '<rect x="5" y="31" width="16" height="5" rx="2" fill="white" opacity=".25"/>',
          '<rect x="27" y="15" width="5" height="5" rx="2.5" fill="#16a34a" opacity=".8"/>',
          '<rect x="27" y="23" width="5" height="5" rx="2.5" fill="#eab308" opacity=".9"/>',
          '<rect x="27" y="31" width="5" height="5" rx="2.5" fill="#dc2626" opacity=".8"/>',
          '<rect x="34" y="16" width="6" height="3" rx="1" fill="white" opacity=".4"/>',
          '<rect x="34" y="24" width="6" height="3" rx="1" fill="white" opacity=".4"/>',
          '<rect x="34" y="32" width="6" height="3" rx="1" fill="white" opacity=".4"/>',
        ] }
      },
      {
        id: 'forecast',
        name: 'Forecast Model',
        desc: 'Scenario columns (Base/Upside/Downside) with variance and assumptions tabs.',
        excelTemplate: 'modern',
        keywords: 'forecast scenario planning assumptions variance model',
        icon: { bg: '#0e7490', paths: [
          '<rect x="2" y="3" width="40" height="46" rx="3" fill="white" opacity=".1"/>',
          '<rect x="2" y="3" width="40" height="46" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="3" width="40" height="7" rx="3" fill="white" opacity=".2"/>',
          '<rect x="5" y="14" width="10" height="3" rx="1.5" fill="white" opacity=".8"/>',
          '<rect x="17" y="14" width="10" height="3" rx="1.5" fill="white" opacity=".6"/>',
          '<rect x="29" y="14" width="10" height="3" rx="1.5" fill="white" opacity=".4"/>',
          '<rect x="5" y="20" width="34" height="1.5" rx=".75" fill="white" opacity=".45"/>',
          '<rect x="5" y="24" width="34" height="1.5" rx=".75" fill="white" opacity=".45"/>',
          '<rect x="5" y="28" width="34" height="1.5" rx=".75" fill="white" opacity=".45"/>',
          '<path d="M6 40 L13 34 L20 36 L27 29 L36 25" stroke="white" stroke-width="1.2" fill="none"/>',
          '<circle cx="13" cy="34" r="1" fill="white"/><circle cx="27" cy="29" r="1" fill="white"/>',
        ] }
      }
    ],
    ppt: [
      {
        id: 'full',
        name: 'Full Executive Deck',
        desc: '5 slides: Cover, Executive Summary, KPI Cards, Category Breakdown, Data Snapshot.',
        slides: 'full',
        icon: { bg: '#d97706', paths: [
          '<rect x="2" y="6" width="40" height="28" rx="3" fill="white" opacity=".12"/>',
          '<rect x="2" y="6" width="40" height="28" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="6" width="40" height="7" rx="3" fill="white" opacity=".2"/>',
          '<text x="22" y="13" text-anchor="middle" font-size="4.5" font-weight="bold" fill="white">COVER</text>',
          '<rect x="5" y="18" width="30" height="2" rx="1" fill="white" opacity=".6"/>',
          '<rect x="5" y="23" width="22" height="2" rx="1" fill="white" opacity=".45"/>',
          '<rect x="2" y="38" width="10" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
          '<rect x="14" y="38" width="10" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
          '<rect x="26" y="38" width="10" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
        ] }
      },
      {
        id: 'kpi',
        name: 'KPI Board',
        desc: '3 slides: Cover, KPI Cards, Data Snapshot. Focused metrics presentation.',
        slides: 'kpi',
        icon: { bg: '#c2410c', paths: [
          '<rect x="2" y="6" width="40" height="28" rx="3" fill="white" opacity=".12"/>',
          '<rect x="2" y="6" width="40" height="28" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="6" width="40" height="7" rx="3" fill="white" opacity=".2"/>',
          '<rect x="4" y="17" width="16" height="13" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
          '<rect x="24" y="17" width="16" height="13" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
          '<rect x="7" y="22" width="10" height="2" rx="1" fill="white" opacity=".8"/>',
          '<rect x="27" y="22" width="10" height="2" rx="1" fill="white" opacity=".8"/>',
          '<rect x="2" y="38" width="10" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
          '<rect x="14" y="38" width="10" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
        ] }
      },
      {
        id: 'summary',
        name: 'Quick Summary',
        desc: '2 slides: Cover and executive summary with AI analysis text.',
        slides: 'summary',
        icon: { bg: '#b45309', paths: [
          '<rect x="2" y="6" width="40" height="28" rx="3" fill="white" opacity=".12"/>',
          '<rect x="2" y="6" width="40" height="28" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="6" width="40" height="7" rx="3" fill="white" opacity=".2"/>',
          '<rect x="5" y="17" width="34" height="2" rx="1" fill="white" opacity=".7"/>',
          '<rect x="5" y="21" width="26" height="2" rx="1" fill="white" opacity=".5"/>',
          '<rect x="5" y="25" width="34" height="2" rx="1" fill="white" opacity=".5"/>',
          '<rect x="5" y="29" width="20" height="2" rx="1" fill="white" opacity=".5"/>',
          '<rect x="2" y="38" width="10" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
          '<rect x="14" y="38" width="10" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
        ] }
      },
      {
        id: 'investor',
        name: 'Investor Pack',
        desc: 'Ocean blue theme, cover, summary and top driver breakdown.',
        slides: 'full',
        keywords: 'investor ocean blue editorial',
        icon: { bg: '#0c63e7', paths: [
          '<rect x="2" y="6" width="40" height="28" rx="3" fill="white" opacity=".12"/>',
          '<rect x="2" y="6" width="40" height="28" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="6" width="40" height="7" rx="3" fill="white" opacity=".2"/>',
          '<text x="22" y="13" text-anchor="middle" font-size="4" fill="white">INVESTOR</text>',
          '<rect x="5" y="17" width="8" height="13" rx="2" fill="white" opacity=".2"/>',
          '<rect x="15" y="20" width="8" height="10" rx="2" fill="white" opacity=".2"/>',
          '<rect x="25" y="15" width="8" height="15" rx="2" fill="white" opacity=".2"/>',
          '<rect x="2" y="38" width="10" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
          '<rect x="14" y="38" width="10" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
          '<rect x="26" y="38" width="10" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
        ] }
      },
      {
        id: 'roadmap',
        name: 'Roadmap & Milestones',
        desc: '3 slides: Cover, visual timeline/roadmap, and next-steps action table.',
        slides: 'full',
        keywords: 'roadmap milestones timeline planning strategy',
        icon: { bg: '#059669', paths: [
          '<rect x="2" y="6" width="40" height="28" rx="3" fill="white" opacity=".12"/>',
          '<rect x="2" y="6" width="40" height="28" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="6" width="40" height="7" rx="3" fill="white" opacity=".2"/>',
          '<line x1="5" y1="21" x2="39" y2="21" stroke="white" stroke-width="1.5" opacity=".5"/>',
          '<circle cx="10" cy="21" r="3" fill="white" opacity=".8"/>',
          '<circle cx="21" cy="21" r="3" fill="white" opacity=".8"/>',
          '<circle cx="32" cy="21" r="3" fill="white" opacity=".8"/>',
          '<rect x="8" y="25" width="6" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="19" y="25" width="6" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="30" y="25" width="6" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="2" y="38" width="10" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
          '<rect x="14" y="38" width="10" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
        ] }
      },
      {
        id: 'oneshot',
        name: 'One-Pager',
        desc: 'Single dense slide: title, KPI row and bar chart in one view.',
        slides: 'kpi',
        keywords: 'one-pager single slide quick brief print',
        icon: { bg: '#7c3aed', paths: [
          '<rect x="2" y="6" width="40" height="28" rx="3" fill="white" opacity=".12"/>',
          '<rect x="2" y="6" width="40" height="28" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="6" width="40" height="5" rx="3" fill="white" opacity=".25"/>',
          '<rect x="4" y="13" width="11" height="9" rx="2" fill="white" opacity=".18"/>',
          '<rect x="17" y="13" width="11" height="9" rx="2" fill="white" opacity=".18"/>',
          '<rect x="30" y="13" width="11" height="9" rx="2" fill="white" opacity=".18"/>',
          '<rect x="5" y="25" width="4" height="7" rx="1" fill="white" opacity=".6"/>',
          '<rect x="11" y="22" width="4" height="10" rx="1" fill="white" opacity=".6"/>',
          '<rect x="17" y="25" width="4" height="7" rx="1" fill="white" opacity=".6"/>',
          '<rect x="23" y="20" width="4" height="12" rx="1" fill="white" opacity=".6"/>',
          '<rect x="29" y="27" width="4" height="5" rx="1" fill="white" opacity=".6"/>',
          '<rect x="2" y="38" width="38" height="7" rx="2" fill="white" opacity=".1" stroke="white" stroke-width="1"/>',
        ] }
      },
      {
        id: 'quarterly',
        name: 'Quarterly Business Review',
        desc: '6 slides: Cover, QBR agenda, KPIs vs targets, highlights, risks, actions.',
        slides: 'full',
        keywords: 'quarterly QBR business review targets risks actions',
        icon: { bg: '#be123c', paths: [
          '<rect x="2" y="6" width="40" height="28" rx="3" fill="white" opacity=".12"/>',
          '<rect x="2" y="6" width="40" height="28" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="6" width="40" height="7" rx="3" fill="white" opacity=".2"/>',
          '<text x="22" y="12" text-anchor="middle" font-size="4.5" font-weight="bold" fill="white">QBR Q2</text>',
          '<rect x="5" y="17" width="34" height="2" rx="1" fill="white" opacity=".6"/>',
          '<rect x="5" y="22" width="25" height="2" rx="1" fill="white" opacity=".4"/>',
          '<rect x="2" y="38" width="7" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
          '<rect x="11" y="38" width="7" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
          '<rect x="20" y="38" width="7" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
          '<rect x="29" y="38" width="7" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
        ] }
      },
      {
        id: 'boardroom',
        name: 'Boardroom Briefing',
        desc: 'Formal board deck with decisions, risks and action owners slide pattern.',
        slides: 'full',
        keywords: 'board boardroom governance risk decisions actions',
        icon: { bg: '#334155', paths: [
          '<rect x="2" y="6" width="40" height="28" rx="3" fill="white" opacity=".12"/>',
          '<rect x="2" y="6" width="40" height="28" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="6" width="40" height="7" rx="3" fill="white" opacity=".2"/>',
          '<rect x="6" y="10" width="14" height="2" rx="1" fill="white" opacity=".85"/>',
          '<rect x="5" y="18" width="34" height="2" rx="1" fill="white" opacity=".55"/>',
          '<rect x="5" y="22" width="24" height="2" rx="1" fill="white" opacity=".45"/>',
          '<rect x="5" y="26" width="30" height="2" rx="1" fill="white" opacity=".45"/>',
          '<rect x="2" y="38" width="10" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
          '<rect x="14" y="38" width="10" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
          '<rect x="26" y="38" width="10" height="7" rx="2" fill="white" opacity=".15" stroke="white" stroke-width="1"/>',
        ] }
      }
    ],
    html: [
      {
        id: 'executive',
        name: 'Executive Dashboard',
        desc: 'Interactive tabs: KPIs, charts, trends, timeline and data table.',
        keywords: 'executive',
        icon: { bg: '#0f172a', paths: [
          '<rect x="2" y="3" width="40" height="46" rx="3" fill="white" opacity=".08"/>',
          '<rect x="2" y="3" width="40" height="46" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="3" width="40" height="8" rx="3" fill="white" opacity=".18"/>',
          '<rect x="4" y="14" width="8" height="5" rx="1.5" fill="white" opacity=".3"/>',
          '<rect x="14" y="14" width="8" height="5" rx="1.5" fill="white" opacity=".18"/>',
          '<rect x="24" y="14" width="8" height="5" rx="1.5" fill="white" opacity=".18"/>',
          '<rect x="4" y="22" width="36" height="16" rx="2" fill="white" opacity=".1" stroke="white" stroke-width=".8"/>',
          '<rect x="4" y="40" width="36" height="6" rx="2" fill="white" opacity=".1" stroke="white" stroke-width=".8"/>',
        ] }
      },
      {
        id: 'board',
        name: 'Board Package',
        desc: 'Printable, formal layout. KPIs and summary text only, no interactive charts.',
        keywords: 'banking board corporate graphite',
        icon: { bg: '#1d2430', paths: [
          '<rect x="4" y="4" width="36" height="44" rx="3" fill="white" opacity=".08"/>',
          '<rect x="4" y="4" width="36" height="44" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="4" y="4" width="36" height="8" rx="3" fill="white" opacity=".18"/>',
          '<rect x="8" y="7" width="20" height="2" rx="1" fill="white"/>',
          '<rect x="8" y="16" width="28" height="1.5" rx=".75" fill="white" opacity=".6"/>',
          '<rect x="8" y="20" width="28" height="1.5" rx=".75" fill="white" opacity=".4"/>',
          '<rect x="8" y="24" width="28" height="1.5" rx=".75" fill="white" opacity=".4"/>',
          '<rect x="8" y="28" width="18" height="1.5" rx=".75" fill="white" opacity=".4"/>',
          '<rect x="8" y="34" width="28" height="5" rx="1.5" fill="white" opacity=".1" stroke="white" stroke-width=".7"/>',
        ] }
      },
      {
        id: 'analytics',
        name: 'Analytics View',
        desc: 'Chart-focused, 6+ ECharts panels, minimal text, data-dense.',
        keywords: 'tech digital analytics charts',
        icon: { bg: '#0c63e7', paths: [
          '<rect x="2" y="3" width="40" height="46" rx="3" fill="white" opacity=".08"/>',
          '<rect x="2" y="3" width="40" height="46" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="3" width="40" height="7" rx="3" fill="white" opacity=".18"/>',
          '<rect x="4" y="13" width="17" height="16" rx="2" fill="white" opacity=".12" stroke="white" stroke-width=".8"/>',
          '<rect x="24" y="13" width="17" height="16" rx="2" fill="white" opacity=".12" stroke="white" stroke-width=".8"/>',
          '<rect x="4" y="32" width="37" height="14" rx="2" fill="white" opacity=".12" stroke="white" stroke-width=".8"/>',
          '<rect x="7" y="21" width="3" height="6" rx="1" fill="white" opacity=".7"/>',
          '<rect x="12" y="18" width="3" height="9" rx="1" fill="white" opacity=".7"/>',
          '<rect x="17" y="23" width="3" height="4" rx="1" fill="white" opacity=".7"/>',
        ] }
      },
      {
        id: 'minimal',
        name: 'Minimal Report',
        desc: 'Plain white, clean typography, no sidebar. Best for email or print.',
        keywords: 'minimal clean white simple report',
        icon: { bg: '#334155', paths: [
          '<rect x="4" y="4" width="36" height="44" rx="3" fill="white" opacity=".1"/>',
          '<rect x="4" y="4" width="36" height="44" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="8" y="10" width="24" height="3" rx="1.5" fill="white" opacity=".8"/>',
          '<rect x="8" y="17" width="28" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="8" y="21" width="28" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="8" y="25" width="22" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="8" y="29" width="28" height="1.5" rx=".75" fill="white" opacity=".5"/>',
          '<rect x="8" y="33" width="28" height="1.5" rx=".75" fill="white" opacity=".5"/>',
        ] }
      },
      {
        id: 'dark',
        name: 'Dark Mode',
        desc: 'Midnight background, neon-accent KPIs, charts with glow. Mobile-optimised.',
        keywords: 'dark mode night neon digital cyber',
        icon: { bg: '#0a0f1e', paths: [
          '<rect x="2" y="3" width="40" height="46" rx="3" fill="white" opacity=".06"/>',
          '<rect x="2" y="3" width="40" height="46" rx="3" stroke="#818cf8" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="3" width="40" height="7" rx="3" fill="#1e1b4b" opacity="1"/>',
          '<rect x="5" y="14" width="10" height="7" rx="2" fill="#312e81" opacity="1"/>',
          '<rect x="17" y="14" width="10" height="7" rx="2" fill="#312e81" opacity="1"/>',
          '<rect x="29" y="14" width="10" height="7" rx="2" fill="#312e81" opacity="1"/>',
          '<rect x="7" y="27" width="4" height="14" rx="1" fill="#818cf8" opacity=".8"/>',
          '<rect x="14" y="23" width="4" height="18" rx="1" fill="#a78bfa" opacity=".8"/>',
          '<rect x="21" y="30" width="4" height="11" rx="1" fill="#818cf8" opacity=".8"/>',
          '<rect x="28" y="21" width="4" height="20" rx="1" fill="#c4b5fd" opacity=".8"/>',
          '<rect x="35" y="26" width="4" height="15" rx="1" fill="#818cf8" opacity=".8"/>',
        ] }
      },
      {
        id: 'newspaper',
        name: 'Newspaper / Editorial',
        desc: 'Two-column editorial layout, large pull-quotes, section dividers.',
        keywords: 'editorial newspaper magazine column pullquote press',
        icon: { bg: '#1c1917', paths: [
          '<rect x="4" y="4" width="36" height="44" rx="3" fill="white" opacity=".08"/>',
          '<rect x="4" y="4" width="36" height="44" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="4" y="4" width="36" height="8" rx="3" fill="white" opacity=".2"/>',
          '<rect x="7" y="7" width="26" height="2.5" rx="1.25" fill="white" opacity=".9"/>',
          '<line x1="22" y1="15" x2="22" y2="44" stroke="white" stroke-width=".8" opacity=".25"/>',
          '<rect x="6" y="15" width="13" height="3" rx="1.5" fill="white" opacity=".7"/>',
          '<rect x="6" y="20" width="14" height="1.5" rx=".75" fill="white" opacity=".4"/>',
          '<rect x="6" y="23" width="14" height="1.5" rx=".75" fill="white" opacity=".4"/>',
          '<rect x="6" y="26" width="12" height="1.5" rx=".75" fill="white" opacity=".4"/>',
          '<rect x="6" y="29" width="14" height="1.5" rx=".75" fill="white" opacity=".4"/>',
          '<rect x="25" y="15" width="13" height="1.5" rx=".75" fill="white" opacity=".4"/>',
          '<rect x="25" y="19" width="13" height="1.5" rx=".75" fill="white" opacity=".4"/>',
          '<rect x="25" y="23" width="10" height="1.5" rx=".75" fill="white" opacity=".4"/>',
          '<rect x="25" y="28" width="13" height="4" rx="1" fill="white" opacity=".15" stroke="white" stroke-width=".6"/>',
        ] }
      },
      {
        id: 'cto',
        name: 'Tech / CTO Brief',
        desc: 'Tech-focused layout: system metrics, uptime, latency table, incident log.',
        keywords: 'tech CTO engineering system metrics uptime latency infrastructure',
        icon: { bg: '#0c4a6e', paths: [
          '<rect x="2" y="3" width="40" height="46" rx="3" fill="white" opacity=".08"/>',
          '<rect x="2" y="3" width="40" height="46" rx="3" stroke="#38bdf8" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="3" width="40" height="7" rx="3" fill="#0369a1" opacity="1"/>',
          '<rect x="5" y="13" width="34" height="2" rx="1" fill="white" opacity=".6"/>',
          '<rect x="5" y="17" width="20" height="1.5" rx=".75" fill="#38bdf8" opacity=".7"/>',
          '<rect x="5" y="21" width="30" height="1.5" rx=".75" fill="white" opacity=".3"/>',
          '<rect x="5" y="25" width="24" height="1.5" rx=".75" fill="#38bdf8" opacity=".5"/>',
          '<rect x="5" y="29" width="34" height="1.5" rx=".75" fill="white" opacity=".3"/>',
          '<rect x="5" y="34" width="7" height="7" rx="3.5" fill="#16a34a" opacity=".8"/>',
          '<rect x="15" y="34" width="7" height="7" rx="3.5" fill="#eab308" opacity=".8"/>',
          '<rect x="25" y="34" width="7" height="7" rx="3.5" fill="#16a34a" opacity=".8"/>',
        ] }
      },
      {
        id: 'portfolio',
        name: 'Portfolio Snapshot',
        desc: 'Card-based portfolio view with holdings, allocation and performance strip.',
        keywords: 'portfolio holdings allocation performance snapshot investor',
        icon: { bg: '#14532d', paths: [
          '<rect x="2" y="3" width="40" height="46" rx="3" fill="white" opacity=".08"/>',
          '<rect x="2" y="3" width="40" height="46" rx="3" stroke="white" stroke-width="1.5" fill="none"/>',
          '<rect x="2" y="3" width="40" height="7" rx="3" fill="white" opacity=".2"/>',
          '<rect x="5" y="13" width="16" height="12" rx="2" fill="white" opacity=".16"/>',
          '<rect x="23" y="13" width="16" height="12" rx="2" fill="white" opacity=".16"/>',
          '<rect x="5" y="27" width="34" height="5" rx="2" fill="white" opacity=".14"/>',
          '<rect x="7" y="28.5" width="8" height="2" rx="1" fill="white" opacity=".7"/>',
          '<rect x="17" y="28.5" width="5" height="2" rx="1" fill="#16a34a" opacity=".9"/>',
          '<rect x="24" y="28.5" width="7" height="2" rx="1" fill="white" opacity=".45"/>',
          '<rect x="33" y="28.5" width="4" height="2" rx="1" fill="white" opacity=".35"/>',
          '<rect x="5" y="35" width="34" height="8" rx="2" fill="white" opacity=".1" stroke="white" stroke-width=".7"/>',
        ] }
      }
    ]
  };

  const FORMAT_META = {
    pdf:  { title: 'PDF template', subtitle: 'Choose a layout for your exported report.' },
    xlsx: { title: 'Excel template', subtitle: 'Choose a workbook style and sheet structure.' },
    ppt:  { title: 'PowerPoint template', subtitle: 'Choose a deck structure and visual theme.' },
    html: { title: 'Executive HTML template', subtitle: 'Choose an interactive report layout.' }
  };

  // ---------------------------------------------------------------
  // Template gallery: small sidebar thumb (22×28 SVG)
  // ---------------------------------------------------------------
  function buildTplThumb (icon) {
    return `<svg viewBox="0 0 22 28" width="22" height="28" xmlns="http://www.w3.org/2000/svg">${icon.paths.join('')}</svg>`;
  }

  // ---------------------------------------------------------------
  // Realistic CSS document preview renderers (per format + template)
  // ---------------------------------------------------------------
  const TPL_PREVIEWS = {
    // ---- PDF ----
    pdf: {
      executive: (bg) => `
        <div class="tpl-mock tpl-mock-pdf">
          <div class="tpl-mock-hero" style="background:${bg}">
            <span class="tpl-mock-hero-title">Executive Report · Q1 2025</span>
          </div>
          <div class="tpl-mock-kpi-row">
            <div class="tpl-mock-kpi" style="background:#f0f4ff"><div class="tpl-mock-kpi-lbl" style="color:#666">Revenue</div><div class="tpl-mock-kpi-val" style="color:${bg}">€ 4.2M</div></div>
            <div class="tpl-mock-kpi" style="background:#f0f4ff"><div class="tpl-mock-kpi-lbl" style="color:#666">Growth</div><div class="tpl-mock-kpi-val" style="color:${bg}">+18%</div></div>
            <div class="tpl-mock-kpi" style="background:#f0f4ff"><div class="tpl-mock-kpi-lbl" style="color:#666">Margin</div><div class="tpl-mock-kpi-val" style="color:${bg}">34%</div></div>
          </div>
          <div class="tpl-mock-section">
            <div class="tpl-mock-bar" style="height:7px;width:90%;background:${bg};opacity:.15;"></div>
            <div style="font-size:9px;font-weight:700;color:#1e293b;padding:4px 0 3px">Summary</div>
            <div class="tpl-mock-bar" style="height:5px;width:95%;background:#94a3b8;opacity:.35;"></div>
            <div class="tpl-mock-bar" style="height:5px;width:80%;background:#94a3b8;opacity:.25;margin-top:3px;"></div>
          </div>
          <div class="tpl-mock-section">
            <div style="font-size:9px;font-weight:700;color:#1e293b;padding:2px 0 4px">Data Table</div>
            <table class="tpl-mock-table">
              <tr><th style="background:${bg};color:#fff">Category</th><th style="background:${bg};color:#fff">Value</th><th style="background:${bg};color:#fff">Δ%</th></tr>
              <tr><td style="background:#f8faff">Operations</td><td style="background:#f8faff">1,240</td><td style="background:#f8faff;color:#16a34a">+12%</td></tr>
              <tr><td>Retail</td><td>892</td><td style="color:#dc2626">-4%</td></tr>
              <tr><td style="background:#f8faff">Digital</td><td style="background:#f8faff">2,068</td><td style="background:#f8faff;color:#16a34a">+31%</td></tr>
            </table>
          </div>
        </div>`,
      report: (bg) => `
        <div class="tpl-mock tpl-mock-pdf">
          <div style="height:30px;background:${bg};display:flex;align-items:center;padding:0 14px;gap:8px;">
            <span style="font-size:10px;font-weight:700;color:#fff;">Standard Report</span>
            <span style="font-size:8px;color:rgba(255,255,255,.7);margin-left:auto">2025-Q1</span>
          </div>
          <div class="tpl-mock-section">
            <div class="tpl-mock-bar" style="height:5px;width:60%;background:#334155;opacity:.3;"></div>
            <div class="tpl-mock-bar" style="height:5px;width:85%;background:#334155;opacity:.2;margin-top:3px;"></div>
          </div>
          <div class="tpl-mock-section" style="padding-top:6px">
            <table class="tpl-mock-table">
              <tr><th style="background:#f1f5f9;color:#475569">Column A</th><th style="background:#f1f5f9;color:#475569">Column B</th><th style="background:#f1f5f9;color:#475569">Value</th></tr>
              <tr><td>Alpha</td><td>Group 1</td><td>1,024</td></tr>
              <tr style="background:#f8faff"><td>Beta</td><td>Group 2</td><td>766</td></tr>
              <tr><td>Gamma</td><td>Group 1</td><td>3,210</td></tr>
              <tr style="background:#f8faff"><td>Delta</td><td>Group 3</td><td>490</td></tr>
              <tr><td>Epsilon</td><td>Group 2</td><td>1,855</td></tr>
            </table>
          </div>
        </div>`,
      compact: (bg) => `
        <div class="tpl-mock tpl-mock-pdf">
          <div style="height:20px;background:${bg};display:flex;align-items:center;padding:0 10px;">
            <span style="font-size:8px;font-weight:700;color:#fff;">Data Export · Compact</span>
            <span style="font-size:7px;color:rgba(255,255,255,.7);margin-left:auto">All rows</span>
          </div>
          <div style="padding:4px 10px">
            <table class="tpl-mock-table">
              <tr><th style="background:#e2e8f0;color:#334155">Cat.</th><th style="background:#e2e8f0;color:#334155">Sub</th><th style="background:#e2e8f0;color:#334155">Val</th><th style="background:#e2e8f0;color:#334155">Δ</th></tr>
              <tr><td>A1</td><td>G1</td><td>104</td><td style="color:#16a34a">+2</td></tr>
              <tr style="background:#f8faff"><td>A2</td><td>G2</td><td>76</td><td style="color:#dc2626">-1</td></tr>
              <tr><td>B1</td><td>G1</td><td>321</td><td style="color:#16a34a">+5</td></tr>
              <tr style="background:#f8faff"><td>B2</td><td>G3</td><td>49</td><td>0</td></tr>
              <tr><td>C1</td><td>G2</td><td>185</td><td style="color:#16a34a">+8</td></tr>
              <tr style="background:#f8faff"><td>C2</td><td>G1</td><td>230</td><td style="color:#16a34a">+3</td></tr>
              <tr><td>D1</td><td>G2</td><td>91</td><td style="color:#dc2626">-2</td></tr>
              <tr style="background:#f8faff"><td>D2</td><td>G3</td><td>410</td><td style="color:#16a34a">+12</td></tr>
            </table>
          </div>
        </div>`,
      confidential: (bg) => `
        <div class="tpl-mock tpl-mock-pdf">
          <div style="height:28px;background:#b91c1c;display:flex;align-items:center;padding:0 14px;gap:8px;">
            <span style="font-size:9px;font-weight:800;color:#fff;letter-spacing:.06em">⛔ CONFIDENTIAL</span>
            <span style="font-size:7px;color:rgba(255,255,255,.7);margin-left:auto">Restricted</span>
          </div>
          <div class="tpl-mock-section">
            <div style="font-size:8px;color:#7f1d1d;font-weight:600;margin-bottom:4px">For authorized recipients only — do not distribute</div>
            <div class="tpl-mock-bar" style="height:5px;width:90%;background:#94a3b8;opacity:.3;"></div>
            <div class="tpl-mock-bar" style="height:5px;width:70%;background:#94a3b8;opacity:.2;margin-top:3px;"></div>
          </div>
          <div class="tpl-mock-section">
            <table class="tpl-mock-table">
              <tr><th style="background:#7f1d1d;color:#fff">Item</th><th style="background:#7f1d1d;color:#fff">Class.</th><th style="background:#7f1d1d;color:#fff">Value</th></tr>
              <tr><td>Segment A</td><td style="color:#b91c1c;font-weight:600">Secret</td><td>████</td></tr>
              <tr style="background:#fff5f5"><td>Segment B</td><td style="color:#d97706;font-weight:600">Private</td><td>1,024</td></tr>
              <tr><td>Segment C</td><td style="color:#b91c1c;font-weight:600">Secret</td><td>██████</td></tr>
            </table>
          </div>
          <div style="padding:6px 14px;font-size:7px;color:#94a3b8">Generated: 2025-01-15 · Classification: CONFIDENTIAL</div>
        </div>`
      ,
      annual: (bg) => `
        <div class="tpl-mock tpl-mock-pdf">
          <div style="height:42px;background:${bg};display:flex;flex-direction:column;justify-content:center;padding:0 14px;">
            <div style="font-size:8px;color:rgba(255,255,255,.6)">Annual Review</div>
            <div style="font-size:14px;font-weight:800;color:#fff;letter-spacing:.02em">2025 Full Year</div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:0;">
            <div style="padding:8px 12px;border-right:1px solid #e2e8f0;">
              <div style="font-size:9px;font-weight:700;color:#1e293b;border-bottom:1px solid #e2e8f0;padding-bottom:3px;margin-bottom:5px">2025</div>
              <div style="font-size:8px;color:#334155;margin-bottom:2px">Revenue: <b>€4.2M</b></div>
              <div style="font-size:8px;color:#334155;margin-bottom:2px">Margin: <b>34%</b></div>
              <div style="font-size:8px;color:#334155;margin-bottom:2px">Customers: <b>1,248</b></div>
            </div>
            <div style="padding:8px 12px;">
              <div style="font-size:9px;font-weight:700;color:#1e293b;border-bottom:1px solid #e2e8f0;padding-bottom:3px;margin-bottom:5px">2024</div>
              <div style="font-size:8px;color:#94a3b8;margin-bottom:2px">Revenue: €3.6M</div>
              <div style="font-size:8px;color:#94a3b8;margin-bottom:2px">Margin: 31%</div>
              <div style="font-size:8px;color:#94a3b8;margin-bottom:2px">Customers: 1,102</div>
            </div>
          </div>
          <div style="padding:6px 14px;background:#f8faff;border-top:1px solid #e2e8f0">
            <div style="font-size:8px;font-weight:600;color:${bg};margin-bottom:3px">Year-over-Year Changes</div>
            <div style="display:flex;gap:10px">
              <span style="font-size:8px;color:#16a34a">▲ Revenue +16%</span>
              <span style="font-size:8px;color:#16a34a">▲ Margin +3pp</span>
              <span style="font-size:8px;color:#16a34a">▲ Customers +13%</span>
            </div>
          </div>
        </div>`,
      narrative: (bg) => `
        <div class="tpl-mock tpl-mock-pdf">
          <div style="height:22px;background:${bg};display:flex;align-items:center;padding:0 14px;">
            <span style="font-size:9px;font-weight:700;color:#fff">Q1 2025 Brief</span>
          </div>
          <div style="padding:10px 14px;">
            <div style="font-size:9px;font-weight:700;color:#0f172a;margin-bottom:6px">Executive Overview</div>
            <div style="font-size:8px;color:#334155;line-height:1.55;margin-bottom:8px">Revenue reached €4.2M this quarter, up 18% year-over-year driven by strong digital channel performance.</div>
            <div style="background:#f0f4ff;border-left:3px solid ${bg};padding:6px 10px;border-radius:0 6px 6px 0;margin-bottom:8px">
              <div style="font-size:8px;font-weight:600;color:${bg}">Key Insight</div>
              <div style="font-size:8px;color:#334155">Digital segment grew 31%, representing 47% of total revenue.</div>
            </div>
          </div>
        </div>`,
      landscape: (bg) => `
        <div class="tpl-mock tpl-mock-pdf" style="background:#fafcff;">
          <div style="height:22px;background:${bg};display:flex;align-items:center;padding:0 14px;">
            <span style="font-size:9px;font-weight:700;color:#fff">Wide Landscape Report · Q1 2025</span>
          </div>
          <div style="display:flex;gap:0;">
            <div style="flex:1;padding:8px 10px;border-right:1px solid #e2e8f0;">
              <div style="font-size:8px;font-weight:600;color:#334155;margin-bottom:4px">Data Table</div>
              <table class="tpl-mock-table">
                <tr><th style="background:${bg};color:#fff">Cat.</th><th style="background:${bg};color:#fff">Val</th></tr>
                <tr><td>Alpha</td><td>1,024</td></tr>
                <tr style="background:#f8faff"><td>Beta</td><td>766</td></tr>
              </table>
            </div>
            <div style="flex:1;padding:8px 10px;">
              <div style="font-size:8px;font-weight:600;color:#334155;margin-bottom:4px">Bar Chart</div>
              <div style="display:flex;align-items:flex-end;gap:5px;height:60px;">
                <div style="flex:1;background:${bg};opacity:.8;border-radius:2px 2px 0 0;height:40%"></div>
                <div style="flex:1;background:${bg};opacity:.8;border-radius:2px 2px 0 0;height:30%"></div>
                <div style="flex:1;background:${bg};opacity:.9;border-radius:2px 2px 0 0;height:90%"></div>
                <div style="flex:1;background:${bg};opacity:.7;border-radius:2px 2px 0 0;height:22%"></div>
              </div>
            </div>
          </div>
        </div>`
      ,
      regulatory: (bg) => `
        <div class="tpl-mock tpl-mock-pdf">
          <div style="height:24px;background:#0f766e;display:flex;align-items:center;padding:0 14px;gap:8px;">
            <span style="font-size:9px;font-weight:700;color:#fff">Regulatory Annex</span>
            <span style="font-size:7px;color:rgba(255,255,255,.7);margin-left:auto">Article 12 / Control Matrix</span>
          </div>
          <div style="padding:8px 14px;display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <div style="border:1px solid #d1e6e2;border-radius:6px;padding:6px 8px;background:#f0fdfa;">
              <div style="font-size:8px;font-weight:700;color:#0f766e;margin-bottom:4px">Risk Flags</div>
              <div style="font-size:8px;color:#334155">• Model drift: Low</div>
              <div style="font-size:8px;color:#334155">• Data lineage: Complete</div>
              <div style="font-size:8px;color:#334155">• Override count: 2</div>
            </div>
            <div style="border:1px solid #d1e6e2;border-radius:6px;padding:6px 8px;background:#f0fdfa;">
              <div style="font-size:8px;font-weight:700;color:#0f766e;margin-bottom:4px">Control Status</div>
              <div style="font-size:8px;color:#16a34a">✔ 8 Passed</div>
              <div style="font-size:8px;color:#eab308">● 1 Warning</div>
              <div style="font-size:8px;color:#dc2626">✖ 0 Failed</div>
            </div>
          </div>
          <div style="padding:0 14px 10px;">
            <table class="tpl-mock-table">
              <tr><th style="background:#0f766e;color:#fff">Control</th><th style="background:#0f766e;color:#fff">Owner</th><th style="background:#0f766e;color:#fff">Status</th></tr>
              <tr><td>KYC sampling</td><td>Compliance</td><td style="color:#16a34a">Pass</td></tr>
              <tr style="background:#f8fffd"><td>AML threshold</td><td>Risk</td><td style="color:#eab308">Watch</td></tr>
              <tr><td>Model explainability</td><td>Data Science</td><td style="color:#16a34a">Pass</td></tr>
            </table>
          </div>
        </div>`
    },
    // ---- XLSX ----
    xlsx: {
      modern: (bg) => `
        <div class="tpl-mock tpl-mock-xlsx">
          <div class="tpl-mock-xlsx-topbar" style="background:#1f7a4a">
            <span class="tpl-mock-xlsx-tab" style="background:#fff;color:#1f7a4a">Summary</span>
            <span class="tpl-mock-xlsx-tab" style="color:rgba(255,255,255,.7)">Data</span>
            <span class="tpl-mock-xlsx-tab" style="color:rgba(255,255,255,.7)">Charts</span>
          </div>
          <div class="tpl-mock-xlsx-grid">
            <div class="tpl-mock-xlsx-hrow">
              <div class="tpl-mock-xlsx-cell hdr" style="background:#1f7a4a;color:#fff;min-width:80px">Category</div>
              <div class="tpl-mock-xlsx-cell hdr" style="background:#1f7a4a;color:#fff">Total</div>
              <div class="tpl-mock-xlsx-cell hdr" style="background:#1f7a4a;color:#fff">Share%</div>
              <div class="tpl-mock-xlsx-cell hdr" style="background:#1f7a4a;color:#fff">Trend</div>
            </div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell" style="min-width:80px">Operations</div><div class="tpl-mock-xlsx-cell">1,240</div><div class="tpl-mock-xlsx-cell">28%</div><div class="tpl-mock-xlsx-cell" style="color:#16a34a">▲ 12%</div></div>
            <div class="tpl-mock-xlsx-hrow" style="background:#f0faf5"><div class="tpl-mock-xlsx-cell" style="min-width:80px">Retail</div><div class="tpl-mock-xlsx-cell">892</div><div class="tpl-mock-xlsx-cell">20%</div><div class="tpl-mock-xlsx-cell" style="color:#dc2626">▼ 4%</div></div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell" style="min-width:80px">Digital</div><div class="tpl-mock-xlsx-cell">2,068</div><div class="tpl-mock-xlsx-cell">47%</div><div class="tpl-mock-xlsx-cell" style="color:#16a34a">▲ 31%</div></div>
            <div class="tpl-mock-xlsx-hrow" style="background:#f0faf5"><div class="tpl-mock-xlsx-cell" style="min-width:80px">Other</div><div class="tpl-mock-xlsx-cell">220</div><div class="tpl-mock-xlsx-cell">5%</div><div class="tpl-mock-xlsx-cell">— 0%</div></div>
            <div class="tpl-mock-xlsx-hrow" style="border-top:2px solid #1f7a4a"><div class="tpl-mock-xlsx-cell hdr" style="font-weight:700;min-width:80px">Total</div><div class="tpl-mock-xlsx-cell hdr" style="font-weight:700">4,420</div><div class="tpl-mock-xlsx-cell hdr" style="font-weight:700">100%</div><div class="tpl-mock-xlsx-cell hdr" style="color:#16a34a;font-weight:700">▲ 18%</div></div>
          </div>
          <div class="tpl-mock-bar-chart" style="background:#f9fafb;border-top:1px solid #e2e8f0">
            <div class="tpl-mock-bar-item" style="height:55%;background:#1f7a4a;opacity:.8"></div>
            <div class="tpl-mock-bar-item" style="height:40%;background:#1f7a4a;opacity:.8"></div>
            <div class="tpl-mock-bar-item" style="height:90%;background:#1f7a4a;opacity:.8"></div>
            <div class="tpl-mock-bar-item" style="height:20%;background:#1f7a4a;opacity:.8"></div>
          </div>
        </div>`,
      financial: (bg) => `
        <div class="tpl-mock tpl-mock-xlsx">
          <div class="tpl-mock-xlsx-topbar" style="background:#0f4c2a">
            <span class="tpl-mock-xlsx-tab" style="background:#fff;color:#0f4c2a">P&amp;L</span>
            <span class="tpl-mock-xlsx-tab" style="color:rgba(255,255,255,.7)">Balance</span>
            <span class="tpl-mock-xlsx-tab" style="color:rgba(255,255,255,.7)">Data</span>
          </div>
          <div class="tpl-mock-xlsx-grid">
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell hdr" style="background:#0f4c2a;color:#fff;min-width:100px">Item</div><div class="tpl-mock-xlsx-cell hdr" style="background:#0f4c2a;color:#fff">2025</div><div class="tpl-mock-xlsx-cell hdr" style="background:#0f4c2a;color:#fff">2024</div><div class="tpl-mock-xlsx-cell hdr" style="background:#0f4c2a;color:#fff">Δ</div></div>
            <div class="tpl-mock-xlsx-hrow" style="background:#f0faf5"><div class="tpl-mock-xlsx-cell hdr" style="min-width:100px">Revenue</div><div class="tpl-mock-xlsx-cell">4,200,000</div><div class="tpl-mock-xlsx-cell">3,600,000</div><div class="tpl-mock-xlsx-cell" style="color:#16a34a">+16%</div></div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell" style="min-width:100px;padding-left:16px">Gross Profit</div><div class="tpl-mock-xlsx-cell">2,940,000</div><div class="tpl-mock-xlsx-cell">2,448,000</div><div class="tpl-mock-xlsx-cell" style="color:#16a34a">+20%</div></div>
            <div class="tpl-mock-xlsx-hrow" style="background:#f0faf5"><div class="tpl-mock-xlsx-cell" style="min-width:100px;padding-left:16px">EBITDA</div><div class="tpl-mock-xlsx-cell">1,260,000</div><div class="tpl-mock-xlsx-cell">1,080,000</div><div class="tpl-mock-xlsx-cell" style="color:#16a34a">+17%</div></div>
            <div class="tpl-mock-xlsx-hrow" style="border-top:2px solid #0f4c2a"><div class="tpl-mock-xlsx-cell hdr" style="min-width:100px">Net Income</div><div class="tpl-mock-xlsx-cell hdr" style="font-weight:700">840,000</div><div class="tpl-mock-xlsx-cell hdr">720,000</div><div class="tpl-mock-xlsx-cell hdr" style="color:#16a34a;font-weight:700">+17%</div></div>
          </div>
        </div>`,
      pivot: (bg) => `
        <div class="tpl-mock tpl-mock-xlsx">
          <div class="tpl-mock-xlsx-topbar" style="background:#6d28d9">
            <span class="tpl-mock-xlsx-tab" style="background:#fff;color:#6d28d9">Pivot</span>
            <span class="tpl-mock-xlsx-tab" style="color:rgba(255,255,255,.7)">Source</span>
          </div>
          <div class="tpl-mock-xlsx-grid">
            <div class="tpl-mock-xlsx-hrow">
              <div class="tpl-mock-xlsx-cell hdr" style="background:#4c1d95;color:#fff;min-width:70px">↓ Cat \ Region →</div>
              <div class="tpl-mock-xlsx-cell hdr" style="background:#4c1d95;color:#fff">North</div>
              <div class="tpl-mock-xlsx-cell hdr" style="background:#4c1d95;color:#fff">South</div>
              <div class="tpl-mock-xlsx-cell hdr" style="background:#4c1d95;color:#fff">Total</div>
            </div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell hdr" style="background:#ede9fe;min-width:70px">Product A</div><div class="tpl-mock-xlsx-cell">450</div><div class="tpl-mock-xlsx-cell">620</div><div class="tpl-mock-xlsx-cell hdr" style="font-weight:700">1,070</div></div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell hdr" style="background:#ede9fe;min-width:70px">Product B</div><div class="tpl-mock-xlsx-cell">820</div><div class="tpl-mock-xlsx-cell">310</div><div class="tpl-mock-xlsx-cell hdr" style="font-weight:700">1,130</div></div>
            <div class="tpl-mock-xlsx-hrow" style="border-top:2px solid #6d28d9"><div class="tpl-mock-xlsx-cell hdr" style="background:#ddd6fe;min-width:70px">Grand Total</div><div class="tpl-mock-xlsx-cell hdr" style="font-weight:700">1,270</div><div class="tpl-mock-xlsx-cell hdr" style="font-weight:700">930</div><div class="tpl-mock-xlsx-cell hdr" style="font-weight:800;color:#6d28d9">2,200</div></div>
          </div>
        </div>`,
      scorecard: (bg) => `
        <div class="tpl-mock tpl-mock-xlsx">
          <div class="tpl-mock-xlsx-topbar" style="background:#92400e">
            <span class="tpl-mock-xlsx-tab" style="background:#fff;color:#92400e">Scorecard</span>
            <span class="tpl-mock-xlsx-tab" style="color:rgba(255,255,255,.7)">Data</span>
          </div>
          <div class="tpl-mock-xlsx-grid">
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell hdr" style="background:#78350f;color:#fff;min-width:90px">KPI</div><div class="tpl-mock-xlsx-cell hdr" style="background:#78350f;color:#fff">Actual</div><div class="tpl-mock-xlsx-cell hdr" style="background:#78350f;color:#fff">Target</div><div class="tpl-mock-xlsx-cell hdr" style="background:#78350f;color:#fff">Status</div></div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell" style="min-width:90px">Revenue</div><div class="tpl-mock-xlsx-cell">4.2M</div><div class="tpl-mock-xlsx-cell">4.0M</div><div class="tpl-mock-xlsx-cell" style="color:#fff;background:#16a34a;font-weight:700;text-align:center">● ON</div></div>
            <div class="tpl-mock-xlsx-hrow" style="background:#fefce8"><div class="tpl-mock-xlsx-cell" style="min-width:90px">Margin</div><div class="tpl-mock-xlsx-cell">32%</div><div class="tpl-mock-xlsx-cell">35%</div><div class="tpl-mock-xlsx-cell" style="color:#fff;background:#eab308;font-weight:700;text-align:center">● AT RISK</div></div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell" style="min-width:90px">Churn</div><div class="tpl-mock-xlsx-cell">3.2%</div><div class="tpl-mock-xlsx-cell">2.5%</div><div class="tpl-mock-xlsx-cell" style="color:#fff;background:#dc2626;font-weight:700;text-align:center">● MISS</div></div>
            <div class="tpl-mock-xlsx-hrow" style="background:#f0fdf4"><div class="tpl-mock-xlsx-cell" style="min-width:90px">NPS</div><div class="tpl-mock-xlsx-cell">62</div><div class="tpl-mock-xlsx-cell">55</div><div class="tpl-mock-xlsx-cell" style="color:#fff;background:#16a34a;font-weight:700;text-align:center">● ON</div></div>
          </div>
        </div>`,
      executive: (bg) => `
        <div class="tpl-mock tpl-mock-xlsx">
          <div class="tpl-mock-xlsx-topbar" style="background:#2d3a50">
            <span class="tpl-mock-xlsx-tab" style="background:#fff;color:#2d3a50">KPIs</span>
            <span class="tpl-mock-xlsx-tab" style="color:rgba(255,255,255,.7)">Data</span>
            <span class="tpl-mock-xlsx-tab" style="color:rgba(255,255,255,.7)">Pivot</span>
          </div>
          <div style="display:flex;gap:8px;padding:10px 12px;background:#f8faff">
            <div style="flex:1;background:#fff;border:1px solid #dde6f4;border-radius:6px;padding:7px 10px">
              <div style="font-size:8px;color:#64748b">Revenue</div>
              <div style="font-size:13px;font-weight:700;color:#2d3a50">€ 4.2M</div>
            </div>
            <div style="flex:1;background:#fff;border:1px solid #dde6f4;border-radius:6px;padding:7px 10px">
              <div style="font-size:8px;color:#64748b">Growth</div>
              <div style="font-size:13px;font-weight:700;color:#16a34a">+18%</div>
            </div>
            <div style="flex:1;background:#fff;border:1px solid #dde6f4;border-radius:6px;padding:7px 10px">
              <div style="font-size:8px;color:#64748b">Margin</div>
              <div style="font-size:13px;font-weight:700;color:#2d3a50">34%</div>
            </div>
          </div>
          <div class="tpl-mock-xlsx-grid">
            <div class="tpl-mock-xlsx-hrow">
              <div class="tpl-mock-xlsx-cell hdr" style="background:#2d3a50;color:#fff;min-width:80px">Category</div>
              <div class="tpl-mock-xlsx-cell hdr" style="background:#2d3a50;color:#fff">Value</div>
              <div class="tpl-mock-xlsx-cell hdr" style="background:#2d3a50;color:#fff">vs. Prior</div>
            </div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell" style="min-width:80px">Operations</div><div class="tpl-mock-xlsx-cell">1,240</div><div class="tpl-mock-xlsx-cell" style="color:#16a34a">+12%</div></div>
            <div class="tpl-mock-xlsx-hrow" style="background:#f8faff"><div class="tpl-mock-xlsx-cell" style="min-width:80px">Retail</div><div class="tpl-mock-xlsx-cell">892</div><div class="tpl-mock-xlsx-cell" style="color:#dc2626">-4%</div></div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell" style="min-width:80px">Digital</div><div class="tpl-mock-xlsx-cell">2,068</div><div class="tpl-mock-xlsx-cell" style="color:#16a34a">+31%</div></div>
          </div>
        </div>`,
      clean: (bg) => `
        <div class="tpl-mock tpl-mock-xlsx">
          <div class="tpl-mock-xlsx-topbar" style="background:#94a3b8">
            <span class="tpl-mock-xlsx-tab" style="background:#fff;color:#475569">Sheet1</span>
          </div>
          <div class="tpl-mock-xlsx-grid">
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell hdr" style="background:#f1f5f9;color:#334155;min-width:70px">Column A</div><div class="tpl-mock-xlsx-cell hdr" style="background:#f1f5f9;color:#334155">Column B</div><div class="tpl-mock-xlsx-cell hdr" style="background:#f1f5f9;color:#334155">Column C</div><div class="tpl-mock-xlsx-cell hdr" style="background:#f1f5f9;color:#334155">Column D</div></div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell" style="min-width:70px">Alpha</div><div class="tpl-mock-xlsx-cell">Group 1</div><div class="tpl-mock-xlsx-cell">1,024</div><div class="tpl-mock-xlsx-cell">2025-01</div></div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell" style="min-width:70px">Beta</div><div class="tpl-mock-xlsx-cell">Group 2</div><div class="tpl-mock-xlsx-cell">766</div><div class="tpl-mock-xlsx-cell">2025-01</div></div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell" style="min-width:70px">Gamma</div><div class="tpl-mock-xlsx-cell">Group 1</div><div class="tpl-mock-xlsx-cell">3,210</div><div class="tpl-mock-xlsx-cell">2025-02</div></div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell" style="min-width:70px">Delta</div><div class="tpl-mock-xlsx-cell">Group 3</div><div class="tpl-mock-xlsx-cell">490</div><div class="tpl-mock-xlsx-cell">2025-02</div></div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell" style="min-width:70px">Epsilon</div><div class="tpl-mock-xlsx-cell">Group 2</div><div class="tpl-mock-xlsx-cell">1,855</div><div class="tpl-mock-xlsx-cell">2025-03</div></div>
          </div>
        </div>`,
      dashboard: (bg) => `
        <div class="tpl-mock tpl-mock-xlsx">
          <div class="tpl-mock-xlsx-topbar" style="background:#0c63e7">
            <span class="tpl-mock-xlsx-tab" style="background:#fff;color:#0c63e7">Dashboard</span>
            <span class="tpl-mock-xlsx-tab" style="color:rgba(255,255,255,.7)">Data</span>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:10px 12px;background:#f8faff">
            <div style="background:#fff;border:1px solid #dde6f4;border-radius:6px;padding:8px 10px">
              <div style="font-size:8px;font-weight:600;color:#1d4ed8;margin-bottom:4px">Revenue Trend</div>
              <div style="display:flex;align-items:flex-end;gap:4px;height:40px">
                <div style="flex:1;background:#bfdbfe;border-radius:1px 1px 0 0;height:30%"></div>
                <div style="flex:1;background:#3b82f6;border-radius:1px 1px 0 0;height:55%"></div>
                <div style="flex:1;background:#3b82f6;border-radius:1px 1px 0 0;height:70%"></div>
                <div style="flex:1;background:#1d4ed8;border-radius:1px 1px 0 0;height:90%"></div>
              </div>
            </div>
            <div style="background:#fff;border:1px solid #dde6f4;border-radius:6px;padding:8px 10px">
              <div style="font-size:8px;font-weight:600;color:#1d4ed8;margin-bottom:4px">Share by Category</div>
              <div style="display:flex;height:40px;border-radius:3px;overflow:hidden">
                <div style="flex:28;background:#1d4ed8"></div>
                <div style="flex:20;background:#3b82f6"></div>
                <div style="flex:47;background:#93c5fd"></div>
                <div style="flex:5;background:#dbeafe"></div>
              </div>
            </div>
          </div>
          <div class="tpl-mock-xlsx-grid">
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell hdr" style="background:#0c63e7;color:#fff;min-width:80px">kpi_name</div><div class="tpl-mock-xlsx-cell hdr" style="background:#0c63e7;color:#fff">value</div><div class="tpl-mock-xlsx-cell hdr" style="background:#0c63e7;color:#fff">target</div></div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell" style="min-width:80px">revenue_total</div><div class="tpl-mock-xlsx-cell">4420000</div><div class="tpl-mock-xlsx-cell">4000000</div></div>
            <div class="tpl-mock-xlsx-hrow" style="background:#f0f6ff"><div class="tpl-mock-xlsx-cell" style="min-width:80px">growth_rate</div><div class="tpl-mock-xlsx-cell">0.18</div><div class="tpl-mock-xlsx-cell">0.15</div></div>
          </div>
        </div>`
      ,
      forecast: (bg) => `
        <div class="tpl-mock tpl-mock-xlsx">
          <div class="tpl-mock-xlsx-topbar" style="background:#0e7490">
            <span class="tpl-mock-xlsx-tab" style="background:#fff;color:#0e7490">Forecast</span>
            <span class="tpl-mock-xlsx-tab" style="color:rgba(255,255,255,.7)">Assumptions</span>
            <span class="tpl-mock-xlsx-tab" style="color:rgba(255,255,255,.7)">Scenarios</span>
          </div>
          <div class="tpl-mock-xlsx-grid">
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell hdr" style="background:#0e7490;color:#fff;min-width:90px">Metric</div><div class="tpl-mock-xlsx-cell hdr" style="background:#0e7490;color:#fff">Base</div><div class="tpl-mock-xlsx-cell hdr" style="background:#0e7490;color:#fff">Upside</div><div class="tpl-mock-xlsx-cell hdr" style="background:#0e7490;color:#fff">Downside</div></div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell" style="min-width:90px">Revenue</div><div class="tpl-mock-xlsx-cell">4.2M</div><div class="tpl-mock-xlsx-cell" style="color:#16a34a">4.7M</div><div class="tpl-mock-xlsx-cell" style="color:#dc2626">3.8M</div></div>
            <div class="tpl-mock-xlsx-hrow" style="background:#f0fbff"><div class="tpl-mock-xlsx-cell" style="min-width:90px">Gross Margin</div><div class="tpl-mock-xlsx-cell">34%</div><div class="tpl-mock-xlsx-cell" style="color:#16a34a">37%</div><div class="tpl-mock-xlsx-cell" style="color:#dc2626">30%</div></div>
            <div class="tpl-mock-xlsx-hrow"><div class="tpl-mock-xlsx-cell" style="min-width:90px">Cash Burn</div><div class="tpl-mock-xlsx-cell">420k</div><div class="tpl-mock-xlsx-cell">380k</div><div class="tpl-mock-xlsx-cell" style="color:#dc2626">510k</div></div>
          </div>
          <div class="tpl-mock-bar-chart" style="background:#f8fafc;border-top:1px solid #e2e8f0">
            <div class="tpl-mock-bar-item" style="height:58%;background:#0e7490;opacity:.85"></div>
            <div class="tpl-mock-bar-item" style="height:70%;background:#16a34a;opacity:.85"></div>
            <div class="tpl-mock-bar-item" style="height:45%;background:#dc2626;opacity:.75"></div>
            <div class="tpl-mock-bar-item" style="height:62%;background:#0e7490;opacity:.85"></div>
          </div>
        </div>`
    },
    // ---- PPT ----
    ppt: {
      full: (bg) => `
        <div style="background:#e5e7eb;padding:12px;display:flex;flex-direction:column;gap:8px">
          <div style="font-size:9px;font-weight:600;color:#6b7280;margin-bottom:2px">5 slides · Full Executive Deck</div>
          <div class="tpl-mock tpl-mock-slide" style="border-radius:6px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12)">
            <div class="tpl-mock-slide-hero" style="background:${bg};height:62px;align-items:center;padding:0 16px">
              <div><div style="font-size:8px;color:rgba(255,255,255,.7)">Executive Report · Q1 2025</div><div style="font-size:14px;font-weight:700;color:#fff">Performance Overview</div></div>
            </div>
            <div style="padding:8px 14px;display:flex;gap:8px">
              <div style="flex:1;background:#f8faff;border-radius:5px;padding:6px 8px"><div style="font-size:7px;color:#64748b">Revenue</div><div style="font-size:11px;font-weight:700;color:${bg}">€4.2M</div></div>
              <div style="flex:1;background:#f8faff;border-radius:5px;padding:6px 8px"><div style="font-size:7px;color:#64748b">Growth</div><div style="font-size:11px;font-weight:700;color:#16a34a">+18%</div></div>
              <div style="flex:1;background:#f8faff;border-radius:5px;padding:6px 8px"><div style="font-size:7px;color:#64748b">Margin</div><div style="font-size:11px;font-weight:700;color:${bg}">34%</div></div>
            </div>
          </div>
          <div style="display:flex;gap:8px">
            <div class="tpl-mock tpl-mock-slide" style="flex:1;border-radius:6px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12)">
              <div style="height:16px;background:${bg};opacity:.8;display:flex;align-items:center;padding:0 8px"><span style="font-size:7px;color:#fff;font-weight:600">Executive Summary</span></div>
              <div style="padding:6px 8px"><div style="height:4px;background:#e2e8f0;border-radius:2px;margin-bottom:3px;width:90%"></div><div style="height:4px;background:#e2e8f0;border-radius:2px;margin-bottom:3px;width:75%"></div><div style="height:4px;background:#e2e8f0;border-radius:2px;width:82%"></div></div>
            </div>
            <div class="tpl-mock tpl-mock-slide" style="flex:1;border-radius:6px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12)">
              <div style="height:16px;background:${bg};opacity:.8;display:flex;align-items:center;padding:0 8px"><span style="font-size:7px;color:#fff;font-weight:600">Data Snapshot</span></div>
              <div style="padding:6px 8px;display:flex;align-items:flex-end;gap:3px;height:38px">
                <div style="flex:1;background:${bg};opacity:.7;border-radius:1px 1px 0 0;height:60%"></div>
                <div style="flex:1;background:${bg};opacity:.7;border-radius:1px 1px 0 0;height:90%"></div>
                <div style="flex:1;background:${bg};opacity:.7;border-radius:1px 1px 0 0;height:45%"></div>
                <div style="flex:1;background:${bg};opacity:.7;border-radius:1px 1px 0 0;height:75%"></div>
              </div>
            </div>
          </div>
        </div>`,
      kpi: (bg) => `
        <div style="background:#e5e7eb;padding:12px;display:flex;flex-direction:column;gap:8px">
          <div style="font-size:9px;font-weight:600;color:#6b7280;margin-bottom:2px">3 slides · KPI Board</div>
          <div class="tpl-mock tpl-mock-slide" style="border-radius:6px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12)">
            <div style="height:24px;background:${bg};display:flex;align-items:center;padding:0 14px"><span style="font-size:10px;font-weight:700;color:#fff">KPI Dashboard · Q1 2025</span></div>
            <div style="padding:10px 12px;display:grid;grid-template-columns:1fr 1fr;gap:8px">
              <div style="background:#f8faff;border:1px solid #e2e8f0;border-radius:6px;padding:8px 10px;border-left:3px solid ${bg}"><div style="font-size:7px;color:#64748b">Revenue</div><div style="font-size:13px;font-weight:700;color:${bg}">€4.2M</div><div style="font-size:7px;color:#16a34a">▲ 18% vs prior</div></div>
              <div style="background:#f8faff;border:1px solid #e2e8f0;border-radius:6px;padding:8px 10px;border-left:3px solid #16a34a"><div style="font-size:7px;color:#64748b">Net Margin</div><div style="font-size:13px;font-weight:700;color:#0f172a">34%</div><div style="font-size:7px;color:#16a34a">▲ 3pp vs prior</div></div>
              <div style="background:#f8faff;border:1px solid #e2e8f0;border-radius:6px;padding:8px 10px;border-left:3px solid ${bg}"><div style="font-size:7px;color:#64748b">Transactions</div><div style="font-size:13px;font-weight:700;color:${bg}">12,048</div><div style="font-size:7px;color:#dc2626">▼ 4% vs prior</div></div>
              <div style="background:#f8faff;border:1px solid #e2e8f0;border-radius:6px;padding:8px 10px;border-left:3px solid #d97706"><div style="font-size:7px;color:#64748b">CAC</div><div style="font-size:13px;font-weight:700;color:#0f172a">€ 42</div><div style="font-size:7px;color:#d97706">→ stable</div></div>
            </div>
          </div>
        </div>`,
      summary: (bg) => `
        <div style="background:#e5e7eb;padding:12px;display:flex;flex-direction:column;gap:8px">
          <div style="font-size:9px;font-weight:600;color:#6b7280;margin-bottom:2px">2 slides · Quick Summary</div>
          <div class="tpl-mock tpl-mock-slide" style="border-radius:6px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12)">
            <div style="height:28px;background:${bg};display:flex;align-items:center;padding:0 14px"><span style="font-size:11px;font-weight:700;color:#fff">Executive Summary</span></div>
            <div style="padding:10px 14px">
              <div style="height:5px;background:#1e293b;opacity:.15;border-radius:2px;width:95%;margin-bottom:4px"></div>
              <div style="height:5px;background:#1e293b;opacity:.15;border-radius:2px;width:80%;margin-bottom:4px"></div>
              <div style="height:5px;background:#1e293b;opacity:.15;border-radius:2px;width:90%;margin-bottom:8px"></div>
              <div style="height:5px;background:#1e293b;opacity:.1;border-radius:2px;width:70%;margin-bottom:4px"></div>
              <div style="height:5px;background:#1e293b;opacity:.1;border-radius:2px;width:85%;margin-bottom:4px"></div>
              <div style="font-size:8px;color:#64748b;margin-top:8px">AI-generated analysis text with key findings and recommendations.</div>
            </div>
          </div>
        </div>`,
      investor: (bg) => `
        <div style="background:#e5e7eb;padding:12px;display:flex;flex-direction:column;gap:8px">
          <div style="font-size:9px;font-weight:600;color:#6b7280;margin-bottom:2px">5 slides · Investor Pack</div>
          <div class="tpl-mock tpl-mock-slide" style="border-radius:6px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12);background:#0a1628">
            <div style="height:56px;background:linear-gradient(135deg,#1e3a8a,#0c63e7);display:flex;align-items:flex-end;padding:0 16px 10px"><div><div style="font-size:8px;color:rgba(255,255,255,.6)">Investor Brief · Confidential</div><div style="font-size:13px;font-weight:700;color:#fff">Performance Review</div></div></div>
            <div style="padding:8px 12px;display:flex;gap:8px">
              <div style="flex:1;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:5px;padding:6px 8px"><div style="font-size:7px;color:rgba(255,255,255,.5)">ARR</div><div style="font-size:11px;font-weight:700;color:#60a5fa">€4.2M</div></div>
              <div style="flex:1;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:5px;padding:6px 8px"><div style="font-size:7px;color:rgba(255,255,255,.5)">YoY</div><div style="font-size:11px;font-weight:700;color:#34d399">+18%</div></div>
              <div style="flex:1;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:5px;padding:6px 8px"><div style="font-size:7px;color:rgba(255,255,255,.5)">LTV/CAC</div><div style="font-size:11px;font-weight:700;color:#60a5fa">8.2x</div></div>
            </div>
          </div>
        </div>`
      ,
      roadmap: (bg) => `
        <div style="background:#e5e7eb;padding:12px;display:flex;flex-direction:column;gap:8px">
          <div style="font-size:9px;font-weight:600;color:#6b7280;margin-bottom:2px">4 slides · Roadmap &amp; Milestones</div>
          <div class="tpl-mock tpl-mock-slide" style="border-radius:6px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12);background:#fff">
            <div style="height:40px;background:linear-gradient(135deg,#7c3aed,#a855f7);display:flex;align-items:flex-end;padding:0 14px 8px"><div style="font-size:12px;font-weight:700;color:#fff">Product Roadmap 2025</div></div>
            <div style="padding:8px 14px">
              <div style="position:relative;height:6px;background:#e9d5ff;border-radius:3px;margin:6px 0 12px">
                <div style="position:absolute;left:0;top:0;height:6px;width:55%;background:#7c3aed;border-radius:3px"></div>
                <div style="position:absolute;left:15%;top:-4px;width:14px;height:14px;background:#fff;border:2px solid #7c3aed;border-radius:50%;display:flex;align-items:center;justify-content:center"></div>
                <div style="position:absolute;left:40%;top:-4px;width:14px;height:14px;background:#7c3aed;border:2px solid #7c3aed;border-radius:50%"></div>
                <div style="position:absolute;left:68%;top:-4px;width:14px;height:14px;background:#e9d5ff;border:2px solid #7c3aed;border-radius:50%"></div>
                <div style="position:absolute;left:90%;top:-4px;width:14px;height:14px;background:#e9d5ff;border:2px solid #a855f7;border-radius:50%"></div>
              </div>
              <div style="display:flex;justify-content:space-between;margin-top:4px">
                <div style="font-size:7px;color:#7c3aed;font-weight:600">Q1 ✓</div>
                <div style="font-size:7px;color:#7c3aed;font-weight:600">Q2 ✓</div>
                <div style="font-size:7px;color:#9ca3af">Q3</div>
                <div style="font-size:7px;color:#9ca3af">Q4</div>
              </div>
            </div>
          </div>
        </div>`,
      oneshot: (bg) => `
        <div style="background:#e5e7eb;padding:12px;display:flex;flex-direction:column;gap:8px">
          <div style="font-size:9px;font-weight:600;color:#6b7280;margin-bottom:2px">1 slide · One-Pager</div>
          <div class="tpl-mock tpl-mock-slide" style="border-radius:6px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12);background:#fff">
            <div style="height:28px;background:#0f172a;display:flex;align-items:center;padding:0 12px;gap:6px"><div style="font-size:10px;font-weight:700;color:#fff">SITUATION · ACTION · RESULT</div></div>
            <div style="padding:6px 10px;display:flex;gap:6px">
              <div style="flex:1"><div style="font-size:7px;font-weight:600;color:#0f172a;margin-bottom:3px">Key KPIs</div>
                <div style="display:flex;gap:4px;margin-bottom:4px">
                  <div style="flex:1;background:#f1f5f9;border-radius:3px;padding:4px;text-align:center"><div style="font-size:8px;font-weight:700;color:#0f172a">€4.2M</div></div>
                  <div style="flex:1;background:#f1f5f9;border-radius:3px;padding:4px;text-align:center"><div style="font-size:8px;font-weight:700;color:#16a34a">+18%</div></div>
                </div>
              </div>
              <div style="flex:1"><div style="font-size:7px;font-weight:600;color:#0f172a;margin-bottom:3px">Conclusion</div>
                <div style="height:4px;background:#cbd5e1;border-radius:2px;width:90%;margin-bottom:3px"></div>
                <div style="height:4px;background:#cbd5e1;border-radius:2px;width:70%"></div>
              </div>
            </div>
          </div>
        </div>`,
      quarterly: (bg) => `
        <div style="background:#e5e7eb;padding:12px;display:flex;flex-direction:column;gap:8px">
          <div style="font-size:9px;font-weight:600;color:#6b7280;margin-bottom:2px">6 slides · QBR</div>
          <div class="tpl-mock tpl-mock-slide" style="border-radius:6px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12);background:#fff">
            <div style="height:36px;background:linear-gradient(135deg,#0f766e,#14b8a6);display:flex;align-items:flex-end;padding:0 14px 8px"><div style="font-size:12px;font-weight:700;color:#fff">Q1 2025 Business Review</div></div>
            <div style="padding:8px 14px">
              <div style="display:flex;flex-direction:column;gap:4px">
                <div style="display:flex;align-items:center;gap:6px"><div style="font-size:7px;color:#374151;width:48px">Revenue</div><div style="flex:1;height:8px;background:#ccfbf1;border-radius:4px"><div style="height:8px;width:88%;background:#14b8a6;border-radius:4px"></div></div><div style="font-size:7px;color:#0f766e;font-weight:600;width:24px">88%</div></div>
                <div style="display:flex;align-items:center;gap:6px"><div style="font-size:7px;color:#374151;width:48px">Margin</div><div style="flex:1;height:8px;background:#fef9c3;border-radius:4px"><div style="height:8px;width:65%;background:#eab308;border-radius:4px"></div></div><div style="font-size:7px;color:#ca8a04;font-weight:600;width:24px">65%</div></div>
                <div style="display:flex;align-items:center;gap:6px"><div style="font-size:7px;color:#374151;width:48px">Churn</div><div style="flex:1;height:8px;background:#fee2e2;border-radius:4px"><div style="height:8px;width:40%;background:#ef4444;border-radius:4px"></div></div><div style="font-size:7px;color:#dc2626;font-weight:600;width:24px">40%</div></div>
                <div style="display:flex;align-items:center;gap:6px"><div style="font-size:7px;color:#374151;width:48px">NPS</div><div style="flex:1;height:8px;background:#ccfbf1;border-radius:4px"><div style="height:8px;width:92%;background:#0f766e;border-radius:4px"></div></div><div style="font-size:7px;color:#0f766e;font-weight:600;width:24px">92%</div></div>
              </div>
            </div>
          </div>
        </div>`,
      boardroom: (bg) => `
        <div style="background:#e5e7eb;padding:12px;display:flex;flex-direction:column;gap:8px">
          <div style="font-size:9px;font-weight:600;color:#6b7280;margin-bottom:2px">5 slides · Boardroom Briefing</div>
          <div class="tpl-mock tpl-mock-slide" style="border-radius:6px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12);background:#fff">
            <div style="height:34px;background:linear-gradient(135deg,#334155,#475569);display:flex;align-items:flex-end;padding:0 14px 8px"><div style="font-size:12px;font-weight:700;color:#fff">Board Decisions & Risks</div></div>
            <div style="padding:8px 14px;display:grid;grid-template-columns:1fr 1fr;gap:8px">
              <div style="border:1px solid #e2e8f0;border-radius:6px;padding:6px 8px;background:#f8fafc"><div style="font-size:8px;font-weight:700;color:#1e293b;margin-bottom:3px">Decisions</div><div style="font-size:7px;color:#334155">• Expand EU operations<br/>• Keep hiring freeze</div></div>
              <div style="border:1px solid #e2e8f0;border-radius:6px;padding:6px 8px;background:#f8fafc"><div style="font-size:8px;font-weight:700;color:#1e293b;margin-bottom:3px">Risks</div><div style="font-size:7px;color:#334155">• FX exposure<br/>• Supplier concentration</div></div>
            </div>
            <div style="padding:0 14px 10px"><div style="height:6px;background:#e2e8f0;border-radius:3px"><div style="height:6px;width:72%;background:#334155;border-radius:3px"></div></div></div>
          </div>
        </div>`,
    },
    // ---- HTML ----
    html: {
      executive: (bg) => `
        <div class="tpl-mock tpl-mock-html">
          <div class="tpl-mock-html-nav" style="background:${bg}">
            <span style="font-size:10px;font-weight:700;color:#fff">Executive Report</span>
            <span class="tpl-mock-html-nav-tab" style="background:rgba(255,255,255,.2);color:#fff;margin-left:auto">KPIs</span>
            <span class="tpl-mock-html-nav-tab" style="color:rgba(255,255,255,.6)">Charts</span>
            <span class="tpl-mock-html-nav-tab" style="color:rgba(255,255,255,.6)">Data</span>
          </div>
          <div class="tpl-mock-html-body">
            <div class="tpl-mock-html-kpi" style="border-left:3px solid ${bg}"><div style="font-size:8px;color:#64748b">Revenue</div><div style="font-size:13px;font-weight:700;color:${bg}">€4.2M</div></div>
            <div class="tpl-mock-html-kpi" style="border-left:3px solid #16a34a"><div style="font-size:8px;color:#64748b">Growth</div><div style="font-size:13px;font-weight:700;color:#16a34a">+18%</div></div>
            <div class="tpl-mock-html-kpi" style="border-left:3px solid ${bg}"><div style="font-size:8px;color:#64748b">Margin</div><div style="font-size:13px;font-weight:700;color:${bg}">34%</div></div>
            <div class="tpl-mock-html-chart">
              <div style="flex:1;background:#dbeafe;border-radius:1px 1px 0 0;height:40%"></div>
              <div style="flex:1;background:#3b82f6;border-radius:1px 1px 0 0;height:65%"></div>
              <div style="flex:1;background:#3b82f6;border-radius:1px 1px 0 0;height:50%"></div>
              <div style="flex:1;background:#1d4ed8;border-radius:1px 1px 0 0;height:85%"></div>
              <div style="flex:1;background:#1d4ed8;border-radius:1px 1px 0 0;height:70%"></div>
              <div style="flex:1;background:#3b82f6;border-radius:1px 1px 0 0;height:55%"></div>
            </div>
          </div>
        </div>`,
      board: (bg) => `
        <div class="tpl-mock tpl-mock-html" style="background:#fff">
          <div style="height:34px;background:#1d2430;display:flex;align-items:center;padding:0 14px;gap:8px">
            <span style="font-size:9px;font-weight:700;color:#fff;letter-spacing:.04em">BOARD PACKAGE</span>
            <span style="font-size:8px;color:rgba(255,255,255,.5);margin-left:auto">Q1 2025 · Confidential</span>
          </div>
          <div style="padding:10px 14px">
            <div style="font-size:9px;font-weight:700;color:#1d2430;margin-bottom:5px;border-bottom:1px solid #e2e8f0;padding-bottom:4px">Executive Summary</div>
            <div style="height:4px;background:#94a3b8;opacity:.3;border-radius:2px;width:95%;margin-bottom:3px"></div>
            <div style="height:4px;background:#94a3b8;opacity:.3;border-radius:2px;width:80%;margin-bottom:3px"></div>
            <div style="height:4px;background:#94a3b8;opacity:.3;border-radius:2px;width:88%;margin-bottom:10px"></div>
            <div style="font-size:9px;font-weight:700;color:#1d2430;margin-bottom:5px;border-bottom:1px solid #e2e8f0;padding-bottom:4px">Key Metrics</div>
            <div style="display:flex;gap:8px">
              <div style="flex:1;border:1px solid #e2e8f0;border-radius:5px;padding:6px 8px"><div style="font-size:7px;color:#64748b">Revenue</div><div style="font-size:12px;font-weight:700;color:#1d2430">€4.2M</div></div>
              <div style="flex:1;border:1px solid #e2e8f0;border-radius:5px;padding:6px 8px"><div style="font-size:7px;color:#64748b">Margin</div><div style="font-size:12px;font-weight:700;color:#1d2430">34%</div></div>
              <div style="flex:1;border:1px solid #e2e8f0;border-radius:5px;padding:6px 8px"><div style="font-size:7px;color:#64748b">YoY</div><div style="font-size:12px;font-weight:700;color:#16a34a">+18%</div></div>
            </div>
          </div>
        </div>`,
      analytics: (bg) => `
        <div class="tpl-mock tpl-mock-html" style="background:#0f172a">
          <div style="height:28px;background:#0c63e7;display:flex;align-items:center;padding:0 12px;gap:8px">
            <span style="font-size:9px;font-weight:700;color:#fff">Analytics Dashboard</span>
            <span style="font-size:8px;color:rgba(255,255,255,.6);margin-left:auto">Live · 6 panels</span>
          </div>
          <div style="padding:8px 10px;display:grid;grid-template-columns:1fr 1fr;gap:6px">
            <div style="background:#1e293b;border-radius:5px;padding:7px 8px">
              <div style="font-size:7px;color:#64748b;margin-bottom:4px">Revenue</div>
              <div style="display:flex;align-items:flex-end;gap:2px;height:36px">
                <div style="flex:1;background:#3b82f6;opacity:.5;border-radius:1px 1px 0 0;height:40%"></div>
                <div style="flex:1;background:#3b82f6;opacity:.7;border-radius:1px 1px 0 0;height:65%"></div>
                <div style="flex:1;background:#3b82f6;border-radius:1px 1px 0 0;height:90%"></div>
                <div style="flex:1;background:#3b82f6;border-radius:1px 1px 0 0;height:75%"></div>
              </div>
            </div>
            <div style="background:#1e293b;border-radius:5px;padding:7px 8px">
              <div style="font-size:7px;color:#64748b;margin-bottom:4px">Share</div>
              <div style="display:flex;height:36px;border-radius:3px;overflow:hidden;margin-top:4px">
                <div style="flex:28;background:#1d4ed8"></div>
                <div style="flex:20;background:#3b82f6"></div>
                <div style="flex:47;background:#60a5fa"></div>
                <div style="flex:5;background:#93c5fd"></div>
              </div>
            </div>
            <div style="background:#1e293b;border-radius:5px;padding:7px 8px;grid-column:span 2">
              <div style="font-size:7px;color:#64748b;margin-bottom:4px">Monthly Trend</div>
              <div style="height:30px;display:flex;align-items:center;padding:0 4px">
                <svg viewBox="0 0 180 30" width="100%" height="30" xmlns="http://www.w3.org/2000/svg"><polyline points="0,25 30,20 60,18 90,12 120,10 150,8 180,5" fill="none" stroke="#3b82f6" stroke-width="2"/><polyline points="0,28 30,27 60,25 90,24 120,22 150,20 180,18" fill="none" stroke="#60a5fa" stroke-width="1.5" stroke-dasharray="3,3"/></svg>
              </div>
            </div>
          </div>
        </div>`,
      minimal: (bg) => `
        <div class="tpl-mock tpl-mock-html" style="background:#fff">
          <div style="height:24px;border-bottom:1px solid #e2e8f0;display:flex;align-items:center;padding:0 14px">
            <span style="font-size:9px;font-weight:600;color:#1e293b">Q1 2025 Report</span>
            <span style="font-size:8px;color:#94a3b8;margin-left:auto">Generated 2025-01-15</span>
          </div>
          <div style="padding:12px 14px">
            <div style="font-size:11px;font-weight:700;color:#0f172a;margin-bottom:8px">Summary</div>
            <div style="height:4px;background:#e2e8f0;border-radius:2px;width:95%;margin-bottom:4px"></div>
            <div style="height:4px;background:#e2e8f0;border-radius:2px;width:80%;margin-bottom:4px"></div>
            <div style="height:4px;background:#e2e8f0;border-radius:2px;width:88%;margin-bottom:12px"></div>
            <div style="font-size:11px;font-weight:700;color:#0f172a;margin-bottom:8px">Metrics</div>
            <div style="border:1px solid #e2e8f0;border-radius:6px;overflow:hidden">
              <div style="display:flex;border-bottom:1px solid #e2e8f0;background:#f8faff"><div style="flex:2;padding:5px 10px;font-size:8px;font-weight:600;color:#475569">Indicator</div><div style="flex:1;padding:5px 10px;font-size:8px;font-weight:600;color:#475569">Value</div></div>
              <div style="display:flex;border-bottom:1px solid #e2e8f0"><div style="flex:2;padding:5px 10px;font-size:8px;color:#334155">Total Revenue</div><div style="flex:1;padding:5px 10px;font-size:8px;color:#334155">€ 4,420,000</div></div>
              <div style="display:flex"><div style="flex:2;padding:5px 10px;font-size:8px;color:#334155">Growth (YoY)</div><div style="flex:1;padding:5px 10px;font-size:8px;color:#16a34a">+18%</div></div>
            </div>
          </div>
        </div>`
      ,
      dark: (bg) => `
        <div class="tpl-mock tpl-mock-html" style="background:#0f172a">
          <div style="height:28px;background:#020617;display:flex;align-items:center;padding:0 14px;gap:10px">
            <span style="font-size:9px;font-weight:700;color:#f8fafc;letter-spacing:.04em">ANALYTICS</span>
            <span style="font-size:8px;color:#64748b;margin-left:auto">Q1 2025</span>
          </div>
          <div style="padding:8px 12px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px">
            <div style="background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px"><div style="font-size:7px;color:#94a3b8">Revenue</div><div style="font-size:12px;font-weight:700;color:#38bdf8">€4.2M</div></div>
            <div style="background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px"><div style="font-size:7px;color:#94a3b8">Growth</div><div style="font-size:12px;font-weight:700;color:#4ade80">+18%</div></div>
            <div style="background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px"><div style="font-size:7px;color:#94a3b8">Margin</div><div style="font-size:12px;font-weight:700;color:#38bdf8">34%</div></div>
          </div>
          <div style="padding:0 12px 8px">
            <div style="display:flex;align-items:flex-end;gap:4px;height:52px;background:#1e293b;border-radius:6px;padding:6px 8px">
              <div style="flex:1;background:#38bdf8;opacity:.5;border-radius:2px 2px 0 0;height:35%"></div>
              <div style="flex:1;background:#38bdf8;opacity:.7;border-radius:2px 2px 0 0;height:55%"></div>
              <div style="flex:1;background:#38bdf8;border-radius:2px 2px 0 0;height:85%"></div>
              <div style="flex:1;background:#38bdf8;opacity:.8;border-radius:2px 2px 0 0;height:68%"></div>
              <div style="flex:1;background:rgba(56,189,248,.3);border-radius:2px 2px 0 0;height:20%"></div>
              <div style="flex:1;background:#4ade80;border-radius:2px 2px 0 0;height:90%"></div>
            </div>
          </div>
        </div>`,
      newspaper: (bg) => `
        <div class="tpl-mock tpl-mock-html" style="background:#fff">
          <div style="border-bottom:3px solid #0f172a;padding:6px 14px;display:flex;align-items:center">
            <div style="font-size:11px;font-weight:900;color:#0f172a;letter-spacing:.05em">FINANCIAL REPORT</div>
            <div style="font-size:7px;color:#64748b;margin-left:auto">Q1 2025 · Audela</div>
          </div>
          <div style="display:flex;gap:0;padding:8px 0 0">
            <div style="flex:1;padding:0 12px;border-right:1px solid #e2e8f0">
              <div style="font-size:8px;font-weight:700;color:#0f172a;margin-bottom:4px">Revenue hits €4.2M</div>
              <div style="height:4px;background:#e2e8f0;border-radius:2px;width:100%;margin-bottom:3px"></div>
              <div style="height:4px;background:#e2e8f0;border-radius:2px;width:85%;margin-bottom:3px"></div>
              <div style="height:4px;background:#e2e8f0;border-radius:2px;width:92%"></div>
              <div style="margin-top:8px;background:#f1f5f9;border-left:3px solid #0f172a;padding:4px 7px"><div style="font-size:7px;font-style:italic;color:#334155">"Digital leads with 47% share"</div></div>
            </div>
            <div style="flex:1;padding:0 12px">
              <div style="font-size:8px;font-weight:700;color:#0f172a;margin-bottom:4px">Key Indicators</div>
              <div style="display:flex;flex-direction:column;gap:4px">
                <div style="display:flex;justify-content:space-between"><span style="font-size:7px;color:#475569">Gross Margin</span><span style="font-size:7px;font-weight:600">34%</span></div>
                <div style="display:flex;justify-content:space-between"><span style="font-size:7px;color:#475569">YoY</span><span style="font-size:7px;font-weight:600;color:#16a34a">+18%</span></div>
                <div style="display:flex;justify-content:space-between"><span style="font-size:7px;color:#475569">Customers</span><span style="font-size:7px;font-weight:600">1,248</span></div>
              </div>
            </div>
          </div>
        </div>`,
      cto: (bg) => `
        <div class="tpl-mock tpl-mock-html" style="background:#fafafa">
          <div style="height:28px;background:#1d2430;display:flex;align-items:center;padding:0 14px;gap:8px">
            <span style="font-size:9px;font-weight:700;color:#fff;font-family:monospace">TECH BRIEF</span>
            <span style="font-size:7px;color:rgba(255,255,255,.5);margin-left:auto;font-family:monospace">Q1 2025</span>
          </div>
          <div style="padding:8px 12px">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:6px">
              <div style="background:#f1f5f9;border-radius:4px;padding:5px 8px;border-left:3px solid #3b82f6"><div style="font-size:7px;color:#64748b">Uptime</div><div style="font-size:10px;font-weight:700;color:#1d2430">99.97%</div></div>
              <div style="background:#f1f5f9;border-radius:4px;padding:5px 8px;border-left:3px solid #16a34a"><div style="font-size:7px;color:#64748b">P99 Latency</div><div style="font-size:10px;font-weight:700;color:#1d2430">142ms</div></div>
              <div style="background:#f1f5f9;border-radius:4px;padding:5px 8px;border-left:3px solid #8b5cf6"><div style="font-size:7px;color:#64748b">Deploys</div><div style="font-size:10px;font-weight:700;color:#1d2430">38</div></div>
              <div style="background:#f1f5f9;border-radius:4px;padding:5px 8px;border-left:3px solid #f59e0b"><div style="font-size:7px;color:#64748b">Incidents</div><div style="font-size:10px;font-weight:700;color:#d97706">2</div></div>
            </div>
          </div>
        </div>`
      ,
      portfolio: (bg) => `
        <div class="tpl-mock tpl-mock-html" style="background:#f6fff9">
          <div style="height:28px;background:#14532d;display:flex;align-items:center;padding:0 14px;gap:8px">
            <span style="font-size:9px;font-weight:700;color:#fff">PORTFOLIO SNAPSHOT</span>
            <span style="font-size:7px;color:rgba(255,255,255,.65);margin-left:auto">Monthly</span>
          </div>
          <div style="padding:8px 12px;display:grid;grid-template-columns:1fr 1fr;gap:6px">
            <div style="background:#fff;border:1px solid #d9eee0;border-radius:6px;padding:6px 8px"><div style="font-size:7px;color:#64748b">Total AUM</div><div style="font-size:12px;font-weight:700;color:#14532d">€28.4M</div></div>
            <div style="background:#fff;border:1px solid #d9eee0;border-radius:6px;padding:6px 8px"><div style="font-size:7px;color:#64748b">Monthly Perf</div><div style="font-size:12px;font-weight:700;color:#16a34a">+2.4%</div></div>
            <div style="background:#fff;border:1px solid #d9eee0;border-radius:6px;padding:6px 8px;grid-column:span 2">
              <div style="font-size:7px;color:#64748b;margin-bottom:4px">Allocation</div>
              <div style="display:flex;height:10px;border-radius:6px;overflow:hidden">
                <div style="flex:45;background:#14532d"></div>
                <div style="flex:30;background:#16a34a"></div>
                <div style="flex:15;background:#4ade80"></div>
                <div style="flex:10;background:#bbf7d0"></div>
              </div>
            </div>
          </div>
        </div>`
    }
  };

  function renderTplPreview (format, tplId, accentColor) {
    const formatPreviews = TPL_PREVIEWS[format];
    if (!formatPreviews) return '<div style="padding:20px;color:#94a3b8;font-size:.9rem">No preview available.</div>';
    const fn = formatPreviews[tplId];
    if (!fn) return '<div style="padding:20px;color:#94a3b8;font-size:.9rem">No preview available.</div>';
    return fn(accentColor || '#1d4ed8');
  }

  function openTemplatePicker (format) {
    return new Promise((resolve, reject) => {
      const overlay    = qs('#studioTplOverlay');
      const sidebar    = qs('#studioTplSidebar');
      const titleEl    = qs('#studioTplTitle');
      const subtitleEl = qs('#studioTplSubtitle');
      const confirmBtn = qs('#studioTplConfirm');
      const cancelBtn  = qs('#studioTplCancel');
      const closeBtn   = qs('#studioTplClose');
      const titleInput = qs('#studioTplTitleInput');
      const previewTitle = qs('#studioTplPreviewTitle');
      const previewDesc  = qs('#studioTplPreviewDesc');
      const badgesEl     = qs('#studioTplBadges');
      const visualEl     = qs('#studioTplVisual');
      if (!overlay || !sidebar) { resolve(null); return; }

      const meta = FORMAT_META[format] || { title: 'Choose a template', subtitle: '' };
      titleEl.textContent = t(meta.title);
      subtitleEl.textContent = t(meta.subtitle);
      titleInput.value = '';

      const templates = EXPORT_TEMPLATES[format] || [];
      sidebar.innerHTML = '';
      let selected = templates[0] ? templates[0].id : null;

      function updatePreview (tpl) {
        if (!tpl) return;
        previewTitle.textContent = t(tpl.name);
        previewDesc.textContent  = t(tpl.desc);
        // Feature tags from keywords
        badgesEl.innerHTML = '';
        const tags = (tpl.keywords || tpl.name).split(/[\s;,]+/).filter(Boolean).slice(0, 6);
        tags.forEach((tag) => {
          const b = el('span', 'tpl-badge');
          b.textContent = tag;
          badgesEl.appendChild(b);
        });
        visualEl.innerHTML = renderTplPreview(format, tpl.id, tpl.icon.bg);
      }

      function selectRow (id) {
        selected = id;
        sidebar.querySelectorAll('.tpl-row').forEach((r) => {
          r.classList.toggle('selected', r.dataset.tplId === id);
        });
        const tpl = templates.find((x) => x.id === id);
        if (tpl) updatePreview(tpl);
      }

      templates.forEach((tpl) => {
        const row = el('div', 'tpl-row' + (tpl.id === selected ? ' selected' : ''));
        row.dataset.tplId = tpl.id;
        // Small thumb SVG (scaled down from icon paths)
        const thumb = el('div', 'tpl-row-thumb');
        thumb.style.background = tpl.icon.bg;
        thumb.innerHTML = buildTplThumb(tpl.icon);
        const label = el('div', 'tpl-row-label');
        label.textContent = t(tpl.name);
        row.appendChild(thumb);
        row.appendChild(label);
        row.addEventListener('click', () => selectRow(tpl.id));
        sidebar.appendChild(row);
      });

      // Show initial preview
      if (templates[0]) updatePreview(templates[0]);

      overlay.classList.add('open');

      function close (result) {
        overlay.classList.remove('open');
        confirmBtn.removeEventListener('click', onConfirm);
        cancelBtn.removeEventListener('click',  onCancel);
        closeBtn.removeEventListener('click',   onCancel);
        overlay.removeEventListener('click',    onOverlayClick);
        if (result) resolve(result); else reject(new Error('cancelled'));
      }

      function onConfirm () {
        const tpl = templates.find((x) => x.id === selected);
        close({ tpl: tpl || templates[0], customTitle: String(titleInput.value || '').trim() });
      }
      function onCancel () { close(null); }
      function onOverlayClick (e) { if (e.target === overlay) onCancel(); }

      confirmBtn.addEventListener('click', onConfirm);
      cancelBtn.addEventListener('click',  onCancel);
      closeBtn.addEventListener('click',   onCancel);
      overlay.addEventListener('click',    onOverlayClick);
    });
  }

  async function boot () {
    const rootEl = qs('#studioRoot');
    const sourceEl = qs('#studioSource');
    const promptEl = qs('#studioPrompt');
    const logEl = qs('#studioLog');
    const statusEl = qs('#studioStatus');
    const sqlEl = qs('#studioSql');
    const filesListEl = qs('#studioFilesList');
    const uploadInput = qs('#studioUploadInput');
    const pinnedContextEl = qs('#studioPinnedContext');
    const stylePresetEl = qs('#studioStylePreset');
    const styleGuideEl = qs('#studioStyleGuide');
    const contextMetaEl = qs('#studioContextMeta');

    const runBtn = qs('#studioRun');
    const dashboardBtn = qs('#studioDashboard');
    const pdfBtn = qs('#studioPdf');
    const excelBtn = qs('#studioExcel');
    const pptBtn = qs('#studioPpt');
    const execBtn = qs('#studioExecutive');

    const saveCtxBtn = qs('#studioSaveContext');
    const resetCtxBtn = qs('#studioResetContext');
    const refreshFilesBtn = qs('#studioRefreshFiles');
    const uploadBtn = qs('#studioUploadBtn');

    if (!sourceEl || !promptEl || !logEl || !statusEl || !sqlEl || !filesListEl || !uploadInput || !pinnedContextEl || !stylePresetEl || !styleGuideEl || !contextMetaEl) return;

    let files = [];
    let attachedIds = new Set();
    let lastResult = null;
    const PRESET_PREF_KEY = 'biLiteStudioStylePreset';

    const STYLE_PRESETS = {
      banking: {
        guide: 'style corporate board; palette graphite; sections kpi charts trends timeline data; images banking finance executive risk management; tone concise for banking committee',
        excelTheme: 'graphite'
      },
      investor: {
        guide: 'style editorial; palette ocean blue; sections kpi charts trends timeline data; tone concise with strategic highlights',
        excelTheme: 'ocean'
      },
      operations: {
        guide: 'style modern tech; palette forest green; sections kpi charts data timeline; tone operational and actionable',
        excelTheme: 'forest'
      }
    };

    function activeStyleGuide () {
      const preset = String(stylePresetEl.value || 'custom');
      const manual = String(styleGuideEl.value || '').trim();
      if (manual) return manual;
      return preset !== 'custom' && STYLE_PRESETS[preset] ? String(STYLE_PRESETS[preset].guide || '') : '';
    }

    function activeExcelTheme () {
      const preset = String(stylePresetEl.value || 'custom');
      if (preset !== 'custom' && STYLE_PRESETS[preset]) return String(STYLE_PRESETS[preset].excelTheme || 'ocean');
      return 'ocean';
    }

    function applyVisualTheme () {
      if (!rootEl) return;
      const preset = String(stylePresetEl.value || 'custom');
      rootEl.setAttribute('data-studio-theme', preset);
    }

    function applyPresetGuide (force) {
      const preset = String(stylePresetEl.value || 'custom');
      if (preset === 'custom') return;
      const entry = STYLE_PRESETS[preset] || null;
      if (!entry) return;
      if (force || !String(styleGuideEl.value || '').trim()) {
        styleGuideEl.value = String(entry.guide || '');
      }
    }

    function setStatus (txt) {
      statusEl.textContent = String(txt || '');
    }

    function setLoading (flag) {
      const disabled = !!flag;
      [runBtn, dashboardBtn, pdfBtn, excelBtn, pptBtn, execBtn, saveCtxBtn, resetCtxBtn, refreshFilesBtn, uploadBtn]
        .forEach((x) => { if (x) x.disabled = disabled; });
    }

    function selectedFileIds () {
      return Array.from(attachedIds.values());
    }

    function renderFiles () {
      filesListEl.innerHTML = '';
      if (!files.length) {
        const empty = el('div', 'p-2 small text-secondary');
        empty.textContent = t('No files yet. Upload CSV/Excel/Parquet data files.');
        filesListEl.appendChild(empty);
        return;
      }

      for (const f of files) {
        const row = el('label', 'studio-file-item');
        const input = el('input', 'form-check-input');
        input.type = 'checkbox';
        input.checked = attachedIds.has(Number(f.id));
        input.addEventListener('change', () => {
          if (input.checked) attachedIds.add(Number(f.id));
          else attachedIds.delete(Number(f.id));
          contextMetaEl.textContent = `${attachedIds.size} ${t('file(s) attached for context')}`;
        });

        const body = el('div', 'small');
        body.innerHTML = `<div class="fw-semibold">${fileLabel(f)}</div>`;

        row.appendChild(input);
        row.appendChild(body);
        filesListEl.appendChild(row);
      }

      contextMetaEl.textContent = `${attachedIds.size} ${t('file(s) attached for context')}`;
    }

    async function loadContext () {
      const payload = await fetchJson('/app/api/ai/studio/context', {
        method: 'GET',
        credentials: 'same-origin'
      });
      pinnedContextEl.value = String(payload.pinned_context || '');
      styleGuideEl.value = String(payload.style_guide || '');
      contextMetaEl.textContent = `${Number(payload.memory_count || 0)} ${t('memory turn(s) in session')}`;
    }

    async function saveContext (clearMemory) {
      const payload = await fetchJson('/app/api/ai/studio/context', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken() ? { 'X-CSRFToken': csrfToken() } : {})
        },
        body: JSON.stringify({
          pinned_context: pinnedContextEl.value || '',
          style_guide: activeStyleGuide(),
          clear_memory: !!clearMemory
        })
      });
      contextMetaEl.textContent = `${Number(payload.memory_count || 0)} ${t('memory turn(s) in session')}`;
      setStatus(t('Context saved.'));
    }

    async function loadFiles () {
      const payload = await fetchJson('/app/api/ai/studio/files', {
        method: 'GET',
        credentials: 'same-origin'
      });
      files = Array.isArray(payload.files) ? payload.files : [];
      const valid = new Set(files.map((f) => Number(f.id)));
      attachedIds = new Set(Array.from(attachedIds).filter((x) => valid.has(x)));
      renderFiles();
    }

    async function uploadFile () {
      const f = uploadInput.files && uploadInput.files[0];
      if (!f) {
        setStatus(t('Choose a file first.'));
        return;
      }
      const fd = new FormData();
      fd.append('file', f);

      const resp = await fetch('/app/api/ai/studio/upload', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          ...(csrfToken() ? { 'X-CSRFToken': csrfToken() } : {})
        },
        body: fd
      });
      const payload = await resp.json().catch(() => ({}));
      if (!resp.ok || payload.ok === false) {
        throw new Error(payload.error || t('Upload failed.'));
      }

      const file = payload.file || null;
      if (file && file.id) {
        files.unshift(file);
        attachedIds.add(Number(file.id));
      }
      renderFiles();
      uploadInput.value = '';
      setStatus(t('File uploaded and attached to context.'));
    }

    async function runAnalysis () {
      const sourceId = Number(sourceEl.value || 0);
      const message = String(promptEl.value || '').trim();
      if (!sourceId) throw new Error(t('Select a data source.'));
      if (!message) throw new Error(t('Type your request.'));

      addMessage(logEl, 'user', message);
      setStatus(t('Analyzing...'));

      const payload = await fetchJson('/app/api/ai/studio/run', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken() ? { 'X-CSRFToken': csrfToken() } : {})
        },
        body: JSON.stringify({
          source_id: sourceId,
          message,
          attached_file_ids: selectedFileIds(),
          use_memory: true,
          style_guide: activeStyleGuide()
        })
      });

      const analysis = String(payload.analysis || t('No analysis returned.'));
      addMessage(logEl, 'assistant', analysis);
      sqlEl.textContent = String(payload.sql || '--');
      renderCharts(payload.charts || []);

      if (Array.isArray(payload.warnings) && payload.warnings.length) {
        addMessage(logEl, 'system', `${t('Warnings')}:\n- ${payload.warnings.slice(0, 6).join('\n- ')}`);
      }

      lastResult = {
        source_id: sourceId,
        source_name: (payload.source && payload.source.name) ? String(payload.source.name) : '',
        message,
        analysis,
        sql: String(payload.sql || ''),
        columns: Array.isArray(payload.columns) ? payload.columns : [],
        rows: Array.isArray(payload.rows) ? payload.rows : []
      };

      setStatus(`${Number(payload.row_count || 0)} ${t('rows analyzed')}.`);
    }

    async function createDashboard () {
      if (!lastResult) throw new Error(t('Run analysis first.'));
      const payload = await fetchJson('/app/api/ai/dashboard', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken() ? { 'X-CSRFToken': csrfToken() } : {})
        },
        body: JSON.stringify({
          source_id: lastResult.source_id,
          message: `${lastResult.message}\n\nStyle guide:\n${activeStyleGuide()}`,
          create_comparison: false
        })
      });

      const dash = payload.dashboard || {};
      const name = String(dash.name || t('Dashboard'));
      addMessage(logEl, 'assistant', `${t('Dashboard created')}: ${name}`);
      if (dash.url) {
        window.open(String(dash.url), '_blank', 'noopener');
      }
    }

    async function exportPdf () {
      if (!lastResult) throw new Error(t('Run analysis first.'));
      const choice = await openTemplatePicker('pdf');
      const tpl = choice.tpl;
      const baseGuide = activeStyleGuide();
      const tplKeywords = tpl.keywords || `pdf template ${tpl.id}`;
      const styleGuide = [tplKeywords, baseGuide].filter(Boolean).join('; ');
      const title = choice.customTitle || `${lastResult.message.slice(0, 60) || 'BI'}_report`;
      const resp = await fetch('/app/api/export/pdf', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken() ? { 'X-CSRFToken': csrfToken() } : {})
        },
        body: JSON.stringify({
          title,
          style_guide: styleGuide,
          columns: lastResult.columns,
          rows: lastResult.rows
        })
      });
      if (!resp.ok) throw new Error(t('PDF export failed.'));
      const blob = await resp.blob();
      downloadBlob(blob, `${tpl.id}_report.pdf`);
      setStatus(t('PDF generated.'));
    }

    async function exportExcel () {
      if (!lastResult) throw new Error(t('Run analysis first.'));
      const choice = await openTemplatePicker('xlsx');
      const tpl = choice.tpl;
      const baseGuide = activeStyleGuide();
      const tplKeywords = tpl.keywords || `excel ${tpl.id}`;
      const styleGuide = [tplKeywords, baseGuide].filter(Boolean).join('; ');
      const title = choice.customTitle || `${lastResult.message.slice(0, 60) || 'BI'}_export`;
      const addExtras = tpl.id !== 'clean';
      const resp = await fetch('/app/api/export/xlsx', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken() ? { 'X-CSRFToken': csrfToken() } : {})
        },
        body: JSON.stringify({
          title,
          style_guide: styleGuide,
          columns: lastResult.columns,
          rows: lastResult.rows,
          add_chart: addExtras,
          add_pivot: addExtras,
          template: tpl.excelTemplate || 'clean',
          color_theme: activeExcelTheme()
        })
      });
      if (!resp.ok) throw new Error(t('Excel export failed.'));
      const blob = await resp.blob();
      downloadBlob(blob, `${tpl.id}_export.xlsx`);
      setStatus(t('Excel generated.'));
    }

    async function exportPpt () {
      if (!lastResult) throw new Error(t('Run analysis first.'));
      const choice = await openTemplatePicker('ppt');
      const tpl = choice.tpl;
      const baseGuide = activeStyleGuide();
      const tplKeywords = tpl.keywords || `powerpoint ${tpl.id}`;
      const styleGuide = [tplKeywords, baseGuide].filter(Boolean).join('; ');
      const title = choice.customTitle || `${lastResult.message.slice(0, 60) || 'BI'} deck`;
      const resp = await fetch('/app/api/ai/studio/ppt', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken() ? { 'X-CSRFToken': csrfToken() } : {})
        },
        body: JSON.stringify({
          title,
          source_name: lastResult.source_name,
          analysis: lastResult.analysis,
          columns: lastResult.columns,
          rows: lastResult.rows,
          style_guide: styleGuide
        })
      });
      if (!resp.ok) {
        const payload = await resp.json().catch(() => ({}));
        throw new Error(payload.error || t('PowerPoint generation failed.'));
      }
      const blob = await resp.blob();
      downloadBlob(blob, `${tpl.id}_deck.pptx`);
      setStatus(t('PowerPoint generated.'));
    }

    async function exportExecutiveHtml () {
      if (!lastResult) throw new Error(t('Run analysis first.'));
      const choice = await openTemplatePicker('html');
      const tpl = choice.tpl;
      const baseGuide = activeStyleGuide();
      const tplKeywords = tpl.keywords || `html ${tpl.id}`;
      const execGuide = [tplKeywords, baseGuide].filter(Boolean).join('; ');
      const payload = await fetchJson('/app/api/ai/lite/executive_html', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken() ? { 'X-CSRFToken': csrfToken() } : {})
        },
        body: JSON.stringify({
          source_id: lastResult.source_id,
          message: lastResult.message,
          analysis: lastResult.analysis,
          executive_guide: execGuide
        })
      });

      const html = String(payload.html || '');
      const filename = String(payload.filename || `${tpl.id}_report.html`);
      const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
      downloadBlob(blob, filename);

      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      setStatus(t('Executive HTML generated.'));
    }

    async function guarded (fn) {
      try {
        setLoading(true);
        await fn();
      } catch (e) {
        const msg = String((e && e.message) || e || t('Error'));
        addMessage(logEl, 'system', msg);
        setStatus(msg);
      } finally {
        setLoading(false);
      }
    }

    if (runBtn) runBtn.addEventListener('click', () => guarded(runAnalysis));
    if (dashboardBtn) dashboardBtn.addEventListener('click', () => guarded(createDashboard));
    if (pdfBtn) pdfBtn.addEventListener('click', () => guarded(exportPdf));
    if (excelBtn) excelBtn.addEventListener('click', () => guarded(exportExcel));
    if (pptBtn) pptBtn.addEventListener('click', () => guarded(exportPpt));
    if (execBtn) execBtn.addEventListener('click', () => guarded(exportExecutiveHtml));
    if (refreshFilesBtn) refreshFilesBtn.addEventListener('click', () => guarded(loadFiles));
    if (uploadBtn) uploadBtn.addEventListener('click', () => guarded(uploadFile));
    if (saveCtxBtn) saveCtxBtn.addEventListener('click', () => guarded(() => saveContext(false)));
    if (resetCtxBtn) {
      resetCtxBtn.addEventListener('click', () => guarded(async () => {
        await saveContext(true);
        addMessage(logEl, 'system', t('Session memory reset.'));
      }));
    }

    promptEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (runBtn) runBtn.click();
      }
    });

    stylePresetEl.addEventListener('change', () => {
      applyVisualTheme();
      applyPresetGuide(true);
      try {
        window.localStorage.setItem(PRESET_PREF_KEY, String(stylePresetEl.value || 'custom'));
      } catch (e) {
        // Ignore storage errors.
      }
      setStatus(t('Preset applied to style guide.'));
    });

    try {
      const savedPreset = String(window.localStorage.getItem(PRESET_PREF_KEY) || '').trim();
      if (savedPreset && STYLE_PRESETS[savedPreset]) {
        stylePresetEl.value = savedPreset;
      }
    } catch (e) {
      // Ignore storage errors.
    }

    applyVisualTheme();
    addMessage(logEl, 'assistant', t('Welcome to BI Lite Studio. Pick a source, attach files if needed, and ask what you want to generate.'));
    await guarded(loadContext);
    applyPresetGuide(false);
    applyVisualTheme();
    await guarded(loadFiles);
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
