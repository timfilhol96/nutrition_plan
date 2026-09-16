"""Pure planning functions. This module must not import Streamlit."""

import math
from collections import Counter
from dataclasses import replace

from nutrition.models import DailyTargets, Meal

MACROS = ("kcal", "carbs", "protein", "fat", "fiber")
TARGET_MACROS = ("kcal", "carbs", "protein", "fat")

# kcal offset from maintenance. The carb target moves by deficit / 4 g.
CALORIE_PLANS = {"maintenance": 0, "cut": -300, "extra_cut": -500}


def apply_plan(base: DailyTargets, plan: str) -> DailyTargets:
    deficit = CALORIE_PLANS[plan]
    return replace(base, kcal=base.kcal + deficit, carbs=base.carbs + deficit / 4)


def clean_rows(rows) -> list[str]:
    """Keep non-empty ingredient texts, dropping None/NaN and whitespace-only rows."""
    cleaned = []
    for row in rows:
        if row is None or (isinstance(row, float) and math.isnan(row)):
            continue
        text = str(row).strip()
        if text:
            cleaned.append(text)
    return cleaned


def meal_totals(meal: Meal) -> dict[str, float]:
    return {m: sum(getattr(item, m) for item in meal.items) for m in MACROS}


def daily_totals(meals: list[Meal]) -> dict[str, float]:
    per_meal = [meal_totals(meal) for meal in meals]
    return {m: sum(totals[m] for totals in per_meal) for m in MACROS}


def diff_vs_targets(
    totals: dict[str, float], targets: DailyTargets
) -> dict[str, float]:
    return {m: totals[m] - getattr(targets, m) for m in TARGET_MACROS}


def atwater_kcal(carbs: float, protein: float, fat: float) -> float:
    return 4 * carbs + 4 * protein + 9 * fat


def meal_numbers(meals: list[Meal]) -> dict[str, int | None]:
    """Number meals whose kind repeats (1, 2, ...); None when the kind is unique."""
    counts = Counter(meal.kind for meal in meals)
    seen: Counter = Counter()
    numbers = {}
    for meal in meals:
        seen[meal.kind] += 1
        numbers[meal.id] = seen[meal.kind] if counts[meal.kind] > 1 else None
    return numbers


def shift_plan(targets: DailyTargets, old_plan: str, new_plan: str) -> DailyTargets:
    """Move targets from one calorie plan to another (carbs absorb the kcal change)."""
    delta = CALORIE_PLANS[new_plan] - CALORIE_PLANS[old_plan]
    return replace(targets, kcal=targets.kcal + delta, carbs=targets.carbs + delta / 4)


# Standard activity multipliers applied to the basal metabolic rate.
ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}
FAT_KCAL_SHARE = 0.30  # share of kcal given to fat when deriving targets from a TDEE


def mifflin_st_jeor(sex: str, age: int, weight_kg: float, height_cm: float) -> float:
    """Basal metabolic rate in kcal/day."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "male" else base - 161


def tdee(bmr: float, activity: str) -> float:
    return bmr * ACTIVITY_MULTIPLIERS[activity]


def targets_from_tdee(
    kcal: float,
    weight_kg: float,
    protein_g_per_kg: float,
    fat_share: float = FAT_KCAL_SHARE,
) -> DailyTargets:
    """Split a kcal budget: protein from bodyweight, fat as a kcal share, carbs the rest."""
    protein = weight_kg * protein_g_per_kg
    fat = kcal * fat_share / 9
    carbs = max(kcal - 4 * protein - 9 * fat, 0) / 4
    return DailyTargets(kcal=kcal, carbs=carbs, protein=protein, fat=fat)


def kcal_mismatch(targets: DailyTargets) -> float:
    """Relative gap between the kcal target and the Atwater kcal of its macros."""
    if targets.kcal <= 0:
        return 0.0
    expected = atwater_kcal(targets.carbs, targets.protein, targets.fat)
    return abs(expected - targets.kcal) / targets.kcal
