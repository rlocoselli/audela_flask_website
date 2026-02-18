from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_mail import Mail


# Prevent instances from being expired after commit to avoid detached-instance surprises
# during tests and request handling where objects may be used after session commits.
db = SQLAlchemy(session_options={"expire_on_commit": False})
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
mail = Mail()
