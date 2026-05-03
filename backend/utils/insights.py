def generate_lift_insight(current_session, prev_data):
    """
    Compare current session vs previous session data.
    current_session: dict with 'best_set' containing 'weight_kg' and 'reps'
    prev_data: dict with 'weight' and 'reps'
    Returns: (insight_text, emoji)
    """
    if not prev_data:
        return "New exercise logged — great start!", "🎉"
    
    current_best = current_session.get('best_set') or {}
    current_w = current_best.get('weight_kg')
    current_r = current_best.get('reps')
    prev_w = prev_data.get('weight')
    prev_r = prev_data.get('reps')

    if current_w and prev_w and current_r and prev_r:
        if current_w > prev_w and current_r >= prev_r:
            return "Stronger than last session", "🔥"
        elif current_w < prev_w and current_r > prev_r:
            return "Higher reps at lower weight — strong volume work", "💪"
        elif current_w > prev_w and current_r < prev_r:
            return "Heavier weight with fewer reps — building strength", "📈"
        elif current_w < prev_w and current_r <= prev_r:
            return "Last session was heavier - variation like this is normal, room to push next time", "💪"
        else:
            return "Consistent with last session — solid baseline", "✨"
    
    return "Consistent with last session — solid baseline", "✨"

def generate_run_insight(new_run, prev_enriched, fastest_ever):
    """
    Compare current run vs previous run.
    new_run: dict with 'pace_seconds_per_km'
    prev_enriched: dict with 'pace_seconds_per_km' or None
    fastest_ever: float or None
    Returns: (insight_text, emoji, is_pb)
    """
    is_pb = False
    curr_pace = new_run['pace_seconds_per_km']
    
    if not prev_enriched:
        insight = "First run logged — great start!"
        emoji = "🎉"
        if fastest_ever is None or curr_pace < fastest_ever:
            is_pb = True
        return insight, emoji, is_pb

    prev_pace = prev_enriched['pace_seconds_per_km']

    if curr_pace < prev_pace * 0.98:
        insight = "Faster than last run — great pace!"
        emoji = "🔥"
        if fastest_ever is None or curr_pace < fastest_ever:
            is_pb = True
            insight = "New pace PB — fastest run ever!"
            emoji = "🏆"
    elif curr_pace > prev_pace * 1.02:
        insight = "Recovery run or tough day? You got this"
        emoji = "💪"
    else:
        insight = "Consistent pace — solid baseline"
        emoji = "✨"
        
    return insight, emoji, is_pb
