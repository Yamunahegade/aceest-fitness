import random

import pytest

import app as m


@pytest.mark.parametrize("program,expected", [
    ("Fat Loss (FL) - 3 day", 70 * 22),
    ("Fat Loss (FL) - 5 day", 70 * 24),
    ("Muscle Gain (MG) - PPL", 70 * 35),
    ("Beginner (BG)", 70 * 26),
    ("Unknown program", 70 * 25),  # falls back to default factor
])
def test_calculate_calories(program, expected):
    assert m.calculate_calories(70, program) == expected


@pytest.mark.parametrize("weight", [None, 0, -5])
def test_calculate_calories_without_valid_weight(weight):
    assert m.calculate_calories(weight, "Beginner (BG)") is None


def test_calculate_bmi():
    assert m.calculate_bmi(70, 175) == 22.9


@pytest.mark.parametrize("w,h", [(0, 170), (70, 0), (-1, 170)])
def test_calculate_bmi_invalid(w, h):
    with pytest.raises(ValueError):
        m.calculate_bmi(w, h)


@pytest.mark.parametrize("bmi,category", [(17.0, "Underweight"), (18.5, "Normal"),
                                          (24.9, "Normal"), (25.0, "Overweight"),
                                          (29.9, "Overweight"), (30.0, "Obese")])
def test_bmi_info_boundaries(bmi, category):
    assert m.bmi_info(bmi)[0] == category


@pytest.mark.parametrize("program,cat", [
    ("Fat Loss (FL) - 5 day", "Fat Loss"), ("Muscle Gain (MG) - PPL", "Muscle Gain"),
    ("Beginner (BG)", "Beginner"), ("Other", None), (None, None)])
def test_program_category(program, cat):
    assert m.program_category(program) == cat


def test_generate_program_respects_category():
    for _ in range(20):
        cat, plan = m.generate_program("Muscle Gain")
        assert cat == "Muscle Gain"
        assert plan in m.PROGRAM_TEMPLATES["Muscle Gain"]


def test_generate_program_random_category_is_deterministic_with_seed():
    a = m.generate_program(None, random.Random(1))
    b = m.generate_program(None, random.Random(1))
    assert a == b and a[0] in m.PROGRAM_TEMPLATES


def test_week_label_format():
    from datetime import datetime
    assert m.current_week_label(datetime(2026, 1, 15)) == "Week 02 - 2026"


@pytest.mark.parametrize("text,ok", [("2026-02-28", True), ("2026-13-01", False),
                                     ("28/02/2026", False), (None, False)])
def test_valid_date(text, ok):
    assert m.valid_date(text) is ok


def test_positive_or_none():
    assert m.positive_or_none("") is None
    assert m.positive_or_none(0) is None
    assert m.positive_or_none("72.5") == 72.5
    with pytest.raises(ValueError):
        m.positive_or_none(-3)
    with pytest.raises(ValueError):
        m.positive_or_none("abc")
