from __future__ import annotations

from typing import Any, Callable, Dict

# Step handler signature: (config, ctx, app=None) -> new_data
REGISTRY: Dict[str, Callable[..., Any]] = {}

def register(step_type: str):
    def deco(fn: Callable[..., Any]):
        REGISTRY[step_type] = fn
        return fn
    return deco