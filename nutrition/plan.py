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
