import pandas as pd
import streamlit as st

from nutrition.config import secret, setting
from nutrition.export import build_csv
from nutrition.hybrid import HybridClient, ResolvedMeal
from nutrition.i18n import LANGUAGES, t
from nutrition.llm import (
    LLMBudgetExhausted,
    LLMProvider,
    LLMUnavailable,
    OpenAICompatibleProvider,
    ProviderChain,
)
from nutrition.models import MEAL_KINDS, DailyTargets, FoodItem, Meal
from nutrition.parser import MealParser, ParseFailed, validate_rows
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
from nutrition.usda import UsdaCandidate, UsdaClient, UsdaError

# TODO(phase 4): replace these personal defaults with neutral targets + TDEE.
BASE_TARGETS = DailyTargets(kcal=2510, carbs=363, protein=110, fat=69)
EDITOR_ROWS = 15
ITEM_COLUMNS = [3, 4, 1.3, 1, 1, 1, 1]  # text, match, grams, kcal, carbs, protein, fat


# ----------------------------------------------------------------- helpers --


def build_providers() -> list[LLMProvider]:
    """One provider per configured key, in fallback order (Groq, then OpenRouter)."""
    timeout = float(setting("LLM_TIMEOUT_S"))
    providers: list[LLMProvider] = []
    if secret("GROQ_API_KEY"):
        providers.append(
            OpenAICompatibleProvider(
                "groq",
                setting("GROQ_BASE_URL"),
                secret("GROQ_API_KEY"),
                setting("GROQ_MODEL"),
                timeout_s=timeout,
            )
        )
    if secret("OPENROUTER_API_KEY"):
        providers.append(
            OpenAICompatibleProvider(
                "openrouter",
                setting("OPENROUTER_BASE_URL"),
                secret("OPENROUTER_API_KEY"),
                setting("OPENROUTER_MODEL"),
                timeout_s=timeout,
                extra_headers={"X-Title": "nutrition_plan"},
            )
        )
    return providers


def plan_label(plan: str, lang: str) -> str:
    deficit = CALORIE_PLANS[plan]
    name = t(f"plan_{plan}", lang)
    return name if deficit == 0 else f"{name} ({deficit:+d} kcal)"


def meal_label(meal: Meal, number: int | None, lang: str) -> str:
    name = t(meal.kind, lang)
    return name if number is None else f"{name} {number}"


def switch_to_manual(message: str) -> None:
    """Flip the manual-mode toggle on the next run and explain why."""
    st.session_state["auto_manual_message"] = message
    st.rerun()


def clear_overrides(meal_id: str) -> None:
    """Drop the match/grams overrides of a meal when it is parsed again."""
    for key in list(st.session_state):
        if key.startswith(f"{meal_id}_ov_"):
            del st.session_state[key]


def usda_search_widget(
    container, key: str, usda: UsdaClient, lang: str, default: str = ""
) -> UsdaCandidate | None:
    """Text search over USDA foods (cached) + a selectbox of the candidates."""
    query = container.text_input(
        t("search_food", lang), value=default, key=f"{key}_q", placeholder="🔍"
    )
    if not query.strip():
        return None
    try:
        candidates = usda.search(query, int(setting("USDA_CANDIDATES")))
    except UsdaError:
        container.warning(t("usda_error", lang))
        return None
    if not candidates:
        container.caption(t("no_results", lang))
        return None
    by_id = {candidate.fdc_id: candidate for candidate in candidates}
    chosen = container.selectbox(
        t("match", lang),
        list(by_id),
        format_func=lambda fdc_id: by_id[fdc_id].description,
        key=f"{key}_sel",
        label_visibility="collapsed",
    )
    return by_id[chosen]


def macro_cells(cols, food: FoodItem | None) -> None:
    for col, macro in zip(cols, TARGET_MACROS):
        col.write("" if food is None else f"{round(getattr(food, macro))}")


def item_header(lang: str) -> None:
    cols = st.columns(ITEM_COLUMNS)
    labels = [t("text", lang), t("match", lang), t("grams", lang)] + [
        t(m, lang) for m in TARGET_MACROS
    ]
    for col, label in zip(cols, labels):
        col.caption(label)


