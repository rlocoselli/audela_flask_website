from __future__ import annotations

from typing import Any, Dict
import json

def normalize_workflow(workflow: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(workflow, dict):
        raise ValueError("workflow must be a dict")
    workflow = drawflow_to_workflow(workflow)
    if "steps" not in workflow or not isinstance(workflow["steps"], list):
        raise ValueError("workflow.steps must be a list")
    if "name" not in workflow:
        workflow["name"] = "unnamed_workflow"
    # Ensure each step has type/config
    for i, s in enumerate(workflow["steps"]):
        if "type" not in s:
            raise ValueError(f"step[{i}] missing type")
        s.setdefault("id", f"step_{i+1}")
        s.setdefault("config", {})
    return workflow

def workflow_to_json(workflow: Dict[str, Any]) -> str:
    return json.dumps(workflow, ensure_ascii=False, indent=2)

def drawflow_to_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Drawflow export() JSON into our linear workflow format.
    MVP: follows the first available connection from each node (linear chain).
    Node 'name' (or data.type) is used as step type.
    Node config can be stored under node.data.config (optional).
    """
    if not isinstance(payload, dict):
        return payload
    home = payload.get("drawflow", {}).get("Home", {})
    data = home.get("data") if isinstance(home, dict) else None
    if not isinstance(data, dict) or not data:
        return payload  # already in workflow format or empty

    # Drawflow keys are strings
    nodes = {}
    for k, v in data.items():
        try:
            nodes[int(k)] = v
        except Exception:
            continue

    def _has_inputs(node: Dict[str, Any]) -> bool:
        inputs = node.get("inputs") or {}
        for inp in inputs.values():
            if (inp or {}).get("connections"):
                return True
        return False

    start_id = None
    for nid, node in nodes.items():
        if not _has_inputs(node):
            start_id = nid
            break
    if start_id is None:
        start_id = next(iter(nodes.keys()))

    steps = []
    visited = set()
    cur = start_id
    while cur is not None and cur not in visited and cur in nodes:
        visited.add(cur)
        node = nodes[cur]
        step_type = node.get("name") or (node.get("data") or {}).get("type") or "unknown"
        cfg = (node.get("data") or {}).get("config") or {}
        steps.append({"id": str(cur), "type": step_type, "config": cfg})

        next_id = None
        outputs = node.get("outputs") or {}
        for out in outputs.values():
            conns = (out or {}).get("connections") or []
            if conns:
                next_id = conns[0].get("node")
                break
        cur = next_id

    name = payload.get("name") or "drawflow_workflow"
    return {"name": name, "steps": steps}
