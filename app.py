import pandas as pd
import streamlit as st

from nutrition.client import NutritionClient, NutritionLookupError
from nutrition.export import build_csv
from nutrition.i18n import LANGUAGES, t
from nutrition.models import MEAL_KINDS, DailyTargets, Meal
from nutrition.nutritionix import NutritionixClient
from nutrition.plan import (
    CALORIE_PLANS,
    MACROS,
    TARGET_MACROS,
    apply_plan,
    clean_rows,
    daily_totals,
    diff_vs_targets,
    meal_numbers,
    meal_totals,
)

# TODO(phase 4): replace these personal defaults with neutral targets + TDEE.
BASE_TARGETS = DailyTargets(kcal=2510, carbs=363, protein=110, fat=69)
EDITOR_ROWS = 15


def get_client() -> NutritionClient | None:
    # st.secrets raises a FileNotFoundError subclass when no secrets file
    # exists and KeyError when the file exists but the key is missing.
    try:
        return NutritionixClient(st.secrets["NIX_APP_ID"], st.secrets["NIX_API_KEY"])
    except (KeyError, FileNotFoundError):
        return None


def plan_label(plan: str, lang: str) -> str:
    deficit = CALORIE_PLANS[plan]
    name = t(f"plan_{plan}", lang)
    return name if deficit == 0 else f"{name} ({deficit:+d} kcal)"


def meal_label(meal: Meal, number: int | None, lang: str) -> str:
    name = t(meal.kind, lang)
    return name if number is None else f"{name} {number}"


def build_meals(
    client: NutritionClient, meal_inputs: list[tuple[str, str, list[str]]], lang: str
) -> tuple[list[Meal], list[str]]:
    """Look up every row of every meal. Returns the meals and the unmatched texts."""
    meals, unmatched = [], []
    for meal_id, kind, rows in meal_inputs:
        items = []
        for text in rows:
            try:
                items.extend(client.lookup(text, lang))
            except NutritionLookupError:
                unmatched.append(text)
        meals.append(Meal(id=meal_id, kind=kind, items=items))
    return meals, unmatched


def meal_table(meal: Meal, lang: str) -> pd.DataFrame:
    """Display table for one meal: one row per item plus a TOTAL row, rounded."""
    rows = [
        {
            t("ingredient", lang): item.source,
            t("food", lang): item.name,
            t("grams", lang): round(item.grams, 1),
            **{t(m, lang): round(getattr(item, m)) for m in MACROS},
        }
        for item in meal.items
    ]
    totals = meal_totals(meal)
    rows.append(
        {
            t("ingredient", lang): "TOTAL",
            t("food", lang): "",
            t("grams", lang): None,
            **{t(m, lang): round(totals[m]) for m in MACROS},
        }
    )
    return pd.DataFrame(rows)


def render_results(
    meals: list[Meal], unmatched: list[str], targets: DailyTargets, lang: str
) -> None:
    for text in unmatched:
        st.warning(t("no_match", lang).format(text=text))

    shown = [meal for meal in meals if not meal.is_empty]
    numbers = meal_numbers(shown)
    labels = {meal.id: meal_label(meal, numbers[meal.id], lang) for meal in shown}

    for col, meal in zip(st.columns(len(shown)), shown):
        col.markdown(f"## {labels[meal.id]}")
        col.dataframe(meal_table(meal, lang), hide_index=True, width="stretch")

    st.markdown("---")
    totals = daily_totals(shown)
    diff = diff_vs_targets(totals, targets)
    for col, m in zip(st.columns(4), TARGET_MACROS):
        unit = "kcal" if m == "kcal" else "g"
        col.metric(
            f"{t('total', lang)} {t(m, lang)}",
            f"{round(totals[m])} {unit}",
            f"{round(diff[m])} {unit}",
            delta_color="normal",
        )
    st.markdown("---")
    for col, m in zip(st.columns(4), TARGET_MACROS):
        unit = "kcal" if m == "kcal" else "g"
        col.metric(
            f"{t('target', lang)} {t(m, lang)}", f"{round(getattr(targets, m))} {unit}"
        )

    st.markdown("---")
    st.download_button(
        t("download", lang),
        build_csv(shown, labels, targets, lang),
        "menu.csv",
        mime="text/csv",
        key="download",
        width="stretch",
    )


st.set_page_config(
    page_title="Nutrition Plan",
    page_icon="🦖",
    layout="wide",
    initial_sidebar_state="auto",
)

with st.sidebar:
    lang = st.radio(
        "language",
        LANGUAGES,
        format_func=lambda code: t("language", code),
        key="lang",
        label_visibility="collapsed",
    )
    st.markdown(t("sidebar", lang))

client = get_client()
if client is None:
    st.error(t("missing_secrets", lang))
    st.stop()

st.columns(3)[1].markdown(f"# {t('app_title', lang)}")
st.markdown(f"---\n## {t('daily_macros', lang)}")

plan = st.selectbox(
    t("plan", lang),
    list(CALORIE_PLANS),
    format_func=lambda p: plan_label(p, lang),
    key="plan",
)
defaults = apply_plan(BASE_TARGETS, plan)
target_cols = st.columns(4)
targets = DailyTargets(
    kcal=target_cols[0].number_input(
        t("target_kcal", lang), value=round(defaults.kcal)
    ),
    carbs=target_cols[1].number_input(
        t("target_carbs", lang), value=round(defaults.carbs)
    ),
    protein=target_cols[2].number_input(
        t("target_protein", lang), value=round(defaults.protein)
    ),
    fat=target_cols[3].number_input(t("target_fat", lang), value=round(defaults.fat)),
)

st.markdown(f"## {t('menu', lang)}")
nb_meals = st.number_input(
    t("nb_meals", lang), min_value=1, step=1, value=3, key="nb_meals"
)

empty_rows = pd.DataFrame({"ingredient": [""] * EDITOR_ROWS})
meal_inputs: list[tuple[str, str, list[str]]] = []
for i, col in enumerate(st.columns(nb_meals)):
    meal_id = f"meal_{i}"
    kind = col.selectbox(
        t("meal_kind", lang),
        MEAL_KINDS,
        format_func=lambda k: t(k, lang),
        key=f"{meal_id}_kind",
        index=None,
        placeholder=t("meal_kind_placeholder", lang),
        label_visibility="collapsed",
    )
    if kind is None:
        continue
    edited = col.data_editor(
        empty_rows,
        key=f"{meal_id}_rows",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "ingredient": st.column_config.TextColumn(t("ingredient", lang))
        },
    )
    meal_inputs.append((meal_id, kind, clean_rows(edited["ingredient"])))

# Results live in session state so they survive reruns (bug 6). They are
# dropped as soon as the meal inputs they were computed from change.
fingerprint = tuple((meal_id, kind, tuple(rows)) for meal_id, kind, rows in meal_inputs)
if st.session_state.get("results_fingerprint") != fingerprint:
    st.session_state.pop("results", None)

if st.button(t("compute", lang), key="compute", width="stretch"):
    with st.spinner("⏳"):
        meals, unmatched = build_meals(client, meal_inputs, lang)
    if all(meal.is_empty for meal in meals):
        for text in unmatched:
            st.warning(t("no_match", lang).format(text=text))
        st.error(t("fill_one_table", lang))
    else:
        st.session_state["results"] = (meals, unmatched)
        st.session_state["results_fingerprint"] = fingerprint

if "results" in st.session_state:
    meals, unmatched = st.session_state["results"]
    render_results(meals, unmatched, targets, lang)
