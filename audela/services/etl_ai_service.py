from __future__ import annotations

import json
import re
from collections import deque
from typing import Any

import requests

from .ai_runtime_config import resolve_ai_runtime_config
from audela.etl.workflow_loader import normalize_workflow


ALLOWED_ETL_STEP_TYPES = {
    "extract.http",
    "extract.web",
    "extract.sql",
    "transform.mapping",
    "transform.cleaning_rules",
    "transform.python_advanced",
    "transform.decision.scalar",
    "load.staging_table",
    "load.warehouse",
    "notify.integration",
}


def _node_html(step_type: str) -> str:
    if step_type == "transform.decision.scalar":
        return (
            "<div>"
            "<strong>transform.decision.scalar</strong>"
            '<div style="font-size:11px;color:#666">Double-click to configure</div>'
            '<div style="font-size:10px;color:#1f2937;margin-top:4px;display:flex;justify-content:space-between;gap:8px;">'
            "<span><b>↑ output_1</b> = TRUE</span>"
            "<span><b>↓ output_2</b> = FALSE</span>"
            "</div></div>"
        )
    return (
        "<div>"
        f"<strong>{step_type}</strong>"
        '<div style="font-size:11px;color:#666">Double-click to configure</div>'
        "</div>"
    )


def compact_schema_meta(meta: dict[str, Any] | None, max_tables: int = 12, max_columns: int = 20) -> dict[str, Any]:
    meta = meta if isinstance(meta, dict) else {}
    out: dict[str, Any] = {"schemas": []}
    for schema in (meta.get("schemas") or [])[:3]:
        tables_out = []
        for table in (schema.get("tables") or [])[:max_tables]:
            cols_out = []
            for column in (table.get("columns") or [])[:max_columns]:
                if isinstance(column, dict):
                    cols_out.append({"name": column.get("name"), "type": str(column.get("type") or "")})
                else:
                    cols_out.append({"name": str(column), "type": ""})
            tables_out.append(
                {
                    "name": table.get("name"),
                    "kind": table.get("kind") or "table",
                    "columns": cols_out,
                }
            )
        out["schemas"].append({"name": schema.get("name") or "default", "tables": tables_out})
    return out


def _slugify_identifier(value: str, default: str = "dataset") -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or default


