import json

def _clean_text_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    return value

def _extract_session_payload(req):
    """Unified extractor for both JSON (frontend) and Form (classic templates)."""
    if req.is_json:
        payload = req.get_json()
        exercise = _clean_text_value(payload.get('exercise'))
        date_str = _clean_text_value(payload.get('date'))
        notes = _clean_text_value(payload.get('notes'))
        unit = _clean_text_value(payload.get('unit')) or 'kg'
        sets = payload.get('sets', [])
    else:
        exercise = _clean_text_value(req.form.get('exercise'))
        date_str = _clean_text_value(req.form.get('date'))
        notes = _clean_text_value(req.form.get('notes'))
        unit = _clean_text_value(req.form.get('unit', 'kg')) or 'kg'
        sets_json = req.form.get('sets', '[]')
        try:
            sets = json.loads(sets_json)
        except (ValueError, TypeError):
            sets = []
            
        # Fallback for standard HTML form arrays
        if not sets:
            weights = req.form.getlist('weight_kg[]')
            reps = req.form.getlist('reps[]')
            print(f"DEBUG - weights list: {weights}, reps list: {reps}")
            for w, r in zip(weights, reps):
                if w and r:
                    sets.append({'weight_kg': w, 'reps': r})

    payload = {
        'exercise': exercise,
        'date': date_str,
        'notes': notes,
        'unit': unit,
        'sets': sets
    }
    print(f"DEBUG - Extracted payload: {payload}")
    return payload
