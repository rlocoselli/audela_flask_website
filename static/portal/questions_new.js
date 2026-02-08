(function(){
  function getCsrf() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  }

  function showWarnings(container, warnings){
    if (!container) return;
    if (!warnings || !warnings.length) {
      container.classList.add('d-none');
      container.innerHTML = '';
      return;
    }
    const items = warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('');
    container.innerHTML = `
      <div class="alert alert-warning mb-0" role="alert">
        <div class="fw-semibold mb-1"><i class="bi bi-exclamation-triangle me-1"></i> Avisos</div>
        <ul class="mb-0">${items}</ul>
      </div>
    `;
    container.classList.remove('d-none');
  }

  function escapeHtml(s){
    return (s ?? '').toString()
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  async function nlq(){
    const srcSel = document.getElementById('q-source');
    const text = document.getElementById('nlq-text');
    const sql = document.getElementById('q-sql');
    const warn = document.getElementById('nlq-warnings');
    const btn = document.getElementById('nlq-generate');

    if (!srcSel || !text || !sql || !btn) return;

    const sourceId = parseInt(srcSel.value || '0', 10);
    if (!sourceId) {
      showWarnings(warn, ['Selecione uma fonte de dados antes de gerar o SQL.']);
      srcSel.focus();
      return;
    }

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Gerando...';
    try {
      const r = await fetch('/app/api/nlq', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrf(),
        },
        body: JSON.stringify({ source_id: sourceId, text: (text.value||'').trim() })
      });
      const data = await r.json().catch(()=> ({}));
      if (!r.ok) {
        showWarnings(warn, [data.error || 'Falha ao gerar SQL.']);
        return;
      }
      if (data.sql) {
        sql.value = data.sql;
      }
      showWarnings(warn, data.warnings || []);
      sql.focus();
    } catch (e) {
      showWarnings(warn, ['Erro ao chamar o servidor: ' + e]);
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-magic"></i> Gerar SQL';
    }
  }

  document.addEventListener('DOMContentLoaded', function(){
    const btn = document.getElementById('nlq-generate');
    if (btn) btn.addEventListener('click', nlq);
  });
})();
