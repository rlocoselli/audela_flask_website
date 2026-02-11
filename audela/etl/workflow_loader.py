from __future__ import annotations

from typing import Any, Dict


def normalize_workflow(workflow: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(workflow, dict):
        raise ValueError("workflow must be a dict")

    # Accept either our native workflow format (with workflow['steps'])
    # or a Drawflow export() payload.
    workflow = drawflow_to_workflow(workflow)

    if "steps" not in workflow or not isinstance(workflow["steps"], list):
        raise ValueError("workflow.steps must be a list")

    for i, s in enumerate(workflow["steps"]):
        if not isinstance(s, dict):
            raise ValueError(f"step[{i}] must be dict")
        if "type" not in s:
            raise ValueError(f"step[{i}] missing type")
        s.setdefault("id", str(i + 1))
        s.setdefault("config", {})

    return workflow


def drawflow_to_workflow(drawflow: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Drawflow export() payload into our linear workflow format.

    IMPORTANT: Drawflow node ids are strings in the exported JSON, and connections
    often reference nodes as strings. We keep ids as strings end-to-end.
    """

    if "drawflow" not in drawflow:
        return drawflow

    data = drawflow.get("drawflow", {}).get("Home", {}).get("data", {})
    if not data:
        return {"name": drawflow.get("name", "workflow"), "steps": []}

    # Ensure node ids are strings
    nodes: Dict[str, Any] = {str(k): v for k, v in data.items()}

    # Find start node: prefer extract.* with no inputs
    start_id: str | None = None
    for nid, n in nodes.items():
        ntype = (n.get("name") or n.get("data", {}).get("type") or "").lower()
        if (ntype.startswith("extract") or ntype.endswith("extract")) and not _has_inputs(n):
            start_id = nid
            break

    # Fallback: first node without inputs, else first node
    if start_id is None:
        for nid, n in nodes.items():
            if not _has_inputs(n):
                start_id = nid
                break
        if start_id is None:
            start_id = next(iter(nodes.keys()))

    steps = []
    visited: set[str] = set()
    cur: str | None = start_id

    # Linear MVP: follow the first connection chain output->next
    while cur and cur not in visited and cur in nodes:
        visited.add(cur)
        n = nodes[cur]
        ndata = n.get("data") or {}
        stype = ndata.get("type") or n.get("name") or "unknown"
        config = ndata.get("config") or {}
        steps.append({"id": str(cur), "type": stype, "config": config})

        outputs = n.get("outputs") or {}
        conns = []
        for out in outputs.values():
            conns.extend(out.get("connections") or [])

        next_id: str | None = None
        if conns:
            nxt = conns[0].get("node")
            if nxt is not None:
                next_id = str(nxt)

        cur = next_id

    return {
        "name": drawflow.get("name", "workflow"),
        "steps": steps,
    }


def _has_inputs(node: Dict[str, Any]) -> bool:
    inputs = node.get("inputs") or {}
    for _, v in inputs.items():
        if v.get("connections"):
            return True
    return False
