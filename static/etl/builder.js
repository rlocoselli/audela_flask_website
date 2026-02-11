import React, { useCallback, useEffect, useMemo, useRef, useState } from "https://esm.sh/react@18";
import ReactDOM from "https://esm.sh/react-dom@18/client";
import ReactFlow, {
  addEdge,
  Background,
  Controls,
  MiniMap,
  useEdgesState,
  useNodesState,
} from "https://esm.sh/reactflow@11";

const STEP_TEMPLATES = {
  "extract.http": {
    type: "extract.http",
    config: { url: "", method: "GET", headers: {}, params: {}, timeout: 30 }
  },
  "extract.sql": {
    type: "extract.sql",
    config: { query: "SELECT 1 as hello" }
  },
  "transform.mapping": {
    type: "transform.mapping",
    config: { fields: { /* out_col: \"$.path\" */ } }
  },
  "load.warehouse": {
    type: "load.warehouse",
    config: { table: "dwh_table", schema: "public", mode: "append", create_table_if_missing: true, add_columns_if_missing: true }
  }
};

function mkNode(stepType, x, y) {
  const t = STEP_TEMPLATES[stepType];
  const id = crypto.randomUUID();
  return {
    id,
    position: { x, y },
    data: {
      label: stepType,
      stepType: t.type,
      config: structuredClone(t.config),
    },
    style: { padding: 10, borderRadius: 12, border: "1px solid #bbb", background: "white" }
  };
}

function App() {
  const [workflowName, setWorkflowName] = useState("my_workflow");
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [configText, setConfigText] = useState("");
  const [status, setStatus] = useState("");

  const selectedNode = useMemo(() => nodes.find(n => n.id === selectedNodeId) || null, [nodes, selectedNodeId]);

  useEffect(() => {
    if (selectedNode) {
      setConfigText(JSON.stringify(selectedNode.data.config ?? {}, null, 2));
    } else {
      setConfigText("");
    }
  }, [selectedNodeId]);

  const onConnect = useCallback((params) => setEdges((eds) => addEdge({ ...params, animated: true }, eds)), []);

  const addStep = (stepType) => {
    const x = 80 + nodes.length * 40;
    const y = 80 + nodes.length * 20;
    setNodes((nds) => nds.concat(mkNode(stepType, x, y)));
  };

  const updateSelectedConfig = () => {
    if (!selectedNode) return;
    try {
      const parsed = JSON.parse(configText || "{}");
      setNodes((nds) => nds.map(n => n.id === selectedNode.id ? ({ ...n, data: { ...n.data, config: parsed } }) : n));
      setStatus("✅ Config updated.");
    } catch (e) {
      setStatus("❌ Invalid JSON: " + e.message);
    }
  };

  const buildWorkflow = () => {
    if (nodes.length === 0) throw new Error("No nodes.");

    // Build adjacency
    const incoming = new Map(nodes.map(n => [n.id, 0]));
    const out = new Map(nodes.map(n => [n.id, []]));
    for (const e of edges) {
      if (incoming.has(e.target)) incoming.set(e.target, incoming.get(e.target) + 1);
      if (out.has(e.source)) out.get(e.source).push(e.target);
    }

    const starts = nodes.filter(n => incoming.get(n.id) === 0);
    if (starts.length !== 1) {
      throw new Error("This MVP expects exactly 1 start node (node with no incoming edges).");
    }

    const steps = [];
    let cur = starts[0];
    const visited = new Set();

    while (cur) {
      if (visited.has(cur.id)) throw new Error("Cycle detected.");
      visited.add(cur.id);

      steps.push({
        id: cur.id,
        type: cur.data.stepType,
        config: cur.data.config ?? {}
      });

      const nexts = out.get(cur.id) || [];
      if (nexts.length === 0) break;
      if (nexts.length > 1) throw new Error("Branching not supported in this MVP (one outgoing edge only).");
      const nextId = nexts[0];
      cur = nodes.find(n => n.id === nextId) || null;
    }

    if (steps.length !== nodes.length) {
      throw new Error("Disconnected graph: some nodes are not in the main chain.");
    }

    return { name: workflowName, steps };
  };

  const saveWorkflow = async () => {
    try {
      const wf = buildWorkflow();
      const res = await fetch("/etl/api/workflows", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(wf)
      });
      const j = await res.json();
      setStatus("✅ Saved: " + JSON.stringify(j, null, 2));
    } catch (e) {
      setStatus("❌ " + e.message);
    }
  };

  const runWorkflow = async () => {
    try {
      const wf = buildWorkflow();
      const res = await fetch("/etl/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(wf)
      });
      const j = await res.json();
      setStatus((j.ok ? "✅ Run OK\n" : "❌ Run failed\n") + JSON.stringify(j, null, 2));
    } catch (e) {
      setStatus("❌ " + e.message);
    }
  };

  return (
    React.createElement("div", { className: "layout" },
      React.createElement("div", { className: "sidebar" },
        React.createElement("div", { className: "row" },
          React.createElement("span", { className: "pill" }, "Extract"),
          React.createElement("span", { className: "pill" }, "Transform"),
          React.createElement("span", { className: "pill" }, "Load"),
        ),
        React.createElement("label", null, "Workflow name"),
        React.createElement("input", { value: workflowName, onChange: (e) => setWorkflowName(e.target.value) }),
        React.createElement("div", { className: "row" },
          React.createElement("button", { onClick: () => addStep("extract.http") }, "+ HTTP Extract"),
          React.createElement("button", { onClick: () => addStep("extract.sql") }, "+ SQL Extract"),
          React.createElement("button", { onClick: () => addStep("transform.mapping") }, "+ Mapping"),
          React.createElement("button", { onClick: () => addStep("load.warehouse") }, "+ Load DWH"),
        ),
        React.createElement("div", { className: "hint" },
          "Connect nodes left→right (single chain). Select a node to edit its config (JSON). ",
          "On Load, tables will be created if missing and columns inferred from data."
        ),
        React.createElement("hr", null),

        selectedNode
          ? React.createElement(React.Fragment, null,
              React.createElement("div", null, React.createElement("strong", null, "Selected node: "), selectedNode.data.stepType),
              React.createElement("textarea", { value: configText, onChange: (e) => setConfigText(e.target.value) }),
              React.createElement("div", { className: "row" },
                React.createElement("button", { onClick: updateSelectedConfig }, "Apply config"),
              ),
            )
          : React.createElement("div", { className: "hint" }, "Select a node to edit its config."),

        React.createElement("hr", null),
        React.createElement("div", { className: "row" },
          React.createElement("button", { onClick: saveWorkflow }, "Save (JSON+YAML)"),
          React.createElement("button", { onClick: runWorkflow }, "Run now"),
        ),
        React.createElement("div", { className: "status" }, status || "Ready.")
      ),

      React.createElement("div", { className: "canvas" },
        React.createElement(ReactFlow, {
          nodes, edges,
          onNodesChange, onEdgesChange,
          onConnect,
          onNodeClick: (_, node) => setSelectedNodeId(node.id),
          fitView: true,
        },
          React.createElement(Background, null),
          React.createElement(MiniMap, null),
          React.createElement(Controls, null),
        )
      )
    )
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(React.createElement(App));