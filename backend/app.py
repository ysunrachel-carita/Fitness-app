import os
from dotenv import load_dotenv
from flask import Flask
from db import init_db
from exercises import populate_exercises_if_needed, load_exercises_from_db

load_dotenv(os.path.join(os.path.dirname(__file__), '.env')) # Load variables from .env in the backend folder

# Import Blueprints
from routes.auth_routes import auth_bp
from routes.main_routes import main_bp
from routes.lift_routes import lift_bp
from routes.workout_routes import workout_bp
from routes.run_routes import run_bp
from routes.progress_routes import progress_bp

def create_app():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    template_dir = os.path.abspath(os.path.join(base_dir, '..', 'frontend', 'templates'))
    static_dir = os.path.abspath(os.path.join(base_dir, '..', 'frontend', 'static'))
    
    import sys, os
    print("\n" + "="*40, file=sys.stderr)
    print("CRITICAL SERVER PATH DIAGNOSTIC", file=sys.stderr)
    print(f"base_dir: {base_dir}", file=sys.stderr)
    print(f"template_dir expected: {template_dir}", file=sys.stderr)
    print(f"Does template_dir exist?: {os.path.exists(template_dir)}", file=sys.stderr)
    parent_dir = os.path.abspath(os.path.join(base_dir, '..'))
    print(f"Contents of {parent_dir}:", file=sys.stderr)
    try:
        print(os.listdir(parent_dir), file=sys.stderr)
    except Exception as e:
        print(f"Error reading parent: {e}", file=sys.stderr)
    print("="*40 + "\n", file=sys.stderr)
    
    app = Flask(__name__, 
                template_folder=template_dir,
                static_folder=static_dir)
    
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-123")
    
    # Initialize Database
    with app.app_context():
        init_db()
        populate_exercises_if_needed()
        load_exercises_from_db()

    # Register Template Filters
    from utils.formatting import (
        format_weight, format_short_date, format_progress_date,
        format_duration, format_distance, format_pace,
        format_rep_label, format_set_label
    )
    app.jinja_env.filters['format_weight'] = format_weight
    app.jinja_env.filters['format_short_date'] = format_short_date
    app.jinja_env.filters['format_progress_date'] = format_progress_date
    app.jinja_env.filters['format_duration'] = format_duration
    app.jinja_env.filters['format_distance'] = format_distance
    app.jinja_env.filters['format_pace'] = format_pace
    app.jinja_env.filters['format_rep_label'] = format_rep_label
    app.jinja_env.filters['format_set_label'] = format_set_label

    # Context Processor for Global Variables
    @app.context_processor
    def inject_user():
        from flask import session
        return {
            'display_name': session.get('username', 'User'),
            'profile_photo': session.get('profile_photo')
        }

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(lift_bp)
    app.register_blueprint(workout_bp)
    app.register_blueprint(run_bp)
    app.register_blueprint(progress_bp)

    return app

app = create_app()

if __name__ == "__main__":
    # Use environment variable for debug mode, defaulting to False for safety
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() in ("true", "1")
    app.run(debug=debug_mode, port=5000)