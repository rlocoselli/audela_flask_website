/* global Sortable, bootstrap */

// Report Builder (banded / Crystal-like):
// - Drag from palette into: ReportHeader, PageHeader, Detail, PageFooter, ReportFooter
// - Blocks: text, markdown, question (table), image, field (date/datetime)
// - Per-block style: text color + background color + alignment
// - Per-question table style: theme, zebra, repeat header, decimals
// - Save layout JSON via /api/reports/<id>

(function () {
  const t = (window.t || (k => k));
  const tf = (window.tf || ((k, vars) => {
    let s = t(k);
    if (!vars) return s;
    for (const key in vars) {
      try { s = s.split('{' + key + '}').join(String(vars[key])); } catch (e) {}
    }
    return s;
  }));

  function qs (sel, root) { return (root || document).querySelector(sel); }
  let _rbUiModal = null;

  function _ensureUiModal () {
    if (_rbUiModal) return _rbUiModal;
    const host = document.createElement('div');
    host.innerHTML = `
      <div class="modal fade" id="rbUiModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="rbUiModalTitle">${escapeHtml(t('Confirmação'))}</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body" id="rbUiModalBody"></div>
            <div class="modal-footer" id="rbUiModalFooter"></div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(host.firstElementChild);
    const el = qs('#rbUiModal');
    _rbUiModal = {
      el,
      title: qs('#rbUiModalTitle'),
      body: qs('#rbUiModalBody'),
      footer: qs('#rbUiModalFooter'),
      bs: new bootstrap.Modal(el)
    };
    return _rbUiModal;
  }

  function rbAlert (message, opts) {
    const o = opts || {};
    const modal = _ensureUiModal();
    modal.title.textContent = String(o.title || t('Information'));
    modal.body.textContent = String(message || '');
    modal.footer.innerHTML = `<button type="button" class="btn btn-primary" data-bs-dismiss="modal">${escapeHtml(t('OK'))}</button>`;
    modal.bs.show();
  }

  function rbConfirm (message, opts) {
    const o = opts || {};
    const modal = _ensureUiModal();
    modal.title.textContent = String(o.title || t('Confirmação'));
    modal.body.textContent = String(message || '');
    modal.footer.innerHTML = `
      <button type="button" class="btn btn-outline-secondary" data-rb-no>${escapeHtml(t('Cancelar'))}</button>
      <button type="button" class="btn btn-primary" data-rb-yes>${escapeHtml(t('Continuer'))}</button>
    `;

    return new Promise(resolve => {
      const yes = modal.footer.querySelector('[data-rb-yes]');
      const no = modal.footer.querySelector('[data-rb-no]');
      const done = (v) => {
        try { yes && yes.removeEventListener('click', onYes); } catch (e) {}
        try { no && no.removeEventListener('click', onNo); } catch (e) {}
        try { modal.el.removeEventListener('hidden.bs.modal', onHidden); } catch (e) {}
        resolve(v);
      };
      const onYes = () => { modal.bs.hide(); done(true); };
      const onNo = () => { modal.bs.hide(); done(false); };
      const onHidden = () => done(false);

      yes && yes.addEventListener('click', onYes);
      no && no.addEventListener('click', onNo);
      modal.el.addEventListener('hidden.bs.modal', onHidden, { once: true });
      modal.bs.show();
    });
  }

  const _placeholderTokens = new Set(['{{date}}', '{{datetime}}']);

  function _registerPlaceholderToken (token) {
    const s = String(token || '').trim();
    if (!s) return;
    _placeholderTokens.add(s);
    _refreshPlaceholderDatalist();
  }

  function _registerBindingPlaceholders (binding) {
    const b = (binding && typeof binding === 'object') ? binding : {};
    const source = String(b.source || '').trim().toLowerCase();
    const field = String(b.field || '').trim();
    if (!field) return;
    if (source === 'question') {
      const qid = Number(b.question_id || 0);
      if (!qid) return;
      _registerPlaceholderToken(`{{question:${qid}.${field}}}`);
      _registerPlaceholderToken(`{{sum(question:${qid}.${field})}}`);
      _registerPlaceholderToken(`{{avg(question:${qid}.${field})}}`);
      _registerPlaceholderToken(`{{count(question:${qid})}}`);
      return;
    }
    if (source === 'table') {
      const table = String(b.table || '').trim();
      if (!table) return;
      _registerPlaceholderToken(`{{table:${table}.${field}}}`);
      _registerPlaceholderToken(`{{sum(table:${table}.${field})}}`);
      _registerPlaceholderToken(`{{avg(table:${table}.${field})}}`);
      _registerPlaceholderToken(`{{count(table:${table})}}`);
    }
  }

  function _refreshPlaceholderDatalist () {
    const list = qs('#rb-edit-placeholder-list');
    if (!list) return;
    const tokens = Array.from(_placeholderTokens).sort((a, b) => a.localeCompare(b));
    list.innerHTML = tokens.map(v => `<option value="${escapeHtml(v)}"></option>`).join('');
  }

  function jsonFetch (url, opts) {
    opts = opts || {};
    const method = String(opts.method || 'GET').toUpperCase();
    const headers = { ...(opts.headers || {}) };

    if (method !== 'GET' && method !== 'HEAD') {
      headers['Content-Type'] = 'application/json';
      const token = window.__RB && window.__RB.csrfToken;
      if (token) headers['X-CSRFToken'] = token;
    }

    return fetch(url, {
      credentials: 'same-origin',
      headers,
      ...opts
    }).then(async (r) => {
      const txt = await r.text();
      let p = {};
      try { p = txt ? JSON.parse(txt) : {}; } catch (e) { p = { error: txt.slice(0, 200) }; }
      if (!r.ok) throw p;
      return p;
    });
  }

  const ZONES = [
    'rb-report-header',
    'rb-page-header',
    'rb-detail',
    'rb-page-footer',
    'rb-report-footer'
  ];

  function normalizeDropHints () {
    for (const id of ZONES) {
      const dz = qs('#' + id);
      if (!dz) continue;
      const hint = dz.querySelector('.rb-drop-hint');
      const blocks = Array.from(dz.children).filter(el => el.classList.contains('rb-block-instance'));
      if (hint) hint.style.display = blocks.length ? 'none' : 'block';
    }
  }

  function escapeHtml (s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function safeJsonParse (s, fallback) {
    try { return JSON.parse(String(s || '')); } catch (e) { return fallback; }
  }

  function readStyleFromEl (el) {
    const raw = el.getAttribute('data-style') || '';
    const st = safeJsonParse(raw, null);
    return (st && typeof st === 'object') ? st : null;
  }

  function writeStyleToEl (el, styleObj) {
    if (!styleObj || typeof styleObj !== 'object' || (!styleObj.color && !styleObj.background && !styleObj.align && !styleObj.font_size && !styleObj.bold && !styleObj.italic && !styleObj.underline)) {
      el.removeAttribute('data-style');
      return;
    }
    el.setAttribute('data-style', JSON.stringify({
      color: styleObj.color || '',
      background: styleObj.background || '',
      align: styleObj.align || '',
      font_size: styleObj.font_size || '',
      bold: !!styleObj.bold,
      italic: !!styleObj.italic,
      underline: !!styleObj.underline
    }));
  }

  function readConfigFromEl (el) {
    const raw = el.getAttribute('data-config') || '';
    const cfg = safeJsonParse(raw, null);
    return (cfg && typeof cfg === 'object') ? cfg : null;
  }

  function writeConfigToEl (el, cfg) {
    if (!cfg || typeof cfg !== 'object' || !Object.keys(cfg).length) {
      el.removeAttribute('data-config');
      return;
    }
    el.setAttribute('data-config', JSON.stringify(cfg));
  }

  function blockSummary (b) {
    const type = (b.type || '').toLowerCase();
    if (type === 'data_field') {
      const bind = (b.config && b.config.binding) ? b.config.binding : {};
      if (bind.source === 'question') {
        const qlbl = bind.question_name || tf('Pergunta #{id}', { id: bind.question_id || '?' });
        return `${qlbl}.${bind.field || ''}`;
      }
      if (bind.source === 'table') return `${bind.table || ''}.${bind.field || ''}`;
      return t('Campo de dados');
    }
    if (type === 'question') {
      const tbl = b.config && b.config.table ? b.config.table : {};
      const dec = (tbl.decimals != null && tbl.decimals !== '') ? `, ${tbl.decimals}d` : '';
      return b.question_name ? `${t('Pergunta')}: ${b.question_name}${dec}` : `${t('Tabela')}${dec}`;
    }
    if (type === 'field') {
      const k = (b.config && b.config.kind) ? b.config.kind : 'date';
      return (k === 'datetime') ? t('Campo: Data e hora') : t('Campo: Data');
    }
    if (type === 'image') {
      const u = (b.url || b.image_url || '').trim();
      const cap = (b.caption || '').trim();
      const s = cap ? `${t('Imagem')}: ${cap}` : (u ? `${t('Imagem')}: ${u}` : t('Imagem'));
      return s.slice(0, 60);
    }
    if (type === 'markdown') return (b.content || b.text || t('Texto em markdown')).slice(0, 60);
    return (b.content || b.text || t('Texto simples')).slice(0, 60);
  }

  function makeBlockEl (block) {
    const type = String(block.type || 'text').toLowerCase();
    const defaultTitle =
      type === 'text' ? t('Texto')
        : type === 'markdown' ? t('Markdown')
          : type === 'question' ? t('Pergunta')
            : type === 'data_field' ? t('Campo de dados')
            : type === 'image' ? t('Imagem')
              : type === 'field' ? t('Campo')
                : type;

    const title = block.title || defaultTitle;

    const el = document.createElement('div');
    el.className = 'rb-block rb-block-instance';
    el.setAttribute('data-type', type);
    el.setAttribute('data-title', String(title || ''));

    const content = (block.content != null ? block.content : block.text) || '';
    if (content) el.setAttribute('data-content', String(content));

    if (block.question_id) el.setAttribute('data-question-id', String(block.question_id));

    const imgUrl = (block.url || block.image_url || '').trim();
    if (imgUrl) el.setAttribute('data-image-url', imgUrl);
    if (block.alt) el.setAttribute('data-image-alt', String(block.alt));
    if (block.caption) el.setAttribute('data-image-caption', String(block.caption));
    if (block.width) el.setAttribute('data-image-width', String(block.width));
    if (block.align) el.setAttribute('data-image-align', String(block.align));

    if (block.style && typeof block.style === 'object') writeStyleToEl(el, block.style);
    if (block.config && typeof block.config === 'object') writeConfigToEl(el, block.config);

    const badgeTxt =
      (type === 'question') ? 'Q'
        : (type === 'data_field') ? 'DB'
        : (type === 'markdown') ? 'MD'
          : (type === 'image') ? 'IMG'
            : (type === 'field') ? 'F'
              : 'T';

    el.innerHTML = `
      <div class="meta">
        <span class="badge text-bg-secondary">${badgeTxt}</span>
        <div>
          <div class="fw-semibold">${escapeHtml(title)}</div>
          <div class="text-muted small">${escapeHtml(blockSummary({
            ...block,
            type,
            content,
            url: imgUrl
          }))}</div>
        </div>
      </div>
      <div class="d-flex align-items-center gap-2">
        <button type="button" class="btn btn-sm btn-outline-secondary rb-edit" title="${t('Editar')}"><i class="bi bi-pencil"></i></button>
        <button type="button" class="btn btn-sm btn-outline-danger rb-remove" title="${t('Remover')}"><i class="bi bi-x"></i></button>
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

  function readBlockFromEl (el) {
    const type = (el.getAttribute('data-type') || 'text').toLowerCase();
    const title = el.getAttribute('data-title') || '';
    const out = { type, title };

    const qid = el.getAttribute('data-question-id');
    if (qid) out.question_id = Number(qid);

    const content = el.getAttribute('data-content');
    if (content != null && (type === 'text' || type === 'markdown')) out.content = content;

    if (type === 'image') {
      out.url = el.getAttribute('data-image-url') || '';
      out.alt = el.getAttribute('data-image-alt') || '';
      out.caption = el.getAttribute('data-image-caption') || '';
      out.width = el.getAttribute('data-image-width') || '';
      out.align = el.getAttribute('data-image-align') || '';
    }

    const cfg = readConfigFromEl(el);
    if (cfg) out.config = cfg;

    const st = readStyleFromEl(el);
    if (st) out.style = st;

    return out;
  }

  function readSettingsFromDom () {
    const enabledEl = qs("#rb-setting-page-number");
    const labelEl = qs("#rb-setting-page-label");
    const enabled = enabledEl ? !!enabledEl.checked : true;
    const label = labelEl ? String(labelEl.value || "").trim() : "";
    return {
      page_number: enabled,
      page_number_label: label || "Page {page} / {pages}"
    };
  }

  function extractLayoutFromDom () {
    function readZone (id) {
      const dz = qs('#' + id);
      if (!dz) return [];
      const blocks = Array.from(dz.children).filter(el => el.classList.contains('rb-block-instance'));
      return blocks.map(el => readBlockFromEl(el));
    }

    return {
      version: 5,
      page: { size: 'A4', orientation: 'portrait' },
      settings: readSettingsFromDom(),
      bands: {
        report_header: readZone('rb-report-header'),
        page_header: readZone('rb-page-header'),
        detail: readZone('rb-detail'),
        page_footer: readZone('rb-page-footer'),
        report_footer: readZone('rb-report-footer')
      }
    };
  }

  // -------------------------
  // Bootstrap modal editor
  // -------------------------
  let _editor = null;

  function getEditor () {
    if (_editor) return _editor;
    const modalEl = qs('#rb-edit-modal');
    if (!modalEl || !window.bootstrap || !bootstrap.Modal) return null;

    const modal = new bootstrap.Modal(modalEl, { backdrop: 'static' });

    _editor = {
      modalEl,
      modal,
      titleEl: qs('#rb-edit-modal-title', modalEl),
      typeEl: qs('#rb-edit-type', modalEl),

      titleInput: qs('#rb-edit-title', modalEl),

      textGroup: qs('#rb-edit-text-group', modalEl),
      contentLabel: qs('#rb-edit-content-label', modalEl),
      contentInput: qs('#rb-edit-content', modalEl),
      placeholderInput: qs('#rb-edit-placeholder-input', modalEl),
      insertPlaceholderBtn: qs('#rb-edit-insert-placeholder', modalEl),

      imageGroup: qs('#rb-edit-image-group', modalEl),
      imageUrl: qs('#rb-edit-image-url', modalEl),
      imageAlt: qs('#rb-edit-image-alt', modalEl),
      imageCaption: qs('#rb-edit-image-caption', modalEl),
      imageWidth: qs('#rb-edit-image-width', modalEl),
      imageAlign: qs('#rb-edit-image-align', modalEl),
      imagePreview: qs('#rb-edit-image-preview', modalEl),

      fieldGroup: qs('#rb-edit-field-group', modalEl),
      fieldKind: qs('#rb-edit-field-kind', modalEl),
      fieldFormat: qs('#rb-edit-field-format', modalEl),

      questionGroup: qs('#rb-edit-question-group', modalEl),
      qTheme: qs('#rb-edit-q-theme', modalEl) || qs('#rb-edit-table-theme', modalEl),
      qDecimals: qs('#rb-edit-q-decimals', modalEl) || qs('#rb-edit-decimals', modalEl),
      qRepeatHeader: qs('#rb-edit-q-repeat-header', modalEl) || qs('#rb-edit-repeat-header', modalEl),
      qZebra: qs('#rb-edit-q-zebra', modalEl) || qs('#rb-edit-zebra', modalEl),
      qGroupBy: qs('#rb-edit-q-group-by', modalEl),
      qGroupLabel: qs('#rb-edit-q-group-label', modalEl),
      qGroupCount: qs('#rb-edit-q-group-count', modalEl),
      qSubtotalMode: qs('#rb-edit-q-subtotal-mode', modalEl),
      qSubtotalField: qs('#rb-edit-q-subtotal-field', modalEl),
      qSubtotalLabel: qs('#rb-edit-q-subtotal-label', modalEl),
      qGrandTotal: qs('#rb-edit-q-grand-total', modalEl),
      qGrandTotalLabel: qs('#rb-edit-q-grand-total-label', modalEl),
      qFooterCount: qs('#rb-edit-q-footer-count', modalEl),
      qFooterCountLabel: qs('#rb-edit-q-footer-count-label', modalEl),
      qFilterField: qs('#rb-edit-q-filter-field', modalEl),
      qFilterOp: qs('#rb-edit-q-filter-op', modalEl),
      qFilterValue: qs('#rb-edit-q-filter-value', modalEl),
      qSortBy: qs('#rb-edit-q-sort-by', modalEl),
      qSortDir: qs('#rb-edit-q-sort-dir', modalEl),

      dataFieldGroup: qs('#rb-edit-data-field-group', modalEl),
      dataBindingInput: qs('#rb-edit-data-binding', modalEl),
      dataEmptyInput: qs('#rb-edit-data-empty', modalEl),
      dataFormatInput: qs('#rb-edit-data-format', modalEl),
      dataGroupKeyInput: qs('#rb-edit-data-group-key', modalEl),
      dataGroupLabelInput: qs('#rb-edit-data-group-label', modalEl),

      colorInput: qs('#rb-edit-color', modalEl),
      bgInput: qs('#rb-edit-bg', modalEl),
      alignSelect: qs('#rb-edit-align', modalEl),
      fontSizeInput: qs('#rb-edit-font-size', modalEl),
      boldInput: qs('#rb-edit-font-bold', modalEl),
      italicInput: qs('#rb-edit-font-italic', modalEl),
      underlineInput: qs('#rb-edit-font-underline', modalEl),

      saveBtn: qs('#rb-edit-save', modalEl),

      currentEl: null,
      currentBlock: null,
      onSave: null
    };

    const contentInput = _editor.contentInput;
    if (contentInput) {
      modalEl.querySelectorAll('[data-rb-wrap], [data-rb-prefix], [data-rb-insert]').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          const wrap = btn.getAttribute('data-rb-wrap');
          const prefix = btn.getAttribute('data-rb-prefix');
          const insert = btn.getAttribute('data-rb-insert');

          const start = contentInput.selectionStart || 0;
          const end = contentInput.selectionEnd || 0;
          const value = String(contentInput.value || '');
          const selected = value.slice(start, end);

          let next = value;
          let ns = start;
          let ne = end;
          if (wrap) {
            const token = String(wrap);
            next = value.slice(0, start) + token + selected + token + value.slice(end);
            ns = start + token.length;
            ne = ns + selected.length;
          } else if (prefix) {
            const text = selected || t('item');
            const lines = text.split('\n').map(line => (line ? prefix + line : line)).join('\n');
            next = value.slice(0, start) + lines + value.slice(end);
            ns = start;
            ne = start + lines.length;
          } else if (insert) {
            next = value.slice(0, start) + insert + value.slice(end);
            ns = ne = start + insert.length;
          }

          contentInput.value = next;
          contentInput.focus();
          try { contentInput.setSelectionRange(ns, ne); } catch (err) {}
        });
      });
    }

    if (_editor.insertPlaceholderBtn && _editor.placeholderInput && _editor.contentInput) {
      _editor.insertPlaceholderBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const tok = String(_editor.placeholderInput.value || '').trim();
        if (!tok) return;
        const start = _editor.contentInput.selectionStart || 0;
        const end = _editor.contentInput.selectionEnd || 0;
        const value = String(_editor.contentInput.value || '');
        _editor.contentInput.value = value.slice(0, start) + tok + value.slice(end);
        const pos = start + tok.length;
        _editor.contentInput.focus();
        try { _editor.contentInput.setSelectionRange(pos, pos); } catch (err) {}
      });
    }

    modalEl.querySelectorAll('[data-rb-insert-placeholder-example]').forEach(btn => {
      if (btn._rbBoundExample) return;
      btn._rbBoundExample = true;
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        if (!_editor.contentInput) return;
        const tok = String(btn.getAttribute('data-rb-insert-placeholder-example') || '').trim();
        if (!tok) return;
        const start = _editor.contentInput.selectionStart || 0;
        const end = _editor.contentInput.selectionEnd || 0;
        const value = String(_editor.contentInput.value || '');
        _editor.contentInput.value = value.slice(0, start) + tok + value.slice(end);
        const pos = start + tok.length;
        _editor.contentInput.focus();
        try { _editor.contentInput.setSelectionRange(pos, pos); } catch (err) {}
        if (_editor.placeholderInput) _editor.placeholderInput.value = tok;
      });
    });
    _refreshPlaceholderDatalist();

    // Palette interactions
    const palettes = modalEl.querySelectorAll('.rb-color-palette');
    palettes.forEach(pal => {
      pal.addEventListener('click', (e) => {
        const btn = e.target.closest('.rb-swatch');
        if (!btn) return;
        e.preventDefault();
        const targetId = pal.getAttribute('data-target');
        const inp = targetId ? qs('#' + targetId, modalEl) : null;
        if (!inp) return;

        const val = btn.getAttribute('data-color') || '';
        inp.value = val.startsWith('#') ? val.slice(1) : (val || '');
        syncPaletteActive(pal, inp.value);
      });
    });

    function syncPaletteActive (pal, hexNoHash) {
      const norm = String(hexNoHash || '').trim().toLowerCase();
      pal.querySelectorAll('.rb-swatch').forEach(b => {
        const c = (b.getAttribute('data-color') || '').trim().toLowerCase();
        const cNorm = c.startsWith('#') ? c.slice(1) : c;
        const isOn = (cNorm === norm) || (!cNorm && !norm);
        b.classList.toggle('border-2', isOn);
        b.classList.toggle('border-primary', isOn);
      });
    }

    function syncAllPalettes () {
      modalEl.querySelectorAll('.rb-color-palette').forEach(pal => {
        const targetId = pal.getAttribute('data-target');
        const inp = targetId ? qs('#' + targetId, modalEl) : null;
        if (!inp) return;
        syncPaletteActive(pal, inp.value);
      });
    }

    // Keep palette active state updated when typing hex
    [_editor.colorInput, _editor.bgInput].forEach(inp => {
      if (!inp) return;
      inp.addEventListener('input', () => syncAllPalettes());
    });

    // Image preview
    if (_editor.imageUrl && _editor.imagePreview) {
      const updatePreview = () => {
        const u = String(_editor.imageUrl.value || '').trim();
        _editor.imagePreview.src = u || '';
        _editor.imagePreview.alt = String(_editor.imageAlt.value || '').trim();
      };
      _editor.imageUrl.addEventListener('input', updatePreview);
      _editor.imageAlt.addEventListener('input', updatePreview);
    }

    // Save button
    _editor.saveBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (!_editor.onSave) { _editor.modal.hide(); return; }

      const type = String(_editor.typeEl.value || '').toLowerCase() || 'text';
      const out = { ...(_editor.currentBlock || {}), type };

      let title = String(_editor.titleInput.value || '').trim();
      if (!title) {
        title = (type === 'markdown') ? t('Markdown')
          : (type === 'question') ? t('Pergunta')
            : (type === 'image') ? t('Imagem')
              : (type === 'field') ? t('Campo')
                : t('Texto');
      }
      out.title = title;

      if (type === 'text' || type === 'markdown') {
        out.content = String(_editor.contentInput.value || '');
      }

      if (type === 'image') {
        out.url = String(_editor.imageUrl.value || '').trim();
        out.alt = String(_editor.imageAlt.value || '');
        out.caption = String(_editor.imageCaption.value || '');
        out.width = String(_editor.imageWidth.value || '').trim();

        let ia = String(_editor.imageAlign.value || '').trim().toLowerCase();
        if (ia && !['left', 'center', 'right'].includes(ia)) ia = '';
        out.align = ia;
      }

      if (type === 'field') {
        const kind = String(_editor.fieldKind.value || 'date').trim().toLowerCase();
        const fmt = String(_editor.fieldFormat.value || '').trim();
        out.config = out.config || {};
        out.config.kind = (kind === 'datetime') ? 'datetime' : 'date';
        out.config.format = fmt;
      }

      if (type === 'question') {
        out.config = out.config || {};
        out.config.table = out.config.table || {};
        out.config.table.theme = String(_editor.qTheme.value || 'crystal').trim().toLowerCase();
        const decRaw = String(_editor.qDecimals.value || '').trim();
        out.config.table.decimals = (decRaw === '') ? '' : Number(decRaw);
        out.config.table.repeat_header = !!(_editor.qRepeatHeader && _editor.qRepeatHeader.checked);
        out.config.table.zebra = !!(_editor.qZebra && _editor.qZebra.checked);
        out.config.table.group_by = String((_editor.qGroupBy && _editor.qGroupBy.value) || '').trim();
        out.config.table.group_label = String((_editor.qGroupLabel && _editor.qGroupLabel.value) || '').trim() || '{group}';
        out.config.table.group_count = !!(_editor.qGroupCount && _editor.qGroupCount.checked);
        {
          let subtotalMode = String((_editor.qSubtotalMode && _editor.qSubtotalMode.value) || '').trim().toLowerCase();
          if (!['count', 'sum'].includes(subtotalMode)) subtotalMode = '';
          out.config.table.group_subtotal_mode = subtotalMode;
        }
        out.config.table.group_subtotal_field = String((_editor.qSubtotalField && _editor.qSubtotalField.value) || '').trim();
        out.config.table.group_subtotal_label = String((_editor.qSubtotalLabel && _editor.qSubtotalLabel.value) || '').trim() || 'Sous-total';
        out.config.table.grand_total = !!(_editor.qGrandTotal && _editor.qGrandTotal.checked);
        out.config.table.grand_total_label = String((_editor.qGrandTotalLabel && _editor.qGrandTotalLabel.value) || '').trim() || 'Grand total';
        out.config.table.footer_item_count = !!(_editor.qFooterCount && _editor.qFooterCount.checked);
        out.config.table.footer_item_count_label = String((_editor.qFooterCountLabel && _editor.qFooterCountLabel.value) || '').trim() || 'Items';
        out.config.table.filter_field = String((_editor.qFilterField && _editor.qFilterField.value) || '').trim();
        out.config.table.filter_op = String((_editor.qFilterOp && _editor.qFilterOp.value) || '').trim().toLowerCase();
        out.config.table.filter_value = String((_editor.qFilterValue && _editor.qFilterValue.value) || '').trim();
        out.config.table.sort_by = String((_editor.qSortBy && _editor.qSortBy.value) || '').trim();
        let sdir = String((_editor.qSortDir && _editor.qSortDir.value) || 'asc').trim().toLowerCase();
        if (!['asc', 'desc'].includes(sdir)) sdir = 'asc';
        out.config.table.sort_dir = sdir;
      }

      if (type === 'data_field') {
        out.config = out.config || {};
        out.config.binding = (out.config.binding && typeof out.config.binding === 'object') ? out.config.binding : {};
        out.config.empty_text = String((_editor.dataEmptyInput && _editor.dataEmptyInput.value) || '').trim();
        out.config.format = String((_editor.dataFormatInput && _editor.dataFormatInput.value) || '').trim();
        out.config.group_key = !!(_editor.dataGroupKeyInput && _editor.dataGroupKeyInput.checked);
        out.config.group_label = String((_editor.dataGroupLabelInput && _editor.dataGroupLabelInput.value) || '').trim() || 'Groupe: {group}';
      }

      // Style (hex fields stored without leading '#')
      let color = String(_editor.colorInput.value || '').trim();
      let bg = String(_editor.bgInput.value || '').trim();
      if (color.startsWith('#')) color = color.slice(1);
      if (bg.startsWith('#')) bg = bg.slice(1);
      color = color ? ('#' + color) : '';
      bg = bg ? ('#' + bg) : '';

      let align = String(_editor.alignSelect.value || '').trim().toLowerCase();
      if (align && !['left', 'center', 'right'].includes(align)) align = '';

      let fontSize = String((_editor.fontSizeInput && _editor.fontSizeInput.value) || '').trim();
      if (fontSize !== '') {
        const n = Number(fontSize);
        fontSize = Number.isFinite(n) && n >= 8 && n <= 72 ? String(Math.round(n)) : '';
      }

      out.style = {
        color,
        background: bg,
        align,
        font_size: fontSize,
        bold: !!(_editor.boldInput && _editor.boldInput.checked),
        italic: !!(_editor.italicInput && _editor.italicInput.checked),
        underline: !!(_editor.underlineInput && _editor.underlineInput.checked)
      };
      if (!out.style.color && !out.style.background && !out.style.align && !out.style.font_size && !out.style.bold && !out.style.italic && !out.style.underline) delete out.style;

      // cleanup empty configs
      if (out.config && typeof out.config === 'object') {
        const str = JSON.stringify(out.config);
        if (str === '{}' || str === 'null') delete out.config;
      }

      _editor.onSave(out);
      _editor.modal.hide();
    });

    // reset on hide
    modalEl.addEventListener('hidden.bs.modal', () => {
      _editor.currentEl = null;
      _editor.currentBlock = null;
      _editor.onSave = null;
    });

    _editor.syncAllPalettes = syncAllPalettes;
    return _editor;
  }

  function openEditorModal (el, block) {
    const ed = getEditor();
    if (!ed) return false;

    ed.currentEl = el;
    ed.currentBlock = { ...block };
    ed.typeEl.value = block.type || 'text';
    ed.titleInput.value = block.title || '';

    const type = String(block.type || 'text').toLowerCase();

    // Text/Markdown
    if (type === 'text' || type === 'markdown') {
      ed.textGroup.classList.remove('d-none');
      ed.contentLabel.textContent = (type === 'markdown') ? t('Markdown') : t('Texto');
      ed.contentInput.value = block.content || '';
    } else {
      ed.textGroup.classList.add('d-none');
      ed.contentInput.value = '';
    }

    // Image
    if (type === 'image') {
      ed.imageGroup.classList.remove('d-none');
      ed.imageUrl.value = block.url || '';
      ed.imageAlt.value = block.alt || '';
      ed.imageCaption.value = block.caption || '';
      ed.imageWidth.value = block.width || '';
      ed.imageAlign.value = block.align || '';
      if (ed.imagePreview) {
        ed.imagePreview.src = String(ed.imageUrl.value || '').trim();
        ed.imagePreview.alt = String(ed.imageAlt.value || '').trim();
      }
    } else {
      ed.imageGroup.classList.add('d-none');
      if (ed.imageUrl) ed.imageUrl.value = '';
      if (ed.imageAlt) ed.imageAlt.value = '';
      if (ed.imageCaption) ed.imageCaption.value = '';
      if (ed.imageWidth) ed.imageWidth.value = '';
      if (ed.imageAlign) ed.imageAlign.value = '';
      if (ed.imagePreview) ed.imagePreview.src = '';
    }

    // Field
    if (type === 'field') {
      ed.fieldGroup.classList.remove('d-none');
      const cfg = block.config || {};
      ed.fieldKind.value = (cfg.kind === 'datetime') ? 'datetime' : 'date';
      ed.fieldFormat.value = cfg.format || (cfg.kind === 'datetime' ? 'dd/MM/yyyy HH:mm' : 'dd/MM/yyyy');
    } else {
      ed.fieldGroup.classList.add('d-none');
      if (ed.fieldFormat) ed.fieldFormat.value = '';
    }

    // Question
    if (type === 'question') {
      ed.questionGroup.classList.remove('d-none');
      const cfg = block.config || {};
      const tbl = cfg.table || {};
      ed.qTheme.value = (tbl.theme || 'crystal');
      ed.qDecimals.value = (tbl.decimals === 0) ? '0' : (tbl.decimals != null ? String(tbl.decimals) : '');
      if (ed.qRepeatHeader) ed.qRepeatHeader.checked = (tbl.repeat_header !== false);
      if (ed.qZebra) ed.qZebra.checked = !!tbl.zebra;
      if (ed.qGroupBy) ed.qGroupBy.value = tbl.group_by || '';
      if (ed.qGroupLabel) ed.qGroupLabel.value = tbl.group_label || '{group}';
      if (ed.qGroupCount) ed.qGroupCount.checked = !!tbl.group_count;
      if (ed.qSubtotalMode) {
        const mode = String(tbl.group_subtotal_mode || '').toLowerCase();
        ed.qSubtotalMode.value = ['count', 'sum'].includes(mode) ? mode : '';
      }
      if (ed.qSubtotalField) ed.qSubtotalField.value = tbl.group_subtotal_field || '';
      if (ed.qSubtotalLabel) ed.qSubtotalLabel.value = tbl.group_subtotal_label || 'Sous-total';
      if (ed.qGrandTotal) ed.qGrandTotal.checked = !!tbl.grand_total;
      if (ed.qGrandTotalLabel) ed.qGrandTotalLabel.value = tbl.grand_total_label || 'Grand total';
      if (ed.qFooterCount) ed.qFooterCount.checked = !!tbl.footer_item_count;
      if (ed.qFooterCountLabel) ed.qFooterCountLabel.value = tbl.footer_item_count_label || 'Items';
      if (ed.qFilterField) ed.qFilterField.value = tbl.filter_field || '';
      if (ed.qFilterOp) ed.qFilterOp.value = tbl.filter_op || '';
      if (ed.qFilterValue) ed.qFilterValue.value = tbl.filter_value || '';
      if (ed.qSortBy) ed.qSortBy.value = tbl.sort_by || '';
      if (ed.qSortDir) ed.qSortDir.value = (tbl.sort_dir === 'desc') ? 'desc' : 'asc';
    } else {
      ed.questionGroup.classList.add('d-none');
      if (ed.qDecimals) ed.qDecimals.value = '';
      if (ed.qRepeatHeader) ed.qRepeatHeader.checked = true;
      if (ed.qZebra) ed.qZebra.checked = false;
      if (ed.qGroupBy) ed.qGroupBy.value = '';
      if (ed.qGroupLabel) ed.qGroupLabel.value = '{group}';
      if (ed.qGroupCount) ed.qGroupCount.checked = false;
      if (ed.qSubtotalMode) ed.qSubtotalMode.value = '';
      if (ed.qSubtotalField) ed.qSubtotalField.value = '';
      if (ed.qSubtotalLabel) ed.qSubtotalLabel.value = 'Sous-total';
      if (ed.qGrandTotal) ed.qGrandTotal.checked = false;
      if (ed.qGrandTotalLabel) ed.qGrandTotalLabel.value = 'Grand total';
      if (ed.qFooterCount) ed.qFooterCount.checked = false;
      if (ed.qFooterCountLabel) ed.qFooterCountLabel.value = 'Items';
      if (ed.qFilterField) ed.qFilterField.value = '';
      if (ed.qFilterOp) ed.qFilterOp.value = '';
      if (ed.qFilterValue) ed.qFilterValue.value = '';
      if (ed.qSortBy) ed.qSortBy.value = '';
      if (ed.qSortDir) ed.qSortDir.value = 'asc';
    }

    if (type === 'data_field') {
      ed.dataFieldGroup.classList.remove('d-none');
      const cfg = block.config || {};
      const bind = (cfg.binding && typeof cfg.binding === 'object') ? cfg.binding : {};
      const sourceLabel = bind.source === 'question'
        ? `${bind.question_name || tf('Pergunta #{id}', { id: bind.question_id || '?' })}.${bind.field || ''}`
        : `${bind.table || ''}.${bind.field || ''}`;
      if (ed.dataBindingInput) ed.dataBindingInput.value = sourceLabel;
      if (ed.dataEmptyInput) ed.dataEmptyInput.value = cfg.empty_text || '';
      if (ed.dataFormatInput) ed.dataFormatInput.value = cfg.format || '';
      if (ed.dataGroupKeyInput) ed.dataGroupKeyInput.checked = !!cfg.group_key;
      if (ed.dataGroupLabelInput) ed.dataGroupLabelInput.value = cfg.group_label || 'Groupe: {group}';
    } else {
      ed.dataFieldGroup.classList.add('d-none');
      if (ed.dataBindingInput) ed.dataBindingInput.value = '';
      if (ed.dataEmptyInput) ed.dataEmptyInput.value = '';
      if (ed.dataFormatInput) ed.dataFormatInput.value = '';
      if (ed.dataGroupKeyInput) ed.dataGroupKeyInput.checked = false;
      if (ed.dataGroupLabelInput) ed.dataGroupLabelInput.value = 'Groupe: {group}';
    }

    const st = block.style || {};
    ed.colorInput.value = (st.color || '').replace('#', '');
    ed.bgInput.value = (st.background || '').replace('#', '');
    ed.alignSelect.value = st.align || '';
    if (ed.fontSizeInput) ed.fontSizeInput.value = st.font_size || '';
    if (ed.boldInput) ed.boldInput.checked = !!st.bold;
    if (ed.italicInput) ed.italicInput.checked = !!st.italic;
    if (ed.underlineInput) ed.underlineInput.checked = !!st.underline;

    ed.onSave = (updatedBlock) => {
      const parent = el.parentElement;
      const newEl = makeBlockEl(updatedBlock);
      if (parent) parent.replaceChild(newEl, el);
      normalizeDropHints();
    };

    ed.syncAllPalettes();
    ed.modal.show();
    return true;
  }

  // Fallback prompt-based editor (kept for robustness)
  function promptEditor (el) {
    const block = readBlockFromEl(el);
    const type = block.type;

    let newTitle = prompt(t('Título do bloco:'), block.title || '');
    if (newTitle === null) return;
    newTitle = String(newTitle).trim();
    if (!newTitle) newTitle = block.title || t('Bloco');
    block.title = newTitle;

    if (type === 'text' || type === 'markdown') {
      const cur = block.content || '';
      let newText = prompt(type === 'markdown' ? t('Texto (Markdown):') : t('Texto:'), cur);
      if (newText === null) newText = cur;
      block.content = String(newText);
    }

    if (type === 'field') {
      const curK = (block.config && block.config.kind) ? block.config.kind : 'date';
      let k = prompt(t('Campo (date/datetime):'), curK);
      if (k === null) k = curK;
      k = String(k || '').trim().toLowerCase();
      if (!['date', 'datetime'].includes(k)) k = 'date';
      block.config = block.config || {};
      block.config.kind = k;
      const curF = block.config.format || '';
      let f = prompt(t('Formato (dd/MM/yyyy HH:mm):'), curF);
      if (f === null) f = curF;
      block.config.format = String(f || '').trim();
    }

    if (type === 'image') {
      const curUrl = block.url || '';
      let url = prompt(t('URL da imagem:'), curUrl);
      if (url === null) url = curUrl;
      block.url = String(url || '').trim();

      const curAlt = block.alt || '';
      let alt = prompt(t('Texto alternativo (alt):'), curAlt);
      if (alt === null) alt = curAlt;
      block.alt = String(alt || '');

      const curCap = block.caption || '';
      let cap = prompt(t('Legenda (opcional):'), curCap);
      if (cap === null) cap = curCap;
      block.caption = String(cap || '');

      const curW = block.width || '';
      let w = prompt(t('Largura (ex.: 300px ou 50%):'), curW);
      if (w === null) w = curW;
      block.width = String(w || '').trim();

      const curA = block.align || '';
      let a = prompt(t('Alinhamento (left/center/right):'), curA);
      if (a === null) a = curA;
      a = String(a || '').trim().toLowerCase();
      if (a && !['left', 'center', 'right'].includes(a)) a = '';
      block.align = a;
    }

    if (type === 'question') {
      const tbl = (block.config && block.config.table) ? block.config.table : {};
      let dec = prompt(t('Decimais (vazio para auto):'), (tbl.decimals != null ? String(tbl.decimals) : ''));
      if (dec !== null) {
        dec = String(dec || '').trim();
        block.config = block.config || {};
        block.config.table = block.config.table || {};
        block.config.table.decimals = dec === '' ? '' : Number(dec);
      }
    }

    const curColor = (block.style && block.style.color) ? block.style.color : '';
    const curBg = (block.style && block.style.background) ? block.style.background : '';
    const curAlign = (block.style && block.style.align) ? block.style.align : '';

    let color = prompt(t('Cor do texto (ex.: #111 ou vazio):'), curColor);
    if (color === null) color = curColor;
    color = String(color || '').trim();

    let bg = prompt(t('Cor de fundo (ex.: #fff ou vazio):'), curBg);
    if (bg === null) bg = curBg;
    bg = String(bg || '').trim();

    let align = prompt(t('Alinhamento (left/center/right):'), curAlign);
    if (align === null) align = curAlign;
    align = String(align || '').trim().toLowerCase();
    if (align && !['left', 'center', 'right'].includes(align)) align = '';

    block.style = { color, background: bg, align };
    if (!block.style.color && !block.style.background && !block.style.align) delete block.style;

    const parent = el.parentElement;
    const newEl = makeBlockEl(block);
    if (parent) parent.replaceChild(newEl, el);
    normalizeDropHints();
  }

  function editBlock (el) {
    const block = readBlockFromEl(el);
    const ok = openEditorModal(el, block);
    if (!ok) promptEditor(el);
  }

  function qsa (sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  function getQuestionDataUrl (qid) {
    const id = Number(qid || 0);
    return `/app/api/questions/${id}/data`;
  }

  function createFieldDragItem (meta) {
    const el = document.createElement('div');
    el.className = 'rb-data-field rb-item';
    el.setAttribute('data-type', 'data_field');
    el.setAttribute('data-title', String(meta.title || meta.field || t('Campo de dados')));
    el.setAttribute('data-binding', JSON.stringify(meta.binding || {}));
    el.setAttribute('data-search-text', String(meta.searchText || '').toLowerCase());
    el.innerHTML = `
      <div>
        <div class="small fw-semibold">${escapeHtml(meta.field || '')}</div>
        <small>${escapeHtml(meta.sub || '')}</small>
      </div>
      <i class="bi bi-grip-vertical text-muted"></i>
    `;
    return el;
  }

  function mountDragSource (container) {
    if (!container || container._rbSortableMounted || !window.Sortable) return;
    container._rbSortableMounted = true;
    Sortable.create(container, {
      group: { name: 'rb', pull: 'clone', put: false },
      sort: false,
      animation: 120
    });
  }

  async function initDataExplorer (cfg) {
    const tablesWrap = qs('#rb-data-tables');
    const qWrap = qs('#rb-data-questions');
    const search = qs('#rb-data-search');
    const tablesCount = qs('#rb-data-tables-count');
    if (!tablesWrap || !cfg || !cfg.sourceSchemaUrl) return;

    function applyFilter () {
      const q = String((search && search.value) || '').trim().toLowerCase();
      if (!q) {
        qsa('[data-search-text]', tablesWrap).forEach(el => { el.style.display = ''; });
        if (qWrap) qsa('[data-search-text]', qWrap).forEach(el => { el.style.display = ''; });
        return;
      }
      qsa('[data-search-text]', tablesWrap).forEach(el => {
        const txt = String(el.getAttribute('data-search-text') || '').toLowerCase();
        el.style.display = txt.includes(q) ? '' : 'none';
      });
      if (qWrap) {
        qsa('[data-search-text]', qWrap).forEach(el => {
          const txt = String(el.getAttribute('data-search-text') || '').toLowerCase();
          const fields = qsa('.rb-data-field[data-search-text]', el);
          const fieldsHas = fields.some(f => String(f.getAttribute('data-search-text') || '').includes(q));
          el.style.display = (txt.includes(q) || fieldsHas) ? '' : 'none';
        });
      }
    }

    if (search && !search._rbBound) {
      search._rbBound = true;
      search.addEventListener('input', applyFilter);
    }

    try {
      const schema = await jsonFetch(cfg.sourceSchemaUrl);
      const schemas = Array.isArray(schema.schemas) ? schema.schemas : [];
      tablesWrap.innerHTML = '';

      let totalTables = 0;
      for (const sch of schemas) {
        const tables = Array.isArray(sch.tables) ? sch.tables : [];
        for (const tbl of tables) {
          totalTables += 1;
          const tableName = String(tbl.name || '').trim();
          const columns = Array.isArray(tbl.columns) ? tbl.columns : [];
          const seenCols = new Set();

          const card = document.createElement('div');
          card.className = 'rb-data-card';
          card.setAttribute('data-search-text', `${tableName} ${(sch.name || '')}`.toLowerCase());

          const fieldsId = `rb-table-fields-${totalTables}`;
          card.innerHTML = `
            <div class="rb-data-head">
              <div class="small fw-semibold text-truncate" title="${escapeHtml(tableName)}">${escapeHtml(tableName)}</div>
              <button class="btn btn-sm btn-outline-secondary" type="button" data-rb-toggle="${fieldsId}">${t('Campos')}</button>
            </div>
            <div class="rb-data-fields d-none" id="${fieldsId}"></div>
          `;

          const fieldsBox = qs('#' + fieldsId, card);
          for (const col of columns) {
            const colName = String((col && col.name) || '').trim();
            if (!colName) continue;
            {
              const key = colName.toLowerCase();
              if (seenCols.has(key)) continue;
              seenCols.add(key);
            }
            const colType = String((col && (col.type || col.data_type)) || '').trim();
            const field = createFieldDragItem({
              field: colName,
              sub: `${tableName}${colType ? ` · ${colType}` : ''}`,
              title: `${tableName}.${colName}`,
              searchText: `${tableName} ${colName} ${colType}`,
              binding: {
                source: 'table',
                table: tableName,
                field: colName
              }
            });
            _registerBindingPlaceholders({ source: 'table', table: tableName, field: colName });
            fieldsBox.appendChild(field);
          }

          const tgl = qs(`[data-rb-toggle="${fieldsId}"]`, card);
          if (tgl) {
            tgl.addEventListener('click', () => {
              fieldsBox.classList.toggle('d-none');
            });
          }

          mountDragSource(fieldsBox);
          tablesWrap.appendChild(card);
        }
      }

      if (!totalTables) {
        tablesWrap.innerHTML = `<div class="text-muted small">${t('Nenhuma tabela encontrada para esta fonte.')}</div>`;
      }
      if (tablesCount) tablesCount.textContent = String(totalTables);
      applyFilter();
    } catch (e) {
      tablesWrap.innerHTML = `<div class="text-danger small">${t('Falha ao carregar esquema da fonte.')}</div>`;
    }

    if (qWrap) {
      qsa('[data-load-question]', qWrap).forEach(btn => {
        if (btn._rbBound) return;
        btn._rbBound = true;
        btn.addEventListener('click', async () => {
          const qid = Number(btn.getAttribute('data-load-question') || 0);
          if (!qid) return;
          const card = btn.closest('[data-question-card]');
          const fieldsWrap = qs('#rb-q-fields-' + qid);
          if (!card || !fieldsWrap) return;

          if (!fieldsWrap.classList.contains('d-none') && fieldsWrap.childElementCount > 0) {
            fieldsWrap.classList.add('d-none');
            return;
          }

          if (!fieldsWrap.childElementCount) {
            fieldsWrap.innerHTML = `<div class="text-muted small">${t('Carregando campos...')}</div>`;
            try {
              const token = window.__RB && window.__RB.csrfToken;
              const resp = await fetch(getQuestionDataUrl(qid), {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                  'Content-Type': 'application/json',
                  ...(token ? { 'X-CSRFToken': token } : {})
                },
                body: JSON.stringify({ params: {} })
              });
              const payload = await resp.json().catch(() => ({}));
              if (!resp.ok) throw new Error(payload.error || t('Erro ao carregar campos da pergunta.'));

              const cols = Array.isArray(payload.columns) ? payload.columns : [];
              fieldsWrap.innerHTML = '';
              const qName = (card.querySelector('.fw-semibold')?.textContent || tf('Pergunta #{id}', { id: qid })).trim();
              const seen = new Set();
              for (const cname of cols) {
                const colName = String(cname || '').trim();
                if (!colName) continue;
                {
                  const key = colName.toLowerCase();
                  if (seen.has(key)) continue;
                  seen.add(key);
                }
                const item = createFieldDragItem({
                  field: colName,
                  sub: qName,
                  title: `${qName}.${colName}`,
                  searchText: `${qName} ${colName}`,
                  binding: {
                    source: 'question',
                    question_id: qid,
                    question_name: qName,
                    field: colName
                  }
                });
                _registerBindingPlaceholders({ source: 'question', question_id: qid, field: colName });
                fieldsWrap.appendChild(item);
              }
              if (!cols.length) fieldsWrap.innerHTML = `<div class="text-muted small">${t('Sem colunas retornadas.')}</div>`;
              mountDragSource(fieldsWrap);
            } catch (err) {
              fieldsWrap.innerHTML = `<div class="text-danger small">${escapeHtml(String(err.message || err || 'erro'))}</div>`;
            }
          }

          fieldsWrap.classList.remove('d-none');
          applyFilter();
        });
      });
    }
  }

  function initFloatingExplorerPanel () {
    const panel = qs('#rb-floating-explorer');
    if (!panel) return;

    const head = qs('#rb-floating-explorer-head');
    const toggleBtn = qs('#rb-floating-explorer-toggle');
    const collapseBtn = qs('#rb-floating-explorer-collapse');
    const dockBtn = qs('#rb-floating-explorer-dock');
    const keyCollapsed = 'rb.explorer.collapsed';

    function setCollapsed (on) {
      panel.classList.toggle('is-collapsed', !!on);
      try { localStorage.setItem(keyCollapsed, on ? '1' : '0'); } catch (e) {}
      if (collapseBtn) {
        const icon = collapseBtn.querySelector('i');
        if (icon) {
          icon.className = on ? 'bi bi-chevron-up' : 'bi bi-chevron-down';
        }
      }
    }

    function toggleVisible () {
      const hidden = panel.style.display === 'none';
      panel.style.display = hidden ? '' : 'none';
    }

    function dockDefault () {
      panel.style.left = '';
      panel.style.top = '';
      panel.style.right = '18px';
    }

    if (collapseBtn && !collapseBtn._rbBound) {
      collapseBtn._rbBound = true;
      collapseBtn.addEventListener('click', (e) => {
        e.preventDefault();
        setCollapsed(!panel.classList.contains('is-collapsed'));
      });
    }

    if (toggleBtn && !toggleBtn._rbBound) {
      toggleBtn._rbBound = true;
      toggleBtn.addEventListener('click', (e) => {
        e.preventDefault();
        toggleVisible();
      });
    }

    if (dockBtn && !dockBtn._rbBound) {
      dockBtn._rbBound = true;
      dockBtn.addEventListener('click', (e) => {
        e.preventDefault();
        dockDefault();
      });
    }

    try {
      setCollapsed(localStorage.getItem(keyCollapsed) === '1');
    } catch (e) {
      setCollapsed(false);
    }

    if (!head) return;

    let dragging = false;
    let startX = 0;
    let startY = 0;
    let origLeft = 0;
    let origTop = 0;

    function onMove (clientX, clientY) {
      if (!dragging) return;
      const dx = clientX - startX;
      const dy = clientY - startY;
      const w = panel.offsetWidth || 300;
      const h = panel.offsetHeight || 200;
      const maxLeft = Math.max(8, window.innerWidth - w - 8);
      const maxTop = Math.max(8, window.innerHeight - h - 8);
      let nextLeft = origLeft + dx;
      let nextTop = origTop + dy;
      nextLeft = Math.max(8, Math.min(maxLeft, nextLeft));
      nextTop = Math.max(8, Math.min(maxTop, nextTop));
      panel.style.left = `${nextLeft}px`;
      panel.style.top = `${nextTop}px`;
      panel.style.right = 'auto';
    }

    function stopDrag () {
      dragging = false;
      document.body.classList.remove('user-select-none');
    }

    if (!head._rbBound) {
      head._rbBound = true;
      head.addEventListener('mousedown', (e) => {
        if (window.matchMedia('(max-width: 991.98px)').matches) return;
        if (e.button !== 0) return;
        if (e.target && e.target.closest('button,input,select,textarea,a,label')) return;
        const rect = panel.getBoundingClientRect();
        dragging = true;
        startX = e.clientX;
        startY = e.clientY;
        origLeft = rect.left;
        origTop = rect.top;
        document.body.classList.add('user-select-none');
        e.preventDefault();
      });

      document.addEventListener('mousemove', (e) => onMove(e.clientX, e.clientY));
      document.addEventListener('mouseup', stopDrag);
    }
  }

  function tableStyleTemplateConfig (templateName) {
    const name = String(templateName || '').trim().toLowerCase();
    if (name === 'professional') {
      return { theme: 'professional', zebra: true, repeat_header: true };
    }
    if (name === 'minimal') {
      return { theme: 'minimal', zebra: true, repeat_header: true };
    }
    return { theme: 'crystal', zebra: false, repeat_header: true };
  }

  function currentTableStyleTemplate () {
    try {
      const stored = localStorage.getItem('rb.style.template');
      const n = String(stored || 'crystal').toLowerCase();
      if (['crystal', 'professional', 'minimal'].includes(n)) return n;
    } catch (e) {}
    return 'crystal';
  }

  function setCurrentTableStyleTemplate (templateName) {
    const n = String(templateName || '').toLowerCase();
    const safe = ['crystal', 'professional', 'minimal'].includes(n) ? n : 'crystal';
    try { localStorage.setItem('rb.style.template', safe); } catch (e) {}
    qsa('[data-rb-style-template]').forEach(btn => {
      const on = (btn.getAttribute('data-rb-style-template') || '').toLowerCase() === safe;
      btn.classList.toggle('btn-primary', on);
      btn.classList.toggle('btn-outline-secondary', !on);
    });
    return safe;
  }

  function applyTemplateToQuestionBlock (el, templateName) {
    if (!el) return false;
    const dtype = String(el.getAttribute('data-type') || '').toLowerCase();
    const hasQuestionId = String(el.getAttribute('data-question-id') || '').trim() !== '';
    const isQuestionBlock = ['question', 'table', 'question_table'].includes(dtype) || hasQuestionId;
    const isDataFieldBlock = dtype === 'data_field';
    if (!isQuestionBlock && !isDataFieldBlock) return false;
    const b = readBlockFromEl(el);
    if (!b.question_id && hasQuestionId) {
      const qid = Number(el.getAttribute('data-question-id') || 0);
      if (qid) b.question_id = qid;
    }
    if (isQuestionBlock && (!b.type || !['question', 'table', 'question_table'].includes(String(b.type).toLowerCase()))) {
      b.type = 'question';
      el.setAttribute('data-type', 'question');
    }
    b.config = (b.config && typeof b.config === 'object') ? b.config : {};
    b.config.table = (b.config.table && typeof b.config.table === 'object') ? b.config.table : {};
    Object.assign(b.config.table, tableStyleTemplateConfig(templateName));
    writeConfigToEl(el, b.config);
    return true;
  }

  function applyTemplateToAllQuestions (templateName) {
    let changed = 0;
    const all = new Set();
    for (const zoneId of ZONES) {
      const zone = qs('#' + zoneId);
      if (!zone) continue;
      qsa('.rb-block-instance', zone).forEach(el => all.add(el));
      qsa('[data-question-id]', zone).forEach(el => all.add(el));
      qsa('[data-type="question"], [data-type="table"], [data-type="question_table"]', zone).forEach(el => all.add(el));
    }
    all.forEach(el => {
      if (applyTemplateToQuestionBlock(el, templateName)) changed += 1;
    });
    return changed;
  }

  function bindStyleTemplateButtons () {
    const startTemplate = setCurrentTableStyleTemplate(currentTableStyleTemplate());
    qsa('[data-rb-style-template]').forEach(btn => {
      if (btn._rbBound) return;
      btn._rbBound = true;
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const tpl = setCurrentTableStyleTemplate(btn.getAttribute('data-rb-style-template') || startTemplate);
        const changed = applyTemplateToAllQuestions(tpl);
        if (window.uiToast) {
          if (changed > 0) {
            window.uiToast(tf('Template appliqué à {n} bloc(s) de tableau.', { n: changed }), { variant: 'success' });
          } else {
            window.uiToast(t('Aucun bloc de tableau trouvé dans le rapport.'), { variant: 'warning' });
          }
        }
      });
    });
  }

  function buildDocumentTemplate (templateName) {
    const name = String(templateName || '').trim().toLowerCase();

    if (name === 'invoice') {
      return {
        report_header: [
          {
            type: 'text',
            title: t('FACTURE'),
            content: t('Entreprise\nAdresse\nTéléphone • Email')
          },
          {
            type: 'markdown',
            title: t('Informations facture'),
            content: t('**N° facture :** INV-2026-001\n**Date :** {{date}}\n**Échéance :** {{due_date}}\n**Client :** {{client_name}}\n**Adresse client :** {{client_address}}')
          }
        ],
        page_header: [],
        detail: [
          {
            type: 'markdown',
            title: t('Lignes de facturation'),
            content: t('| Description | Qté | PU | Total |\n|---|---:|---:|---:|\n| Service A | 1 | 1000 | 1000 |\n| Service B | 2 | 250 | 500 |')
          },
          {
            type: 'markdown',
            title: t('Totaux'),
            content: t('**Sous-total :** {{subtotal}}\n**TVA :** {{tax}}\n**Total TTC :** {{grand_total}}')
          }
        ],
        page_footer: [
          {
            type: 'text',
            title: t('Conditions de paiement'),
            content: t('Paiement à 30 jours. Merci pour votre confiance.')
          }
        ],
        report_footer: []
      };
    }

    if (name === 'letter') {
      return {
        report_header: [
          {
            type: 'text',
            title: t('En-tête'),
            content: t('Entreprise\nAdresse\nTéléphone • Email')
          }
        ],
        page_header: [],
        detail: [
          {
            type: 'markdown',
            title: t('Objet'),
            content: t('**Objet :** {{subject}}')
          },
          {
            type: 'markdown',
            title: t('Corps de lettre'),
            content: t('Madame, Monsieur,\n\n{{body}}\n\nCordialement,\n{{signatory_name}}\n{{signatory_role}}')
          }
        ],
        page_footer: [],
        report_footer: [
          {
            type: 'field',
            title: t('Date'),
            config: { kind: 'date', format: 'dd/MM/yyyy' }
          }
        ]
      };
    }

    if (name === 'quote') {
      return {
        report_header: [
          {
            type: 'text',
            title: t('DEVIS'),
            content: t('Entreprise\nAdresse\nTéléphone • Email')
          },
          {
            type: 'markdown',
            title: t('Informations devis'),
            content: t('**N° devis :** QUO-2026-001\n**Date :** {{date}}\n**Valide jusqu’au :** {{valid_until}}\n**Client :** {{client_name}}')
          }
        ],
        page_header: [],
        detail: [
          {
            type: 'markdown',
            title: t('Prestations proposées'),
            content: t('| Description | Qté | PU | Total |\n|---|---:|---:|---:|\n| Prestation A | 1 | 800 | 800 |\n| Prestation B | 1 | 450 | 450 |')
          },
          {
            type: 'markdown',
            title: t('Montant estimé'),
            content: t('**Total estimé :** {{grand_total}}\n\n{{terms}}')
          }
        ],
        page_footer: [],
        report_footer: []
      };
    }

    return null;
  }

  function countBlocksInZones () {
    let count = 0;
    for (const zoneId of ZONES) {
      const zone = qs('#' + zoneId);
      if (!zone) continue;
      count += qsa('.rb-block-instance', zone).length;
    }
    return count;
  }

  function applyDocumentTemplate (templateName) {
    const tpl = buildDocumentTemplate(templateName);
    if (!tpl) return false;

    const zoneMap = {
      report_header: qs('#rb-report-header'),
      page_header: qs('#rb-page-header'),
      detail: qs('#rb-detail'),
      page_footer: qs('#rb-page-footer'),
      report_footer: qs('#rb-report-footer')
    };

    for (const band of Object.keys(zoneMap)) {
      const zone = zoneMap[band];
      if (!zone) continue;
      zone.innerHTML = `<div class="rb-drop-hint">${t('Arraste aqui...')}</div>`;
      const blocks = Array.isArray(tpl[band]) ? tpl[band] : [];
      for (const b of blocks) {
        zone.appendChild(makeBlockEl(b));
      }
    }
    normalizeDropHints();
    return true;
  }

  function bindDocumentTemplateButtons () {
    qsa('[data-rb-doc-template]').forEach(btn => {
      if (btn._rbBoundDocTpl) return;
      btn._rbBoundDocTpl = true;
      btn.addEventListener('click', async (e) => {
        e.preventDefault();
        const name = btn.getAttribute('data-rb-doc-template') || '';
        const existing = countBlocksInZones();
        if (existing > 0) {
          const ok = await rbConfirm(t('Ce template remplacera la mise en page actuelle. Continuer ?'), {
            title: t('Appliquer le template')
          });
          if (!ok) return;
        }
        const applied = applyDocumentTemplate(name);
        if (window.uiToast) {
          if (applied) window.uiToast(t('Template de document chargé.'), { variant: 'success' });
          else window.uiToast(t('Impossible de charger ce template.'), { variant: 'danger' });
        }
      });
    });
  }

  async function boot () {
    const cfg = window.__RB;
    if (!cfg || !cfg.apiUrl) return;

    const palette = qs('#rb-palette');
    const reportHeader = qs('#rb-report-header');
    const pageHeader = qs('#rb-page-header');
    const detail = qs('#rb-detail');
    const pageFooter = qs('#rb-page-footer');
    const reportFooter = qs('#rb-report-footer');
    const saveBtn = qs('#rb-save');

    initFloatingExplorerPanel();

    Sortable.create(palette, {
      group: { name: 'rb', pull: 'clone', put: false },
      sort: false,
      animation: 150
    });

    function zoneOptions () {
      return {
        group: { name: 'rb', pull: true, put: true },
        animation: 150,
        onAdd: (evt) => {
          const it = evt.item;
          if (!it) return;
          if (it.classList.contains('rb-block-instance')) {
            normalizeDropHints();
            return;
          }
          const type = (it.getAttribute('data-type') || 'text').toLowerCase();
          const title = it.getAttribute('data-title') || (
            type === 'markdown' ? t('Markdown')
              : type === 'question' ? t('Tabela')
                : type === 'image' ? t('Imagem')
                  : type === 'field' ? t('Campo')
                    : t('Texto')
          );

          const block = { type, title, content: '' };
          if (type === 'field') block.config = { kind: 'date', format: 'dd/MM/yyyy' };
          if (type === 'question') {
            block.config = {
              table: {
                ...tableStyleTemplateConfig(currentTableStyleTemplate()),
                decimals: ''
              }
            };
          }
          if (type === 'data_field') {
            const bindingRaw = it.getAttribute('data-binding') || '{}';
            const binding = safeJsonParse(bindingRaw, {}) || {};
            block.config = {
              binding,
              format: '',
              empty_text: ''
            };
          }

          const newEl = makeBlockEl(block);
          it.replaceWith(newEl);
          normalizeDropHints();

          // open editor immediately for most blocks
          if (['text', 'markdown', 'image', 'field', 'question', 'data_field'].includes(type)) editBlock(newEl);
        },
        onSort: normalizeDropHints,
        onRemove: normalizeDropHints
      };
    }

    Sortable.create(reportHeader, zoneOptions());
    Sortable.create(pageHeader, zoneOptions());
    Sortable.create(detail, zoneOptions());
    Sortable.create(pageFooter, zoneOptions());
    Sortable.create(reportFooter, zoneOptions());

    await initDataExplorer(cfg);
    bindDocumentTemplateButtons();
    bindStyleTemplateButtons();

    // Load existing layout
    try {
      const rep = await jsonFetch(cfg.apiUrl);
      const layout = rep.layout || {};
      const settings = (layout.settings || {});
      const spn = qs('#rb-setting-page-number');
      const spl = qs('#rb-setting-page-label');
      if (spn) spn.checked = settings.page_number !== false;
      if (spl) spl.value = String(settings.page_number_label || 'Page {page} / {pages}');


      // Backward compat: sections -> bands
      const bands = layout.bands || null;
      const secs = layout.sections || null;
      const effective = bands ? {
        report_header: bands.report_header || [],
        page_header: bands.page_header || [],
        detail: bands.detail || [],
        page_footer: bands.page_footer || [],
        report_footer: bands.report_footer || []
      } : {
        report_header: [],
        page_header: (secs && Array.isArray(secs.header)) ? secs.header : [],
        detail: (secs && Array.isArray(secs.body)) ? secs.body : [],
        page_footer: (secs && Array.isArray(secs.footer)) ? secs.footer : [],
        report_footer: []
      };

      const zoneMap = {
        'rb-report-header': reportHeader,
        'rb-page-header': pageHeader,
        'rb-detail': detail,
        'rb-page-footer': pageFooter,
        'rb-report-footer': reportFooter
      };

      const bandToZone = {
        report_header: 'rb-report-header',
        page_header: 'rb-page-header',
        detail: 'rb-detail',
        page_footer: 'rb-page-footer',
        report_footer: 'rb-report-footer'
      };

      for (const bandKey of Object.keys(bandToZone)) {
        const zoneId = bandToZone[bandKey];
        const dz = zoneMap[zoneId];
        if (!dz) continue;
        dz.innerHTML = `<div class="rb-drop-hint">${t('Arraste aqui...')}</div>`;
        const blocks = Array.isArray(effective[bandKey]) ? effective[bandKey] : [];
        for (const b of blocks) {
          const bb = { ...b };
          if (bb.text != null && bb.content == null) bb.content = bb.text;
          if (bb.image_url != null && bb.url == null) bb.url = bb.image_url;
          if (bb.type === 'data_field' && bb.config && bb.config.binding) {
            _registerBindingPlaceholders(bb.config.binding);
          }
          dz.appendChild(makeBlockEl(bb));
        }
      }
    } catch (e) {
      // ignore
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
        const label = qSel.options[qSel.selectedIndex]?.textContent || tf('Pergunta #{n}', { n: qid });
        detail.appendChild(makeBlockEl({
          type: 'question',
          title: label,
          question_id: qid,
          config: {
            table: {
              ...tableStyleTemplateConfig(currentTableStyleTemplate()),
              decimals: ''
            }
          }
        }));
        normalizeDropHints();
      });
    }

    // Add image shortcut
    const imgUrlInput = qs('#rb-image-url');
    const addImg = qs('#rb-add-image');
    if (addImg && imgUrlInput) {
      addImg.addEventListener('click', (e) => {
        e.preventDefault();
        const url = String(imgUrlInput.value || '').trim();
        if (!url) return;
        const el = makeBlockEl({ type: 'image', title: t('Imagem'), url });
        detail.appendChild(el);
        imgUrlInput.value = '';
        normalizeDropHints();
        editBlock(el);
      });
    }

    // Add field shortcut
    const addFieldDate = qs('#rb-add-field-date');
    const addFieldDateTime = qs('#rb-add-field-datetime');
    if (addFieldDate) {
      addFieldDate.addEventListener('click', (e) => {
        e.preventDefault();
        const el = makeBlockEl({ type: 'field', title: t('Data'), config: { kind: 'date', format: 'dd/MM/yyyy' } });
        pageHeader.appendChild(el);
        normalizeDropHints();
        editBlock(el);
      });
    }
    if (addFieldDateTime) {
      addFieldDateTime.addEventListener('click', (e) => {
        e.preventDefault();
        const el = makeBlockEl({ type: 'field', title: t('Data e hora'), config: { kind: 'datetime', format: 'dd/MM/yyyy HH:mm' } });
        pageHeader.appendChild(el);
        normalizeDropHints();
        editBlock(el);
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
          saveBtn.innerHTML = `<i class="bi bi-check2 me-1"></i>${t('Salvo')}`;
          setTimeout(() => { saveBtn.innerHTML = `<i class="bi bi-save me-1"></i>${t('Salvar')}`; }, 1200);
        } catch (err) {
          const msg = err?.error || t('Falha ao salvar');
          if (window.uiToast) window.uiToast(msg, { variant: 'danger' });
          else rbAlert(msg, { title: t('Erreur') });
        } finally {
          saveBtn.disabled = false;
        }
      });
    }
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
