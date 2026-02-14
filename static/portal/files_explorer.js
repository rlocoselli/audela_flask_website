(function () {
  function qs (sel) { return document.querySelector(sel); }
  function qsa (sel) { return Array.from(document.querySelectorAll(sel)); }

  function csrfToken () {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  function apiUrl (tpl, id) {
    const s = String(tpl || '');
    // Replace a trailing /0/ segment with the actual id
    return s.replace(/\/0(\/[^\/]+$)/, `/${id}$1`);
  }

  function showToast (title, body, kind) {
    try {
      const toastEl = qs('#app-toast');
      if (!toastEl || typeof bootstrap === 'undefined') return;
      qs('#app-toast-title').textContent = title;
      qs('#app-toast-body').textContent = body;
      const icon = qs('#app-toast-icon');
      if (icon) {
        icon.className = 'bi me-2 ' + (kind === 'error' ? 'bi-exclamation-triangle' : (kind === 'success' ? 'bi-check-circle' : 'bi-info-circle'));
      }
      const toast = bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 2800 });
      toast.show();
    } catch (e) {}
  }

  function normalizeStr (s) {
    return String(s || '').toLowerCase();
  }

  function bootTreeToggles () {
    qsa('[data-fe-toggle]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const row = btn.closest('.fe-node-row');
        const li = btn.closest('li');
        const ul = li ? li.querySelector(':scope > ul.fe-tree') : null;
        if (!ul) return;
        const isHidden = ul.hasAttribute('hidden');
        if (isHidden) {
          ul.removeAttribute('hidden');
          const ic = btn.querySelector('i');
          if (ic) ic.classList.add('rot');
          row?.classList.add('expanded');
        } else {
          ul.setAttribute('hidden', '');
          const ic = btn.querySelector('i');
          if (ic) ic.classList.remove('rot');
          row?.classList.remove('expanded');
        }
      });
    });

    // Auto-expand path nodes (so the active folder is visible)
    qsa('.fe-node-row.in-path').forEach(row => {
      const li = row.closest('li');
      const btn = row.querySelector('[data-fe-toggle]');
      const ul = li ? li.querySelector(':scope > ul.fe-tree') : null;
      if (btn && ul) {
        ul.removeAttribute('hidden');
        const ic = btn.querySelector('i');
        if (ic) ic.classList.add('rot');
      }
    });
  }

  function bootSearch () {
    const input = qs('#fe-search');
    const rows = qsa('#fe-table tbody tr.fe-row');
    if (!input) return;
    input.addEventListener('input', () => {
      const q = normalizeStr(input.value).trim();
      rows.forEach(r => {
        const name = normalizeStr(r.getAttribute('data-name'));
        r.style.display = (!q || name.includes(q)) ? '' : 'none';
      });
    });
  }

  function bootDnD () {
    // drag sources
    qsa('tr.fe-row[draggable="true"], li.fe-node[draggable="true"]').forEach(el => {
      el.addEventListener('dragstart', (e) => {
        const type = el.getAttribute('data-drag-type');
        const id = el.getAttribute('data-id');
        if (!type || !id) return;
        const payload = JSON.stringify({ type, id: Number(id) });
        e.dataTransfer?.setData('application/json', payload);
        e.dataTransfer?.setData('text/plain', payload);
        el.classList.add('dragging');
      });
      el.addEventListener('dragend', () => el.classList.remove('dragging'));
    });

    // drop targets (folder nodes + root)
    const targets = qsa('[data-drop-folder-id]');
    targets.forEach(tgt => {
      tgt.addEventListener('dragover', (e) => {
        e.preventDefault();
        tgt.classList.add('drop-hover');
      });
      tgt.addEventListener('dragleave', () => tgt.classList.remove('drop-hover'));
      tgt.addEventListener('drop', async (e) => {
        e.preventDefault();
        tgt.classList.remove('drop-hover');

        let payload = e.dataTransfer?.getData('application/json') || e.dataTransfer?.getData('text/plain');
        if (!payload) return;
        let obj;
        try { obj = JSON.parse(payload); } catch (err) { return; }
        if (!obj || !obj.type || !obj.id) return;

        const dest = tgt.getAttribute('data-drop-folder-id'); // '' = root
        const destId = (dest === '' ? null : Number(dest));

        try {
          if (obj.type === 'file') {
            await moveFile(obj.id, destId);
          } else if (obj.type === 'folder') {
            await moveFolder(obj.id, destId);
          }
          window.location.reload();
        } catch (err) {
          showToast(t('Erro'), err?.message || String(err), 'error');
        }
      });
    });
  }

  async function renameFile (id, name) {
    const url = apiUrl(window.FE_ENDPOINTS?.renameFile, id);
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken()
      },
      credentials: 'same-origin',
      body: JSON.stringify({ name })
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data.error || t('Falha ao renomear.'));
    }
  }

  async function renameFolder (id, name) {
    const url = apiUrl(window.FE_ENDPOINTS?.renameFolder, id);
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken()
      },
      credentials: 'same-origin',
      body: JSON.stringify({ name })
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data.error || t('Falha ao renomear.'));
    }
  }

  async function moveFile (id, folderId) {
    const url = apiUrl(window.FE_ENDPOINTS?.moveFile, id);
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken()
      },
      credentials: 'same-origin',
      body: JSON.stringify({ folder_id: folderId })
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data.error || t('Falha ao mover.'));
    }
  }

  async function moveFolder (id, parentId) {
    const url = apiUrl(window.FE_ENDPOINTS?.moveFolder, id);
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken()
      },
      credentials: 'same-origin',
      body: JSON.stringify({ parent_id: parentId })
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data.error || t('Falha ao mover.'));
    }
  }

  function bootRenameMoveModals () {
    const renameModalEl = qs('#modalRename');
    const moveModalEl = qs('#modalMove');
    if (!renameModalEl || !moveModalEl || typeof bootstrap === 'undefined') return;

    const renameModal = bootstrap.Modal.getOrCreateInstance(renameModalEl);
    const moveModal = bootstrap.Modal.getOrCreateInstance(moveModalEl);

    const renameKind = qs('#fe-rename-kind');
    const renameId = qs('#fe-rename-id');
    const renameName = qs('#fe-rename-name');

    const moveKind = qs('#fe-move-kind');
    const moveId = qs('#fe-move-id');
    const moveDest = qs('#fe-move-dest');

    // open rename
    qsa('[data-fe-rename]').forEach(btn => {
      btn.addEventListener('click', () => {
        renameKind.value = btn.getAttribute('data-kind') || '';
        renameId.value = btn.getAttribute('data-id') || '';
        renameName.value = btn.getAttribute('data-name') || '';
        renameModal.show();
        setTimeout(() => renameName.focus(), 50);
      });
    });

    // submit rename
    const renameForm = qs('#fe-rename-form');
    renameForm?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const kind = renameKind.value;
      const id = Number(renameId.value);
      const name = String(renameName.value || '').trim();
      if (!name) return;

      try {
        if (kind === 'file') await renameFile(id, name);
        else await renameFolder(id, name);
        renameModal.hide();
        window.location.reload();
      } catch (err) {
        showToast(t('Erro'), err?.message || String(err), 'error');
      }
    });

    // open move
    qsa('[data-fe-move]').forEach(btn => {
      btn.addEventListener('click', () => {
        moveKind.value = btn.getAttribute('data-kind') || '';
        moveId.value = btn.getAttribute('data-id') || '';
        // default to root
        if (moveDest) moveDest.value = '';
        moveModal.show();
      });
    });

    const moveForm = qs('#fe-move-form');
    moveForm?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const kind = moveKind.value;
      const id = Number(moveId.value);
      const dest = moveDest?.value;
      const destId = (dest === '' ? null : Number(dest));
      try {
        if (kind === 'file') await moveFile(id, destId);
        else await moveFolder(id, destId);
        moveModal.hide();
        window.location.reload();
      } catch (err) {
        showToast(t('Erro'), err?.message || String(err), 'error');
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    bootTreeToggles();
    bootSearch();
    bootDnD();
    bootRenameMoveModals();
  });
})();
