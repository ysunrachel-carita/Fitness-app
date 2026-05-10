def generate_lift_insight(current_session, is_pr, is_first_time=False):
    """
    Generate a simple insight for a lift session.
    """
    if is_first_time:
        return "New exercise logged — great start!", "🎉"
    if is_pr:
        return "New Personal Record! You're getting stronger.", "🏆"
    return "Lift logged successfully", "✅"

def generate_run_insight(new_run, is_pb, is_first_run=False):
    """
    Generate a simple insight for a run.
    """
    if is_first_run:
        return "First run logged — great start!", "🎉"
    if is_pb:
        return "New Personal Best! Fastest pace ever.", "🏆"
    return "Run logged successfully", "✅"
