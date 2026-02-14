/* global bootstrap */

(function () {
  function qs (sel, root) { return (root || document).querySelector(sel); }

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

    const auth = user ? (enc(user) + (pass ? (':' + enc(pass)) : '') + '@') : '';
    const hp = host ? host : '';
    const pp = port ? (':' + port) : '';

    if (type === 'postgres') {
      return `postgresql+psycopg://${auth}${hp}${pp}/${enc(db)}`;
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

    if (!typeSel || !urlInp || !useBuilderInp) return;

    const builderTab = qs('#ds-tab-builder');
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

    function refreshVisibility () {
      const type = String(typeSel.value || '').toLowerCase();
      const isSqlite = type === 'sqlite';
      const isSqlserver = type === 'sqlserver';
      const isOracle = type === 'oracle';

      show(sqliteRow, isSqlite);

      show(hostRow, !isSqlite);
      show(portRow, !isSqlite);
      show(dbRow, !isSqlite);
      show(userRow, !isSqlite);
      show(passRow, !isSqlite);

      show(driverRow, isSqlserver);
      show(serviceRow, isOracle);
      show(sidRow, isOracle);

      // placeholders
      if (type === 'postgres') urlInp.placeholder = 'postgresql+psycopg://user:pass@host:5432/dbname';
      else if (type === 'mysql') urlInp.placeholder = 'mysql+pymysql://user:pass@host:3306/dbname';
      else if (type === 'sqlserver') urlInp.placeholder = 'mssql+pyodbc://user:pass@host:1433/dbname?driver=ODBC+Driver+18+for+SQL+Server';
      else if (type === 'oracle') urlInp.placeholder = 'oracle+oracledb://user:pass@host:1521/?service_name=ORCLPDB1';
      else if (type === 'sqlite') urlInp.placeholder = 'sqlite:////abs/path/file.db';

      // defaults
      const d = defaultsFor(type);
      if (portInp && !portInp.value && d.port) portInp.value = d.port;
      if (driverInp && !driverInp.value && d.driver) driverInp.value = d.driver;
      if (serviceInp && !serviceInp.value && d.service_name) serviceInp.value = d.service_name;

      refreshUrlFromBuilder();
    }

    function refreshUrlFromBuilder () {
      if (useBuilderInp.value !== '1') return;
      const type = String(typeSel.value || '').toLowerCase();
      const f = readBuilderFields();
      const u = buildUrl(type, f);
      if (u) urlInp.value = u;
    }

    // Tabs logic (Bootstrap)
    function setMode (mode) {
      useBuilderInp.value = (mode === 'builder') ? '1' : '0';
      urlInp.readOnly = (mode === 'builder');
      if (mode === 'builder') refreshUrlFromBuilder();
    }

    // If user manually types in URL, switch to manual
    urlInp.addEventListener('input', () => {
      if (urlInp.readOnly) return;
      useBuilderInp.value = '0';
    });

    // Builder inputs
    [typeSel, hostInp, portInp, dbInp, userInp, passInp, driverInp, serviceInp, sidInp, sqliteInp].forEach(el => {
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
    const initialMode = (useBuilderInp.value === '1') ? 'builder' : 'manual';
    setMode(initialMode);
    refreshVisibility();
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
