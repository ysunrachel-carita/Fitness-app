from functools import wraps
from flask import session, redirect, url_for
from werkzeug.security import generate_password_hash
from datetime import datetime
from db import get_db

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def get_user(username):
    conn = get_db()
    try:
        return conn.execute("SELECT * FROM users WHERE username = %s", (username,)).fetchone()
    finally:
        conn.close()

def create_user(username, password):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name) VALUES (%s, %s, %s)",
            (username, generate_password_hash(password), username)
        )
        return get_user(username)
    finally:
        conn.close()

def validate_password_strength(password):
    # This matches the existing logic in app.py
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)
    
    if not has_upper:
        return False, "Password must include at least 1 uppercase letter"
    if not has_lower:
        return False, "Password must include at least 1 lowercase letter"
    if not has_digit:
        return False, "Password must include at least 1 number"
    if not has_special:
        return False, "Password must include at least 1 special character"
    
    return True, None
