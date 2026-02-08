/* global BI, marked */

(function () {
  function safeParseJson (txt, fallback) {
    try { return JSON.parse(txt || ''); } catch (e) { return fallback; }
  }

  function getJsonById (id, fallback) {
    if (!id) return fallback;
    const el = document.getElementById(id);
    if (!el) return fallback;
    return safeParseJson(el.textContent || el.innerText || '', fallback);
  }

  function renderMarkdown () {
    const nodes = document.querySelectorAll('[data-rb-md]');
    nodes.forEach((n) => {
      const sid = n.getAttribute('data-rb-md');
      const md = getJsonById(sid, '');
      if (typeof marked !== 'undefined' && marked && typeof marked.parse === 'function') {
        try {
          n.innerHTML = marked.parse(String(md || ''));
        } catch (e) {
          n.textContent = String(md || '');
        }
      } else {
        n.textContent = String(md || '');
      }
    });
  }

  function renderVizzes () {
    const nodes = document.querySelectorAll('.report-viz');
    nodes.forEach((n) => {
      const dataId = n.getAttribute('data-data-id');
      const cfgId = n.getAttribute('data-cfg-id');
      const data = getJsonById(dataId, {});
      const cfg = getJsonById(cfgId, { type: 'table' });
      if (window.BI && typeof window.BI.renderViz === 'function') {
        window.BI.renderViz(n, data || {}, cfg || { type: 'table' });
      } else {
        // basic fallback: try to show table-like JSON
        n.innerHTML = '<pre class="small text-muted" style="white-space:pre-wrap;">' +
          String(JSON.stringify(data || {}, null, 2)) +
          '</pre>';
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    renderMarkdown();
    renderVizzes();
  });
})();
