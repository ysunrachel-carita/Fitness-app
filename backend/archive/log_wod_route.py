@app.route('/log_wod', methods=['GET', 'POST'])
@login_required
def log_wod():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        wod_type = request.form.get("wod_type", "").strip()
        workout_text = request.form.get("workout_text", "").strip()
        result = request.form.get("result", "").strip()
        notes = request.form.get("notes", "").strip()

        # Validate required fields
        if not wod_type:
            return render_template("log_wod.html", error="WOD type is required")
        if not workout_text or not result:
            return render_template("log_wod.html", error="Workout description and result are required")

        # Get optional fields based on WOD type
        time_cap_minutes = request.form.get("time_cap_minutes", "").strip()
        emom_interval = request.form.get("emom_interval", "").strip()
        emom_duration = request.form.get("emom_duration", "").strip()

        # Validate required fields based on type
        if wod_type in ['AMRAP', 'For Time'] and not time_cap_minutes:
            return render_template("log_wod.html", error="Time cap is required for this WOD type")
        if wod_type == 'EMOM' and (not emom_interval or not emom_duration):
            return render_template("log_wod.html", error="EMOM interval and duration are required for this WOD type")

        conn = get_db()
        user_id = session["user_id"]
        date_str = request.form.get('date', '').strip()

        # Use submitted date or default to current date
        if date_str:
            entry_date = date_str
        else:
            entry_date = datetime.now().strftime('%Y-%m-%d')

        # Convert to integers if provided
        time_cap_val = int(time_cap_minutes) if time_cap_minutes else None
        emom_interval_val = int(emom_interval) if emom_interval else None
        emom_duration_val = int(emom_duration) if emom_duration else None

        conn.execute("""
            INSERT INTO wods (user_id, name, wod_type, workout_text, result, notes, date, time_cap_minutes, emom_interval, emom_duration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, name or None, wod_type, workout_text, result, notes or None, entry_date, time_cap_val, emom_interval_val, emom_duration_val))

        conn.commit()
        conn.close()

        flash("WOD logged successfully!", "success")
        return redirect(url_for('log_wod'))
    
    # GET request - show recent WODs
    conn = get_db()
    user_id = session["user_id"]
    
    cursor = conn.execute(
        'SELECT * FROM wods WHERE user_id = ? ORDER BY date DESC LIMIT 10', (user_id,)
    )
    wods = cursor.fetchall()
    
    conn.close()
    
    return render_template("log_wod.html", wods=wods, today_date=date.today().isoformat())
