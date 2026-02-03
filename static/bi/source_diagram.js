(function(){
  function qs(s){ return document.querySelector(s); }
  function qsa(s){ return Array.from(document.querySelectorAll(s)); }

  let network = null;

  function buildNetwork(container, schema) {
    // schema: { tables: [{ name, columns: [] }], relations: [{ from: 'table.col', to: 'table.col' }] }
    const nodes = [];
    const edges = [];
    const tableMap = {};
    schema.tables.forEach((t, idx) => {
      const nid = 't_' + idx;
      tableMap[t.name] = nid;
      nodes.push({ id: nid, label: t.name, shape: 'box', title: t.columns ? t.columns.join('\n') : '' });
    });
    schema.relations.forEach((r) => {
      const [fromTable] = r.from.split('.');
      const [toTable] = r.to.split('.');
      const fromId = tableMap[fromTable];
      const toId = tableMap[toTable];
      if (fromId && toId) edges.push({ from: fromId, to: toId, arrows: 'to' });
    });

    const data = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) };
    const opts = {
      layout: { hierarchical: false },
      physics: { stabilization: true, barnesHut: { gravitationalConstant: -2000 } },
      nodes: { margin: 10, widthConstraint: { maximum: 220 } }
    };
    if (network) {
      try { network.destroy(); } catch (e) {}
      network = null;
    }
    network = new vis.Network(container, data, opts);

    network.on('click', params => {
      if (params.nodes && params.nodes.length) {
        const nid = params.nodes[0];
        highlightNode(nid);
      } else {
        resetHighlight();
      }
    });
  }

  function highlightNode(nid) {
    if (!network) return;
    const allNodes = network.body.data.nodes.get();
    const allEdges = network.body.data.edges.get();
    const toKeep = new Set();
    allEdges.forEach(e => {
      if (e.from === nid || e.to === nid) { toKeep.add(e.from); toKeep.add(e.to); }
    });
    network.body.data.nodes.update(allNodes.map(n => ({ id: n.id, color: toKeep.has(n.id) ? undefined : { background: '#f1f3f5' } }))); 
  }
  function resetHighlight(){ if (!network) return; const allNodes = network.body.data.nodes.get(); network.body.data.nodes.update(allNodes.map(n => ({ id: n.id, color: undefined }))); }

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
    const sel = qs('#sd-source');
    const container = qs('#diagram');
    if (!container) return;

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

    // auto-load first
    if (sel && sel.options.length > 1) {
      const first = Array.from(sel.options).find((o, i) => i>0 && o.value);
      if (first) { sel.value = first.value; loadBtn && loadBtn.click(); }
    }
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
