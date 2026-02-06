from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

def create_app():
    app = Flask(__name__)

    # 🔑 Indispensable derrière Nginx + SSL
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_proto=1,
        x_host=1
    )

    app.config["PREFERRED_URL_SCHEME"] = "https"

    # blueprints, config, extensions…
    return app