/* global Sortable */

// MVP Report Builder:
// - Drag from palette into Header/Body/Footer
// - Save layout JSON via /api/reports/<id>

(function () {
  function qs (sel) { return document.querySelector(sel); }

function jsonFetch (url, opts) {
  opts = opts || {};
  const method = String(opts.method || 'GET').toUpperCase();

  const headers = { ...(opts.headers || {}) };

  // Só setar Content-Type em requests com body (POST/PUT/PATCH/DELETE)
  if (method !== 'GET' && method !== 'HEAD') {
    headers['Content-Type'] = 'application/json';

    // CSRF header (Flask-WTF aceita X-CSRFToken / X-CSRF-Token)
    const token = window.__RB && window.__RB.csrfToken;
    if (token) headers['X-CSRFToken'] = token;
  }

  return fetch(url, {
    credentials: 'same-origin',
    headers,
    ...opts
  }).then(async (r) => {
    // Melhor: tenta ler JSON; se vier HTML (ex.: CSRF error), mostra parte do texto
    const txt = await r.text();
    let p = {};
    try { p = txt ? JSON.parse(txt) : {}; } catch (e) { p = { error: txt.slice(0, 200) }; }
    if (!r.ok) throw p;
    return p;
  });
}

  function normalizeDropHints () {
    for (const id of ['rb-header', 'rb-body', 'rb-footer']) {
      const dz = qs('#' + id);
      if (!dz) continue;
      const hint = dz.querySelector('.rb-drop-hint');
      const blocks = Array.from(dz.children).filter(el => el.classList.contains('rb-block-instance'));
      if (hint) hint.style.display = blocks.length ? 'none' : 'block';
    }
  }

  function makeBlockEl (block) {
    const type = block.type || 'text';
    const title = block.title || (type === 'text' ? 'Texto' : type === 'markdown' ? 'Markdown' : 'Pergunta');

    const el = document.createElement('div');
    el.className = 'rb-block rb-block-instance';
    el.setAttribute('data-type', type);
    el.setAttribute('data-title', title);
    if (block.question_id) el.setAttribute('data-question-id', String(block.question_id));
    if (block.text) el.setAttribute('data-text', String(block.text));

    const badgeTxt = type === 'question' ? 'Q' : (type === 'markdown' ? 'MD' : 'T');

    el.innerHTML = `
      <div class="meta">
        <span class="badge text-bg-secondary">${badgeTxt}</span>
        <div>
          <div class="fw-semibold">${escapeHtml(title)}</div>
          <div class="text-muted small">${escapeHtml(blockSummary(block))}</div>
        </div>
      </div>
      <div class="d-flex align-items-center gap-2">
        <button type="button" class="btn btn-sm btn-outline-secondary rb-edit" title="Editar"><i class="bi bi-pencil"></i></button>
        <button type="button" class="btn btn-sm btn-outline-danger rb-remove" title="Remover"><i class="bi bi-x"></i></button>
      </div>
    `;

    el.querySelector('.rb-remove').addEventListener('click', (e) => {
      e.preventDefault();
      el.remove();
      normalizeDropHints();
    });

    el.querySelector('.rb-edit').addEventListener('click', (e) => {
      e.preventDefault();
      editBlock(el);
    });

    return el;
  }

  function escapeHtml (s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function blockSummary (b) {
    if (b.type === 'question') return b.question_name ? `Pergunta: ${b.question_name}` : 'Pergunta salva';
    if (b.type === 'markdown') return (b.text || 'Texto em markdown').slice(0, 60);
    return (b.text || 'Texto simples').slice(0, 60);
  }

  function extractLayoutFromDom () {
    function readZone (id) {
      const dz = qs('#' + id);
      if (!dz) return [];
      const blocks = Array.from(dz.children).filter(el => el.classList.contains('rb-block-instance'));
      return blocks.map(el => {
        const type = el.getAttribute('data-type') || 'text';
        const title = el.getAttribute('data-title') || '';
        const out = { type, title };
        const qid = el.getAttribute('data-question-id');
        if (qid) out.question_id = Number(qid);
        const text = el.getAttribute('data-text');
        if (text) out.text = text;
        return out;
      });
    }

    return {
      version: 1,
      page: { size: 'A4', orientation: 'portrait' },
      sections: {
        header: readZone('rb-header'),
        body: readZone('rb-body'),
        footer: readZone('rb-footer')
      }
    };
  }

  function editBlock (el) {
    const type = el.getAttribute('data-type') || 'text';
    const curTitle = el.getAttribute('data-title') || '';

    let newTitle = prompt('Título do bloco:', curTitle);
    if (newTitle === null) return;
    newTitle = String(newTitle).trim();
    if (!newTitle) newTitle = curTitle || 'Bloco';

    el.setAttribute('data-title', newTitle);

    if (type === 'text' || type === 'markdown') {
      const curText = el.getAttribute('data-text') || '';
      let newText = prompt(type === 'markdown' ? 'Texto (Markdown):' : 'Texto:', curText);
      if (newText === null) newText = curText;
      el.setAttribute('data-text', String(newText));
    }

    // refresh display
    const block = {
      type,
      title: el.getAttribute('data-title') || '',
      text: el.getAttribute('data-text') || '',
      question_id: Number(el.getAttribute('data-question-id') || 0)
    };

    // replace element content keeping handlers
    const parent = el.parentElement;
    const newEl = makeBlockEl(block);
    if (el.getAttribute('data-question-id')) newEl.setAttribute('data-question-id', el.getAttribute('data-question-id'));
    if (parent) parent.replaceChild(newEl, el);
    normalizeDropHints();
  }

  async function boot () {
    const cfg = window.__RB;
    if (!cfg || !cfg.apiUrl) return;

    const palette = qs('#rb-palette');
    const header = qs('#rb-header');
    const body = qs('#rb-body');
    const footer = qs('#rb-footer');
    const saveBtn = qs('#rb-save');

    // Palette sorter: clone items
    Sortable.create(palette, {
      group: { name: 'rb', pull: 'clone', put: false },
      sort: false,
      animation: 150,
      onClone: (evt) => {
        // nothing
      }
    });

    function zoneOptions () {
      return {
        group: { name: 'rb', pull: true, put: true },
        animation: 150,
        // drag by the whole block (simpler + works for cloned blocks)
        onAdd: (evt) => {
          // When a palette item is dropped, convert it to an instance
          const it = evt.item;
          if (!it) return;
          // ignore already-built instances
          if (it.classList.contains('rb-block-instance')) {
            normalizeDropHints();
            return;
          }
          const type = it.getAttribute('data-type') || 'text';
          const title = it.getAttribute('data-title') || (type === 'markdown' ? 'Markdown' : type === 'question' ? 'Tabela' : 'Texto');
          const block = { type, title, text: '' };
          const newEl = makeBlockEl(block);
          it.replaceWith(newEl);
          normalizeDropHints();
        },
        onSort: normalizeDropHints,
        onRemove: normalizeDropHints
      };
    }

    Sortable.create(header, zoneOptions());
    Sortable.create(body, zoneOptions());
    Sortable.create(footer, zoneOptions());

    // Load existing layout
    try {
      const rep = await jsonFetch(cfg.apiUrl);
      const layout = rep.layout || {};
      const secs = (layout.sections || {});
      const zoneMap = { header, body, footer };
      for (const key of ['header', 'body', 'footer']) {
        const dz = zoneMap[key];
        if (!dz) continue;
        dz.innerHTML = '<div class="rb-drop-hint">Arraste aqui...</div>';
        const blocks = Array.isArray(secs[key]) ? secs[key] : [];
        for (const b of blocks) {
          dz.appendChild(makeBlockEl(b));
        }
      }
    } catch (e) {
      // ignore; still usable
    }

    normalizeDropHints();

    // Add question shortcut
    const qSel = qs('#rb-question');
    const addQ = qs('#rb-add-question');
    if (addQ && qSel) {
      addQ.addEventListener('click', (e) => {
        e.preventDefault();
        const qid = Number(qSel.value || 0);
        if (!qid) return;
        const label = qSel.options[qSel.selectedIndex]?.textContent || `Pergunta #${qid}`;
        body.appendChild(makeBlockEl({ type: 'question', title: label, question_id: qid }));
        normalizeDropHints();
      });
    }

    // Save
    if (saveBtn) {
      saveBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        const layout = extractLayoutFromDom();
        saveBtn.disabled = true;
        try {
          await jsonFetch(cfg.saveUrl, { method: 'POST', body: JSON.stringify({ layout }) });
          saveBtn.innerHTML = '<i class="bi bi-check2 me-1"></i>Salvo';
          setTimeout(() => { saveBtn.innerHTML = '<i class="bi bi-save me-1"></i>Salvar'; }, 1200);
        } catch (err) {
          if (window.uiToast) window.uiToast(err?.error || 'Falha ao salvar', { variant: 'danger' });
          else alert(err?.error || 'Falha ao salvar');
        } finally {
          saveBtn.disabled = false;
        }
      });
    }
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
