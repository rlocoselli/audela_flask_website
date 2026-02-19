from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time

from .registry import REGISTRY
from .workflow_loader import normalize_workflow


@dataclass
class StepResult:
    step_id: str
    rows_in: Optional[int] = None
    rows_out: Optional[int] = None
    duration_ms: int = 0
    error: Optional[str] = None


@dataclass
class ETLContext:
    data: Any = None
    meta: Dict[str, Any] = field(default_factory=dict)


class ETLEngine:
    def run(self, workflow: Dict[str, Any], *, app=None, progress_cb=None) -> Dict[str, Any]:
        wf = normalize_workflow(workflow)

        ctx = ETLContext(data=None, meta={"workflow": wf})
        results: List[StepResult] = []
        started = time.time()

        step_map = {str(s.get("id")): s for s in (wf.get("steps") or []) if isinstance(s, dict)}
        transitions = wf.get("transitions") if isinstance(wf.get("transitions"), dict) else {}
        use_graph = bool(transitions) and bool(wf.get("start_id"))

        linear_ids = [str(s.get("id")) for s in (wf.get("steps") or []) if isinstance(s, dict)]
        linear_idx = 0
        cur_id = str(wf.get("start_id")) if use_graph else None
        hops = 0
        max_hops = max(1, len(step_map) * 20)

        while True:
            if use_graph:
                if not cur_id:
                    break
                sid = str(cur_id)
            else:
                if linear_idx >= len(linear_ids):
                    break
                sid = str(linear_ids[linear_idx])
                linear_idx += 1

            hops += 1
            if hops > max_hops:
                results.append(StepResult(step_id=str(sid), error="Workflow exceeded max hops (possible cycle)"))
                break

            step = step_map.get(str(sid))
            if not step:
                if use_graph:
                    break
                continue
            if progress_cb:
                progress_cb({"event": "step_start", "step": step})

            step_id = step.get("id") or step.get("name") or step.get("type")
            sr = StepResult(step_id=str(step_id))
            t0 = time.time()

            try:
                handler = REGISTRY.get(step["type"])
                if handler is None:
                    raise ValueError(f"Unknown step type: {step['type']}")

                # expose current step id to handlers (for branching route decisions)
                ctx.meta["_current_step_id"] = str(step_id)

                sr.rows_in = _count_rows(ctx.data)
                ctx.data = handler(step.get("config") or {}, ctx, app=app)

                sr.rows_out = _count_rows(ctx.data)

                if progress_cb:
                    progress_cb({
                        "event": "step_end",
                        "step": step,
                        "rows_out": sr.rows_out,
                    })

                if ctx.meta.get("_stop_workflow"):
                    sr.duration_ms = int((time.time() - t0) * 1000)
                    results.append(sr)
                    break

                if use_graph:
                    route_by_step = ctx.meta.get("_step_route") if isinstance(ctx.meta.get("_step_route"), dict) else {}
                    chosen_output = str(route_by_step.get(str(sid)) or "output_1")
                    trans = transitions.get(str(sid)) if isinstance(transitions.get(str(sid)), dict) else {}
                    nxt = trans.get(chosen_output) or trans.get("output_1")
                    cur_id = str(nxt) if nxt else None

            except Exception as e:
                sr.error = str(e)
                sr.duration_ms = int((time.time() - t0) * 1000)
                results.append(sr)
                break

            sr.duration_ms = int((time.time() - t0) * 1000)
            results.append(sr)

        ended = time.time()
        stopped = bool(ctx.meta.get("_stop_workflow"))
        has_error = any(r.error is not None for r in results)
        ok = (not has_error) if use_graph else ((not has_error) and (stopped or len(results) == len(wf["steps"])))
        return {
            "ok": ok,
            "workflow": wf.get("name"),
            "duration_ms": int((ended - started) * 1000),
            "stopped": stopped,
            "stop_reason": ctx.meta.get("_stop_reason"),
            "meta": {
                "last_scalar": ctx.meta.get("last_scalar"),
                "scalars": ctx.meta.get("scalars") if isinstance(ctx.meta.get("scalars"), dict) else {},
                "last_decision": ctx.meta.get("last_decision"),
            },
            "steps": [r.__dict__ for r in results],
        }

    def preview(self, workflow: Dict[str, Any], *, app=None, limit: int = 20, progress_cb=None) -> Dict[str, Any]:
        """Run the workflow step-by-step and return small samples after each step.

        limit: max rows returned per step (only for list-of-dict data).
        """
        wf = normalize_workflow(workflow)
        ctx = ETLContext(data=None, meta={"workflow": wf})
        previews: List[Dict[str, Any]] = []
        started = time.time()

        step_map = {str(s.get("id")): s for s in (wf.get("steps") or []) if isinstance(s, dict)}
        transitions = wf.get("transitions") if isinstance(wf.get("transitions"), dict) else {}
        use_graph = bool(transitions) and bool(wf.get("start_id"))

        linear_ids = [str(s.get("id")) for s in (wf.get("steps") or []) if isinstance(s, dict)]
        linear_idx = 0
        cur_id = str(wf.get("start_id")) if use_graph else None
        hops = 0
        max_hops = max(1, len(step_map) * 20)

        while True:
            if use_graph:
                if not cur_id:
                    break
                sid = str(cur_id)
            else:
                if linear_idx >= len(linear_ids):
                    break
                sid = str(linear_ids[linear_idx])
                linear_idx += 1

            hops += 1
            if hops > max_hops:
                previews.append({
                    "step_id": str(sid),
                    "error": "Workflow exceeded max hops (possible cycle)",
                    "duration_ms": 0,
                })
                break

            step = step_map.get(str(sid))
            if not step:
                if use_graph:
                    break
                continue
            if progress_cb:
                progress_cb({"event": "step_start", "step": step})

            step_id = step.get("id") or step.get("name") or step.get("type")
            t0 = time.time()

            try:
                handler = REGISTRY.get(step["type"])
                if handler is None:
                    raise ValueError(f"Unknown step type: {step['type']}")

                ctx.meta["_current_step_id"] = str(step_id)

                ctx.data = handler(step.get("config") or {}, ctx, app=app)
                rows_out = _count_rows(ctx.data)

                if progress_cb:
                    progress_cb({
                        "event": "step_end",
                        "step": step,
                        "rows_out": rows_out,
                    })

                sample = None
                if isinstance(ctx.data, list):
                    sample = ctx.data[: max(0, limit)]

                previews.append({
                    "step_id": str(step_id),
                    "type": step.get("type"),
                    "rows_out": rows_out,
                    "duration_ms": int((time.time() - t0) * 1000),
                    "sample": sample,
                })

                if ctx.meta.get("_stop_workflow"):
                    break

                if use_graph:
                    route_by_step = ctx.meta.get("_step_route") if isinstance(ctx.meta.get("_step_route"), dict) else {}
                    chosen_output = str(route_by_step.get(str(sid)) or "output_1")
                    trans = transitions.get(str(sid)) if isinstance(transitions.get(str(sid)), dict) else {}
                    nxt = trans.get(chosen_output) or trans.get("output_1")
                    cur_id = str(nxt) if nxt else None

            except Exception as e:
                previews.append({
                    "step_id": str(step_id),
                    "type": step.get("type"),
                    "error": str(e),
                    "duration_ms": int((time.time() - t0) * 1000),
                })
                break

        ended = time.time()
        stopped = bool(ctx.meta.get("_stop_workflow"))
        has_error = any("error" in p for p in previews)
        return {
            "ok": (not has_error) if use_graph else ((not has_error) and (stopped or len(previews) == len(wf["steps"]))),
            "workflow": wf.get("name"),
            "duration_ms": int((ended - started) * 1000),
            "stopped": stopped,
            "stop_reason": ctx.meta.get("_stop_reason"),
            "meta": {
                "last_scalar": ctx.meta.get("last_scalar"),
                "scalars": ctx.meta.get("scalars") if isinstance(ctx.meta.get("scalars"), dict) else {},
                "last_decision": ctx.meta.get("last_decision"),
            },
            "previews": previews,
        }


def _count_rows(data: Any) -> Optional[int]:
    if data is None:
        return None
    if isinstance(data, list):
        return len(data)
    return None
