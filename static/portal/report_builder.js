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
    if (!styleObj || typeof styleObj !== 'object' || (!styleObj.color && !styleObj.background && !styleObj.align)) {
      el.removeAttribute('data-style');
      return;
    }
    el.setAttribute('data-style', JSON.stringify({
      color: styleObj.color || '',
      background: styleObj.background || '',
      align: styleObj.align || ''
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
      version: 4,
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
      qTheme: qs('#rb-edit-q-theme', modalEl),
      qDecimals: qs('#rb-edit-q-decimals', modalEl),
      qRepeatHeader: qs('#rb-edit-q-repeat-header', modalEl),
      qZebra: qs('#rb-edit-q-zebra', modalEl),

      colorInput: qs('#rb-edit-color', modalEl),
      bgInput: qs('#rb-edit-bg', modalEl),
      alignSelect: qs('#rb-edit-align', modalEl),

      saveBtn: qs('#rb-edit-save', modalEl),

      currentEl: null,
      currentBlock: null,
      onSave: null
    };

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

      out.style = { color, background: bg, align };
      if (!out.style.color && !out.style.background && !out.style.align) delete out.style;

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
    } else {
      ed.questionGroup.classList.add('d-none');
      if (ed.qDecimals) ed.qDecimals.value = '';
      if (ed.qRepeatHeader) ed.qRepeatHeader.checked = true;
      if (ed.qZebra) ed.qZebra.checked = false;
    }

    const st = block.style || {};
    ed.colorInput.value = (st.color || '').replace('#', '');
    ed.bgInput.value = (st.background || '').replace('#', '');
    ed.alignSelect.value = st.align || '';

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
          if (type === 'question') block.config = { table: { theme: 'crystal', repeat_header: true, zebra: false, decimals: '' } };

          const newEl = makeBlockEl(block);
          it.replaceWith(newEl);
          normalizeDropHints();

          // open editor immediately for most blocks
          if (['text', 'markdown', 'image', 'field', 'question'].includes(type)) editBlock(newEl);
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
          config: { table: { theme: 'crystal', repeat_header: true, zebra: false, decimals: '' } }
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
          else alert(msg);
        } finally {
          saveBtn.disabled = false;
        }
      });
    }
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
