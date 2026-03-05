#!/usr/bin/env python3
"""Validate Audela Credit readiness.

Usage:
    /home/testuser/audela_flask_website/.venv/bin/python validate_credit_readiness.py
    /home/testuser/audela_flask_website/.venv/bin/python validate_credit_readiness.py --mode static
    /home/testuser/audela_flask_website/.venv/bin/python validate_credit_readiness.py --mode smoke
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""


class Checker:
    def __init__(self) -> None:
        self.results: list[Result] = []

    def run(self, name: str, fn: Callable[[], None]) -> None:
        try:
            fn()
            self.results.append(Result(name=name, ok=True))
            print(f"  [OK] {name}")
        except Exception as exc:  # pragma: no cover - diagnostics path
            self.results.append(Result(name=name, ok=False, detail=str(exc)))
            print(f"  [KO] {name}: {exc}")

    @property
    def has_failures(self) -> bool:
        return any(not r.ok for r in self.results)


def _print_header(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def _check_imports() -> None:
    from audela.models import (  # noqa: F401
        CreditApproval,
        CreditApprovalWorkflowStep,
        CreditAnalystFunction,
        CreditAnalystGroup,
        CreditAnalystGroupMember,
        CreditBorrower,
        CreditCollateral,
        CreditCollateralType,
        CreditCountry,
        CreditDeal,
        CreditDocument,
        CreditFacility,
        CreditFacilityType,
        CreditFinancialStatement,
        CreditGuaranteeType,
        CreditGuarantor,
        CreditMemo,
        CreditRating,
        CreditRatioSnapshot,
        CreditSector,
    )


def _check_credit_document_model_columns() -> None:
    from audela.models.credit import CreditDocument

    expected = {
        "tenant_id",
        "borrower_id",
        "deal_id",
        "memo_id",
        "title",
        "doc_type",
        "file_path",
        "uploaded_by_user_id",
        "created_at",
    }
    actual = {c.name for c in CreditDocument.__table__.columns}
    missing = sorted(expected - actual)
    if missing:
        raise AssertionError(f"missing columns: {missing}")


def _check_templates_exist() -> None:
    root = os.path.abspath(os.path.dirname(__file__))
    required = [
        "templates/credit/page_base.html",
        "templates/credit/overview.html",
        "templates/credit/borrowers.html",
        "templates/credit/deals.html",
        "templates/credit/facilities.html",
        "templates/credit/collateral.html",
        "templates/credit/guarantors.html",
        "templates/credit/financials.html",
        "templates/credit/ratios.html",
        "templates/credit/memos.html",
        "templates/credit/approvals.html",
        "templates/credit/approval_workflow.html",
        "templates/credit/documents.html",
        "templates/credit/references.html",
        "templates/credit/reports.html",
    ]
    missing = [p for p in required if not os.path.exists(os.path.join(root, p))]
    if missing:
        raise AssertionError(f"missing templates: {missing}")


def _check_i18n_keys() -> None:
    root = os.path.abspath(os.path.dirname(__file__))
    i18n_path = os.path.join(root, "audela", "i18n.py")
    with open(i18n_path, "r", encoding="utf-8") as f:
        content = f.read()

    required_literals = [
        "Audela Credit References",
        "Reference row updated.",
        "Browse",
        "Drop files here or click Browse.",
        "Pasta inválida.",
    ]
    missing = [literal for literal in required_literals if literal not in content]
    if missing:
        raise AssertionError(f"missing i18n literals: {missing}")


def _check_routes_registered() -> None:
    from audela import create_app

    app = create_app()
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    required = {
        "credit.overview",
        "credit.borrowers",
        "credit.deals",
        "credit.facilities",
        "credit.collateral",
        "credit.guarantors",
        "credit.financials",
        "credit.financials_import",
        "credit.ratios",
        "credit.references",
        "credit.references_save",
        "credit.references_delete",
        "credit.memos",
        "credit.approvals",
        "credit.approval_workflow",
        "credit.documents",
        "credit.documents_create_folder",
        "credit.documents_upload",
        "credit.documents_from_url",
        "credit.documents_from_s3",
        "credit.documents_download",
        "credit.documents_delete",
        "credit.documents_folders_delete",
        "credit.documents_rename",
        "credit.documents_folders_rename",
        "credit.documents_move",
        "credit.documents_folders_move",
        "credit.reports",
        "credit.reports_csv",
    }
    missing = sorted(required - endpoints)
    if missing:
        raise AssertionError(f"missing endpoints: {missing}")


def _run_smoke_scenario() -> None:
    from audela import create_app
    from audela.extensions import db
    from audela.models.bi import FileAsset, FileFolder
    from audela.models.core import Tenant, User
    from audela.models.credit import CreditDocument
    from audela.models.credit import (
        CreditApproval,
        CreditApprovalWorkflowStep,
        CreditAnalystFunction,
        CreditAnalystGroup,
        CreditBorrower,
        CreditFinancialStatement,
        CreditMemo,
    )
    from audela.models.subscription import SubscriptionPlan, TenantSubscription

    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    suffix = uuid.uuid4().hex[:8]
    tenant_slug = f"credit-smoke-{suffix}"
    user_email = f"credit-smoke-{suffix}@example.com"
    plan_code = f"credit_smoke_{suffix}"

    with app.app_context():
        tenant = Tenant(slug=tenant_slug, name=f"Credit Smoke {suffix}", settings_json={})
        db.session.add(tenant)
        db.session.flush()

        user = User(tenant_id=tenant.id, email=user_email, status="active")
        user.set_password("secret")
        db.session.add(user)

        plan = SubscriptionPlan(
            code=plan_code,
            name="Credit Smoke Plan",
            description="Readiness smoke",
            price_monthly=Decimal("0.00"),
            price_yearly=Decimal("0.00"),
            has_finance=False,
            has_bi=False,
            max_users=10,
            max_companies=10,
            max_transactions_per_month=-1,
            trial_days=30,
            is_active=True,
            is_public=False,
            features_json={"has_credit": True},
        )
        db.session.add(plan)
        db.session.flush()

        subscription = TenantSubscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status="active",
            current_period_start=datetime.utcnow() - timedelta(days=1),
            current_period_end=datetime.utcnow() + timedelta(days=30),
        )
        db.session.add(subscription)
        memo = CreditMemo(
            tenant_id=tenant.id,
            title="Smoke memo",
            recommendation="review",
            summary_text="smoke summary",
            ai_generated=False,
        )
        db.session.add(memo)
        borrower = CreditBorrower(tenant_id=tenant.id, name="Smoke Borrower")
        db.session.add(borrower)
        db.session.commit()

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True
            sess["tenant_id"] = tenant.id
            sess["tenant_slug"] = tenant.slug
            sess["lang"] = "fr"

        # Pages main flows
        r = client.get("/credit/overview")
        assert r.status_code == 200, f"overview status={r.status_code}"

        r = client.get("/credit/references")
        assert r.status_code == 200, f"references status={r.status_code}"

        r = client.get("/credit/approval-workflow")
        assert r.status_code == 200, f"approval workflow status={r.status_code}"

        r = client.post(
            "/credit/approval-workflow",
            data={"action": "create_group", "name": "Smoke Risk Team", "description": "smoke"},
            follow_redirects=False,
        )
        assert r.status_code in (302, 303), f"create group status={r.status_code}"

        group = CreditAnalystGroup.query.filter_by(tenant_id=tenant.id, name="Smoke Risk Team").first()
        assert group is not None, "analyst group not created"

        function_row = CreditAnalystFunction.query.filter_by(tenant_id=tenant.id, code="risk_manager").first()
        assert function_row is not None, "default analyst function not seeded"

        r = client.post(
            "/credit/approval-workflow",
            data={
                "action": "add_step",
                "stage": "risk_manager",
                "step_name": "Risk sign-off",
                "step_order": "4",
                "group_id": str(group.id),
                "function_id": str(function_row.id),
                "sla_days": "3",
                "is_required": "on",
            },
            follow_redirects=False,
        )
        assert r.status_code in (302, 303), f"add workflow step status={r.status_code}"

        step = CreditApprovalWorkflowStep.query.filter_by(
            tenant_id=tenant.id,
            step_name="Risk sign-off",
        ).first()
        assert step is not None, "workflow step not created"

        r = client.post(
            "/credit/approvals",
            data={
                "memo_id": str(memo.id),
                "workflow_step_id": str(step.id),
                "decision": "approved",
                "comments": "smoke approval",
            },
            follow_redirects=False,
        )
        assert r.status_code in (302, 303), f"approval submit status={r.status_code}"

        approval = CreditApproval.query.filter_by(tenant_id=tenant.id, memo_id=memo.id).order_by(CreditApproval.id.desc()).first()
        assert approval is not None, "approval row not created"
        assert approval.workflow_step_id == step.id, "workflow step link missing"
        assert approval.analyst_group_id == group.id, "analyst group link missing"
        assert approval.analyst_function == "risk_manager", "analyst function missing"

        csv_payload = (
            "borrower_id,period_label,fiscal_year,revenue,ebitda,total_debt,cash,net_income,spreading_status\n"
            f"{borrower.id},FY,2025,1000000,220000,500000,120000,95000,completed\n"
        )
        r = client.post(
            "/credit/financials/import",
            data={
                "analyst_user_id": str(user.id),
                "analyst_function_id": str(function_row.id),
                "file": (io.BytesIO(csv_payload.encode("utf-8")), "financials.csv"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert r.status_code in (302, 303), f"financial import status={r.status_code}"

        fs = CreditFinancialStatement.query.filter_by(tenant_id=tenant.id, borrower_id=borrower.id).first()
        assert fs is not None, "financial statement not imported"
        assert fs.analyst_user_id == user.id, "analyst user link missing"
        assert fs.analyst_function_id == function_row.id, "analyst function link missing"
        assert str(fs.import_source or "").startswith("csv:"), "import source missing"

        r = client.get("/credit/documents")
        assert r.status_code == 200, f"documents status={r.status_code}"

        r = client.post("/credit/documents/folders", data={"name": "smoke-folder"}, follow_redirects=False)
        assert r.status_code in (302, 303), f"create folder status={r.status_code}"

        root_folder = FileFolder.query.filter_by(tenant_id=tenant.id, parent_id=None, name="__credit_documents__").first()
        assert root_folder is not None, "root folder not created"

        folder = FileFolder.query.filter_by(tenant_id=tenant.id, parent_id=root_folder.id, name="smoke-folder").first()
        assert folder is not None, "child folder not created"

        upload_payload = {
            "folder_id": str(folder.id),
            "doc_type": "supporting",
            "display_name": "Smoke Upload",
            "file": (io.BytesIO(b"a,b\n1,2\n"), "smoke.csv"),
        }
        r = client.post(
            "/credit/documents/upload",
            data=upload_payload,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert r.status_code in (302, 303), f"upload status={r.status_code}"

        asset = FileAsset.query.filter_by(tenant_id=tenant.id).order_by(FileAsset.id.desc()).first()
        assert asset is not None, "asset not created"

        doc = CreditDocument.query.filter_by(tenant_id=tenant.id, file_path=asset.storage_path).first()
        assert doc is not None, "credit document row not created"

        r = client.post(f"/credit/documents/files/{asset.id}/rename", json={"name": "Renamed Smoke"})
        assert r.status_code == 200, f"rename file status={r.status_code}"

        r = client.post(f"/credit/documents/files/{asset.id}/move", json={"folder_id": ""})
        assert r.status_code == 200, f"move file status={r.status_code}"

        r = client.get(f"/credit/documents/files/{asset.id}/download")
        assert r.status_code == 200, f"download status={r.status_code}"

        r = client.post(f"/credit/documents/files/{asset.id}/delete", follow_redirects=False)
        assert r.status_code in (302, 303), f"delete file status={r.status_code}"

        r = client.post(f"/credit/documents/folders/{folder.id}/delete", follow_redirects=False)
        assert r.status_code in (302, 303), f"delete folder status={r.status_code}"

        remaining_assets = FileAsset.query.filter_by(tenant_id=tenant.id).count()
        assert remaining_assets == 0, f"remaining assets={remaining_assets}"

        # Cleanup test records
        CreditApproval.query.filter_by(tenant_id=tenant.id).delete(synchronize_session=False)
        CreditApprovalWorkflowStep.query.filter_by(tenant_id=tenant.id).delete(synchronize_session=False)
        CreditFinancialStatement.query.filter_by(tenant_id=tenant.id).delete(synchronize_session=False)
        CreditBorrower.query.filter_by(tenant_id=tenant.id, name="Smoke Borrower").delete(synchronize_session=False)
        CreditAnalystFunction.query.filter_by(tenant_id=tenant.id).delete(synchronize_session=False)
        CreditAnalystGroup.query.filter_by(tenant_id=tenant.id).delete(synchronize_session=False)
        CreditMemo.query.filter_by(tenant_id=tenant.id, title="Smoke memo").delete(synchronize_session=False)
        CreditDocument.query.filter_by(tenant_id=tenant.id).delete(synchronize_session=False)
        FileAsset.query.filter_by(tenant_id=tenant.id).delete(synchronize_session=False)
        FileFolder.query.filter_by(tenant_id=tenant.id).delete(synchronize_session=False)
        TenantSubscription.query.filter_by(tenant_id=tenant.id).delete(synchronize_session=False)
        User.query.filter_by(tenant_id=tenant.id, email=user_email).delete(synchronize_session=False)
        Tenant.query.filter_by(id=tenant.id).delete(synchronize_session=False)
        SubscriptionPlan.query.filter_by(code=plan_code).delete(synchronize_session=False)
        db.session.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Audela Credit readiness")
    parser.add_argument(
        "--mode",
        choices=("all", "static", "smoke"),
        default="all",
        help="Which checks to run",
    )
    args = parser.parse_args()

    checker = Checker()

    _print_header("AUDELA CREDIT - READINESS VALIDATION")

    if args.mode in ("all", "static"):
        _print_header("Static checks")
        checker.run("Model imports", _check_imports)
        checker.run("CreditDocument columns", _check_credit_document_model_columns)
        checker.run("Credit templates exist", _check_templates_exist)
        checker.run("Credit i18n keys", _check_i18n_keys)
        checker.run("Credit routes registered", _check_routes_registered)

    if args.mode in ("all", "smoke"):
        _print_header("Runtime smoke checks")
        checker.run("Credit smoke scenario", _run_smoke_scenario)

    _print_header("Summary")
    ok_count = len([r for r in checker.results if r.ok])
    ko_count = len([r for r in checker.results if not r.ok])
    print(f"Checks passed: {ok_count}")
    print(f"Checks failed: {ko_count}")

    if checker.has_failures:
        print("\nFailed checks:")
        for result in checker.results:
            if not result.ok:
                print(f"  - {result.name}: {result.detail}")
        return 1

    print("\nAll requested checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
