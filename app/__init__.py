import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate  # <-- 1. IMPORT MIGRATE

db = SQLAlchemy()
migrate = Migrate()  # <-- 2. CREATE THE MIGRATE INSTANCE
login_manager = LoginManager()
login_manager.login_view = 'main.admin_login'
login_manager.login_message_category = 'info'

def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__)

    # --- Configuration ---
    app.config['SECRET_KEY'] = 'a-very-secret-key-that-should-be-changed'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:Thete%40123@localhost/inventory_db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # --- Configuration for File Uploads ---
    UPLOAD_FOLDER = os.path.join(app.root_path, 'static/uploads')
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)


    # --- Initialize Extensions ---
    db.init_app(app)
    migrate.init_app(app, db)  # <-- 3. INITIALIZE MIGRATE
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

    # <-- 4. REMOVED the `with app.app_context(): db.create_all()` block

    return app