from flask import Blueprint, render_template, session, redirect, url_for, request, flash, jsonify
from datetime import date
from db import get_db
from utils.auth import login_required
from services.lift_service import fetch_user_sessions
from werkzeug.security import generate_password_hash

main_bp = Blueprint('main', __name__)

@main_bp.route('/ping')
def ping():
    return "pong"

@main_bp.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))

from services.dashboard_service import fetch_dashboard_activities

@main_bp.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    user_id = session["user_id"]
    
    # Unified timeline of activities
    activities, weekly_sessions = fetch_dashboard_activities(conn, user_id)
    
    conn.close()
    return render_template("dashboard.html", 
        display_name=session.get("username"),
        activities=activities,
        weekly_sessions=weekly_sessions,
        page='dashboard'
    )

@main_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    conn = get_db()
    user_id = session["user_id"]
    
    if request.method == "POST":
        display_name = request.form.get("display_name")
        weight = request.form.get("weight")
        weight_unit = request.form.get("weight_unit", "kg")
        height = request.form.get("height")
        height_unit = request.form.get("height_unit", "cm")
        goal = request.form.get("goal")
        freq = request.form.get("training_frequency", 3)
        
        # Check if profile exists
        existing = conn.execute("SELECT id FROM profiles WHERE user_id = %s", (user_id,)).fetchone()
        
        if existing:
            conn.execute("""
                UPDATE profiles SET 
                    display_name = %s, weight_display = %s, weight_unit = %s,
                    height_display = %s, height_unit = %s, goal = %s, 
                    training_frequency = %s
                WHERE user_id = %s
            """, (display_name, weight, weight_unit, height, height_unit, goal, freq, user_id))
        else:
            conn.execute("""
                INSERT INTO profiles (user_id, display_name, weight_display, weight_unit, height_display, height_unit, goal, training_frequency)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, display_name, weight, weight_unit, height, height_unit, goal, freq))
            
        conn.commit()
        # Update session display_name
        if display_name:
            session["display_name"] = display_name
            
        flash("Profile updated successfully!", "success")
        return redirect(url_for("main.profile"))

    # GET request
    profile_data = conn.execute("SELECT * FROM profiles WHERE user_id = %s", (user_id,)).fetchone()
    conn.close()
    
    return render_template("profile.html", 
        profile=profile_data or {}, 
        username=session.get("username"), 
        page='profile'
    )

@main_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm = request.form.get("confirm_password")
        
        if not new_password or new_password != confirm:
            flash("Passwords must match.", "error")
            return redirect(url_for("main.profile"))
            
        hashed = generate_password_hash(new_password)
        conn = get_db()
        conn.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hashed, session["user_id"]))
        conn.commit()
        conn.close()
        
        flash("Password updated!", "success")
        return redirect(url_for("main.profile"))
    return redirect(url_for("main.profile"))

@main_bp.route("/register-success")
def register_success():
    return render_template("register_success.html")

@main_bp.route("/wins")
@login_required
def wins():
    conn = get_db()
    user_id = session["user_id"]
    wins_rows = conn.execute("SELECT * FROM wins WHERE user_id = %s ORDER BY date DESC", (user_id,)).fetchall()
    
    # Simple grouping logic for the template
    from collections import defaultdict
    groups_dict = defaultdict(list)
    for w in wins_rows:
        groups_dict["All Wins"].append(w)
        
    groups = [{"label": k, "entries": v} for k, v in groups_dict.items()]
    
    conn.close()
    return render_template("wins.html", 
        groups=groups, 
        streak_count=len(wins_rows), # Simple streak for now
        today_str=date.today().isoformat(),
        page='wins'
    )

@main_bp.route("/wins/create", methods=["POST"])
@login_required
def create_win():
    content = request.form.get("entry")
    category = request.form.get("category", "PR")
    win_date = request.form.get("date", date.today().isoformat())
    
    if content:
        conn = get_db()
        conn.execute("INSERT INTO wins (user_id, content, date, category) VALUES (%s, %s, %s, %s)", 
                     (session["user_id"], content, win_date, category))
        conn.commit()
        conn.close()
        flash("Win logged!", "success")
    return redirect(url_for("main.wins"))

@main_bp.route("/wins/<int:win_id>/delete", methods=["POST"])
@login_required
def delete_win(win_id):
    conn = get_db()
    conn.execute("DELETE FROM wins WHERE id = %s AND user_id = %s", (win_id, session["user_id"]))
    conn.commit()
    conn.close()
    flash("Win deleted.", "success")
    return redirect(url_for("main.wins"))
