from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # Register blueprints
    from app.views.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Home route blueprint
    from app.views.home import home_bp
    app.register_blueprint(home_bp)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import Admin
        return Admin.query.get(int(user_id))

    return app