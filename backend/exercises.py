from db import get_db
from utils.formatting import canonical

# ── Exercise Catalog ───────────────────────────────────────────────────────────
EXERCISES = {}
ALL_EXERCISES = []
CALORIE_EXERCISES = []

# canonical_key -> display_name, populated by load_exercises_from_db()
EXERCISE_BY_KEY = {}

EXERCISE_ALIASES = {
    'pullups': 'pull up',
    'pullup': 'pull up',
    'pull ups': 'pull up',
    'pushups': 'push up',
    'pushup': 'push up',
    'push ups': 'push up',
    'muscleups': 'muscle up',
    'muscleup': 'muscle up',
    'muscle ups': 'muscle up',
    'situps': 'sit up',
    'situp': 'sit up',
    'sit ups': 'sit up',
    'chest to bar': 'chest to bar pull up',
    'c2b': 'chest to bar pull up',
    't2b': 'toes to bar',
    'hspu': 'handstand push up',
    'double unders': 'double under',
    'dubs': 'double under',
    'burpees': 'burpee',
    'kb swing': 'kettlebell swing',
    'kb swings': 'kettlebell swing',
    'american kb swing': 'kettlebell swing',
    'box jumps': 'box jump',
    'wallballs': 'wall ball',
    'wallball': 'wall ball',
    'wall balls': 'wall ball',
    'db snatch': 'dumbbell snatch',
    'assault bike': 'echo bike',
    'bike': 'echo bike',
    'row': 'rowing',
    'ghd situps': 'ghd sit up',
    'ghd situp': 'ghd sit up'
}

def normalize(name):
    if not name:
        return ''
    return ' '.join(name.lower().strip().replace('-', ' ').replace('_', ' ').split())

def canonical_exercise_key(name):
    if not name:
        return ''
    normalized = normalize(name)
    if not normalized:
        return ''
    alias_target = EXERCISE_ALIASES.get(normalized)
    return normalize(alias_target) if alias_target else normalized

def _friendly_display_name(user_input):
    cleaned = normalize(user_input)
    if not cleaned:
        return None
    if cleaned in EXERCISE_ALIASES:
        return EXERCISE_ALIASES[cleaned].title()
    return user_input.title()

def normalize_exercise_input(user_input):
    if not user_input:
        return None
    key = canonical_exercise_key(user_input)
    if key in EXERCISE_BY_KEY:
        return EXERCISE_BY_KEY[key]
    return _friendly_display_name(user_input) or None

def load_exercises_from_db():
    global EXERCISE_BY_KEY, ALL_EXERCISES, CALORIE_EXERCISES, EXERCISES
    conn = get_db()
    try:
        by_key = {}
        all_names = []
        calorie_names = []
        by_category = {}

        rows = conn.execute(
            "SELECT name, category, canonical_key FROM exercises ORDER BY name"
        ).fetchall()

        for row in rows:
            name = row['name']
            category = row['category']
            key = row['canonical_key'] or canonical_exercise_key(name)
            
            by_key[key] = name
            all_names.append(name)
            if category.lower() == 'cardio':
                calorie_names.append(name)
            
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(name)

        EXERCISE_BY_KEY = by_key
        ALL_EXERCISES = all_names
        CALORIE_EXERCISES = calorie_names
        EXERCISES = by_category
        print(f"✅ Loaded {len(all_names)} exercises into cache.")
    except Exception as e:
        print(f"⚠️ Could not load exercise cache: {e}")
    finally:
        conn.close()

def resolve_exercise(conn, user_input):
    if not user_input:
        return None, None
    
    key = canonical_exercise_key(user_input)
    
    row = conn.execute(
        'SELECT id, name FROM exercises WHERE canonical_key = %s', (key,)
    ).fetchone()
    
    if row:
        return row['id'], row['name']
    
    insert_cursor = conn.execute(
        'INSERT INTO exercises (name, category, canonical_key) '
        'VALUES (%s, %s, %s) RETURNING id',
        (user_input.title(), 'Other', key)
    )
    new_id = insert_cursor.lastrowid
    
    # Refresh cache
    load_exercises_from_db()
    
    return new_id, user_input.title()

def populate_exercises_if_needed():
    conn = get_db()
    try:
        print("🌱 Seeding baseline exercises...")
        catalog = {
            'Legs': ['Squat', 'Deadlift', 'Lunge', 'Leg Press', 'Calf Raise'],
            'Chest': ['Bench Press', 'Incline Bench Press', 'Chest Fly'],
            'Back': ['Pull Up', 'Rowing', 'Lat Pulldown'],
            'Shoulders': ['Shoulder Press', 'Lateral Raise', 'Front Raise'],
            'Arms': ['Bicep Curl', 'Tricep Extension', 'Hammer Curl'],
            'Core': ['Plank', 'Sit Up', 'Toes To Bar', 'Leg Raise'],
            'Cardio': ['Running', 'Echo Bike', 'Rowing', 'Ski Erg', 'Burpee']
        }
        
        for category, names in catalog.items():
            for name in names:
                key = canonical_exercise_key(name)
                conn.execute(
                    "INSERT INTO exercises (name, category, canonical_key) "
                    "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (name, category, key)
                )
        conn.commit()
        print("✅ Baseline exercises seeded.")
        load_exercises_from_db()
    except Exception as e:
        print(f"⚠️ Error seeding exercises: {e}")
    finally:
        conn.close()

def get_all_exercises():
    return ALL_EXERCISES

def get_calorie_exercises():
    return CALORIE_EXERCISES

def get_exercises_by_category():
    return EXERCISES
