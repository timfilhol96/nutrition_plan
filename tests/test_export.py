import csv
import io

from nutrition.export import build_csv
from nutrition.i18n import LANGUAGES, t
from nutrition.models import DailyTargets, FoodItem, Meal

CREPE = FoodItem("crêpe", 40, 90.4, 12.6, 2.9, 3.1, 0.4, source="1 crêpe")
PATE = FoodItem("pâté de campagne", 30, 95.0, 0.6, 4.2, 8.4, 0.0, source="30g de pâté")


def _parse(data: bytes) -> list[list[str]]:
    assert data.startswith(b"\xef\xbb\xbf"), "CSV must carry a UTF-8 BOM for Excel"
    return list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))


def test_csv_round_trip_with_accents():
    meals = [Meal(id="meal_0", kind="breakfast", items=[CREPE, PATE])]
    labels = {"meal_0": "Petit-déjeuner"}
    targets = DailyTargets(kcal=2000, carbs=250, protein=120, fat=60)

    rows = _parse(build_csv(meals, labels, targets, "fr"))

    assert rows[0] == ["Petit-déjeuner"]
    assert rows[1] == [
        "Ingrédient",
        "Aliment",
        "Poids (g)",
        "Calories",
        "Glucides",
        "Protéines",
        "Lipides",
        "Fibres",
    ]
    assert rows[2] == ["1 crêpe", "crêpe", "40.0", "90", "13", "3", "3", "0"]
    assert rows[3] == [
        "30g de pâté",
        "pâté de campagne",
        "30.0",
        "95",
        "1",
        "4",
        "8",
        "0",
    ]
    # Meal total is computed from unrounded values: 12.6 + 0.6 = 13.2 -> 13
    assert rows[4] == ["TOTAL", "", "", "185", "13", "7", "12", "0"]
    assert rows[5] == []

    summary = {row[0]: row[1:] for row in rows[6:]}
    assert summary["Résumé"] == [
        "Calories",
        "Glucides",
        "Protéines",
        "Lipides",
        "Fibres",
    ]
    assert summary["Petit-déjeuner"] == ["185", "13", "7", "12", "0"]
    assert summary["TOTAL"] == ["185", "13", "7", "12", "0"]
    assert summary["Idéal"] == ["2000", "250", "120", "60", ""]
    assert summary["Écart"] == [
        str(185 - 2000),
        str(13 - 250),
        str(7 - 120),
        str(12 - 60),
        "",
    ]


def test_empty_meals_are_skipped():
    meals = [
        Meal(id="meal_0", kind="lunch"),
        Meal(id="meal_1", kind="dinner", items=[CREPE]),
    ]
    labels = {"meal_0": "Lunch", "meal_1": "Dinner"}
    rows = _parse(build_csv(meals, labels, DailyTargets(1, 1, 1, 1), "en"))
    first_cells = [row[0] for row in rows if row]
    assert "Lunch" not in first_cells
    assert first_cells.count("Dinner") == 2  # table header + summary line


def test_both_languages_have_the_same_keys():
    keys = {lang: set(t.__globals__["STRINGS"][lang]) for lang in LANGUAGES}
    assert keys["en"] == keys["fr"]


def test_long_csv_has_one_row_per_food_with_a_bom():
    from nutrition.export import build_long_csv

    meals = [
        Meal(id="meal_0", kind="breakfast", items=[CREPE, PATE]),
        Meal(id="extras", kind="extras", items=[CREPE]),
    ]
    labels = {"meal_0": "Petit-déjeuner", "extras": "Extras"}
    rows = _parse(build_long_csv(meals, labels))
    assert rows[0] == [
        "meal",
        "food",
        "grams",
        "kcal",
        "carbs",
        "protein",
        "fat",
        "fiber",
    ]
    assert rows[1] == [
        "Petit-déjeuner",
        "crêpe",
        "40.0",
        "90.4",
        "12.6",
        "2.9",
        "3.1",
        "0.4",
    ]
    assert rows[2][:2] == ["Petit-déjeuner", "pâté de campagne"]
    assert rows[3] == ["Extras", "crêpe", "40.0", "90.4", "12.6", "2.9", "3.1", "0.4"]
    assert len(rows) == 4
