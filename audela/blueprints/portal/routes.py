from __future__ import annotations

from datetime import datetime

import json

from flask import abort, flash, g, jsonify, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ...extensions import db
from ...models.bi import AuditEvent, Dashboard, DashboardCard, DataSource, Question, QueryRun, Report
from ...models.core import Tenant
from ...models.core import User, Role
from ...security import require_roles
from ...services.query_service import QueryExecutionError, execute_sql
from ...services.datasource_service import decrypt_config, introspect_source
from ...services.nlq_service import generate_sql_from_nl
from ...services.pdf_export import table_to_pdf_bytes
from ...services.ai_service import analyze_with_ai
from ...services.statistics_service import run_statistics_analysis, stats_report_to_pdf_bytes
from ...services.report_render_service import report_to_pdf_bytes
from ...tenancy import get_current_tenant_id
from ...i18n import tr
from . import bp


@bp.before_app_request
def load_tenant_into_g() -> None:
    """Load current tenant from session.

    MVP: tenant is stored in session during login.
    """
    tenant_id = get_current_tenant_id()
    g.tenant = None
    if tenant_id:
        tenant = Tenant.query.get(tenant_id)
        if tenant:
            g.tenant = tenant


def _require_tenant() -> None:
    if not current_user.is_authenticated:
        abort(401)
    if not g.tenant or current_user.tenant_id != g.tenant.id:
        abort(403)


def _audit(event_type: str, payload: dict | None = None) -> None:
    if not g.tenant:
        return
    evt = AuditEvent(
        tenant_id=g.tenant.id,
        user_id=getattr(current_user, "id", None),
        event_type=event_type,
        payload_json=payload or {},
    )
    db.session.add(evt)


@bp.route("/")
@login_required
def home():
    _require_tenant()
    # Show main dashboard (if any) and recent dashboards on home
    main = None
    try:
        main = Dashboard.query.filter_by(tenant_id=g.tenant.id, is_primary=True).first()
    except Exception:
        # DB schema may be out of date (missing is_primary). Don't crash the home page.
        main = None
    dashes = Dashboard.query.filter_by(tenant_id=g.tenant.id).order_by(Dashboard.updated_at.desc()).all()
    return render_template("portal/home.html", tenant=g.tenant, dashboards=dashes, main_dashboard=main)


# -----------------------------
# Data Sources
# -----------------------------


@bp.route("/sources")
@login_required
@require_roles("tenant_admin", "creator")
def sources_list():
    _require_tenant()
    sources = (
        DataSource.query.filter_by(tenant_id=g.tenant.id)
        .order_by(DataSource.created_at.desc())
        .all()
    )
    return render_template("portal/sources_list.html", tenant=g.tenant, sources=sources)


