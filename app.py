import os
from flask import Flask, render_template

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")

    @app.route("/")
    def index():
        return render_template("index.html")

    # --- Projects / products ---
    @app.route("/projets/mobile")
    def projects_mobile():
        return render_template("projects_mobile.html")

    @app.route("/projets/iot")
    def projects_iot():
        return render_template("projects_iot.html")

    @app.route("/projets/belegal")
    def belegal():
        return render_template("belegal.html")

    @app.route("/bi/metabase")
    def metabase():
        return render_template("metabase.html")

    @app.route("/plans")
    def plans():
        return render_template("plans.html")

    @app.route("/left-sidebar")
    def left_sidebar():
        return render_template("left-sidebar.html")

    @app.route("/right-sidebar")
    def right_sidebar():
        return render_template("right-sidebar.html")

    @app.route("/no-sidebar")
    def no_sidebar():
        return render_template("no-sidebar.html")

    @app.route("/elements")
    def elements():
        return render_template("elements.html")

    return app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
