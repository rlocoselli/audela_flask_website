from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
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
    def run(self, workflow: Dict[str, Any], *, app=None) -> Dict[str, Any]:
        wf = normalize_workflow(workflow)

        ctx = ETLContext(data=None, meta={"workflow": wf})
        results: List[StepResult] = []
        started = time.time()

        for step in wf["steps"]:
            step_id = step.get("id") or step.get("name") or step.get("type")
            sr = StepResult(step_id=step_id)
            t0 = time.time()
            try:
                handler = REGISTRY.get(step["type"])
                if handler is None:
                    raise ValueError(f"Unknown step type: {step['type']}")
                rows_in = _count_rows(ctx.data)
                sr.rows_in = rows_in

                ctx.data = handler(step.get("config") or {}, ctx, app=app)

                sr.rows_out = _count_rows(ctx.data)
            except Exception as e:
                sr.error = str(e)
                sr.duration_ms = int((time.time() - t0) * 1000)
                results.append(sr)
                break
            sr.duration_ms = int((time.time() - t0) * 1000)
            results.append(sr)

        ended = time.time()
        ok = all(r.error is None for r in results) and len(results) == len(wf["steps"])
        return {
            "ok": ok,
            "workflow": wf.get("name"),
            "duration_ms": int((ended - started) * 1000),
            "steps": [r.__dict__ for r in results],
        }

    def preview(self, workflow: Dict[str, Any], *, app=None, limit: int = 20) -> Dict[str, Any]:
        """Run the workflow step-by-step and return small samples after each step.
        limit: max rows returned per step (only for list-of-dict data).
        """
        wf = normalize_workflow(workflow)
        ctx = ETLContext(data=None, meta={"workflow": wf})
        previews: List[Dict[str, Any]] = []
        started = time.time()

        for step in wf["steps"]:
            step_id = step.get("id") or step.get("name") or step.get("type")
            t0 = time.time()
            try:
                handler = REGISTRY.get(step["type"])
                if handler is None:
                    raise ValueError(f"Unknown step type: {step['type']}")
                ctx.data = handler(step.get("config") or {}, ctx, app=app)
                sample = None
                if isinstance(ctx.data, list):
                    sample = ctx.data[: max(0, limit)]
                previews.append({
                    "step_id": step_id,
                    "type": step.get("type"),
                    "rows_out": _count_rows(ctx.data),
                    "duration_ms": int((time.time() - t0) * 1000),
                    "sample": sample,
                })
            except Exception as e:
                previews.append({
                    "step_id": step_id,
                    "type": step.get("type"),
                    "error": str(e),
                    "duration_ms": int((time.time() - t0) * 1000),
                })
                break

        ended = time.time()
        return {
            "ok": all("error" not in p for p in previews) and len(previews) == len(wf["steps"]),
            "workflow": wf.get("name"),
            "duration_ms": int((ended - started) * 1000),
            "previews": previews,
        }


def _count_rows(data: Any) -> Optional[int]:
    if data is None:
        return None
    if isinstance(data, list):
        return len(data)
    return None