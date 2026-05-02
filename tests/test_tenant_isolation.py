import pytest

from audela import create_app
from audela.extensions import db
from audela.models.core import Tenant, User, Role
from audela.models.bi import Dashboard


@pytest.fixture()
def app():
    app = create_app()
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SECRET_KEY="test",
    )
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        # roles (idempotent in case startup already seeded records)
        existing = {r.code for r in Role.query.all()}
        for code in ["platform_admin", "tenant_admin", "creator", "viewer"]:
            if code not in existing:
                db.session.add(Role(code=code))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _mk_tenant_user(name: str, slug: str, email: str, pwd: str, role_code: str = "viewer"):
    tenant = Tenant(name=name, slug=slug)
    db.session.add(tenant)
    db.session.flush()
    user = User(tenant_id=tenant.id, email=email)
    user.set_password(pwd)
    role = Role.query.filter_by(code=role_code).first()
    if role is not None:
        user.roles.append(role)
    db.session.add(user)
    db.session.commit()
    return tenant, user


def test_user_cannot_access_other_tenant_dashboard(app, client):
    with app.app_context():
        t1, u1 = _mk_tenant_user("Tenant A", "a", "a@ex.com", "pw", role_code="tenant_admin")
        t2, u2 = _mk_tenant_user("Tenant B", "b", "b@ex.com", "pw")

        d2 = Dashboard(tenant_id=t2.id, name="B dashboard")
        db.session.add(d2)
        db.session.commit()

    # Login as tenant A
    login_resp = client.post(
        "/app/login",
        data={"tenant_slug": "a", "email": "a@ex.com", "password": "pw"},
        follow_redirects=False,
    )
    assert login_resp.status_code in {302, 303}

    # Must not expose tenant B dashboard content to tenant A.
    resp = client.get(f"/app/dashboards/{d2.id}")
    assert resp.status_code in {302, 404}
    assert b"B dashboard" not in resp.data
