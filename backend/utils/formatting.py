from datetime import date, datetime

def format_weight(value):
    if value is None:
        return "-"
    try:
        val = float(value)
        if val.is_integer():
            return str(int(val))
        return f"{val:.1f}"
    except (ValueError, TypeError):
        return str(value)

def format_rep_label(value):
    try:
        return 'rep' if int(value) == 1 else 'reps'
    except (ValueError, TypeError):
        return 'reps'

def format_set_label(value):
    try:
        return 'set' if int(value) == 1 else 'sets'
    except (ValueError, TypeError):
        return 'sets'

def format_short_date(value):
    if not value:
        return "-"
    if isinstance(value, (date, datetime)):
        return value.strftime("%b %d")

    date_value = str(value).split(' ')[0]
    try:
        return datetime.strptime(date_value, "%Y-%m-%d").strftime("%b %d")
    except (ValueError, TypeError):
        return date_value

def format_progress_date(value):
    if not value:
        return "-"
    date_value = str(value).split(' ')[0]
    try:
        parsed_date = datetime.strptime(date_value, "%Y-%m-%d")
        return f"{parsed_date.day} {parsed_date.strftime('%B %Y')}"
    except (ValueError, TypeError):
        return date_value

def _date_only(value):
    if not value:
        return "-"
    return str(value).split(' ')[0]

def format_pace(time_seconds, distance_km, unit='km'):
    if not distance_km or distance_km <= 0 or not time_seconds:
        return "-"
    
    total_minutes = time_seconds / 60
    pace_min_per_unit = total_minutes / distance_km
    
    minutes = int(pace_min_per_unit)
    seconds = int((pace_min_per_unit - minutes) * 60)
    return f"{minutes}:{seconds:02d} min/{unit}"

def format_duration(time_seconds):
    if not time_seconds:
        return "-"
    minutes = int(time_seconds // 60)
    seconds = int(time_seconds % 60)
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"

def format_distance(distance_km, unit='km'):
    if distance_km is None:
        return "-"
    if unit == 'miles':
        return f"{distance_km:.2f} mi"
    return f"{distance_km:.2f} km"

def _pace_seconds_per_km(time_seconds, distance_km):
    if not distance_km or distance_km <= 0:
        return 0
    return time_seconds / distance_km

def score_exercise(name, query):
    if not query:
        return 0
    name_n = canonical(name)
    query_n = canonical(query)
    
    if query_n == name_n:
        return 100
    if name_n.startswith(query_n):
        return 80
    if query_n in name_n:
        return 50
    return 0

def canonical(s):
    if not s:
        return ""
    return "".join(c for c in s.lower() if c.isalnum())
