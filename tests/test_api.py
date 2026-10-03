import pytest

FL3 = "Fat Loss (FL) - 3 day"


# ------------------------------------------------------------ basic endpoints
def test_home_and_health(client):
    assert client.get("/").get_json()["status"] == "running"
    assert client.get("/health").get_json() == {"status": "healthy"}


def test_programs_listed(client):
    data = client.get("/programs").get_json()
    assert data[FL3]["factor"] == 22 and len(data) == 4


# -------------------------------------------------------------------- clients
def test_create_client_computes_calories(asha):
    data = asha.get("/clients/Asha").get_json()
    assert data["calories"] == 70 * 22
    assert data["membership_status"] == "Active"
    assert "id" not in data


def test_create_client_validation(client):
    assert client.post("/clients", json={"program": FL3}).status_code == 400
    assert client.post("/clients", json={"name": "X", "program": "Nope"}).status_code == 400
    assert client.post("/clients", json={"name": "X", "program": FL3,
                                         "weight": "abc"}).status_code == 400
    assert client.post("/clients", json={"name": "X", "program": FL3,
                                         "weight": -4}).status_code == 400
    assert client.post("/clients").status_code == 400


def test_duplicate_client_rejected(asha):
    r = asha.post("/clients", json={"name": "Asha", "program": FL3})
    assert r.status_code == 409


def test_client_without_weight_has_no_calories(client):
    client.post("/clients", json={"name": "Ravi", "program": "Beginner (BG)"})
    assert client.get("/clients/Ravi").get_json()["calories"] is None


def test_list_clients_sorted(client):
    for n in ("Zed", "Amy"):
        client.post("/clients", json={"name": n, "program": "Beginner (BG)"})
    assert [c["name"] for c in client.get("/clients").get_json()] == ["Amy", "Zed"]


def test_update_client_recalculates_calories(asha):
    r = asha.put("/clients/Asha", json={"weight": 80, "program": "Muscle Gain (MG) - PPL"})
    assert r.status_code == 200
    assert r.get_json()["calories"] == 80 * 35
    assert r.get_json()["height"] == 165  # untouched fields preserved


def test_update_client_errors(asha, client):
    assert asha.put("/clients/Ghost", json={}).status_code == 404
    assert asha.put("/clients/Asha", json={"program": "Nope"}).status_code == 400
    assert asha.put("/clients/Asha", json={"weight": "x"}).status_code == 400


def test_get_unknown_client_404(client):
    assert client.get("/clients/Ghost").status_code == 404


def test_delete_client_cascades(asha):
    asha.post("/clients/Asha/progress", json={"adherence": 50})
    asha.post("/clients/Asha/workouts", json={"workout_type": "Strength",
                                              "exercises": [{"name": "Squat"}]})
    asha.post("/clients/Asha/metrics", json={"weight": 69})
    assert asha.delete("/clients/Asha").status_code == 204
    assert asha.get("/clients/Asha").status_code == 404
    assert asha.delete("/clients/Asha").status_code == 404
    # recreating gives a clean slate
    asha.post("/clients", json={"name": "Asha", "program": FL3})
    assert asha.get("/clients/Asha/progress").get_json() == []
    assert asha.get("/clients/Asha/workouts").get_json() == []


# ------------------------------------------------------------------- progress
def test_progress_log_and_history(asha):
    assert asha.post("/clients/Asha/progress", json={"adherence": 80}).status_code == 201
    asha.post("/clients/Asha/progress", json={"adherence": 90, "week": "Week 01 - 2026"})
    rows = asha.get("/clients/Asha/progress").get_json()
    assert [r["adherence"] for r in rows] == [80, 90]
    assert rows[1]["week"] == "Week 01 - 2026"


@pytest.mark.parametrize("value", [-1, 101, "high", None, True, 55.5])
def test_progress_rejects_bad_adherence(asha, value):
    assert asha.post("/clients/Asha/progress", json={"adherence": value}).status_code == 400


def test_progress_unknown_client(client):
    assert client.post("/clients/Ghost/progress", json={"adherence": 5}).status_code == 404
    assert client.get("/clients/Ghost/progress").status_code == 404


# ------------------------------------------------------------------- workouts
def test_workout_with_exercises(asha):
    r = asha.post("/clients/Asha/workouts", json={
        "date": "2026-03-01", "workout_type": "Strength", "duration_min": 45,
        "notes": "heavy day",
        "exercises": [{"name": "Back Squat", "sets": 5, "reps": 5, "weight": 80}]})
    assert r.status_code == 201 and r.get_json()["exercises"] == 1
    history = asha.get("/clients/Asha/workouts").get_json()
    assert history[0]["exercises"][0] == {"name": "Back Squat", "sets": 5, "reps": 5,
                                          "weight": 80.0}


def test_workout_history_newest_first(asha):
    for d in ("2026-03-01", "2026-03-05", "2026-03-03"):
        asha.post("/clients/Asha/workouts", json={"date": d, "workout_type": "Mixed"})
    dates = [w["date"] for w in asha.get("/clients/Asha/workouts").get_json()]
    assert dates == ["2026-03-05", "2026-03-03", "2026-03-01"]


