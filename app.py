import os

from flask import Flask

from models import User, db
from routes import main


def create_app():
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")
    db_url = os.environ.get("DATABASE_URL") or (
        "sqlite:///" + os.path.join(basedir, "feedback.db")
    )
    # Use the psycopg (v3) driver for PostgreSQL (Neon/Render); also fixes "postgres://" URLs.
    for prefix in ("postgres://", "postgresql://"):
        if db_url.startswith(prefix):
            db_url = "postgresql+psycopg://" + db_url[len(prefix):]
            break
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Reconnect cleanly when a cloud database drops idle connections.
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB upload limit

    db.init_app(app)
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()
        seed_admin()

    return app


def seed_admin():
    """Create the admin account on first run.

    If the ADMIN_PASSWORD environment variable is set, it is used instead of the
    default "admin123", and it also replaces the default password on an existing
    admin account. A password changed from the app itself is never overwritten.
    """
    password = os.environ.get("ADMIN_PASSWORD")
    admin = User.query.filter_by(role="admin").first()
    if admin is None:
        admin = User(name="Administrator", username="admin", role="admin")
        admin.set_password(password or "admin123")
        db.session.add(admin)
        db.session.commit()
    elif password and admin.check_password("admin123"):
        admin.set_password(password)
        db.session.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1")
