from __future__ import annotations

import click
from flask.cli import with_appcontext

from audela.extensions import db
from audela.models import Role, Tenant, User


@click.group()
def admin():
    """Admin and platform user management commands."""


@admin.command("createsuperuser")
@click.option("--identifier", prompt=True, help="Admin identifier (stored in users.email, e.g. admin_user)")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Superuser password")
@click.option("--tenant-slug", default="platform-admin", show_default=True, help="Platform admin tenant slug")
@click.option("--tenant-name", default="Platform Admin", show_default=True, help="Platform admin tenant name")
@click.option("--update-existing/--no-update-existing", default=True, show_default=True, help="Update password if user already exists")
@with_appcontext
def createsuperuser(
    identifier: str,
    password: str,
    tenant_slug: str,
    tenant_name: str,
    update_existing: bool,
):
    """Create or update a platform superuser using the configured DB connection."""

    identifier = (identifier or "").strip().lower()
    tenant_slug = (tenant_slug or "platform-admin").strip().lower()
    tenant_name = (tenant_name or "Platform Admin").strip()

    if not identifier:
        raise click.ClickException("Identifier is required")

    if len(password or "") < 12:
        raise click.ClickException("Password must be at least 12 characters")

    # Ensure platform admin tenant exists.
    tenant = Tenant.query.filter_by(slug=tenant_slug).first()
    if not tenant:
        tenant = Tenant(slug=tenant_slug, name=tenant_name, plan="enterprise", settings_json={})
        db.session.add(tenant)
        db.session.flush()

    # Ensure role exists.
    role = Role.query.filter_by(code="platform_admin").first()
    if not role:
        role = Role(code="platform_admin", description="Super administrateur plateforme")
        db.session.add(role)
        db.session.flush()

    user = User.query.filter_by(tenant_id=tenant.id, email=identifier).first()

    created = False
    if user is None:
        user = User(tenant_id=tenant.id, email=identifier, status="active")
        user.set_password(password)
        user.roles.append(role)
        db.session.add(user)
        created = True
    else:
        if not update_existing:
            raise click.ClickException(
                f"User '{identifier}' already exists in tenant '{tenant_slug}'. Use --update-existing to rotate password."
            )
        user.set_password(password)
        user.status = "active"
        if not user.has_role("platform_admin"):
            user.roles.append(role)

    db.session.commit()

    action = "created" if created else "updated"
    click.secho(f"Superuser {action} successfully.", fg="green")
    click.echo(f"Tenant: {tenant.slug} (id={tenant.id})")
    click.echo(f"Identifier: {user.email}")
    click.echo(f"User ID: {user.id}")


def init_admin_cli(app):
    """Register admin commands with Flask app."""
    app.cli.add_command(admin)
