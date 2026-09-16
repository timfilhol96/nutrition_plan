import math

import pytest

from nutrition.models import DailyTargets, FoodItem, Meal
from nutrition.plan import (
    CALORIE_PLANS,
    MACROS,
    apply_plan,
    atwater_kcal,
    clean_rows,
    daily_totals,
    diff_vs_targets,
    meal_numbers,
    meal_totals,
)

EGG = FoodItem("egg", 50, 71.5, 0.4, 6.3, 4.8, 0.0, source="1 egg")
TOAST = FoodItem("toast", 30, 79.2, 14.7, 2.7, 1.0, 0.7, source="toast")
RICE = FoodItem("rice", 150, 194.6, 42.2, 4.0, 0.4, 0.6, source="150g rice")


def test_empty_meal_totals_are_zero():
    meal = Meal(id="meal_0", kind="lunch")
    assert meal.is_empty
    assert meal_totals(meal) == {m: 0 for m in MACROS}
    assert daily_totals([meal]) == {m: 0 for m in MACROS}


def test_clean_rows_drops_none_nan_and_whitespace():
    rows = ["  2 eggs ", None, "", "   ", float("nan"), "\ttoast\n"]
    assert clean_rows(rows) == ["2 eggs", "toast"]


def test_clean_rows_empty_input():
    assert clean_rows([]) == []
    assert clean_rows([None, "  "]) == []


def test_meal_totals_sum_all_items_without_rounding():
    meal = Meal(id="meal_0", kind="breakfast", items=[EGG, EGG, TOAST])
    totals = meal_totals(meal)
    assert totals["kcal"] == pytest.approx(71.5 + 71.5 + 79.2)
    assert totals["carbs"] == pytest.approx(0.4 + 0.4 + 14.7)
    assert totals["protein"] == pytest.approx(6.3 + 6.3 + 2.7)
    assert totals["fat"] == pytest.approx(4.8 + 4.8 + 1.0)
    assert totals["fiber"] == pytest.approx(0.7)


def test_daily_totals_and_diff_vs_targets():
    meals = [
        Meal(id="meal_0", kind="breakfast", items=[EGG, TOAST]),
        Meal(id="meal_1", kind="lunch"),  # empty meals contribute nothing
        Meal(id="meal_2", kind="dinner", items=[RICE]),
    ]
    totals = daily_totals(meals)
    assert totals["kcal"] == pytest.approx(71.5 + 79.2 + 194.6)
    assert totals["fiber"] == pytest.approx(0.7 + 0.6)

    targets = DailyTargets(kcal=300, carbs=50, protein=20, fat=10)
    diff = diff_vs_targets(totals, targets)
    assert set(diff) == {"kcal", "carbs", "protein", "fat"}
    assert diff["kcal"] == pytest.approx(345.3 - 300)
    assert diff["carbs"] == pytest.approx(57.3 - 50)
    assert diff["protein"] == pytest.approx(13.0 - 20)
    assert diff["fat"] == pytest.approx(6.2 - 10)


def test_rounding_happens_only_at_display_time():
    # 0.4 + 0.4 + 0.4 = 1.2 -> rounds to 1; rounding per item first would give 0.
    meal = Meal(id="m", kind="snack", items=[EGG, EGG, EGG])
    assert round(meal_totals(meal)["carbs"]) == 1


def test_atwater_kcal():
    assert atwater_kcal(carbs=50, protein=25, fat=10) == 4 * 50 + 4 * 25 + 9 * 10
    assert atwater_kcal(0, 0, 0) == 0
    # A real food's kcal should be close to its Atwater estimate.
    for item in (EGG, TOAST, RICE):
        estimate = atwater_kcal(item.carbs, item.protein, item.fat)
        assert math.isclose(item.kcal, estimate, rel_tol=0.15), item


def test_calorie_plans_adjust_kcal_and_carbs():
    base = DailyTargets(kcal=2500, carbs=300, protein=150, fat=70)
    assert apply_plan(base, "maintenance") == base
    cut = apply_plan(base, "cut")
    assert (cut.kcal, cut.carbs, cut.protein, cut.fat) == (2200, 225, 150, 70)
    extra = apply_plan(base, "extra_cut")
    assert (extra.kcal, extra.carbs) == (2000, 175)
    for plan, deficit in CALORIE_PLANS.items():
        assert apply_plan(base, plan).carbs == base.carbs + deficit / 4


def test_meal_numbers_only_for_repeated_kinds():
    meals = [
        Meal(id="a", kind="lunch"),
        Meal(id="b", kind="breakfast"),
        Meal(id="c", kind="lunch"),
        Meal(id="d", kind="lunch"),
    ]
    assert meal_numbers(meals) == {"a": 1, "b": None, "c": 2, "d": 3}
    assert meal_numbers([]) == {}


def test_plan_and_export_do_not_import_streamlit():
    import subprocess
    import sys

    code = (
        "import sys, nutrition.plan, nutrition.export; "
        "sys.exit(1 if 'streamlit' in sys.modules else 0)"
    )
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0


def test_mifflin_st_jeor_and_tdee():
    from nutrition.plan import ACTIVITY_MULTIPLIERS, mifflin_st_jeor, tdee

    assert mifflin_st_jeor("male", 30, 70, 175) == pytest.approx(1648.75)
    assert mifflin_st_jeor("female", 30, 70, 175) == pytest.approx(1482.75)
    assert tdee(1648.75, "sedentary") == pytest.approx(1648.75 * 1.2)
    assert tdee(1648.75, "very_active") == pytest.approx(1648.75 * 1.9)
    assert list(ACTIVITY_MULTIPLIERS.values()) == [1.2, 1.375, 1.55, 1.725, 1.9]


def test_targets_from_tdee_use_bodyweight_protein_and_close_the_kcal_budget():
    from nutrition.plan import targets_from_tdee

    targets = targets_from_tdee(2000, weight_kg=70, protein_g_per_kg=1.6)
    assert targets.protein == pytest.approx(112)
    assert targets.fat == pytest.approx(2000 * 0.30 / 9)
    assert atwater_kcal(targets.carbs, targets.protein, targets.fat) == pytest.approx(
        2000
    )
    # Carbs never go negative when protein + fat already exceed the budget.
    assert targets_from_tdee(500, weight_kg=100, protein_g_per_kg=3).carbs == 0


def test_kcal_mismatch():
    from nutrition.plan import kcal_mismatch

    assert kcal_mismatch(DailyTargets(kcal=2000, carbs=250, protein=100, fat=67)) < 0.01
    assert (
        kcal_mismatch(DailyTargets(kcal=2000, carbs=250, protein=100, fat=100)) > 0.05
    )
    assert kcal_mismatch(DailyTargets(kcal=0, carbs=1, protein=1, fat=1)) == 0.0


def test_shift_plan_moves_kcal_and_carbs_relative_to_current_targets():
    from nutrition.plan import shift_plan

    base = DailyTargets(kcal=2000, carbs=250, protein=100, fat=67)
    cut = shift_plan(base, "maintenance", "cut")
    assert (cut.kcal, cut.carbs, cut.protein, cut.fat) == (1700, 175, 100, 67)
    assert shift_plan(cut, "cut", "extra_cut").kcal == 1500
    assert shift_plan(cut, "cut", "maintenance") == base
