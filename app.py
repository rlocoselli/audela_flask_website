"""Flask entrypoint.

Important:
This project uses the application factory defined in `audela.create_app`.
Keeping this file as a thin wrapper ensures Flask CLI commands (e.g. migrations)
work when you run:

  flask --app app db upgrade

or:

  python -m flask --app app db upgrade
"""

from werkzeug.middleware.proxy_fix import ProxyFix

from audela import create_app as _create_app


def create_app():
    app = _create_app()

    # Useful behind a reverse proxy (Nginx/Traefik) + TLS termination.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    app.config.setdefault("PREFERRED_URL_SCHEME", "https")
    return app


# Expose an `app` variable for servers that don't support factories.
app = create_app()