def _guess_table_name(prompt: str, workflow_name: str) -> str:
    prompt_text = str(prompt or "")
    patterns = [
        r"\btable\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        r"\binto\s+([a-zA-Z_][a-zA-Z0-9_]*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt_text, flags=re.IGNORECASE)
        if match:
            return _slugify_identifier(match.group(1), default="dataset")
    return _slugify_identifier(workflow_name or prompt_text, default="dataset")


def _selected_sources(source_context: dict[str, Any], source_key: str, selected_key: str) -> list[dict[str, Any]]:
    sources = source_context.get(source_key) if isinstance(source_context.get(source_key), list) else []
    rules = source_context.get("rules") if isinstance(source_context.get("rules"), dict) else {}
    selected_ids = {str(v) for v in (rules.get(selected_key) or [])}
    if selected_ids:
        selected = [src for src in sources if str(src.get("id")) in selected_ids]
        if selected:
            return selected
    return list(sources)


def _first_schema_table(source: dict[str, Any] | None) -> tuple[str, list[str]]:
    schema_meta = source.get("schema") if isinstance(source, dict) else {}
    schemas = schema_meta.get("schemas") if isinstance(schema_meta, dict) else []
    for schema in schemas or []:
        schema_name = str(schema.get("name") or "public")
        for table in (schema.get("tables") or []):
            table_name = str(table.get("name") or "").strip()
            if not table_name:
                continue
            full_name = f"{schema_name}.{table_name}" if schema_name else table_name
            columns = [str(col.get("name") or "").strip() for col in (table.get("columns") or []) if str(col.get("name") or "").strip()]
            return full_name, columns
    return "", []


def _starter_mapping_fields(prompt: str, schema_columns: list[str]) -> dict[str, str]:
    if schema_columns:
        return {column: column for column in schema_columns[:8]}

    text = str(prompt or "").lower()
    if "weather" in text:
        fields = ["city", "temperature", "humidity", "description", "observed_at"]
    elif "order" in text or "commande" in text:
        fields = ["order_id", "customer_id", "amount", "status", "created_at"]
    elif "invoice" in text or "facture" in text:
        fields = ["invoice_id", "customer_id", "amount", "currency", "issued_at"]
    else:
        fields = ["id", "name", "value"]
    return {field: f"$.{field}" for field in fields}


def _hydrate_generated_workflow(workflow: dict[str, Any], source_context: dict[str, Any], prompt: str) -> dict[str, Any]:
    db_sources = _selected_sources(source_context, "db_sources", "selected_db_source_ids")
    api_sources = _selected_sources(source_context, "api_sources", "selected_api_source_ids")
    primary_db = db_sources[0] if db_sources else None
    primary_api = api_sources[0] if api_sources else None
    first_table_name, first_table_columns = _first_schema_table(primary_db)
    workflow_name = str(workflow.get("name") or "ai_generated_workflow")
    guessed_table_name = _guess_table_name(prompt, workflow_name)

    steps = workflow.get("steps") if isinstance(workflow.get("steps"), list) else []
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_type = str(step.get("type") or "")
        config = step.get("config") if isinstance(step.get("config"), dict) else {}
        step["config"] = config

        if step_type == "extract.http":
            if primary_api and not config.get("api_source_id"):
                config["api_source_id"] = primary_api.get("id")
            if primary_api and not config.get("method"):
                config["method"] = primary_api.get("method") or "GET"
            config.setdefault("headers", {})
            config.setdefault("params", {})
            config.setdefault("timeout", 30)

        elif step_type == "extract.sql":
            if primary_db and not config.get("db_source_id"):
                config["db_source_id"] = primary_db.get("id")
            if not config.get("query") and first_table_name:
                selected_cols = ", ".join(first_table_columns[:8]) if first_table_columns else "*"
                config["query"] = f"SELECT {selected_cols} FROM {first_table_name} LIMIT 100"
            config.setdefault("result_mode", "rows")
            config.setdefault("strict_scalar", True)
            config.setdefault("scalar_key", "last_scalar")

        elif step_type == "transform.mapping":
            if not isinstance(config.get("fields"), dict) or not config.get("fields"):
                config["fields"] = _starter_mapping_fields(prompt, first_table_columns)

        elif step_type == "load.warehouse":
            if primary_db and not config.get("warehouse_source_id"):
                config["warehouse_source_id"] = primary_db.get("id")
            config.setdefault("schema", "public")
            config.setdefault("table", guessed_table_name)
            config.setdefault("mode", "append")
            config.setdefault("create_table_if_missing", True)
            config.setdefault("add_columns_if_missing", True)

        elif step_type == "load.staging_table":
            if primary_db and not config.get("warehouse_source_id"):
                config["warehouse_source_id"] = primary_db.get("id")
            config.setdefault("schema", "staging")
            config.setdefault("table", guessed_table_name)
            config.setdefault("table_prefix", "stg_")
            config.setdefault("table_key", "staging")
            config.setdefault("mode", "append")
            config.setdefault("run_suffix", True)
            config.setdefault("create_table_if_missing", True)
            config.setdefault("add_columns_if_missing", True)

        elif step_type == "extract.web":
            if not config.get("schema") and first_table_columns:
                config["schema"] = ", ".join(first_table_columns[:8])
            config.setdefault("max_rows", 200)
            config.setdefault("verify_ssl", True)
            config.setdefault("visual_actions", [])

    return workflow


def workflow_to_drawflow(workflow: dict[str, Any]) -> dict[str, Any]:
    wf = normalize_workflow(workflow)
    steps = wf.get("steps") or []
    steps_by_id = {str(step.get("id")): step for step in steps}
    transitions = wf.get("transitions") if isinstance(wf.get("transitions"), dict) else {}
    start_id = str(wf.get("start_id") or steps[0]["id"])

    level_map: dict[str, int] = {start_id: 0}
    lane_map: dict[str, int] = {start_id: 0}
    queue: deque[str] = deque([start_id])
    seen: set[str] = set()
    next_free_lane = 1

    while queue:
        cur = queue.popleft()
        if cur in seen:
            continue
        seen.add(cur)
        cur_level = level_map.get(cur, 0)
        cur_lane = lane_map.get(cur, 0)
        out_map = transitions.get(cur) if isinstance(transitions.get(cur), dict) else {}
        ordered_edges = sorted(out_map.items(), key=lambda item: item[0])
        for edge_name, next_id in ordered_edges:
            next_id = str(next_id)
            if next_id not in steps_by_id:
                continue
            level_map.setdefault(next_id, cur_level + 1)
            if next_id not in lane_map:
                if edge_name == "output_2":
                    lane_map[next_id] = next_free_lane
                    next_free_lane += 1
                else:
                    lane_map[next_id] = cur_lane
            queue.append(next_id)

    data: dict[str, Any] = {}
    for idx, step in enumerate(steps, start=1):
        step_id = str(step.get("id"))
        step_type = str(step.get("type") or "")
        outputs_count = 2 if step_type == "transform.decision.scalar" else 1
        inputs = {"input_1": {"connections": []}}
        outputs = {f"output_{n}": {"connections": []} for n in range(1, outputs_count + 1)}
        data[step_id] = {
            "id": int(step_id) if step_id.isdigit() else idx,
            "name": step_type,
            "data": {"type": step_type, "config": step.get("config") or {}},
            "class": step_type,
            "html": _node_html(step_type),
            "typenode": False,
            "inputs": inputs,
            "outputs": outputs,
            "pos_x": 100 + 340 * level_map.get(step_id, 0),
            "pos_y": 100 + 180 * lane_map.get(step_id, 0),
        }

    for src_id, out_map in transitions.items():
        if str(src_id) not in data or not isinstance(out_map, dict):
            continue
        for output_name, dst_id in out_map.items():
            src_key = str(src_id)
            dst_key = str(dst_id)
            if dst_key not in data:
                continue
            output_name = str(output_name or "output_1")
            data[src_key]["outputs"].setdefault(output_name, {"connections": []})
            data[src_key]["outputs"][output_name]["connections"].append(
                {"node": data[dst_key]["id"], "output": "input_1"}
            )
            data[dst_key]["inputs"]["input_1"]["connections"].append(
                {"node": data[src_key]["id"], "input": output_name}
            )

    return {"name": str(wf.get("name") or "workflow"), "drawflow": {"Home": {"data": data}}}


def _sanitize_generated_workflow(obj: dict[str, Any]) -> dict[str, Any]:
    workflow = obj.get("workflow") if isinstance(obj.get("workflow"), dict) else obj
    steps_raw = workflow.get("steps") if isinstance(workflow.get("steps"), list) else []
    if not steps_raw:
        raise RuntimeError("AI returned no workflow steps")

    steps: list[dict[str, Any]] = []
    raw_to_normalized_id: dict[str, str] = {}
    for idx, raw in enumerate(steps_raw, start=1):
        if not isinstance(raw, dict):
            continue
        step_type = str(raw.get("type") or "").strip()
        if step_type not in ALLOWED_ETL_STEP_TYPES:
            raise RuntimeError(f"Unsupported ETL step type returned by AI: {step_type}")
        normalized_id = str(idx)
        raw_to_normalized_id[str(raw.get("id") or idx)] = normalized_id
        steps.append(
            {
                "id": normalized_id,
                "type": step_type,
                "config": raw.get("config") if isinstance(raw.get("config"), dict) else {},
            }
        )
    if not steps:
        raise RuntimeError("AI returned no supported ETL steps")

    valid_ids = {str(step["id"]) for step in steps}
    transitions_raw = workflow.get("transitions") if isinstance(workflow.get("transitions"), dict) else {}
    transitions: dict[str, dict[str, str]] = {}
    for src_id, out_map in transitions_raw.items():
        src_id = raw_to_normalized_id.get(str(src_id), str(src_id))
        if src_id not in valid_ids or not isinstance(out_map, dict):
            continue
        cleaned: dict[str, str] = {}
        for output_name, dst_id in out_map.items():
            output_name = str(output_name or "output_1")
            dst_id = raw_to_normalized_id.get(str(dst_id), str(dst_id))
            if dst_id in valid_ids:
                cleaned[output_name] = dst_id
        if cleaned:
            transitions[src_id] = cleaned

    if not transitions and len(steps) > 1:
        for i in range(len(steps) - 1):
            transitions[str(steps[i]["id"])] = {"output_1": str(steps[i + 1]["id"])}

    start_id = raw_to_normalized_id.get(str(workflow.get("start_id") or steps[0]["id"]), str(steps[0]["id"]))
    if start_id not in valid_ids:
        start_id = str(steps[0]["id"])

    normalized = {
        "name": str(workflow.get("name") or obj.get("name") or "ai_generated_workflow").strip() or "ai_generated_workflow",
        "start_id": start_id,
        "steps": steps,
        "transitions": transitions,
    }
    return normalize_workflow(normalized)


def generate_etl_workflow_from_prompt(
    prompt: str,
    source_context: dict[str, Any],
    *,
    lang: str | None = None,
) -> dict[str, Any]:
    runtime = resolve_ai_runtime_config(default_model="gpt-4o-mini")
    api_key = runtime.get("api_key")
    if not api_key:
        raise RuntimeError(f"{runtime.get('missing_key_env') or 'OPENAI_API_KEY'} missing")

    model = runtime.get("model") or "gpt-4o-mini"
    base_url = runtime.get("base_url") or "https://api.openai.com/v1"
    timeout_seconds = int(runtime.get("read_timeout_seconds") or runtime.get("timeout_seconds") or 90)

    user_prompt = str(prompt or "").strip()
    if not user_prompt:
        raise RuntimeError("Prompt is required")

    system_prompt = (
        "You are an ETL workflow designer for a visual builder. "
        "Return ONLY JSON with keys: name, summary, warnings, workflow. "
        "workflow must be an object with keys: start_id, steps, transitions. "
        "Allowed step types are exactly: extract.http, extract.web, extract.sql, transform.mapping, "
        "transform.cleaning_rules, transform.python_advanced, transform.decision.scalar, "
        "load.staging_table, load.warehouse, notify.integration. "
        "Use only source ids provided in context. "
        "If DB schema is provided, SQL must use only listed tables/columns. "
        "Prefer 2 to 5 steps. At most one decision node. "
        "Each step needs id, type, config. transitions must map step ids to outputs like output_1 or output_2. "
        "Use these exact config keys when relevant: extract.http -> api_source_id, path, method, headers, params, timeout; "
        "extract.sql -> db_source_id, query, result_mode, scalar_key, strict_scalar; "
        "transform.mapping -> fields; load.staging_table -> warehouse_source_id, schema, table, table_prefix, mode, table_key; "
        "load.warehouse -> warehouse_source_id, schema, table, mode; notify.integration -> integration, to, subject, message. "
        "When sources are selected, fill the corresponding source id fields in config. "
        "When transform.mapping is used, provide starter fields instead of leaving fields empty. "
        "Use practical default configs that can run after small user edits. No markdown."
    )

    payload = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Language: "
                    + str(lang or "en")
                    + "\n\nSOURCE CONTEXT (JSON):\n"
                    + json.dumps(source_context, ensure_ascii=False)
                    + "\n\nUSER REQUEST:\n"
                    + user_prompt
                ),
            },
        ],
    }

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{str(base_url).rstrip('/')}/chat/completions"
    response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
    if response.status_code >= 400:
        payload.pop("response_format", None)
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
    response.raise_for_status()

    body = response.json()
    content = (body.get("choices") or [{}])[0].get("message", {}).get("content") or "{}"
    try:
        obj = json.loads(content)
    except Exception as exc:
        raise RuntimeError("OpenAI returned invalid JSON") from exc
    if not isinstance(obj, dict):
        raise RuntimeError("OpenAI output must be a JSON object")

    workflow = _hydrate_generated_workflow(_sanitize_generated_workflow(obj), source_context, user_prompt)
    drawflow = workflow_to_drawflow(workflow)
    warnings = obj.get("warnings") if isinstance(obj.get("warnings"), list) else []
    return {
        "name": str(obj.get("name") or workflow.get("name") or "ai_generated_workflow"),
        "summary": str(obj.get("summary") or "").strip(),
        "warnings": [str(w) for w in warnings if str(w).strip()],
        "workflow": workflow,
        "drawflow": drawflow,
    }