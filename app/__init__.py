# app/__init__.py
from flask import Flask
from werkzeug.security import generate_password_hash
from .config import Config
from .extensions import db, login_manager, mail
import os

# ================================================
# ⭐ ADD THIS
from flask_socketio import SocketIO
socketio = SocketIO(cors_allowed_origins="*")   # <--- GLOBAL
# ================================================


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ------------------------------------------------------
    # GOOGLE CLOUD TTS CREDENTIAL SETUP
    # ------------------------------------------------------
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"D:\HackOMandia\smart_pill_portal\google-tts-key.json"

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    # ================================================
    # ⭐ REGISTER SOCKET.IO WITH THE APP
    # ================================================
    socketio.init_app(app, cors_allowed_origins="*")   # <--- REQUIRED
    # ================================================

    # Login redirect setup
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    # Register Blueprints
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.admin import admin_bp
    from app.routes.doctor import doctor_bp
    from app.routes.patient import patient_bp
    from app.routes.device_api import device_api_bp
    app.register_blueprint(admin_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(device_api_bp)

    # Create database tables and default admin
    with app.app_context():
        from .models import User
        db.create_all()

        admin_username = "admin"
        admin = User.query.filter_by(username=admin_username).first()

        if not admin:
            admin_user = User(
                username=admin_username,
                name="Super Admin",
                email=None,
                password_hash=generate_password_hash("admin123"),
                role="admin",
                approved=True
            )
            db.session.add(admin_user)
            db.session.commit()
            print("✅ Default admin created:")
            print("   Username: admin")
            print("   Password: admin123")

        print("🚀 Smart Pill Dispenser Portal Initialized Successfully")

    return app
