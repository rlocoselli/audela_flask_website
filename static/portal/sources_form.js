/* global bootstrap */

(function () {
  function qs (sel, root) { return (root || document).querySelector(sel); }

  function csrfToken () {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  function setVal (el, v) {
    if (!el) return;
    el.value = (v == null) ? '' : String(v);
  }

  function show (el, on) {
    if (!el) return;
    el.classList.toggle('d-none', !on);
  }

  // Build a SQLAlchemy URL (best-effort). Server will validate/build too.
  function buildUrl (type, f) {
    type = String(type || '').toLowerCase();
    const host = (f.host || '').trim();
    const port = (f.port || '').trim();
    const db = (f.database || '').trim();
    const user = (f.username || '').trim();
    const pass = (f.password || '');
    const driver = (f.driver || '').trim();
    const service = (f.service_name || '').trim();
    const sid = (f.sid || '').trim();
    const sqlitePath = (f.sqlite_path || '').trim();

    const enc = encodeURIComponent;

    if (type === 'sqlite') {
      if (!sqlitePath) return '';
      if (sqlitePath.startsWith('sqlite:')) return sqlitePath;
      if (sqlitePath.startsWith('/')) return 'sqlite:////' + sqlitePath.replace(/^\/+/, '');
      return 'sqlite:///' + sqlitePath;
    }

    if (type === 'audela_finance') {
      return 'internal://audela_finance';
    }
    if (type === 'audela_project') {
      return 'internal://audela_project';
    }

    const auth = user ? (enc(user) + (pass ? (':' + enc(pass)) : '') + '@') : '';
    const hp = host ? host : '';
    const pp = port ? (':' + port) : '';

    if (type === 'postgres') {
      return `postgresql+psycopg2://${auth}${hp}${pp}/${enc(db)}`;
    }
    if (type === 'mysql') {
      return `mysql+pymysql://${auth}${hp}${pp}/${enc(db)}`;
    }
    if (type === 'sqlserver') {
      // Use driver query param for pyodbc
      const q = driver ? `?driver=${encodeURIComponent(driver)}` : '';
      return `mssql+pyodbc://${auth}${hp}${pp}/${enc(db)}${q}`;
    }
    if (type === 'oracle') {
      // oracledb supports service_name or sid in query string
      const q = service ? `?service_name=${encodeURIComponent(service)}` : (sid ? `?sid=${encodeURIComponent(sid)}` : '');
      return `oracle+oracledb://${auth}${hp}${pp}/${q}`.replace('/?', '/?');
    }

    return '';
  }

  function safeJson (obj) {
    try {
      return JSON.stringify(obj, null, 2);
    } catch (e) {
      return '';
    }
  }

  // Best-effort parse of a SQLAlchemy URL to populate builder fields
  function parseUrlToFields (rawUrl) {
    const s = String(rawUrl || '').trim();
    if (!s) return null;

    // SQLite can be tricky with multiple slashes
    if (s.toLowerCase().startsWith('sqlite:')) {
      const p = s.replace(/^sqlite:\/*/i, '');
      return { type: 'sqlite', sqlite_path: p ? '/' + p.replace(/^\/*/, '') : '' };
    }

    if (s.toLowerCase().startsWith('internal://audela_finance')) {
      return { type: 'audela_finance' };
    }
    if (s.toLowerCase().startsWith('internal://audela_project')) {
      return { type: 'audela_project' };
    }

    try {
      const u = new URL(s);
      const scheme = (u.protocol || '').replace(':', '').toLowerCase();
      let type = '';
      if (scheme.startsWith('postgres')) type = 'postgres';
      else if (scheme.startsWith('mysql')) type = 'mysql';
      else if (scheme.startsWith('mssql')) type = 'sqlserver';
      else if (scheme.startsWith('oracle')) type = 'oracle';

      const out = {
        type,
        host: u.hostname || '',
        port: u.port || '',
        database: (u.pathname || '').replace(/^\//, ''),
        username: decodeURIComponent(u.username || ''),
        password: decodeURIComponent(u.password || '')
      };
      // query params
      const qp = u.searchParams;
      if (type === 'sqlserver' && qp.get('driver')) out.driver = qp.get('driver');
      if (type === 'oracle') {
        if (qp.get('service_name')) out.service_name = qp.get('service_name');
        if (qp.get('sid')) out.sid = qp.get('sid');
      }
      return out;
    } catch (e) {
      return null;
    }
  }

  function defaultsFor (type) {
    type = String(type || '').toLowerCase();
    if (type === 'postgres') return { port: '5432' };
    if (type === 'mysql') return { port: '3306' };
    if (type === 'sqlserver') return { port: '1433', driver: 'ODBC Driver 18 for SQL Server' };
    if (type === 'oracle') return { port: '1521', service_name: 'ORCLPDB1' };
    return {};
  }

  function boot () {
    const typeSel = qs('#ds-type');
    const urlInp = qs('#ds-url');
    const useBuilderInp = qs('#ds-use-builder');

    const formEl = qs('#ds-form');
    const testUrl = formEl?.getAttribute('data-test-url') || '';
    const sourceId = formEl?.getAttribute('data-source-id') || '';
    const hasPassword = (formEl?.getAttribute('data-has-password') || '0') === '1';

    if (!typeSel || !urlInp || !useBuilderInp) return;

    const builderTab = qs('#ds-tab-builder') || qs('#ds-tab-assist');
    const manualTab = qs('#ds-tab-manual');

    const hostRow = qs('[data-ds-row="host"]');
    const portRow = qs('[data-ds-row="port"]');
    const dbRow = qs('[data-ds-row="database"]');
    const userRow = qs('[data-ds-row="username"]');
    const passRow = qs('[data-ds-row="password"]');
    const driverRow = qs('[data-ds-row="driver"]');
    const serviceRow = qs('[data-ds-row="service_name"]');
    const sidRow = qs('[data-ds-row="sid"]');
    const sqliteRow = qs('[data-ds-row="sqlite_path"]');

    const hostInp = qs('#ds-host');
    const portInp = qs('#ds-port');
    const dbInp = qs('#ds-database');
    const userInp = qs('#ds-username');
    const passInp = qs('#ds-password');
    const driverInp = qs('#ds-driver');
    const serviceInp = qs('#ds-service');
    const sidInp = qs('#ds-sid');
    const sqliteInp = qs('#ds-sqlite-path');

    function readBuilderFields () {
      return {
        host: hostInp?.value || '',
        port: portInp?.value || '',
        database: dbInp?.value || '',
        username: userInp?.value || '',
        password: passInp?.value || '',
        driver: driverInp?.value || '',
        service_name: serviceInp?.value || '',
        sid: sidInp?.value || '',
        sqlite_path: sqliteInp?.value || ''
      };
    }

    const urlPreviewInp = qs('#ds-url-preview') || qs('#ds-url-generated');
    const copyUrlBtn = qs('#ds-copy-url');
    const cfgPreviewInp = qs('#ds-config-preview');
    const copyCfgBtn = qs('#ds-copy-config');
    const testBtn = qs('#ds-test-conn');

    function refreshVisibility () {
      const type = String(typeSel.value || '').toLowerCase();
      const isSqlite = type === 'sqlite';
      const isSqlserver = type === 'sqlserver';
      const isOracle = type === 'oracle';
      const isInternal = type === 'audela_finance' || type === 'audela_project';

      show(sqliteRow, isSqlite && !isInternal);

      show(hostRow, !isSqlite && !isInternal);
      show(portRow, !isSqlite && !isInternal);
      show(dbRow, !isSqlite && !isInternal);
      show(userRow, !isSqlite && !isInternal);
      show(passRow, !isSqlite && !isInternal);

      show(driverRow, isSqlserver && !isInternal);
      show(serviceRow, isOracle && !isInternal);
      show(sidRow, isOracle && !isInternal);

      // placeholders
      if (type === 'postgres') urlInp.placeholder = 'postgresql+psycopg2://user:pass@host:5432/dbname';
      else if (type === 'mysql') urlInp.placeholder = 'mysql+pymysql://user:pass@host:3306/dbname';
      else if (type === 'sqlserver') urlInp.placeholder = 'mssql+pyodbc://user:pass@host:1433/dbname?driver=ODBC+Driver+18+for+SQL+Server';
      else if (type === 'oracle') urlInp.placeholder = 'oracle+oracledb://user:pass@host:1521/?service_name=ORCLPDB1';
      else if (type === 'audela_finance') urlInp.placeholder = 'internal://audela_finance';
      else if (type === 'audela_project') urlInp.placeholder = 'internal://audela_project';
      else if (type === 'sqlite') urlInp.placeholder = 'sqlite:////abs/path/file.db';

      // defaults
      const d = defaultsFor(type);
      if (portInp && !portInp.value && d.port) portInp.value = d.port;
      if (driverInp && !driverInp.value && d.driver) driverInp.value = d.driver;
      if (serviceInp && !serviceInp.value && d.service_name) serviceInp.value = d.service_name;

      refreshUrlFromBuilder();
    }

    function refreshUrlFromBuilder () {
      if (useBuilderInp.value !== '1') {
        // In manual mode we still want the JSON preview to update.
        if (urlPreviewInp) urlPreviewInp.value = urlInp.value || '';
        refreshConfigPreview();
        return;
      }
      const type = String(typeSel.value || '').toLowerCase();
      const f = readBuilderFields();
      const u = buildUrl(type, f);
      if (u) {
        urlInp.value = u;
        if (urlPreviewInp) urlPreviewInp.value = u;
      }
      refreshConfigPreview();
    }

    function refreshConfigPreview () {
      if (!cfgPreviewInp) return;
      const cfg = {
        url: (urlInp.value || '').trim(),
        default_schema: (qs('input[name="default_schema"]')?.value || '').trim() || null,
        tenant_column: (qs('input[name="tenant_column"]')?.value || '').trim() || null,
        conn: {
          host: (hostInp?.value || '').trim(),
          port: (portInp?.value || '').trim(),
          database: (dbInp?.value || '').trim(),
          username: (userInp?.value || '').trim(),
          password: (passInp?.value || '') || (hasPassword ? '••••••' : ''),
          driver: (driverInp?.value || '').trim(),
          service_name: (serviceInp?.value || '').trim(),
          sid: (sidInp?.value || '').trim(),
          sqlite_path: (sqliteInp?.value || '').trim()
        }
      };
      cfgPreviewInp.value = safeJson(cfg);
    }

    // Tabs logic (Bootstrap)
    function setMode (mode) {
      useBuilderInp.value = (mode === 'builder') ? '1' : '0';
      urlInp.readOnly = (mode === 'builder');
      if (mode === 'builder') refreshUrlFromBuilder();
      else {
        if (urlPreviewInp) urlPreviewInp.value = urlInp.value || '';
        refreshConfigPreview();
      }
    }

    // If user manually types in URL, switch to manual
    urlInp.addEventListener('input', () => {
      if (urlInp.readOnly) return;
      useBuilderInp.value = '0';
      if (urlPreviewInp) urlPreviewInp.value = urlInp.value || '';

      // Best-effort: parse URL and populate builder fields so config matches.
      const parsed = parseUrlToFields(urlInp.value || '');
      if (parsed) {
        if (parsed.type && typeSel.value !== parsed.type) typeSel.value = parsed.type;
        if (hostInp && parsed.host != null) hostInp.value = parsed.host;
        if (portInp && parsed.port != null) portInp.value = parsed.port;
        if (dbInp && parsed.database != null) dbInp.value = parsed.database;
        if (userInp && parsed.username != null) userInp.value = parsed.username;
        if (passInp && parsed.password != null && parsed.password !== '') passInp.value = parsed.password;
        if (driverInp && parsed.driver != null) driverInp.value = parsed.driver;
        if (serviceInp && parsed.service_name != null) serviceInp.value = parsed.service_name;
        if (sidInp && parsed.sid != null) sidInp.value = parsed.sid;
        if (sqliteInp && parsed.sqlite_path != null) sqliteInp.value = parsed.sqlite_path;
        refreshVisibility();
      }
      refreshConfigPreview();
    });

    // Builder inputs
    [typeSel, hostInp, portInp, dbInp, userInp, passInp, driverInp, serviceInp, sidInp, sqliteInp, qs('input[name="default_schema"]'), qs('input[name="tenant_column"]')].forEach(el => {
      if (!el) return;
      el.addEventListener('input', refreshUrlFromBuilder);
      el.addEventListener('change', refreshUrlFromBuilder);
    });

    typeSel.addEventListener('change', refreshVisibility);

    // Tabs events
    if (builderTab) {
      builderTab.addEventListener('shown.bs.tab', () => setMode('builder'));
    }
    if (manualTab) {
      manualTab.addEventListener('shown.bs.tab', () => setMode('manual'));
    }

    // Init based on current hidden value
    const initialMode = (useBuilderInp.value === '1' || !useBuilderInp.value) ? 'builder' : 'manual';
    setMode(initialMode);
    refreshVisibility();

    // Init previews
    if (urlPreviewInp) urlPreviewInp.value = urlInp.value || '';
    refreshConfigPreview();

    if (copyUrlBtn) {
      copyUrlBtn.addEventListener('click', async () => {
        const txt = (urlPreviewInp?.value || urlInp.value || '').trim();
        if (!txt) return;
        try {
          await navigator.clipboard.writeText(txt);
          window.uiToast?.(window.t('Copiado.'), { variant: 'success' });
        } catch (e) {
          window.uiToast?.(window.t('Falha ao copiar.'), { variant: 'danger' });
        }
      });
    }

    if (copyCfgBtn) {
      copyCfgBtn.addEventListener('click', async () => {
        const txt = (cfgPreviewInp?.value || '').trim();
        if (!txt) return;
        try {
          await navigator.clipboard.writeText(txt);
          window.uiToast?.(window.t('Copiado.'), { variant: 'success' });
        } catch (e) {
          window.uiToast?.(window.t('Falha ao copiar.'), { variant: 'danger' });
        }
      });
    }

    async function testConnection () {
      if (!testUrl) {
        window.uiToast?.(window.t('Endpoint de teste não configurado.'), { variant: 'danger' });
        return;
      }
      const payload = {
        source_id: sourceId || null,
        type: (typeSel.value || '').toLowerCase(),
        use_builder: useBuilderInp.value || '0',
        url: (urlInp.value || '').trim(),
        ...readBuilderFields()
      };
      // normalize builder fields naming for server
      payload.database = payload.database || '';
      payload.service_name = payload.service_name || '';
      payload.sqlite_path = payload.sqlite_path || '';

      let oldHtml = null;
      try {
        testBtn?.setAttribute('disabled', 'disabled');
        oldHtml = testBtn?.innerHTML || null;
        if (testBtn) testBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>${window.t('Testando...')}`;
        const res = await fetch(testUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(csrfToken() ? { 'X-CSRFToken': csrfToken() } : {})
          },
          body: JSON.stringify(payload)
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok && data && data.ok) {
          window.uiToast?.(data.message || window.t('Conexão OK.'), { variant: 'success' });
        } else {
          const msg = (data && (data.error || data.message)) || window.t('Falha na conexão.');
          window.uiToast?.(msg, { variant: 'danger' });
        }
      } catch (e) {
        window.uiToast?.(window.tf('Falha na conexão: {error}', { error: String(e) }), { variant: 'danger' });
      } finally {
        if (testBtn && oldHtml != null) testBtn.innerHTML = oldHtml;
        testBtn?.removeAttribute('disabled');
      }
    }

    if (testBtn) testBtn.addEventListener('click', testConnection);
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
