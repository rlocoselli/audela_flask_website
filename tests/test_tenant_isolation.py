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
        db.create_all()
        # roles
        for code in ["platform_admin", "tenant_admin", "creator", "viewer"]:
            db.session.add(Role(code=code))
        db.session.commit()
        yield app
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _mk_tenant_user(name: str, slug: str, email: str, pwd: str):
    tenant = Tenant(name=name, slug=slug)
    db.session.add(tenant)
    db.session.flush()
    user = User(tenant_id=tenant.id, email=email)
    user.set_password(pwd)
    user.roles.append(Role.query.filter_by(code="viewer").first())
    db.session.add(user)
    db.session.commit()
    return tenant, user


def test_user_cannot_access_other_tenant_dashboard(app, client):
    with app.app_context():
        t1, u1 = _mk_tenant_user("Tenant A", "a", "a@ex.com", "pw")
        t2, u2 = _mk_tenant_user("Tenant B", "b", "b@ex.com", "pw")

        d2 = Dashboard(tenant_id=t2.id, name="B dashboard")
        db.session.add(d2)
        db.session.commit()

    # Login as tenant A
    client.post("/app/login", data={"tenant_slug": "a", "email": "a@ex.com", "password": "pw"})

    # Must return 404 (not 200) to avoid leaking dashboard existence across tenants
    resp = client.get(f"/app/dashboards/{d2.id}")
    assert resp.status_code == 404
