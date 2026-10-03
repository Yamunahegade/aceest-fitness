"""ACEest Fitness & Gym - Flask API.

Ported from the Tkinter desktop versions (v1.0 -> v3.2.4) so the same business
logic (programs, calorie estimates, progress, workouts, metrics, BMI,
program generator, membership) can run headless in Docker / CI.
"""
import os
import random
import sqlite3
from datetime import date, datetime

from flask import Flask, g, jsonify, request

DEFAULT_DB = os.environ.get("ACEEST_DB", "aceest_fitness.db")

# ---------------------------------------------------------------- domain data
PROGRAMS = {
    "Fat Loss (FL) - 3 day": {"factor": 22, "desc": "3-day full-body fat loss"},
    "Fat Loss (FL) - 5 day": {"factor": 24, "desc": "5-day split, higher volume fat loss"},
    "Muscle Gain (MG) - PPL": {"factor": 35, "desc": "Push/Pull/Legs hypertrophy"},
    "Beginner (BG)": {"factor": 26, "desc": "3-day simple beginner full-body"},
}
DEFAULT_FACTOR = 25
PROGRAM_TEMPLATES = {
    "Fat Loss": ["Full Body HIIT", "Circuit Training", "Cardio + Weights"],
    "Muscle Gain": ["Push/Pull/Legs", "Upper/Lower Split", "Full Body Strength"],
    "Beginner": ["Full Body 3x/week", "Light Strength + Mobility"],
}
WORKOUT_TYPES = ["Strength", "Hypertrophy", "Conditioning", "Mixed", "Mobility"]
MEMBERSHIP_STATUSES = ["Active", "Inactive", "Expired"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    age INTEGER, height REAL, weight REAL,
    program TEXT, calories INTEGER,
    target_weight REAL, target_adherence INTEGER,
    membership_status TEXT DEFAULT 'Active', membership_end TEXT,
    generated_plan TEXT
);
CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT, week TEXT, adherence INTEGER
);
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT, date TEXT, workout_type TEXT,
    duration_min INTEGER, notes TEXT
);
CREATE TABLE IF NOT EXISTS exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER, name TEXT, sets INTEGER, reps INTEGER, weight REAL
);
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT, date TEXT, weight REAL, waist REAL, bodyfat REAL
);
"""


# ----------------------------------------------------------- pure logic (unit-testable)
def calculate_calories(weight_kg, program):
    """Estimated daily kcal = weight x program factor (None if no weight)."""
    if not weight_kg or weight_kg <= 0:
        return None
    factor = PROGRAMS.get(program, {}).get("factor", DEFAULT_FACTOR)
    return int(weight_kg * factor)


def calculate_bmi(weight_kg, height_cm):
    if weight_kg <= 0 or height_cm <= 0:
        raise ValueError("weight and height must be positive")
    return round(weight_kg / ((height_cm / 100.0) ** 2), 1)


def bmi_info(bmi):
    """Return (category, risk note) for a BMI value."""
    if bmi < 18.5:
        return "Underweight", "Potential nutrient deficiency, low energy."
    if bmi < 25:
        return "Normal", "Low risk if active and strong."
    if bmi < 30:
        return "Overweight", "Moderate risk; focus on adherence and progressive activity."
    return "Obese", "Higher risk; prioritize fat loss, consistency, and supervision."


def program_category(program):
    """Map a stored program name to a template category (or None)."""
    if not program:
        return None
    if program.startswith("Fat Loss"):
        return "Fat Loss"
    if program.startswith("Muscle Gain"):
        return "Muscle Gain"
    if program.startswith("Beginner"):
        return "Beginner"
    return None


def generate_program(category=None, rng=random):
    if category not in PROGRAM_TEMPLATES:
        category = rng.choice(sorted(PROGRAM_TEMPLATES))
    return category, rng.choice(PROGRAM_TEMPLATES[category])


def current_week_label(now=None):
    return (now or datetime.now()).strftime("Week %U - %Y")


def valid_date(text):
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return True
    except (TypeError, ValueError):
        return False


def positive_or_none(value):
    """Return a positive float, None for empty/zero, raise ValueError if invalid."""
    if value in (None, "", 0):
        return None
    number = float(value)
    if number < 0:
        raise ValueError("negative value")
    return number or None


# ------------------------------------------------------------------- app factory
def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or DEFAULT_DB

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB_PATH"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with sqlite3.connect(app.config["DB_PATH"]) as conn:
        conn.executescript(SCHEMA)

    def err(message, code=400):
        return jsonify(error=message), code

    def find_client(name):
        return get_db().execute("SELECT * FROM clients WHERE name=?", (name,)).fetchone()

    def client_json(row):
        data = dict(row)
        data.pop("id", None)
        return data

    def parse_client_fields(data):
        try:
            return {
                "age": int(positive_or_none(data.get("age")) or 0) or None,
                "height": positive_or_none(data.get("height")),
                "weight": positive_or_none(data.get("weight")),
                "target_weight": positive_or_none(data.get("target_weight")),
                "target_adherence":
                    int(positive_or_none(data.get("target_adherence")) or 0) or None,
            }
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------- basic routes
    @app.route("/")
    def home():
        return jsonify(service="ACEest Fitness & Gym", status="running")

    @app.route("/health")
    def health():
        return jsonify(status="healthy")

    @app.route("/programs")
    def programs():
        return jsonify(PROGRAMS)

    # ------------------------------------------------------------------ clients
    @app.route("/clients", methods=["GET"])
    def list_clients():
        rows = get_db().execute("SELECT * FROM clients ORDER BY name").fetchall()
        return jsonify([client_json(r) for r in rows])

    @app.route("/clients", methods=["POST"])
    def create_client():
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        program = data.get("program")
        if not name:
            return err("name is required")
        if program not in PROGRAMS:
            return err(f"program must be one of {list(PROGRAMS)}")
        fields = parse_client_fields(data)
        if fields is None:
            return err("age, height, weight and targets must be non-negative numbers")
        if find_client(name):
            return err("client already exists", 409)
        db = get_db()
        db.execute(
            "INSERT INTO clients (name, age, height, weight, program, calories,"
            " target_weight, target_adherence) VALUES (?,?,?,?,?,?,?,?)",
            (name, fields["age"], fields["height"], fields["weight"], program,
             calculate_calories(fields["weight"], program),
             fields["target_weight"], fields["target_adherence"]),
        )
        db.commit()
        return jsonify(client_json(find_client(name))), 201

    @app.route("/clients/<name>", methods=["GET"])
    def get_client(name):
        row = find_client(name)
        return jsonify(client_json(row)) if row else err("client not found", 404)

    @app.route("/clients/<name>", methods=["PUT"])
    def update_client(name):
        row = find_client(name)
        if not row:
            return err("client not found", 404)
        data = request.get_json(silent=True) or {}
        program = data.get("program", row["program"])
        if program not in PROGRAMS:
            return err(f"program must be one of {list(PROGRAMS)}")
        merged = {k: data.get(k, row[k]) for k in
                  ("age", "height", "weight", "target_weight", "target_adherence")}
        fields = parse_client_fields(merged)
        if fields is None:
            return err("age, height, weight and targets must be non-negative numbers")
        db = get_db()
        db.execute(
            "UPDATE clients SET age=?, height=?, weight=?, program=?, calories=?,"
            " target_weight=?, target_adherence=? WHERE name=?",
            (fields["age"], fields["height"], fields["weight"], program,
             calculate_calories(fields["weight"], program),
             fields["target_weight"], fields["target_adherence"], name),
        )
        db.commit()
        return jsonify(client_json(find_client(name)))

    @app.route("/clients/<name>", methods=["DELETE"])
    def delete_client(name):
        if not find_client(name):
            return err("client not found", 404)
        db = get_db()
        db.execute("DELETE FROM exercises WHERE workout_id IN"
                   " (SELECT id FROM workouts WHERE client_name=?)", (name,))
        for table in ("workouts", "progress", "metrics"):
            db.execute(f"DELETE FROM {table} WHERE client_name=?", (name,))
        db.execute("DELETE FROM clients WHERE name=?", (name,))
        db.commit()
        return "", 204

    # ----------------------------------------------------------------- progress
    @app.route("/clients/<name>/progress", methods=["POST"])
    def add_progress(name):
        if not find_client(name):
            return err("client not found", 404)
        data = request.get_json(silent=True) or {}
        adherence = data.get("adherence")
        if isinstance(adherence, bool) or not isinstance(adherence, int) \
                or not 0 <= adherence <= 100:
            return err("adherence must be an integer between 0 and 100")
        week = data.get("week") or current_week_label()
        db = get_db()
        db.execute("INSERT INTO progress (client_name, week, adherence) VALUES (?,?,?)",
                   (name, week, adherence))
        db.commit()
        return jsonify(week=week, adherence=adherence), 201

    @app.route("/clients/<name>/progress", methods=["GET"])
    def get_progress(name):
        if not find_client(name):
            return err("client not found", 404)
        rows = get_db().execute(
            "SELECT week, adherence FROM progress WHERE client_name=? ORDER BY id", (name,))
        return jsonify([dict(r) for r in rows])

    # ----------------------------------------------------------------- workouts
    @app.route("/clients/<name>/workouts", methods=["POST"])
    def add_workout(name):
        if not find_client(name):
            return err("client not found", 404)
        data = request.get_json(silent=True) or {}
        w_date = data.get("date") or date.today().isoformat()
        w_type = data.get("workout_type")
        duration = data.get("duration_min", 60)
        exercises = data.get("exercises") or []
        if not valid_date(w_date):
            return err("date must be YYYY-MM-DD")
        if w_type not in WORKOUT_TYPES:
            return err(f"workout_type must be one of {WORKOUT_TYPES}")
        if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0:
            return err("duration_min must be a positive integer")
        if not isinstance(exercises, list) or any(
                not isinstance(e, dict) or not e.get("name") for e in exercises):
            return err("each exercise needs a name")
        db = get_db()
        cur = db.execute(
            "INSERT INTO workouts (client_name, date, workout_type, duration_min, notes)"
            " VALUES (?,?,?,?,?)", (name, w_date, w_type, duration, data.get("notes", "")))
        for ex in exercises:
            db.execute(
                "INSERT INTO exercises (workout_id, name, sets, reps, weight) VALUES (?,?,?,?,?)",
                (cur.lastrowid, ex["name"], ex.get("sets", 3), ex.get("reps", 10),
                 ex.get("weight", 0.0)))
        db.commit()
        return jsonify(id=cur.lastrowid, date=w_date, workout_type=w_type,
                       duration_min=duration, exercises=len(exercises)), 201

    @app.route("/clients/<name>/workouts", methods=["GET"])
    def workout_history(name):
        if not find_client(name):
            return err("client not found", 404)
        db = get_db()
        rows = db.execute(
            "SELECT id, date, workout_type, duration_min, notes FROM workouts"
            " WHERE client_name=? ORDER BY date DESC, id DESC", (name,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["exercises"] = [dict(e) for e in db.execute(
                "SELECT name, sets, reps, weight FROM exercises WHERE workout_id=?",
                (row["id"],))]
            result.append(item)
        return jsonify(result)

    # ------------------------------------------------------------------ metrics
    @app.route("/clients/<name>/metrics", methods=["POST"])
    def add_metrics(name):
        row = find_client(name)
        if not row:
            return err("client not found", 404)
        data = request.get_json(silent=True) or {}
        m_date = data.get("date") or date.today().isoformat()
        if not valid_date(m_date):
            return err("date must be YYYY-MM-DD")
        try:
            weight = positive_or_none(data.get("weight"))
            waist = positive_or_none(data.get("waist"))
            bodyfat = positive_or_none(data.get("bodyfat"))
        except (TypeError, ValueError):
            return err("weight, waist and bodyfat must be non-negative numbers")
        db = get_db()
        db.execute("INSERT INTO metrics (client_name, date, weight, waist, bodyfat)"
                   " VALUES (?,?,?,?,?)", (name, m_date, weight, waist, bodyfat))
        if weight:  # keep the client's current weight / calories in sync (as in v2.2+)
            db.execute("UPDATE clients SET weight=?, calories=? WHERE name=?",
                       (weight, calculate_calories(weight, row["program"]), name))
        db.commit()
        return jsonify(date=m_date, weight=weight, waist=waist, bodyfat=bodyfat), 201

    @app.route("/clients/<name>/metrics", methods=["GET"])
    def get_metrics(name):
        if not find_client(name):
            return err("client not found", 404)
        rows = get_db().execute(
            "SELECT date, weight, waist, bodyfat FROM metrics WHERE client_name=?"
            " ORDER BY date", (name,))
        return jsonify([dict(r) for r in rows])

    # ------------------------------------------------------- analytics / summary
    @app.route("/clients/<name>/bmi")
    def client_bmi(name):
        row = find_client(name)
        if not row:
            return err("client not found", 404)
        if not row["height"] or not row["weight"]:
            return err("height and weight are required to compute BMI")
        bmi = calculate_bmi(row["weight"], row["height"])
        category, risk = bmi_info(bmi)
        return jsonify(bmi=bmi, category=category, risk=risk)

    @app.route("/clients/<name>/summary")
    def client_summary(name):
        row = find_client(name)
        if not row:
            return err("client not found", 404)
        db = get_db()
        count, avg = db.execute(
            "SELECT COUNT(*), AVG(adherence) FROM progress WHERE client_name=?",
            (name,)).fetchone()
        last = db.execute(
            "SELECT date, weight, waist, bodyfat FROM metrics WHERE client_name=?"
            " ORDER BY date DESC, id DESC LIMIT 1", (name,)).fetchone()
        return jsonify(
            profile=client_json(row),
            program_notes=PROGRAMS.get(row["program"], {}).get("desc", ""),
            goals={"target_weight": row["target_weight"],
                   "target_adherence": row["target_adherence"]},
            progress={"weeks_logged": count,
                      "average_adherence": round(avg, 1) if avg is not None else 0},
            last_metrics=dict(last) if last else None,
        )

    @app.route("/clients/<name>/generate-program", methods=["POST"])
    def generate_client_program(name):
        row = find_client(name)
        if not row:
            return err("client not found", 404)
        category, plan = generate_program(program_category(row["program"]))
        db = get_db()
        db.execute("UPDATE clients SET generated_plan=? WHERE name=?", (plan, name))
        db.commit()
        return jsonify(category=category, program=plan)

    # --------------------------------------------------------------- membership
    @app.route("/clients/<name>/membership", methods=["GET"])
    def get_membership(name):
        row = find_client(name)
        if not row:
            return err("client not found", 404)
        end = row["membership_end"]
        days_left = None
        if end:
            days_left = (datetime.strptime(end, "%Y-%m-%d").date() - date.today()).days
        return jsonify(status=row["membership_status"], end_date=end, days_remaining=days_left)

    @app.route("/clients/<name>/membership", methods=["PUT"])
    def set_membership(name):
        if not find_client(name):
            return err("client not found", 404)
        data = request.get_json(silent=True) or {}
        status = data.get("status")
        end = data.get("end_date")
        if status not in MEMBERSHIP_STATUSES:
            return err(f"status must be one of {MEMBERSHIP_STATUSES}")
        if end is not None and not valid_date(end):
            return err("end_date must be YYYY-MM-DD")
        db = get_db()
        db.execute("UPDATE clients SET membership_status=?, membership_end=? WHERE name=?",
                   (status, end, name))
        db.commit()
        return jsonify(status=status, end_date=end)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
