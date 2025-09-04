# FILE: app/__init__.py
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'main.admin_login'
login_manager.login_message_category = 'info'

def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__)

    # --- Configuration ---
    # CORRECTED: Load secrets from environment variables for security
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-very-secret-key-that-should-be-changed')

    # CORRECTED: Load database URI from environment variable for deployment,
    # with a fallback for local development.
    database_uri = os.environ.get('DATABASE_URL')
    if not database_uri:
        database_uri = 'mysql+pymysql://root:Thete%40123@localhost/inventory_db'
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # --- Configuration for File Uploads ---
    UPLOAD_FOLDER = os.path.join(app.root_path, 'static/uploads')
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)


    # --- Initialize Extensions ---
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # --- Make functions and classes available in all templates ---
    from .models import Customer, AdminUser
    @app.context_processor
    def inject_global_vars():
        return dict(isinstance=isinstance, Customer=Customer, AdminUser=AdminUser)


    # --- Register Blueprints ---
    from .main.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .admin.routes import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')

    return app