def render_resolved_meal(
    meal_id: str, resolved: ResolvedMeal, usda: UsdaClient, lang: str
) -> list[FoodItem]:
    """Free-text results: editable match + grams per item. Recomputes locally."""
    item_header(lang)
    foods = []
    for index, item in enumerate(resolved.items):
        key = f"{meal_id}_ov_r{item.row}_i{index}"
        cols = st.columns(ITEM_COLUMNS)
        cols[0].write(item.text)
        if item.found:
            by_id = {c.fdc_id: c for c in item.candidates}
            chosen = cols[1].selectbox(
                t("match", lang),
                list(by_id),
                format_func=lambda fdc_id, by_id=by_id: by_id[fdc_id].description,
                key=f"{key}_match",
                label_visibility="collapsed",
            )
            candidate = by_id[chosen]
        else:
            cols[1].caption(t("not_found", lang))
            candidate = usda_search_widget(
                cols[1], key, usda, lang, default=item.name_en
            )
        grams = cols[2].number_input(
            t("grams", lang),
            min_value=0.0,
            value=float(item.grams),
            step=5.0,
            key=f"{key}_grams",
            label_visibility="collapsed",
        )
        food = candidate.scaled(grams, source=item.text) if candidate else None
        macro_cells(cols[3:], food)
        if item.assumption:
            cols[0].caption(f"↳ {item.assumption}")
        if food:
            foods.append(food)

    for row, text in resolved.failed_rows:
        key = f"{meal_id}_ov_r{row}_failed"
        cols = st.columns(ITEM_COLUMNS)
        cols[0].write(text)
        cols[0].caption(f"↳ {t('not_found', lang)}")
        candidate = usda_search_widget(cols[1], key, usda, lang)
        grams = cols[2].number_input(
            t("grams", lang),
            min_value=0.0,
            value=100.0,
            step=5.0,
            key=f"{key}_grams",
            label_visibility="collapsed",
        )
        food = candidate.scaled(grams, source=text) if candidate else None
        macro_cells(cols[3:], food)
        if food:
            foods.append(food)
    return foods


def render_manual_meal(meal_id: str, usda: UsdaClient, lang: str) -> list[FoodItem]:
    """Manual mode: search a food, enter grams, add it to the meal."""
    items = st.session_state.setdefault("manual_items", {}).setdefault(meal_id, [])
    cols = st.columns([7, 1.3, 1.2])
    candidate = usda_search_widget(cols[0], f"{meal_id}_manual", usda, lang)
    grams = cols[1].number_input(
        t("grams", lang),
        min_value=0.0,
        value=100.0,
        step=5.0,
        key=f"{meal_id}_manual_grams",
    )
    if cols[2].button(
        t("add", lang), key=f"{meal_id}_manual_add", disabled=candidate is None
    ):
        items.append((candidate, grams))
        st.rerun()

    foods = []
    if items:
        item_header(lang)
    for index, (candidate, grams) in enumerate(items):
        cols = st.columns(ITEM_COLUMNS)
        food = candidate.scaled(grams, source=candidate.description)
        cols[0].write(candidate.description)
        cols[1].write("")
        cols[2].write(f"{grams:g} g")
        macro_cells(cols[3:], food)
        if cols[1].button(t("remove", lang), key=f"{meal_id}_manual_rm_{index}"):
            items.pop(index)
            st.rerun()
        foods.append(food)
    return foods


def render_totals(
    meals: list[Meal], labels: dict[str, str], targets: DailyTargets, lang: str
) -> None:
    shown = [meal for meal in meals if not meal.is_empty]
    if not shown:
        return

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
    for col, m in zip(st.columns(4), TARGET_MACROS):
        unit = "kcal" if m == "kcal" else "g"
        col.metric(
            f"{t('target', lang)} {t(m, lang)}", f"{round(getattr(targets, m))} {unit}"
        )

    st.download_button(
        t("download", lang),
        build_csv(shown, labels, targets, lang),
        "menu.csv",
        mime="text/csv",
        key="download",
        width="stretch",
    )


def meal_total_line(meal: Meal, lang: str) -> None:
    totals = meal_totals(meal)
    parts = [
        f"{round(totals[m])} {'kcal' if m == 'kcal' else 'g ' + t(m, lang)}"
        for m in MACROS
    ]
    st.caption(f"**{t('meal_total', lang)}:** " + " · ".join(parts))


# -------------------------------------------------------------------- page --

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

fdc_key = secret("FDC_API_KEY")
if not fdc_key:
    st.error(t("missing_secrets", lang))
    st.stop()
usda = UsdaClient(fdc_key)
providers = build_providers()
llm_configured = bool(providers)

