from flask import Blueprint, request, session, redirect, url_for, render_template, flash, jsonify
from datetime import date
from db import get_db
from utils.auth import login_required
from services.run_service import log_run_service, get_user_runs

run_bp = Blueprint('run', __name__)

@run_bp.route('/log_run', methods=['GET', 'POST'])
@login_required
def log_run():
    user_id = session["user_id"]
    if request.method == 'POST':
        result, error = log_run_service(user_id, request.form)
        if error:
            flash(error, "error")
            return redirect(url_for('run.log_run'))

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            new_run = result['new_run']
            return jsonify({
                "success": True,
                "run": {
                    "id": new_run['id'],
                    "distance_display": new_run['distance_display'],
                    "duration_display": new_run['duration_display'],
                    "time_seconds": new_run['time_seconds'],
                    "pace_display": new_run['pace_display'],
                    "run_type": new_run.get('run_type', 'Run'),
                    "date": new_run['date'],
                    "notes": new_run['notes'] or '',
                    "pace_seconds_per_km": new_run['pace_seconds_per_km'],
                    "distance_km": new_run['distance_km'],
                },
                "previous": result['previous'],
                "insight": result['insight'],
                "emoji": result['emoji'],
                "is_pb": result['is_pb'],
            })
        flash("Run logged successfully!", "success")
        return redirect(url_for('run.log_run'))

    # GET
    all_enriched = get_user_runs(user_id)
    fastest_runs = sorted(all_enriched, key=lambda x: x['pace_seconds_per_km'])[:3]
    longest_runs = sorted(all_enriched, key=lambda x: (-x['distance_km'], x['time_seconds']))[:3]
    best_pace = fastest_runs[0]['pace_display'] if fastest_runs else '-'

    return render_template(
        'log_run.html',
        runs=all_enriched,
        fastest_runs=fastest_runs,
        longest_runs=longest_runs,
        total_runs=len(all_enriched),
        best_pace=best_pace,
        today_date=date.today().isoformat(),
        page='run'
    )

@run_bp.route('/runs/history')
@login_required
def run_history():
    user_id = session["user_id"]
    runs = get_user_runs(user_id)
    return render_template('runs_history.html', runs=runs, page='history')
