"""CSV export. This module must not import Streamlit."""

import csv
import io

from nutrition.i18n import t
from nutrition.models import DailyTargets, Meal
from nutrition.plan import (
    MACROS,
    TARGET_MACROS,
    daily_totals,
    diff_vs_targets,
    meal_totals,
)


def _num(value: float) -> int:
    # Values are kept unrounded until this point; round only for display.
    return round(value)


def build_csv(
    meals: list[Meal], labels: dict[str, str], targets: DailyTargets, lang: str
) -> bytes:
    """Per-meal tables followed by a daily summary, as Excel-friendly UTF-8 bytes."""
    shown = [meal for meal in meals if not meal.is_empty]
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    for meal in shown:
        writer.writerow([labels[meal.id]])
        writer.writerow(
            [t("ingredient", lang), t("food", lang), t("grams", lang)]
            + [t(m, lang) for m in MACROS]
        )
        for item in meal.items:
            writer.writerow(
                [item.source, item.name, round(float(item.grams), 1)]
                + [_num(getattr(item, m)) for m in MACROS]
            )
        totals = meal_totals(meal)
        writer.writerow(["TOTAL", "", ""] + [_num(totals[m]) for m in MACROS])
        writer.writerow([])

    totals = daily_totals(shown)
    diff = diff_vs_targets(totals, targets)
    writer.writerow([t("summary", lang)] + [t(m, lang) for m in MACROS])
    for meal in shown:
        meal_total = meal_totals(meal)
        writer.writerow([labels[meal.id]] + [_num(meal_total[m]) for m in MACROS])
    writer.writerow(["TOTAL"] + [_num(totals[m]) for m in MACROS])
    writer.writerow(
        [t("target", lang)] + [_num(getattr(targets, m)) for m in TARGET_MACROS] + [""]
    )
    writer.writerow([t("diff", lang)] + [_num(diff[m]) for m in TARGET_MACROS] + [""])

    return buffer.getvalue().encode("utf-8-sig")


def build_long_csv(meals: list[Meal], labels: dict[str, str]) -> bytes:
    """Tidy long format: one row per food (meal, food, grams, kcal, carbs, protein, fat, fiber)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["meal", "food", "grams"] + list(MACROS))
    for meal in meals:
        for item in meal.items:
            writer.writerow(
                [labels[meal.id], item.name, round(float(item.grams), 1)]
                + [round(float(getattr(item, m)), 1) for m in MACROS]
            )
    return buffer.getvalue().encode("utf-8-sig")