@bp.route("/sources/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def sources_new():
    _require_tenant()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        ds_type = request.form.get("type", "").strip().lower()
        url = request.form.get("url", "").strip()
        default_schema = request.form.get("default_schema", "").strip() or None
        tenant_column = request.form.get("tenant_column", "").strip() or None

        if not name or not ds_type or not url:
            flash(tr("Preencha nome, tipo e URL de conexão.", getattr(g, "lang", None)), "error")
            return render_template("portal/sources_new.html", tenant=g.tenant)

        from ...services.crypto import encrypt_json

        config = {
            "url": url,
            "default_schema": default_schema,
            "tenant_column": tenant_column,
        }
        ds = DataSource(
            tenant_id=g.tenant.id,
            type=ds_type,
            name=name,
            config_encrypted=encrypt_json(config),
            policy_json={
                "timeout_seconds": 30,
                "max_rows": 5000,
                "read_only": True,
            },
        )
        db.session.add(ds)
        _audit("bi.datasource.created", {"id": None, "name": name, "type": ds_type})
        db.session.commit()

        flash(tr("Fonte criada.", getattr(g, "lang", None)), "success")
        return redirect(url_for("portal.sources_list"))

    return render_template("portal/sources_new.html", tenant=g.tenant)


@bp.get("/sources/api")
def api_sources_list():
    """List API sources separately (for quick access)."""
    _require_tenant()
    sources = (
        db.session.query(DataSource)
        .filter(DataSource.tenant_id == g.tenant.id)
        .filter(DataSource.type == "api")
        .order_by(DataSource.created_at.desc())
        .all()
    )
    return render_template("portal/api_sources_list.html", tenant=g.tenant, sources=sources)


@bp.route("/sources/api/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin")
def api_sources_new():
    """Create a new API source.

    We store the API base URL in the encrypted config.
    Headers can be provided as JSON (optional).
    """
    _require_tenant()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        base_url = request.form.get("base_url", "").strip()
        headers_raw = (request.form.get("headers_json", "") or "").strip()

        if not name or not base_url:
            flash(tr("Preencha nome e URL base.", getattr(g, "lang", None)), "error")
            return render_template("portal/api_sources_new.html", tenant=g.tenant)

        headers = None
        if headers_raw:
            import json

            try:
                headers = json.loads(headers_raw)
                if not isinstance(headers, dict):
                    raise ValueError("headers_json must be a JSON object")
            except Exception as e:
                flash(tr("JSON inválido em cabeçalhos: {error}", getattr(g, "lang", None), error=str(e)), "error")
                return render_template(
                    "portal/api_sources_new.html",
                    tenant=g.tenant,
                    form={"name": name, "base_url": base_url, "headers_json": headers_raw},
                )

        from ...services.crypto import encrypt_json

        config = {
            "base_url": base_url,
            "headers": headers or {},
        }

        ds = DataSource(
            tenant_id=g.tenant.id,
            type="api",
            name=name,
            base_url=base_url,
            config_encrypted=encrypt_json(config),
            policy_json={
                "timeout_seconds": 30,
                "max_rows": 5000,
                "read_only": True,
            },
        )
        db.session.add(ds)
        _audit("bi.datasource.created", {"id": None, "name": name, "type": "api"})
        db.session.commit()

        flash(tr("Fonte API criada.", getattr(g, "lang", None)), "success")
        return redirect(url_for("portal.api_sources_list"))

    return render_template("portal/api_sources_new.html", tenant=g.tenant)


@bp.route("/sources/<int:source_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin")
def sources_delete(source_id: int):
    _require_tenant()
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first_or_404()
    _audit("bi.datasource.deleted", {"id": src.id, "name": src.name})
    db.session.delete(src)
    db.session.commit()
    flash(tr("Fonte removida.", getattr(g, "lang", None)), "success")
    return redirect(url_for("portal.sources_list"))

@bp.route("/apisources/<int:source_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin")
def apisources_delete(source_id: int):
    _require_tenant()
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first_or_404()
    _audit("bi.datasource.deleted", {"id": src.id, "name": src.name})
    db.session.delete(src)
    db.session.commit()
    flash(tr("Fonte removida.", getattr(g, "lang", None)), "success")
    return redirect(url_for("portal.api_sources_list"))

@bp.route("/sources/<int:source_id>")
@login_required
@require_roles("tenant_admin", "creator")
def sources_view(source_id: int):
    _require_tenant()
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first_or_404()
    cfg = decrypt_config(src)
    return render_template("portal/sources_view.html", tenant=g.tenant, source=src, config=cfg)


@bp.route("/sources/<int:source_id>/introspect")
@login_required
@require_roles("tenant_admin", "creator")
def sources_introspect(source_id: int):
    _require_tenant()
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first_or_404()
    try:
        meta = introspect_source(src)
    except Exception as e:  # noqa: BLE001
        flash(tr("Falha ao introspectar: {error}", getattr(g, "lang", None), error=str(e)), "error")
        meta = {"schemas": []}
    _audit("bi.datasource.introspected", {"id": src.id})
    db.session.commit()
    return render_template(
        "portal/sources_introspect.html",
        tenant=g.tenant,
        source=src,
        meta=meta,
    )


@bp.route("/sources/diagram")
@login_required
@require_roles("tenant_admin", "creator")
def sources_diagram():
    _require_tenant()
    sources = (
        DataSource.query.filter_by(tenant_id=g.tenant.id)
        .order_by(DataSource.name.asc())
        .all()
    )
    return render_template("portal/sources_diagram.html", tenant=g.tenant, sources=sources)


# -----------------------------
# API (schema, NLQ, export)
# -----------------------------


@bp.route("/api/sources/<int:source_id>/schema")
@login_required
@require_roles("tenant_admin", "creator")
def api_source_schema(source_id: int):
    _require_tenant()
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first_or_404()
    meta = introspect_source(src)
    return jsonify(meta)


@bp.route("/api/sources/<int:source_id>/diagram")
@login_required
@require_roles("tenant_admin", "creator")
def api_source_diagram(source_id: int):
    """Return a simple graph (tables + inferred relations) for a source."""
    _require_tenant()
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first_or_404()
    meta = introspect_source(src)
    # Flatten tables across schemas
    tables = []
    for s in meta.get("schemas", []):
        for t in s.get("tables", []):
            tables.append({"name": t.get("name"), "columns": [c.get("name") for c in t.get("columns", [])]})

    # Infer relations via simple foreign-key naming heuristics (col ending with _id)
    name_index = {t["name"]: t for t in tables}
    relations = []
    for t in tables:
        for col in t.get("columns", []):
            if not isinstance(col, str):
                continue
            if not col.endswith("_id"):
                continue
            base = col[:-3]
            target = None
            # direct match
            if base in name_index:
                target = base
            # try plural/singular heuristics
            elif base + "s" in name_index:
                target = base + "s"
            elif base.endswith("s") and base[:-1] in name_index:
                target = base[:-1]
            else:
                # fallback: find table that contains base
                for tn in name_index:
                    if tn.endswith(base) or tn.startswith(base):
                        target = tn
                        break
            if target:
                relations.append({"from": f"{t['name']}.{col}", "to": f"{target}.id"})

    return jsonify({"tables": tables, "relations": relations})


@bp.route("/api/nlq", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def api_nlq():
    _require_tenant()
    payload = request.get_json(silent=True) or {}
    try:
        source_id = int(payload.get("source_id") or 0)
    except Exception:
        source_id = 0
    text = (payload.get("text") or "").strip()
    if not source_id:
        return jsonify({"error": tr("Selecione uma fonte.", getattr(g, "lang", None))}), 400
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
    if not src:
        return jsonify({"error": tr("Fonte inválida.", getattr(g, "lang", None))}), 404
    sql_text, warnings = generate_sql_from_nl(src, text, lang=getattr(g, "lang", None))
    return jsonify({"sql": sql_text, "warnings": warnings})


@bp.route("/api/export/pdf", methods=["POST"])
@login_required
def api_export_pdf():
    _require_tenant()
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "Export").strip()
    columns = payload.get("columns") or []
    rows = payload.get("rows") or []

    # Conservative limits
    if not isinstance(columns, list) or not isinstance(rows, list):
        return jsonify({"error": "Payload inválido."}), 400
    if len(columns) > 200:
        return jsonify({"error": "Muitas colunas."}), 400
    if len(rows) > 5000:
        rows = rows[:5000]

    pdf_bytes = table_to_pdf_bytes(title, [str(c) for c in columns], rows)
    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'attachment; filename="{title[:80].replace(" ", "_")}.pdf"'
    return resp


# -----------------------------
# Statistics (advanced analysis)
# -----------------------------


@bp.route("/statistics", methods=["GET"]) 
@login_required
@require_roles("tenant_admin", "creator")
def statistics_home():
    """Statistics module: run advanced analyses on a selected datasource/query."""
    _require_tenant()
    sources = DataSource.query.filter_by(tenant_id=g.tenant.id).order_by(DataSource.name.asc()).all()
    questions = Question.query.filter_by(tenant_id=g.tenant.id).order_by(Question.updated_at.desc()).all()
    return render_template(
        "portal/statistics.html",
        tenant=g.tenant,
        sources=sources,
        questions=questions,
        result=None,
        stats=None,
        ai=None,
        error=None,
    )


@bp.route("/statistics/run", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def statistics_run():
    _require_tenant()
    sources = DataSource.query.filter_by(tenant_id=g.tenant.id).order_by(DataSource.name.asc()).all()
    questions = Question.query.filter_by(tenant_id=g.tenant.id).order_by(Question.updated_at.desc()).all()

    # Inputs
    source_id = int(request.form.get("source_id") or 0)
    question_id = int(request.form.get("question_id") or 0)
    sql_text = (request.form.get("sql_text") or "").strip()
    note = (request.form.get("note") or "").strip()

    src = None
    q = None
    if question_id:
        q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first()
        if q:
            src = DataSource.query.filter_by(id=q.source_id, tenant_id=g.tenant.id).first()
            sql_text = (q.sql_text or "").strip()

    if not src and source_id:
        src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()

    if not src:
        return render_template(
            "portal/statistics.html",
            tenant=g.tenant,
            sources=sources,
            questions=questions,
            result=None,
            stats=None,
            ai=None,
            error=tr("Selecione uma fonte (ou pergunta).", getattr(g, "lang", None)),
        )

    if not sql_text:
        return render_template(
            "portal/statistics.html",
            tenant=g.tenant,
            sources=sources,
            questions=questions,
            result=None,
            stats=None,
            ai=None,
            error=tr("Informe um SQL (somente leitura) ou selecione uma pergunta.", getattr(g, "lang", None)),
        )

    # Run query (light sample for analysis)
    try:
        res = execute_sql(src, sql_text, params={"tenant_id": g.tenant.id})
    except QueryExecutionError as e:
        return render_template(
            "portal/statistics.html",
            tenant=g.tenant,
            sources=sources,
            questions=questions,
            result=None,
            stats=None,
            ai=None,
            error=str(e),
        )

    # Keep the in-memory dataset bounded for UI + OpenAI
    if isinstance(res.get("rows"), list) and len(res["rows"]) > 2000:
        res["rows"] = res["rows"][:2000]

    stats = run_statistics_analysis(res)

    # Ask OpenAI for an interpreted report (optional)
    ai = None
    try:
        # Send a compact bundle (stats + a small sample)
        sample_rows = (res.get("rows") or [])[:200]
        bundle = {
            "question": {"name": q.name, "id": q.id} if q else None,
            "source": {"id": src.id, "name": src.name, "type": src.type},
            "result": {"columns": res.get("columns"), "rows": sample_rows},
            "stats": stats,
        }
        user_msg = note or tr(
            "Faça uma análise estatística completa (distribuição normal/gaussiana, correlação, regressão linear e um pequeno cenário de Monte Carlo). Explique achados e riscos. Retorne em linguagem clara.",
            getattr(g, "lang", None),
        )
        ai = analyze_with_ai(bundle, user_msg, history=None, lang=getattr(g, "lang", None))
    except Exception as e:  # noqa: BLE001
        ai = {"error": f"IA indisponível: {e}"}

    # Store last run in session for PDF export
    try:
        from flask import session

        session["stats_last"] = {
            "source_id": src.id,
            "question_id": q.id if q else None,
            "sql_text": sql_text,
            "note": note,
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception:
        pass

    return render_template(
        "portal/statistics.html",
        tenant=g.tenant,
        sources=sources,
        questions=questions,
        result=res,
        stats=stats,
        ai=ai,
        error=None,
    )


@bp.route("/statistics/pdf", methods=["GET"])
@login_required
@require_roles("tenant_admin", "creator")
def statistics_pdf():
    """Export the last statistics report to PDF."""
    _require_tenant()
    from flask import session

    payload = session.get("stats_last") or {}
    source_id = int(payload.get("source_id") or 0)
    sql_text = (payload.get("sql_text") or "").strip()
    if not source_id or not sql_text:
        flash(tr("Nenhuma análise recente para exportar.", getattr(g, "lang", None)), "error")
        return redirect(url_for("portal.statistics_home"))

    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first_or_404()

    res = execute_sql(src, sql_text, params={"tenant_id": g.tenant.id})
    if isinstance(res.get("rows"), list) and len(res["rows"]) > 5000:
        res["rows"] = res["rows"][:5000]

    stats = run_statistics_analysis(res)

    # Try to reuse AI output from a fresh call (best-effort)
    ai = None
    try:
        sample_rows = (res.get("rows") or [])[:200]
        bundle = {
            "source": {"id": src.id, "name": src.name, "type": src.type},
            "result": {"columns": res.get("columns"), "rows": sample_rows},
            "stats": stats,
        }
        user_msg = (payload.get("note") or "").strip() or tr(
            "Gere um resumo executivo da análise estatística, com recomendações.",
            getattr(g, "lang", None),
        )
        ai = analyze_with_ai(bundle, user_msg, history=None, lang=getattr(g, "lang", None))
    except Exception:
        ai = None

    title = f"Statistics - {src.name}"
    pdf_bytes = stats_report_to_pdf_bytes(title=title, source=src, sql_text=sql_text, result=res, stats=stats, ai=ai)

    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'attachment; filename="{title[:80].replace(" ", "_")}.pdf"'
    return resp


# -----------------------------
# SQL Editor (ad-hoc)
# -----------------------------


@bp.route("/sql", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def sql_editor():
    _require_tenant()
    sources = DataSource.query.filter_by(tenant_id=g.tenant.id).order_by(DataSource.name.asc()).all()
    result = None
    error = None
    elapsed_ms = None

    if request.method == "POST":
        source_id = int(request.form.get("source_id") or 0)
        sql_text = request.form.get("sql_text", "")
        params_text = (request.form.get("params_json") or "").strip()
        src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
        if not src:
            flash("Selecione uma fonte válida.", "error")
            return render_template("portal/sql_editor.html", tenant=g.tenant, sources=sources)

        started = datetime.utcnow()
        qr = QueryRun(tenant_id=g.tenant.id, question_id=None, user_id=current_user.id, status="running")
        db.session.add(qr)
        db.session.flush()
        # Parse user parameters (JSON) and enforce tenant_id server-side.
        user_params: dict = {}
        if params_text:
            try:
                maybe = json.loads(params_text)
                if isinstance(maybe, dict):
                    user_params = maybe
                else:
                    raise ValueError("params must be object")
            except Exception as e:  # noqa: BLE001
                error = f"Parâmetros JSON inválidos: {e}"
                qr.status = "error"
                qr.error = error
                _audit("bi.query.failed", {"source_id": src.id, "query_run_id": qr.id, "error": error})
                elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
                qr.duration_ms = elapsed_ms
                db.session.commit()
                return render_template(
                    "portal/sql_editor.html",
                    tenant=g.tenant,
                    sources=sources,
                    result=None,
                    error=error,
                    elapsed_ms=elapsed_ms,
                )

        # Never let the client spoof tenant_id.
        user_params["tenant_id"] = g.tenant.id

        try:
            result = execute_sql(src, sql_text, params=user_params)
            qr.status = "success"
            qr.rows = len(result.get("rows", []))
            _audit("bi.query.executed", {"source_id": src.id, "query_run_id": qr.id, "ad_hoc": True})
        except QueryExecutionError as e:
            error = str(e)
            qr.status = "error"
            qr.error = error
            _audit("bi.query.failed", {"source_id": src.id, "query_run_id": qr.id, "error": error})
        finally:
            elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
            qr.duration_ms = elapsed_ms
            db.session.commit()

    return render_template(
        "portal/sql_editor.html",
        tenant=g.tenant,
        sources=sources,
        result=result,
        error=error,
        elapsed_ms=elapsed_ms,
    )
# -----------------------------
# Questions
# -----------------------------


@bp.route("/questions")
@login_required
def questions_list():
    _require_tenant()
    qs = Question.query.filter_by(tenant_id=g.tenant.id).order_by(Question.updated_at.desc()).all()
    return render_template("portal/questions_list.html", tenant=g.tenant, questions=qs)


@bp.route("/questions/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def questions_new():
    _require_tenant()
    sources = DataSource.query.filter_by(tenant_id=g.tenant.id).order_by(DataSource.name.asc()).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        source_id = int(request.form.get("source_id") or 0)
        sql_text = request.form.get("sql_text", "")
        if not name or not source_id or not sql_text.strip():
            flash(tr("Preencha nome, fonte e SQL.", getattr(g, "lang", None)), "error")
            return render_template("portal/questions_new.html", tenant=g.tenant, sources=sources)
        src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
        if not src:
            flash(tr("Fonte inválida.", getattr(g, "lang", None)), "error")
            return render_template("portal/questions_new.html", tenant=g.tenant, sources=sources)

        q = Question(
            tenant_id=g.tenant.id,
            source_id=src.id,
            name=name,
            sql_text=sql_text,
            params_schema_json={},
            viz_config_json={},
            acl_json={},
        )
        db.session.add(q)
        db.session.flush()
        _audit("bi.question.created", {"id": q.id, "name": q.name, "source_id": src.id})
        db.session.commit()
        flash(tr("Pergunta criada.", getattr(g, "lang", None)), "success")
        return redirect(url_for("portal.questions_view", question_id=q.id))

    return render_template("portal/questions_new.html", tenant=g.tenant, sources=sources)


@bp.route("/questions/<int:question_id>")
@login_required
def questions_view(question_id: int):
    _require_tenant()
    q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=q.source_id, tenant_id=g.tenant.id).first_or_404()
    _audit("bi.question.viewed", {"id": q.id})
    db.session.commit()
    return render_template("portal/questions_view.html", tenant=g.tenant, question=q, source=src)


@bp.route("/questions/<int:question_id>/viz", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def questions_viz(question_id: int):
    """Configure question visualization (charts/pivot/gauge)."""

    _require_tenant()
    q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=q.source_id, tenant_id=g.tenant.id).first_or_404()

    if request.method == "POST":
        raw = request.form.get("viz_config_json", "{}")
        try:
            cfg = json.loads(raw) if raw else {}
        except Exception:
            cfg = {}
            flash(tr("Configuração inválida.", getattr(g, "lang", None)), "error")
            return redirect(url_for("portal.questions_viz", question_id=q.id))

        if not isinstance(cfg, dict):
            cfg = {}

        q.viz_config_json = cfg
        _audit("bi.question.viz.updated", {"id": q.id})
        db.session.commit()
        flash(tr("Visualização salva.", getattr(g, "lang", None)), "success")
        return redirect(url_for("portal.questions_view", question_id=q.id))

    # GET: run once to preview
    try:
        res = execute_sql(src, q.sql_text, params={"tenant_id": g.tenant.id})
    except QueryExecutionError as e:
        res = {"columns": [], "rows": [], "error": str(e)}

    # keep preview light
    if isinstance(res.get("rows"), list) and len(res["rows"]) > 1000:
        res["rows"] = res["rows"][:1000]

    return render_template(
        "portal/questions_viz.html",
        tenant=g.tenant,
        question=q,
        source=src,
        result=res,
        viz_config=q.viz_config_json or {},
    )


@bp.route("/questions/<int:question_id>/run", methods=["GET", "POST"])
@login_required
def questions_run(question_id: int):
    _require_tenant()
    q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=q.source_id, tenant_id=g.tenant.id).first_or_404()

    if request.method == "GET":
        return render_template(
            "portal/questions_run.html",
            tenant=g.tenant,
            question=q,
            source=src,
            result=None,
            error=None,
            elapsed_ms=None,
            viz_config=q.viz_config_json or {},
            sql_text=q.sql_text,
            params_json="",
        )

    # Allow editing the SQL at runtime (does not overwrite the saved Question unless explicitly saved elsewhere)
    sql_text = (request.form.get("sql_text") or q.sql_text or "").strip()
    params_text = (request.form.get("params_json") or "").strip()

    started = datetime.utcnow()
    qr = QueryRun(tenant_id=g.tenant.id, question_id=q.id, user_id=current_user.id, status="running")
    db.session.add(qr)
    db.session.flush()

    result = None
    error = None
    elapsed_ms = None
    # Parse user parameters (JSON) and enforce tenant_id server-side.
    user_params: dict = {}
    if params_text:
        try:
            maybe = json.loads(params_text)
            if isinstance(maybe, dict):
                user_params = maybe
            else:
                raise ValueError("params must be object")
        except Exception as e:  # noqa: BLE001
            error = f"Parâmetros JSON inválidos: {e}"
            qr.status = "error"
            qr.error = error
            _audit("bi.question.failed", {"id": q.id, "query_run_id": qr.id, "error": error})
            elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
            qr.duration_ms = elapsed_ms
            db.session.commit()
            return render_template(
                "portal/questions_run.html",
                tenant=g.tenant,
                question=q,
                source=src,
                result=None,
                error=error,
                elapsed_ms=elapsed_ms,
                viz_config=q.viz_config_json or {},
            )

    user_params["tenant_id"] = g.tenant.id

    try:
        result = execute_sql(src, sql_text, params=user_params)
        qr.status = "success"
        qr.rows = len(result.get("rows", []))
        _audit("bi.question.executed", {"id": q.id, "query_run_id": qr.id})
    except QueryExecutionError as e:
        error = str(e)
        qr.status = "error"
        qr.error = error
        _audit("bi.question.failed", {"id": q.id, "query_run_id": qr.id, "error": error})
    finally:
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        qr.duration_ms = elapsed_ms
        db.session.commit()

    return render_template(
        "portal/questions_run.html",
        tenant=g.tenant,
        question=q,
        source=src,
        result=result,
        error=error,
        elapsed_ms=elapsed_ms,
        viz_config=q.viz_config_json or {},
        sql_text=sql_text,
        params_json=params_text,
    )


@bp.route("/questions/<int:question_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def questions_delete(question_id: int):
    _require_tenant()
    q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first_or_404()
    _audit("bi.question.deleted", {"id": q.id, "name": q.name})
    db.session.delete(q)
    db.session.commit()
    flash(tr("Pergunta removida.", getattr(g, "lang", None)), "success")
    return redirect(url_for("portal.questions_list"))


# -----------------------------
# Dashboards
# -----------------------------


@bp.route("/dashboards")
@login_required
def dashboards_list():
    _require_tenant()
    ds = Dashboard.query.filter_by(tenant_id=g.tenant.id).order_by(Dashboard.updated_at.desc()).all()
    return render_template("portal/dashboards_list.html", tenant=g.tenant, dashboards=ds)


# -----------------------------
# Reports (Crystal-like builder)
# -----------------------------


@bp.route("/reports")
@login_required
def reports_list():
    _require_tenant()
    reps = Report.query.filter_by(tenant_id=g.tenant.id).order_by(Report.updated_at.desc()).all()
    return render_template("portal/reports_list.html", tenant=g.tenant, reports=reps)


@bp.route("/reports/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def reports_new():
    _require_tenant()
    sources = DataSource.query.filter_by(tenant_id=g.tenant.id).order_by(DataSource.name.asc()).all()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        source_id = int(request.form.get("source_id") or 0)
        if not name or not source_id:
            flash(tr("Informe nome e fonte.", getattr(g, "lang", None)), "error")
            return render_template("portal/reports_new.html", tenant=g.tenant, sources=sources)
        src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
        if not src:
            flash(tr("Fonte inválida.", getattr(g, "lang", None)), "error")
            return render_template("portal/reports_new.html", tenant=g.tenant, sources=sources)

        rep = Report(
            tenant_id=g.tenant.id,
            source_id=src.id,
            name=name,
            layout_json={
                "version": 1,
                "page": {"size": "A4", "orientation": "portrait"},
                "sections": {
                    "header": [],
                    "body": [],
                    "footer": [],
                },
            },
        )
        db.session.add(rep)
        db.session.commit()
        flash(tr("Relatório criado.", getattr(g, "lang", None)), "success")
        return redirect(url_for("portal.report_builder", report_id=rep.id))

    return render_template("portal/reports_new.html", tenant=g.tenant, sources=sources)


@bp.route("/reports/<int:report_id>/builder", methods=["GET"])
@login_required
@require_roles("tenant_admin", "creator")
def report_builder(report_id: int):
    _require_tenant()
    rep = Report.query.filter_by(id=report_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=rep.source_id, tenant_id=g.tenant.id).first_or_404()
    questions = Question.query.filter_by(tenant_id=g.tenant.id, source_id=src.id).order_by(Question.name.asc()).all()
    return render_template(
        "portal/report_builder.html",
        tenant=g.tenant,
        report=rep,
        source=src,
        questions=questions,
    )


@bp.route("/reports/<int:report_id>/view", methods=["GET"])
@login_required
def report_view(report_id: int):
    """Read-only viewer for Report Builder layouts."""
    _require_tenant()
    rep = Report.query.filter_by(id=report_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=rep.source_id, tenant_id=g.tenant.id).first_or_404()
    questions = Question.query.filter_by(tenant_id=g.tenant.id, source_id=src.id).order_by(Question.name.asc()).all()
    q_by_id = {q.id: q for q in questions}

    # For HTML preview, fetch data for question blocks (limited) so we can render tables quickly.
    layout = rep.layout_json or {}
    sections = (layout.get("sections") or {})
    blocks_data = {}
    for sec in ("header", "body", "footer"):
        for b in (sections.get(sec) or []):
            if (b.get("type") or "").lower() == "question":
                qid = int(b.get("question_id") or 0)
                q = q_by_id.get(qid)
                if not q:
                    continue
                try:
                    blocks_data[qid] = execute_sql(src, q.sql_text or "", {"tenant_id": g.tenant.id}, row_limit=25)
                except Exception as e:
                    blocks_data[qid] = {"columns": [], "rows": [], "error": str(e)}

    return render_template(
        "portal/report_view.html",
        tenant=g.tenant,
        report=rep,
        source=src,
        questions=q_by_id,
        layout=layout,
        blocks_data=blocks_data,
    )


@bp.route("/reports/<int:report_id>/pdf", methods=["GET"])
@login_required
def report_pdf(report_id: int):
    """Export a Report Builder layout to PDF."""
    _require_tenant()
    rep = Report.query.filter_by(id=report_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=rep.source_id, tenant_id=g.tenant.id).first_or_404()
    questions = Question.query.filter_by(tenant_id=g.tenant.id, source_id=src.id).order_by(Question.name.asc()).all()
    q_by_id = {q.id: q for q in questions}

    pdf = report_to_pdf_bytes(
        title=rep.name or "Report",
        report=rep,
        source=src,
        tenant_id=g.tenant.id,
        questions_by_id=q_by_id,
        lang=getattr(g, "lang", None),
    )
    resp = make_response(pdf)
    resp.headers["Content-Type"] = "application/pdf"
    safe = (rep.name or "report").replace("/", "-")
    resp.headers["Content-Disposition"] = f'attachment; filename="{safe}.pdf"'
    return resp


@bp.route("/api/reports/<int:report_id>", methods=["GET"])
@login_required
def api_report_get(report_id: int):
    _require_tenant()
    rep = Report.query.filter_by(id=report_id, tenant_id=g.tenant.id).first_or_404()
    return jsonify({"id": rep.id, "name": rep.name, "source_id": rep.source_id, "layout": rep.layout_json or {}})


@bp.route("/api/reports/<int:report_id>", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def api_report_save(report_id: int):
    _require_tenant()
    rep = Report.query.filter_by(id=report_id, tenant_id=g.tenant.id).first_or_404()
    payload = request.get_json(silent=True) or {}
    layout = payload.get("layout")
    if not isinstance(layout, dict):
        return jsonify({"error": "layout inválido"}), 400
    # keep it small / safe
    rep.layout_json = layout
    db.session.commit()
    return jsonify({"ok": True})


@bp.route('/users')
@login_required
@require_roles('tenant_admin')
def users_list():
    _require_tenant()
    users = User.query.filter_by(tenant_id=g.tenant.id).order_by(User.email.asc()).all()
    return render_template('portal/users_list.html', tenant=g.tenant, users=users)


@bp.route('/users/new', methods=['GET', 'POST'])
@login_required
@require_roles('tenant_admin')
def users_new():
    _require_tenant()
    roles = Role.query.order_by(Role.code.asc()).all()
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','').strip()
        role_ids = request.form.getlist('roles') or []
        if not email or not password:
            flash(tr('Email e senha são obrigatórios.', getattr(g, "lang", None)), 'error')
            return render_template('portal/users_new.html', tenant=g.tenant, roles=roles)
        u = User(tenant_id=g.tenant.id, email=email)
        u.set_password(password)
        if role_ids:
            u.roles = Role.query.filter(Role.id.in_(role_ids)).all()
        db.session.add(u)
        db.session.commit()
        flash(tr('Usuário criado.', getattr(g, "lang", None)), 'success')
        return redirect(url_for('portal.users_list'))
    return render_template('portal/users_new.html', tenant=g.tenant, roles=roles)


@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@require_roles('tenant_admin')
def users_delete(user_id: int):
    _require_tenant()
    u = User.query.filter_by(id=user_id, tenant_id=g.tenant.id).first_or_404()
    db.session.delete(u)
    db.session.commit()
    flash(tr('Usuário removido.', getattr(g, "lang", None)), 'success')
    return redirect(url_for('portal.users_list'))


@bp.route("/dashboards/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def dashboards_new():
    _require_tenant()
    questions = Question.query.filter_by(tenant_id=g.tenant.id).order_by(Question.name.asc()).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        selected = request.form.getlist("question_ids")
        if not name:
            flash(tr("Informe um nome.", getattr(g, "lang", None)), "error")
            return render_template("portal/dashboards_new.html", tenant=g.tenant, questions=questions)

        dash = Dashboard(tenant_id=g.tenant.id, name=name, layout_json={}, filters_json={}, acl_json={})
        db.session.add(dash)
        db.session.flush()

        # Create cards in a simple vertical layout
        y = 0
        for qid_str in selected:
            try:
                qid = int(qid_str)
            except ValueError:
                continue
            q = Question.query.filter_by(id=qid, tenant_id=g.tenant.id).first()
            if not q:
                continue
            card = DashboardCard(
                tenant_id=g.tenant.id,
                dashboard_id=dash.id,
                question_id=q.id,
                viz_config_json={},
                position_json={"x": 0, "y": y, "w": 12, "h": 6},
            )
            y += 6
            db.session.add(card)

        _audit("bi.dashboard.created", {"id": dash.id, "name": dash.name, "cards": len(selected)})
        db.session.commit()
        flash(tr("Dashboard criado.", getattr(g, "lang", None)), "success")
        return redirect(url_for("portal.dashboard_view", dashboard_id=dash.id))

    return render_template("portal/dashboards_new.html", tenant=g.tenant, questions=questions)


@bp.route("/dashboards/<int:dashboard_id>")
@login_required
def dashboard_view(dashboard_id: int):
    _require_tenant()

    # IMPORTANT: avoid leaking existence across tenants -> 404 if tenant mismatch
    dash = Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.tenant.id).first_or_404()
    cards = (
        DashboardCard.query.filter_by(dashboard_id=dash.id, tenant_id=g.tenant.id)
        .order_by(DashboardCard.id.asc())
        .all()
    )

    

    # For the dashboard builder (Add card)
    all_questions = (
        Question.query.filter_by(tenant_id=g.tenant.id)
        .order_by(Question.updated_at.desc())
        .all()
    )

    rendered_cards = []
    for c in cards:
        q = Question.query.filter_by(id=c.question_id, tenant_id=g.tenant.id).first()
        if not q:
            continue
        src = DataSource.query.filter_by(id=q.source_id, tenant_id=g.tenant.id).first()
        if not src:
            continue
        try:
            res = execute_sql(src, q.sql_text, params={"tenant_id": g.tenant.id})
        except QueryExecutionError as e:
            res = {"columns": [], "rows": [], "error": str(e)}
        
        # Determine visualization config with intelligent fallback
        viz_cfg = {"type": "table"}
        
        # Use question-level config as base
        if isinstance(getattr(q, "viz_config_json", None), dict) and q.viz_config_json:
            viz_cfg = q.viz_config_json.copy() if isinstance(q.viz_config_json, dict) else {}
        
        # Card-level config overrides, but only if it specifies more than just type
        card_cfg = getattr(c, "viz_config_json", None)
        if isinstance(card_cfg, dict) and card_cfg and len(card_cfg) > 1:
            # Card has meaningful overrides beyond just type
            viz_cfg = card_cfg
        elif isinstance(card_cfg, dict) and card_cfg and card_cfg.get("type") not in [None, "table"]:
            # Card specifies a non-table type, use it but merge with question config
            viz_cfg.update(card_cfg)

        rendered_cards.append({"card": c, "question": q, "result": res, "viz_config": viz_cfg})

    _audit("bi.dashboard.viewed", {"id": dash.id})
    db.session.commit()
    return render_template(
        "portal/dashboard_view.html",
        tenant=g.tenant,
        dashboard=dash,
        cards=rendered_cards,
        all_questions=all_questions,
    )


@bp.route("/dashboards/<int:dashboard_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def dashboards_delete(dashboard_id: int):
    _require_tenant()
    dash = Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.tenant.id).first_or_404()
    _audit("bi.dashboard.deleted", {"id": dash.id, "name": dash.name})
    db.session.delete(dash)
    db.session.commit()
    flash(tr("Dashboard removido.", getattr(g, "lang", None)), "success")
    return redirect(url_for("portal.dashboards_list"))


@bp.route("/dashboards/<int:dashboard_id>/set_primary", methods=["POST"])
@login_required
@require_roles("tenant_admin")
def dashboards_set_primary(dashboard_id: int):
    _require_tenant()
    dash = Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.tenant.id).first_or_404()
    try:
        # clear previous primary
        Dashboard.query.filter_by(tenant_id=g.tenant.id, is_primary=True).update({"is_primary": False})
        dash.is_primary = True
        db.session.commit()
        flash(tr("Dashboard definido como principal.", getattr(g, "lang", None)), "success")
    except Exception:
        db.session.rollback()
        flash(tr("Operação não suportada: execute as migrações do banco para habilitar essa função.", getattr(g, "lang", None)), "error")
    return redirect(url_for("portal.dashboards_list"))




# -----------------------------
# Explore (Superset-like)
# -----------------------------


@bp.route("/explore")
@login_required
def explore():
    _require_tenant()
    qs = Question.query.filter_by(tenant_id=g.tenant.id).order_by(Question.updated_at.desc()).all()
    dashes = Dashboard.query.filter_by(tenant_id=g.tenant.id).order_by(Dashboard.updated_at.desc()).all()
    return render_template("portal/explore.html", tenant=g.tenant, questions=qs, dashboards=dashes)


@bp.route("/api/questions/<int:question_id>/data", methods=["POST"])
@login_required
def api_question_data(question_id: int):
    _require_tenant()
    q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=q.source_id, tenant_id=g.tenant.id).first_or_404()
    payload = request.get_json(silent=True) or {}
    params = payload.get("params") or {}
    agg = payload.get("agg")
    if params and not isinstance(params, dict):
        return jsonify({"error": "Parâmetros devem ser um objeto JSON."}), 400
    user_params: dict = {}
    if isinstance(params, dict):
        user_params.update(params)
    user_params["tenant_id"] = g.tenant.id
    try:
        # If aggregation requested, build an aggregated SQL wrapping the original query
        if agg and isinstance(agg, dict):
            dim = agg.get("dim")
            metric = agg.get("metric")
            func = (agg.get("func") or "SUM").upper()
            if not dim or not metric:
                return jsonify({"error": "Agg requires dim and metric."}), 400
            # Build a safe-ish aggregated query by wrapping the original SQL as a subquery
            agg_sql = f"SELECT {dim} AS dim, {func}({metric}) AS value FROM (\n{q.sql_text}\n) AS _t GROUP BY {dim} ORDER BY value DESC LIMIT 1000"
            res = execute_sql(src, agg_sql, params=user_params)
        else:
            res = execute_sql(src, q.sql_text, params=user_params)
    except QueryExecutionError as e:
        return jsonify({"error": str(e)}), 400
    # trim for safety
    rows = res.get("rows") or []
    if len(rows) > 5000:
        res["rows"] = rows[:5000]
    return jsonify(res)


@bp.route("/api/questions/<int:question_id>/viz", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def api_question_save_viz(question_id: int):
    _require_tenant()
    q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first_or_404()
    payload = request.get_json(silent=True) or {}
    cfg = payload.get("viz_config") or {}
    if cfg and not isinstance(cfg, dict):
        return jsonify({"error": "viz_config inválido."}), 400
    q.viz_config_json = cfg
    _audit("bi.question.viz.updated", {"id": q.id})
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/dashboards/<int:dashboard_id>/cards", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def api_dashboard_add_card(dashboard_id: int):
    _require_tenant()
    dash = Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.tenant.id).first_or_404()
    payload = request.get_json(silent=True) or {}
    try:
        qid = int(payload.get("question_id") or 0)
    except Exception:
        qid = 0
    if not qid:
        return jsonify({"error": "Pergunta inválida."}), 400
    q = Question.query.filter_by(id=qid, tenant_id=g.tenant.id).first_or_404()
    cfg = payload.get("viz_config") or {}
    if cfg and not isinstance(cfg, dict):
        return jsonify({"error": "viz_config inválido."}), 400

    # place at bottom (roughly)
    cards = DashboardCard.query.filter_by(dashboard_id=dash.id, tenant_id=g.tenant.id).all()
    max_y = 0
    for c in cards:
        pj = c.position_json or {}
        try:
            y = int(pj.get("y") or 0)
            h = int(pj.get("h") or 6)
        except Exception:
            y, h = 0, 6
        max_y = max(max_y, y + h)

    card = DashboardCard(
        tenant_id=g.tenant.id,
        dashboard_id=dash.id,
        question_id=q.id,
        position_json={"x": 0, "y": max_y, "w": 12, "h": 6},
        viz_config_json=cfg or {},
    )
    db.session.add(card)
    _audit("bi.dashboard.card.created", {"dashboard_id": dash.id, "card_id": None, "question_id": q.id})
    db.session.commit()
    return jsonify({"ok": True, "card_id": card.id})


@bp.route("/api/dashboards/<int:dashboard_id>/cards/<int:card_id>", methods=["DELETE"])
@login_required
@require_roles("tenant_admin", "creator")
def api_dashboard_delete_card(dashboard_id: int, card_id: int):
    _require_tenant()
    dash = Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.tenant.id).first_or_404()
    card = DashboardCard.query.filter_by(id=card_id, dashboard_id=dash.id, tenant_id=g.tenant.id).first_or_404()
    _audit("bi.dashboard.card.deleted", {"dashboard_id": dash.id, "card_id": card.id})
    db.session.delete(card)
    db.session.commit()
    return jsonify({"ok": True})

# -----------------------------
# Audit & Query Runs
# -----------------------------


@bp.route("/audit")
@login_required
@require_roles("tenant_admin", "creator")
def audit_list():
    _require_tenant()
    events = (
        AuditEvent.query.filter_by(tenant_id=g.tenant.id)
        .order_by(AuditEvent.created_at.desc())
        .limit(200)
        .all()
    )
    return render_template("portal/audit_list.html", tenant=g.tenant, events=events)


@bp.route("/runs")
@login_required
@require_roles("tenant_admin", "creator")
def runs_list():
    _require_tenant()
    runs = (
        QueryRun.query.filter_by(tenant_id=g.tenant.id)
        .order_by(QueryRun.started_at.desc())
        .limit(200)
        .all()
    )
    return render_template("portal/runs_list.html", tenant=g.tenant, runs=runs)



# -----------------------------
# Dashboard Layout API (Gridstack)
# -----------------------------


@bp.route("/api/dashboards/<int:dashboard_id>/layout", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def api_dashboard_layout(dashboard_id: int):
    _require_tenant()
    dash = Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.tenant.id).first_or_404()

    payload = request.get_json(silent=True) or {}
    items = payload.get("items") or []
    if not isinstance(items, list):
        return jsonify({"error": "Payload inválido."}), 400

    # Build map for faster validation
    cards = DashboardCard.query.filter_by(dashboard_id=dash.id, tenant_id=g.tenant.id).all()
    card_map = {c.id: c for c in cards}

    updated = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            cid = int(it.get("card_id") or 0)
            x = int(it.get("x") or 0)
            y = int(it.get("y") or 0)
            w = int(it.get("w") or 12)
            h = int(it.get("h") or 6)
        except Exception:
            continue
        c = card_map.get(cid)
        if not c:
            continue
        # Conservative bounds
        if w < 1: w = 1
        if w > 12: w = 12
        if h < 2: h = 2
        if h > 30: h = 30
        if x < 0: x = 0
        if x > 11: x = 11
        if y < 0: y = 0

        c.position_json = {"x": x, "y": y, "w": w, "h": h}
        updated += 1

    _audit("bi.dashboard.layout.updated", {"id": dash.id, "updated": updated})
    db.session.commit()
    return jsonify({"ok": True, "updated": updated})


# -----------------------------
# AI Assistant (Chat + analysis)
# -----------------------------


@bp.route("/ai")
@login_required
def ai_chat():
    _require_tenant()
    qs = Question.query.filter_by(tenant_id=g.tenant.id).order_by(Question.updated_at.desc()).all()
    return render_template("portal/ai_chat.html", tenant=g.tenant, questions=qs)


@bp.route("/api/ai/chat", methods=["POST"])
@login_required
def api_ai_chat():
    _require_tenant()
    payload = request.get_json(silent=True) or {}

    try:
        question_id = int(payload.get("question_id") or 0)
    except Exception:
        question_id = 0

    message = (payload.get("message") or "").strip()
    history = payload.get("history") or []
    params = payload.get("params") or {}

    if not question_id:
        return jsonify({"error": "Selecione uma pergunta."}), 400
    if not message:
        return jsonify({"error": "Mensagem vazia."}), 400
    if params and not isinstance(params, dict):
        return jsonify({"error": "Parâmetros devem ser um objeto JSON."}), 400
    if history and not isinstance(history, list):
        history = []

    q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=q.source_id, tenant_id=g.tenant.id).first_or_404()

    # Execute query (bounded)
    user_params: dict = {}
    if isinstance(params, dict):
        user_params.update(params)
    user_params["tenant_id"] = g.tenant.id

    try:
        res = execute_sql(src, q.sql_text, params=user_params)
    except QueryExecutionError as e:
        return jsonify({"error": str(e)}), 400

    # Keep payload light
    rows = res.get("rows") or []
    cols = res.get("columns") or []
    if len(rows) > 2000:
        rows = rows[:2000]

    # Quick profile (no heavy deps)
    profile = {"columns": [], "row_count": len(rows)}
    for i, c in enumerate(cols):
        col_vals = [r[i] for r in rows if isinstance(r, list) and i < len(r)]
        non_null = [v for v in col_vals if v is not None]
        sample = non_null[:10]
        # numeric?
        nums = []
        for v in non_null[:500]:
            try:
                nums.append(float(v))
            except Exception:
                pass
        col_info = {"name": str(c), "sample": sample}
        if len(nums) >= max(3, int(0.6 * min(500, len(non_null) or 1))):
            if nums:
                col_info.update({
                    "type": "number",
                    "min": min(nums),
                    "max": max(nums),
                    "avg": sum(nums) / len(nums),
                })
        else:
            col_info["type"] = "text"
            # top values (light)
            counts = {}
            for v in non_null[:1000]:
                sv = str(v)
                counts[sv] = counts.get(sv, 0) + 1
            top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:8]
            col_info["top"] = top
        profile["columns"].append(col_info)

    data_bundle = {
        "question": {"id": q.id, "name": q.name},
        "sql": q.sql_text,
        "params": {k: v for k, v in (params or {}).items()},
        "result": {
            "columns": cols,
            "rows_sample": rows[:200],
            "row_count": len(rows),
        },
        "profile": profile,
        "lang": getattr(g, "lang", None),
    }

    ai = analyze_with_ai(data_bundle, message, history=history, lang=getattr(g, "lang", None))
    return jsonify(ai)

@bp.get("/etls")
def etls_list():
    # List saved ETL workflows for the current tenant
    return render_template("portal/etls_list.html", title="ETLs")
