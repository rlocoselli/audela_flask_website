(function(){
  function qs(s){ return document.querySelector(s); }
  function qsa(s){ return Array.from(document.querySelectorAll(s)); }

  let network = null;
  let currentNodeIds = [];
  let currentEdgeIds = [];
  let currentAdjacency = {};
  let tableByNodeId = {};
  let activeNodeId = null;
  let lastSchema = null;

  function colName(col) {
    if (typeof col === 'string') return col;
    if (col && typeof col === 'object') return String(col.name || '');
    return '';
  }

  function colType(col) {
    if (!col || typeof col !== 'object') return '';
    return String(col.type || '');
  }

  function colNullable(col) {
    if (!col || typeof col !== 'object') return null;
    if (typeof col.nullable === 'boolean') return col.nullable;
    return null;
  }

  function colPrimaryKey(col) {
    if (!col || typeof col !== 'object') return null;
    if (typeof col.primary_key === 'boolean') return col.primary_key;
    if (typeof col.pk === 'boolean') return col.pk;
    return null;
  }

  function clearDetails() {
    const host = qs('#sd-details');
    if (!host) return;
    host.innerHTML = '';
    const msg = document.createElement('div');
    msg.className = 'text-secondary';
    msg.textContent = 'Select an entity to view properties.';
    host.appendChild(msg);
  }

  function showTableDetails(nid) {
    const host = qs('#sd-details');
    if (!host) return;
    const table = tableByNodeId[nid];
    if (!table) {
      clearDetails();
      return;
    }

    const tableName = String(table.name || '—');
    const schemaName = String(table.schema || '—');
    const fullName = String(table.full_name || tableName || '—');
    const columns = sortColumnsErwin(normalizeColumns(table.columns));

    host.innerHTML = '';

    const title = document.createElement('div');
    title.className = 'fw-semibold mb-2';
    title.textContent = 'Entity properties';
    host.appendChild(title);

    const tableBlock = document.createElement('div');
    tableBlock.className = 'mb-2';
    [
      ['Table', tableName],
      ['Schema', schemaName],
      ['Full name', fullName],
      ['Columns', String(columns.length)]
    ].forEach(([label, value]) => {
      const row = document.createElement('div');
      const strong = document.createElement('strong');
      strong.textContent = `${label}: `;
      const text = document.createTextNode(value);
      row.appendChild(strong);
      row.appendChild(text);
      tableBlock.appendChild(row);
    });
    host.appendChild(tableBlock);

    const listWrap = document.createElement('div');
    listWrap.className = 'border rounded p-2';
    listWrap.style.maxHeight = '260px';
    listWrap.style.overflowY = 'auto';

    if (!columns.length) {
      const empty = document.createElement('div');
      empty.className = 'text-secondary';
      empty.textContent = 'No column metadata available.';
      listWrap.appendChild(empty);
    } else {
      columns.forEach((c) => {
        const row = document.createElement('div');
        row.className = 'mb-1';
        const name = colName(c);
        const type = colType(c);
        const nullable = colNullable(c);
        const pk = colPrimaryKey(c);
        const chips = [];
        if (type) chips.push(type);
        if (pk === true) chips.push('PK');
        if (nullable === true) chips.push('NULL');
        if (nullable === false) chips.push('NOT NULL');
        row.textContent = chips.length ? `${name} — ${chips.join(' · ')}` : name;
        listWrap.appendChild(row);
      });
    }
    host.appendChild(listWrap);
  }

  function themeColor(varName, fallback) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(varName);
    return (value && value.trim()) || fallback;
  }

  function isFkCol(col) {
    const name = colName(col);
    return !!name && name.endsWith('_id');
  }

  function isPkCol(col) {
    const name = colName(col);
    const explicitPk = colPrimaryKey(col) === true;
    return explicitPk || name === 'id';
  }

  function normalizeColumns(rawColumns) {
    return (Array.isArray(rawColumns) ? rawColumns : [])
      .map((c) => {
        if (typeof c === 'string') return { name: c };
        if (c && typeof c === 'object') return c;
        return null;
      })
      .filter(Boolean)
      .filter((c) => colName(c));
  }

  function sortColumnsErwin(columns) {
    return [...columns].sort((a, b) => {
      const aPk = isPkCol(a) ? 1 : 0;
      const bPk = isPkCol(b) ? 1 : 0;
      if (aPk !== bPk) return bPk - aPk;

      const aFk = isFkCol(a) ? 1 : 0;
      const bFk = isFkCol(b) ? 1 : 0;
      if (aFk !== bFk) return bFk - aFk;

      return colName(a).localeCompare(colName(b));
    });
  }

  function entityLabel(table) {
    const columns = sortColumnsErwin(normalizeColumns(table.columns));

    const maxCols = 12;
    const shown = columns.slice(0, maxCols);
    const more = columns.length > maxCols ? [`… +${columns.length - maxCols}`] : [];
    const title = String(table.full_name || table.name || 'TABLE').toUpperCase();

    const bodyLines = shown.map((c) => {
      const n = colName(c);
      const t = colType(c);
      const marker = isPkCol(c) ? 'PK' : (isFkCol(c) ? 'FK' : '• ');
      return t ? `${marker} ${n} : ${t}` : `${marker} ${n}`;
    });
    const body = bodyLines.concat(more).join('\n');
    return body ? `${title}\n════════\n${body}` : title;
  }

  function relationLabel(relation) {
    const fromCol = (relation.from || '').split('.').slice(1).join('.');
    const toCol = (relation.to || '').split('.').slice(1).join('.');
    if (!fromCol || !toCol) return '';
    return `${fromCol} → ${toCol}`;
  }

  function computeLevels(nodes, edges) {
    const inDegree = {};
    const outgoing = {};
    const level = {};
    nodes.forEach((n) => {
      inDegree[n.id] = 0;
      outgoing[n.id] = [];
      level[n.id] = 0;
    });

    edges.forEach((e) => {
      if (!(e.from in inDegree) || !(e.to in inDegree)) return;
      inDegree[e.to] += 1;
      outgoing[e.from].push(e.to);
    });

    const queue = nodes.filter((n) => inDegree[n.id] === 0).map((n) => n.id);
    const visited = new Set();

    while (queue.length) {
      const id = queue.shift();
      visited.add(id);
      const targets = outgoing[id] || [];
      targets.forEach((to) => {
        level[to] = Math.max(level[to], level[id] + 1);
        inDegree[to] -= 1;
        if (inDegree[to] === 0) queue.push(to);
      });
    }

    if (visited.size < nodes.length) {
      nodes.forEach((n) => {
        if (!visited.has(n.id)) {
          const out = (outgoing[n.id] || []).length;
          level[n.id] = Math.max(level[n.id], out > 0 ? 1 : 0);
        }
      });
    }

    return level;
  }

  function buildAdjacency(nodeIds, edges) {
    const adjacency = {};
    nodeIds.forEach((id) => { adjacency[id] = new Set(); });
    edges.forEach((e) => {
      if (adjacency[e.from]) adjacency[e.from].add(e.to);
      if (adjacency[e.to]) adjacency[e.to].add(e.from);
    });
    return adjacency;
  }

  function collectNeighbors(startId, maxDepth) {
    const byDepth = {};
    const visited = new Set([startId]);
    let frontier = new Set([startId]);

    for (let depth = 1; depth <= maxDepth; depth += 1) {
      const next = new Set();
      frontier.forEach((id) => {
        const neighbors = currentAdjacency[id] || new Set();
        neighbors.forEach((n) => {
          if (!visited.has(n)) {
            visited.add(n);
            next.add(n);
          }
        });
      });
      byDepth[depth] = next;
      frontier = next;
      if (!frontier.size) break;
    }

    return byDepth;
  }

  function applyStaticPositions(nodes, edges) {
    const levels = computeLevels(nodes, edges);
    const byLevel = {};
    nodes.forEach((n) => {
      const level = levels[n.id] || 0;
      if (!byLevel[level]) byLevel[level] = [];
      byLevel[level].push(n);
    });

    const levelKeys = Object.keys(byLevel).map(Number).sort((a, b) => a - b);
    const xGap = 380;
    const yGap = 165;

    levelKeys.forEach((lvl, colIdx) => {
      const column = byLevel[lvl].sort((a, b) => String(a.id).localeCompare(String(b.id)));
      const offset = ((column.length - 1) * yGap) / 2;
      column.forEach((node, rowIdx) => {
        node.x = colIdx * xGap;
        node.y = (rowIdx * yGap) - offset;
        node.fixed = { x: false, y: false };
      });
    });
  }

  function buildNetwork(container, schema) {
    // schema: { tables: [{ name, columns: [] }], relations: [{ from: 'table.col', to: 'table.col' }] }
    lastSchema = schema;
    const nodes = [];
    const edges = [];
    const tableMap = {};
    const primary = themeColor('--bs-primary', '#0d6efd');
    const border = themeColor('--bs-border-color', '#dee2e6');
    const bodyBg = themeColor('--bs-body-bg', '#ffffff');
    const bodyColor = themeColor('--bs-body-color', '#212529');
    const secondary = themeColor('--bs-secondary-color', '#6c757d');
    const secondaryBg = themeColor('--bs-secondary-bg', '#e9ecef');

    schema.tables.forEach((t, idx) => {
      const nid = 't_' + idx;
      tableMap[t.name] = nid;
      tableByNodeId[nid] = t;
      const columns = Array.isArray(t.columns) ? t.columns.map(colName).filter(Boolean) : [];
      nodes.push({
        id: nid,
        label: entityLabel(t),
        shape: 'box',
        title: columns.join('\n'),
        color: {
          background: bodyBg,
          border,
          highlight: { background: bodyBg, border: primary },
          hover: { background: bodyBg, border: primary }
        },
        font: { color: bodyColor, face: 'system-ui, sans-serif', multi: false, size: 13, align: 'left' },
        margin: { top: 10, right: 12, bottom: 10, left: 12 }
      });
    });
    schema.relations.forEach((r, idx) => {
      const [fromTable] = r.from.split('.');
      const [toTable] = r.to.split('.');
      const fromId = tableMap[fromTable];
      const toId = tableMap[toTable];
      if (fromId && toId) {
        edges.push({
          id: `e_${idx}`,
          from: fromId,
          to: toId,
          arrows: {
            to: { enabled: true, scaleFactor: 0.8 },
            from: { enabled: true, scaleFactor: 0.25 }
          },
          title: relationLabel(r),
          font: { align: 'middle', color: secondary, size: 11, strokeWidth: 0 },
          color: { color: border, highlight: primary, hover: primary },
          smooth: false,
          width: 1.15
        });
      }
    });

    applyStaticPositions(nodes, edges);
    currentNodeIds = nodes.map((n) => n.id);
    currentEdgeIds = edges.map((e) => e.id).filter(Boolean);
    currentAdjacency = buildAdjacency(currentNodeIds, edges);

    const data = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) };
    const opts = {
      layout: {
        improvedLayout: false,
        randomSeed: 7,
        hierarchical: false
      },
      interaction: {
        hover: true,
        tooltipDelay: 150,
        navigationButtons: true,
        keyboard: true,
        dragNodes: true,
        dragView: true
      },
      physics: false,
      nodes: {
        widthConstraint: { minimum: 260, maximum: 330 },
        borderWidth: 1.2,
        borderWidthSelected: 2
      },
      edges: { selectionWidth: 2.2 }
    };
    if (network) {
      try { network.destroy(); } catch (e) {}
      network = null;
    }
    network = new vis.Network(container, data, opts);

    function selectEntity(nid) {
      if (!nid) return;
      activeNodeId = nid;
      highlightNode(nid);
      showTableDetails(nid);
    }

    network.on('click', params => {
      const nid = (params.nodes && params.nodes.length)
        ? params.nodes[0]
        : (params.pointer && params.pointer.DOM ? network.getNodeAt(params.pointer.DOM) : null);
      if (nid) {
        selectEntity(nid);
      } else {
        activeNodeId = null;
        resetHighlight();
        clearDetails();
      }
    });

    network.on('selectNode', params => {
      const nid = params && params.nodes && params.nodes.length ? params.nodes[0] : null;
      if (nid) selectEntity(nid);
    });

    network.on('deselectNode', () => {
      activeNodeId = null;
      resetHighlight();
      clearDetails();
    });

    network.on('doubleClick', params => {
      const nid = (params.nodes && params.nodes.length)
        ? params.nodes[0]
        : (params.pointer && params.pointer.DOM ? network.getNodeAt(params.pointer.DOM) : null);
      if (nid) return;
      activeNodeId = null;
      resetHighlight();
      clearDetails();
      network.fit({ animation: false });
    });

    const firstNode = currentNodeIds.length ? currentNodeIds[0] : null;
    if (firstNode) {
      network.selectNodes([firstNode]);
      selectEntity(firstNode);
    } else {
      clearDetails();
    }
  }

  function highlightNode(nid) {
    if (!network) return;
    const allEdges = network.body.data.edges.get();
    const connectedNodes = new Set([nid]);
    const connectedEdges = new Set();
    allEdges.forEach(e => {
      if (e.from === nid || e.to === nid) {
        connectedNodes.add(e.from);
        connectedNodes.add(e.to);
        connectedEdges.add(e.id);
      }
    });

    const depths = collectNeighbors(nid, 2);
    const depth1 = depths[1] || new Set();
    const depth2 = depths[2] || new Set();

    const border = themeColor('--bs-border-color', '#dee2e6');
    const primary = themeColor('--bs-primary', '#0d6efd');
    const bodyBg = themeColor('--bs-body-bg', '#ffffff');
    const secondaryBg = themeColor('--bs-secondary-bg', '#e9ecef');
    const secondary = themeColor('--bs-secondary-color', '#6c757d');

    network.body.data.nodes.update(
      currentNodeIds.map(id => ({
        id,
        opacity: id === nid ? 1 : depth1.has(id) ? 0.94 : depth2.has(id) ? 0.78 : 0.58,
        color: id === nid
          ? { background: bodyBg, border: primary }
          : depth1.has(id)
            ? { background: bodyBg, border }
            : depth2.has(id)
              ? { background: secondaryBg, border }
              : { background: secondaryBg, border }
      }))
    );

    network.body.data.edges.update(
      allEdges.map(e => ({
        id: e.id,
        hidden: false,
        width: connectedEdges.has(e.id) ? 2.4 : 1,
        color: connectedEdges.has(e.id)
          ? { color: primary, highlight: primary, hover: primary, opacity: 0.95 }
          : { color: border, highlight: border, hover: border, opacity: 0.15 },
        font: connectedEdges.has(e.id)
          ? { color: primary, size: 11 }
          : { color: secondary, size: 10 }
      }))
    );
  }
  function resetHighlight(){
    if (!network) return;
    activeNodeId = null;
    network.body.data.nodes.update(currentNodeIds.map(id => ({ id, opacity: 1, color: undefined })));
    if (currentEdgeIds.length) network.body.data.edges.update(currentEdgeIds.map(id => ({ id, width: undefined, color: undefined, font: undefined })));
  }

  async function fetchSchema(sourceId) {
    if (!sourceId) return null;
    try {
      const r = await fetch(`/app/api/sources/${sourceId}/diagram`, { credentials: 'same-origin' });
      if (!r.ok) return null;
      return await r.json();
    } catch (e) {
      console.error('fetchSchema error', e);
      return null;
    }
  }

  function mockSchema(){
    return {
      tables: [
        { name: 'users', columns: ['id', 'name', 'email'] },
        { name: 'orders', columns: ['id', 'user_id', 'amount'] },
        { name: 'order_items', columns: ['id', 'order_id', 'product_id', 'qty'] },
        { name: 'products', columns: ['id', 'name', 'price'] }
      ],
      relations: [
        { from: 'orders.user_id', to: 'users.id' },
        { from: 'order_items.order_id', to: 'orders.id' },
        { from: 'order_items.product_id', to: 'products.id' }
      ]
    };
  }

  function boot(){
    const loadBtn = qs('#sd-load');
    const refreshBtn = qs('#sd-refresh');
    const relayoutBtn = qs('#sd-relayout');
    const sel = qs('#sd-source');
    const container = qs('#diagram');
    if (!container) return;
    clearDetails();

    loadBtn && loadBtn.addEventListener('click', async () => {
      const sid = sel?.value;
      let schema = await fetchSchema(sid);
      if (!schema) schema = mockSchema();
      buildNetwork(container, schema);
    });

    refreshBtn && refreshBtn.addEventListener('click', async () => {
      const sid = sel?.value;
      let schema = await fetchSchema(sid);
      if (!schema) schema = mockSchema();
      buildNetwork(container, schema);
    });

    relayoutBtn && relayoutBtn.addEventListener('click', () => {
      if (lastSchema) {
        buildNetwork(container, lastSchema);
      }
    });

    // auto-load first
    if (sel && sel.options.length > 1) {
      const first = Array.from(sel.options).find((o, i) => i>0 && o.value);
      if (first) { sel.value = first.value; loadBtn && loadBtn.click(); }
    }
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