# An automatic switch (LLM down, cap reached) must set the toggle's state
# before the toggle is created on this run.
auto_message = st.session_state.pop("auto_manual_message", None)
if auto_message or not llm_configured:
    st.session_state["manual_mode"] = True

with st.sidebar:
    st.toggle(
        t("manual_mode", lang),
        key="manual_mode",
        help=t("manual_mode_help", lang),
        disabled=not llm_configured,
    )
    st.markdown(t("sidebar", lang))

if auto_message:
    st.info(auto_message)
elif not llm_configured:
    st.info(t("no_llm_configured", lang))

cap = int(setting("LLM_SESSION_CAP"))
llm_calls_used = st.session_state.setdefault("llm_calls", 0)
chain = ProviderChain(
    providers,
    cooldowns=st.session_state.setdefault("provider_cooldowns", {}),
    cooldown_s=float(setting("PROVIDER_COOLDOWN_S")),
    budget=max(cap - llm_calls_used, 0),
)
client = HybridClient(MealParser(chain), usda, k=int(setting("USDA_CANDIDATES")))

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

# One column per meal: the kind selectbox, and in free-text mode the editor.
manual_mode = st.session_state["manual_mode"]
empty_rows = pd.DataFrame({"ingredient": [""] * EDITOR_ROWS})
meal_kinds: list[tuple[str, str]] = []
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
    meal_kinds.append((meal_id, kind))
    if manual_mode:
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

numbers = meal_numbers([Meal(id=meal_id, kind=kind) for meal_id, kind in meal_kinds])
labels = {
    meal_id: meal_label(Meal(id=meal_id, kind=kind), numbers[meal_id], lang)
    for meal_id, kind in meal_kinds
}
meals: list[Meal] = []

if manual_mode:
    for meal_id, kind in meal_kinds:
        st.subheader(labels[meal_id])
        foods = render_manual_meal(meal_id, usda, lang)
        meal = Meal(id=meal_id, kind=kind, items=foods)
        if foods:
            meal_total_line(meal, lang)
        meals.append(meal)
else:
    # Results live in session state so they survive reruns. They are dropped
    # as soon as the meal inputs they were computed from change.
    fingerprint = tuple(
        (meal_id, kind, tuple(rows)) for meal_id, kind, rows in meal_inputs
    )
    if st.session_state.get("results_fingerprint") != fingerprint:
        st.session_state.pop("results", None)

    if st.button(t("compute", lang), key="compute", width="stretch"):
        max_chars, max_rows = int(setting("MAX_ROW_CHARS")), int(
            setting("MAX_ROWS_PER_MEAL")
        )
        problems = [
            validate_rows(rows, max_chars, max_rows) for _, _, rows in meal_inputs
        ]
        problems = [p for p in problems if p]
        if not any(rows for _, _, rows in meal_inputs):
            st.error(t("fill_one_table", lang))
        elif problems:
            key, args = problems[0]
            st.error(t(key, lang).format(**args))
        else:
            results: dict[str, ResolvedMeal] = {}
            try:
                with st.spinner("⏳"):
                    for meal_id, kind, rows in meal_inputs:
                        if not rows:
                            continue
                        try:
                            results[meal_id] = client.resolve_meal(rows, lang)
                        except ParseFailed:
                            results[meal_id] = ResolvedMeal(
                                items=[], failed_rows=list(enumerate(rows, start=1))
                            )
                        clear_overrides(meal_id)
                st.session_state["results"] = results
                st.session_state["results_fingerprint"] = fingerprint
            except LLMBudgetExhausted:
                switch_to_manual(t("cap_reached_info", lang).format(cap=cap))
            except LLMUnavailable as exc:
                switch_to_manual(t("llm_unavailable_info", lang).format(reason=exc))
            except UsdaError:
                st.error(t("usda_error", lang))
            finally:
                st.session_state["llm_calls"] = llm_calls_used + chain.calls

    results = st.session_state.get("results", {})
    for meal_id, kind, rows in meal_inputs:
        resolved = results.get(meal_id)
        if resolved is None:
            continue
        st.subheader(labels[meal_id])
        if not resolved.items:
            st.warning(t("parse_failed_meal", lang))
        foods = render_resolved_meal(meal_id, resolved, usda, lang)
        meal = Meal(id=meal_id, kind=kind, items=foods)
        if foods:
            meal_total_line(meal, lang)
        meals.append(meal)

render_totals(meals, labels, targets, lang)

st.markdown("---")
st.caption(t("footer", lang))
