import os

from flask import Flask

from models import User, db
from routes import main


def create_app():
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(basedir, "feedback.db")
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB upload limit

    db.init_app(app)
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()
        seed_admin()

    return app


def seed_admin():
    """Create the default admin account on first run."""
    if not User.query.filter_by(role="admin").first():
        admin = User(name="Administrator", username="admin", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