@pytest.mark.parametrize("payload", [
    {"workout_type": "Yoga"},
    {"workout_type": "Strength", "date": "01-03-2026"},
    {"workout_type": "Strength", "duration_min": 0},
    {"workout_type": "Strength", "duration_min": "long"},
    {"workout_type": "Strength", "exercises": [{"sets": 3}]},
    {"workout_type": "Strength", "exercises": "squat"},
])
def test_workout_validation(asha, payload):
    assert asha.post("/clients/Asha/workouts", json=payload).status_code == 400


def test_workout_unknown_client(client):
    assert client.post("/clients/Ghost/workouts",
                       json={"workout_type": "Mixed"}).status_code == 404
    assert client.get("/clients/Ghost/workouts").status_code == 404


# -------------------------------------------------------------------- metrics
def test_metrics_update_client_weight_and_calories(asha):
    r = asha.post("/clients/Asha/metrics", json={"date": "2026-03-01", "weight": 68,
                                                 "waist": 74, "bodyfat": 24})
    assert r.status_code == 201
    c = asha.get("/clients/Asha").get_json()
    assert c["weight"] == 68 and c["calories"] == 68 * 22


def test_metrics_without_weight_keeps_client_weight(asha):
    asha.post("/clients/Asha/metrics", json={"waist": 74})
    assert asha.get("/clients/Asha").get_json()["weight"] == 70


def test_metrics_history_sorted_and_validation(asha):
    asha.post("/clients/Asha/metrics", json={"date": "2026-03-05", "weight": 68})
    asha.post("/clients/Asha/metrics", json={"date": "2026-03-01", "weight": 69})
    assert [m["date"] for m in asha.get("/clients/Asha/metrics").get_json()] == \
        ["2026-03-01", "2026-03-05"]
    assert asha.post("/clients/Asha/metrics", json={"date": "bad"}).status_code == 400
    assert asha.post("/clients/Asha/metrics", json={"weight": "x"}).status_code == 400
    assert asha.post("/clients/Asha/metrics", json={"waist": -2}).status_code == 400


def test_metrics_unknown_client(client):
    assert client.post("/clients/Ghost/metrics", json={}).status_code == 404
    assert client.get("/clients/Ghost/metrics").status_code == 404


# ----------------------------------------------------------------- BMI / summary
def test_client_bmi(asha):
    data = asha.get("/clients/Asha/bmi").get_json()
    assert data["bmi"] == 25.7 and data["category"] == "Overweight"
    assert "risk" in data


def test_client_bmi_needs_height_and_weight(client):
    client.post("/clients", json={"name": "Ravi", "program": "Beginner (BG)"})
    assert client.get("/clients/Ravi/bmi").status_code == 400
    assert client.get("/clients/Ghost/bmi").status_code == 404


def test_summary_aggregates(asha):
    asha.post("/clients/Asha/progress", json={"adherence": 80})
    asha.post("/clients/Asha/progress", json={"adherence": 91})
    asha.post("/clients/Asha/metrics", json={"date": "2026-03-01", "weight": 69, "waist": 75})
    s = asha.get("/clients/Asha/summary").get_json()
    assert s["progress"] == {"weeks_logged": 2, "average_adherence": 85.5}
    assert s["goals"] == {"target_weight": 62.0, "target_adherence": 85}
    assert s["last_metrics"]["weight"] == 69
    assert s["program_notes"] == "3-day full-body fat loss"


def test_summary_empty_state(client):
    client.post("/clients", json={"name": "Ravi", "program": "Beginner (BG)"})
    s = client.get("/clients/Ravi/summary").get_json()
    assert s["progress"] == {"weeks_logged": 0, "average_adherence": 0}
    assert s["last_metrics"] is None
    assert client.get("/clients/Ghost/summary").status_code == 404


# ------------------------------------------------------------ generate program
def test_generate_program_matches_client_category(asha):
    from app import PROGRAM_TEMPLATES
    data = asha.post("/clients/Asha/generate-program").get_json()
    assert data["category"] == "Fat Loss"
    assert data["program"] in PROGRAM_TEMPLATES["Fat Loss"]
    assert asha.get("/clients/Asha").get_json()["generated_plan"] == data["program"]


def test_generate_program_unknown_client(client):
    assert client.post("/clients/Ghost/generate-program").status_code == 404


# ----------------------------------------------------------------- membership
def test_membership_roundtrip(asha):
    assert asha.get("/clients/Asha/membership").get_json() == {
        "status": "Active", "end_date": None, "days_remaining": None}
    r = asha.put("/clients/Asha/membership", json={"status": "Expired",
                                                   "end_date": "2000-01-01"})
    assert r.status_code == 200
    data = asha.get("/clients/Asha/membership").get_json()
    assert data["status"] == "Expired" and data["days_remaining"] < 0


def test_membership_validation(asha, client):
    assert asha.put("/clients/Asha/membership", json={"status": "VIP"}).status_code == 400
    assert asha.put("/clients/Asha/membership",
                    json={"status": "Active", "end_date": "soon"}).status_code == 400
    assert client.put("/clients/Ghost/membership", json={"status": "Active"}).status_code == 404
    assert client.get("/clients/Ghost/membership").status_code == 404
