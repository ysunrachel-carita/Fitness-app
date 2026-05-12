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
    
    from collections import OrderedDict
    grouped_runs = OrderedDict()
    for r in runs:
        date_str = r['date']
        # If it's a datetime object or string containing time, just get the date part
        if isinstance(date_str, str) and ' ' in date_str:
            date_str = date_str.split(' ')[0]
        elif hasattr(date_str, 'strftime'):
            date_str = date_str.strftime('%Y-%m-%d')
            
        if date_str not in grouped_runs:
            grouped_runs[date_str] = []
        grouped_runs[date_str].append(r)
        
    return render_template('runs_history.html', grouped=grouped_runs, current_range='', page='history')

@run_bp.route('/delete_run/<int:run_id>', methods=['POST'])
@login_required
def delete_run(run_id):
    conn = get_db()
    user_id = session["user_id"]
    
    # Check ownership
    run = conn.execute("SELECT id FROM runs WHERE id = %s AND user_id = %s", (run_id, user_id)).fetchone()
    if not run:
        conn.close()
        return jsonify({"success": False, "error": "Run not found"}), 404
        
    conn.execute("DELETE FROM runs WHERE id = %s", (run_id,))
    conn.commit()
    conn.close()
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True})
        
    flash("Run deleted", "success")
    return redirect(url_for('run.run_history'))

@run_bp.route('/runs/<int:run_id>/edit', methods=['POST'])
@login_required
def edit_run(run_id):
    conn = get_db()
    user_id = session["user_id"]
    
    # Check ownership
    run_row = conn.execute("SELECT id FROM runs WHERE id = %s AND user_id = %s", (run_id, user_id)).fetchone()
    if not run_row:
        conn.close()
        return jsonify({"success": False, "error": "Run not found"}), 404
        
    try:
        distance_raw = float(request.form.get('distance', 0))
        unit = request.form.get('unit', 'km')
        run_type = request.form.get('run_type', 'Run')
        dur_min = int(request.form.get('duration_minutes', 0))
        dur_sec = int(request.form.get('duration_seconds', 0))
        run_date = request.form.get('date')
        notes = request.form.get('notes')
        
        distance_km = distance_raw / 1.60934 if unit == 'mi' else distance_raw
        time_seconds = dur_min * 60 + dur_sec
        
        conn.execute("""
            UPDATE runs SET 
                distance_km = %s, time_seconds = %s, unit = %s, 
                run_type = %s, date = %s, notes = %s
            WHERE id = %s
        """, (distance_km, time_seconds, unit, run_type, run_date, notes, run_id))
        
        conn.commit()
        
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            # Re-fetch for enrichment
            updated = conn.execute("SELECT * FROM runs WHERE id = %s", (run_id,)).fetchone()
            from utils.progress_math import _enrich_run
            enriched = _enrich_run(dict(updated))
            return jsonify({"success": True, "run": enriched})
            
        flash("Run updated", "success")
        return redirect(url_for('run.run_history'))
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()
