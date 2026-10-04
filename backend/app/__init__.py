import os
from flask import Flask
from flask_cors import CORS
from app.config import Config
from app.models_db import db, AdminUser
from werkzeug.security import generate_password_hash

def create_app():
    app = Flask(__name__)
    CORS(app)  # Enable cross-origin requests from Vercel frontend
    app.config.from_object(Config)
    
    # Ensure instance folder exists for SQLite DB
    os.makedirs(app.config['INSTANCE_DIR'], exist_ok=True)
    
    # Initialize SQLAlchemy with app
    db.init_app(app)
    
    with app.app_context():
        # Create all database tables
        db.create_all()
        
        # Seed default admin user if it doesn't exist
        if not AdminUser.query.filter_by(username='admin').first():
            default_admin = AdminUser(
                username='admin',
                password_hash=generate_password_hash('admin123')
            )
            db.session.add(default_admin)
            db.session.commit()
            print("Default admin user seeded (admin / admin123).")
            
    # Register API blueprints
    from app.routes_api import api_bp
    app.register_blueprint(api_bp)
    
    # Setup middleware
    from app.middleware import init_middleware
    init_middleware(app)

    return app
