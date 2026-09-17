import pandas as pd
import streamlit as st

from nutrition.config import secret, setting
from nutrition.export import build_csv, build_long_csv
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
    ACTIVITY_MULTIPLIERS,
    CALORIE_PLANS,
    MACROS,
    TARGET_MACROS,
    atwater_kcal,
    clean_rows,
    daily_totals,
    diff_vs_targets,
    kcal_mismatch,
    meal_numbers,
    meal_totals,
    mifflin_st_jeor,
    shift_plan,
    targets_from_tdee,
    tdee,
)
from nutrition.usda import UsdaCandidate, UsdaClient, UsdaError

EDITOR_ROWS = 15
EXTRAS_ID = "extras"

# Inputs restored from / persisted to the URL: key -> (cast, default, min, max, options).
# Neutral defaults (2000 kcal split 50/20/30), not anyone's personal macros.
PERSISTED = {
    "plan": (str, "maintenance", None, None, tuple(CALORIE_PLANS)),
    "kcal": (int, 2000, 0, 20000, None),
    "carbs": (int, 250, 0, 5000, None),
    "protein": (int, 100, 0, 5000, None),
    "fat": (int, 67, 0, 5000, None),
    "sex": (str, "male", None, None, ("male", "female")),
    "age": (int, 30, 10, 100, None),
    "weight": (float, 70.0, 30.0, 300.0, None),
    "height": (float, 175.0, 100.0, 250.0, None),
    "activity": (str, "moderate", None, None, tuple(ACTIVITY_MULTIPLIERS)),
    "gkg": (float, 1.6, 0.5, 3.0, None),
}
ITEM_COLUMNS = [3, 4, 1.3, 1, 1, 1, 1]  # text, match, grams, kcal, carbs, protein, fat
MEAL_ICONS = {
    "breakfast": "🍳",
    "lunch": "🥗",
    "snack": "🍎",
    "dinner": "🍽️",
    EXTRAS_ID: "➕",
}
OVER_COLOR = "#e0a044"  # amber for the part of a bar past its target

# Styles of the summary strip (macro cards + per-meal chips). Colors come from
# the theme so the strip follows .streamlit/config.toml and dark mode.
SUMMARY_CSS = """<style>
.np-summary{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:.75rem;margin:.25rem 0 .6rem}}
.np-card{{background:{surface};border-radius:.6rem;padding:.65rem .9rem .8rem}}
.np-head{{display:flex;justify-content:space-between;gap:.5rem;font-size:.78rem;opacity:.75}}
.np-note{{font-weight:600;white-space:nowrap}}
.np-over .np-note{{color:{over};opacity:1}}
.np-ok .np-note{{color:{primary};opacity:1}}
.np-value{{font-size:1.45rem;font-weight:650;line-height:1.3;margin:.1rem 0 .45rem}}
.np-target{{font-size:.85rem;font-weight:400;opacity:.65}}
.np-track{{position:relative;height:8px;border-radius:4px;background:rgba(128,128,128,.22);
  overflow:hidden}}
.np-fill{{position:absolute;left:0;top:0;bottom:0;background:{primary};border-radius:4px}}
.np-overfill{{position:absolute;top:0;bottom:0;background:{over}}}
.np-marker{{position:absolute;top:0;bottom:0;width:2px;margin-left:-1px;background:{text};opacity:.55}}
.np-meals{{display:flex;flex-wrap:wrap;gap:.3rem 1.2rem;font-size:.85rem;opacity:.85;
  margin-bottom:.75rem}}
</style>"""


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


def restore_from_url() -> None:
    """Seed the persisted widgets from st.query_params on the first run."""
    for key, (cast, default, low, high, options) in PERSISTED.items():
        if key in st.session_state:
            continue
        raw = st.query_params.get(key)
        try:
            value = cast(float(raw)) if raw is not None and cast is not str else raw
        except ValueError:
            value = None
        if value is None or (options and value not in options):
            value = default
        if low is not None:
            value = min(max(value, low), high)
        st.session_state[key] = value
    st.session_state.setdefault("plan_applied", st.session_state["plan"])


def sync_to_url() -> None:
    for key in PERSISTED:
        value = str(st.session_state[key])
        if st.query_params.get(key) != value:
            st.query_params[key] = value


def current_targets() -> DailyTargets:
    return DailyTargets(
        kcal=st.session_state["kcal"],
        carbs=st.session_state["carbs"],
        protein=st.session_state["protein"],
        fat=st.session_state["fat"],
    )


def set_targets(targets: DailyTargets) -> None:
    for macro in TARGET_MACROS:
        st.session_state[macro] = round(getattr(targets, macro))


def on_plan_change() -> None:
    """Shift kcal (and carbs by kcal/4) by the difference between the two plans."""
    old, new = st.session_state["plan_applied"], st.session_state["plan"]
    set_targets(shift_plan(current_targets(), old, new))
    st.session_state["plan_applied"] = new


def estimated_targets() -> tuple[float, float, DailyTargets]:
    """(BMR, maintenance TDEE, targets under the selected plan) from the TDEE inputs."""
    state = st.session_state
    bmr = mifflin_st_jeor(state["sex"], state["age"], state["weight"], state["height"])
    maintenance = tdee(bmr, state["activity"])
    kcal = maintenance + CALORIE_PLANS[state["plan"]]
    return bmr, maintenance, targets_from_tdee(kcal, state["weight"], state["gkg"])


def on_use_estimate() -> None:
    set_targets(estimated_targets()[2])


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


def theme_colors() -> dict[str, str]:
    """Theme colors from config.toml for the current (light/dark) theme."""
    dark = st.context.theme.type == "dark"

    def option(name: str, fallback: str) -> str:
        value = st.get_option(f"theme.dark.{name}") if dark else None
        return value or st.get_option(f"theme.{name}") or fallback

    return {
        "primary": option("primaryColor", "#3f7d4e"),
        "surface": option("secondaryBackgroundColor", "#f1efe7"),
        "text": option("textColor", "#24302a"),
        "over": OVER_COLOR,
    }


def macro_card(macro: str, total: float, target: float, lang: str) -> str:
    """One summary card: value / target, a bar with a target marker, and the
    amount left or over. The bar keeps growing past the target (in amber)."""
    unit = "kcal" if macro == "kcal" else "g"
    diff = total - target
    span = max(total, target, 1.0)
    fill = min(total, target) / span * 100
    over = max(diff, 0.0) / span * 100
    marker = target / span * 100
    if target > 0 and abs(diff) <= 0.05 * target:
        state, note = "ok", t("on_target", lang)
    elif diff > 0:
        state, note = "over", t("over", lang).format(diff=round(diff), unit=unit)
    else:
        state, note = "under", t("left", lang).format(diff=round(-diff), unit=unit)
    return (
        f'<div class="np-card np-{state}">'
        f'<div class="np-head"><span>{t(macro, lang)}</span>'
        f'<span class="np-note">{note}</span></div>'
        f'<div class="np-value">{round(total)}'
        f'<span class="np-target"> / {round(target)} {unit}</span></div>'
        f'<div class="np-track"><div class="np-fill" style="width:{fill:.1f}%"></div>'
        f'<div class="np-overfill" style="left:{marker:.1f}%;width:{over:.1f}%"></div>'
        f'<div class="np-marker" style="left:{marker:.1f}%"></div></div>'
        "</div>"
    )


def render_summary(
    container,
    meals: list[Meal],
    labels: dict[str, str],
    targets: DailyTargets,
    lang: str,
) -> None:
    """Daily totals vs targets, drawn into a container placed above the meals."""
    shown = [meal for meal in meals if not meal.is_empty]
    if not shown:
        return
    totals = daily_totals(shown)
    cards = "".join(
        macro_card(m, totals[m], getattr(targets, m), lang) for m in TARGET_MACROS
    )
    chips = "".join(
        f"<span>{MEAL_ICONS[meal.kind]} {labels[meal.id]} "
        f'<b>{round(meal_totals(meal)["kcal"])} kcal</b></span>'
        for meal in shown
    )
    with container:
        st.subheader(t("summary_title", lang))
        st.markdown(
            SUMMARY_CSS.format(**theme_colors())
            + f'<div class="np-summary">{cards}</div><div class="np-meals">{chips}</div>',
            unsafe_allow_html=True,
        )


def render_downloads(
    meals: list[Meal], labels: dict[str, str], targets: DailyTargets, lang: str
) -> None:
    shown = [meal for meal in meals if not meal.is_empty]
    if not shown:
        return
    left, right = st.columns(2)
    left.download_button(
        t("download", lang),
        build_csv(shown, labels, targets, lang),
        "menu.csv",
        mime="text/csv",
        key="download",
        width="stretch",
    )
    right.download_button(
        t("download_long", lang),
        build_long_csv(shown, labels),
        "menu_detailed.csv",
        mime="text/csv",
        key="download_long",
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
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="auto",
)
restore_from_url()

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

st.title(f"🍽️ {t('app_title', lang)}")
st.header(t("daily_macros", lang))

# ---- targets ----
st.selectbox(
    t("plan", lang),
    list(CALORIE_PLANS),
    format_func=lambda p: plan_label(p, lang),
    key="plan",
    on_change=on_plan_change,
)

with st.expander(t("tdee_expander", lang)):
    cols = st.columns(3)
    cols[0].selectbox(
        t("sex", lang), ["male", "female"], format_func=lambda s: t(s, lang), key="sex"
    )
    cols[1].number_input(t("age", lang), min_value=10, max_value=100, step=1, key="age")
    cols[2].selectbox(
        t("activity", lang),
        list(ACTIVITY_MULTIPLIERS),
        format_func=lambda a: t(f"activity_{a}", lang),
        key="activity",
    )
    cols = st.columns(3)
    cols[0].number_input(
        t("weight", lang), min_value=30.0, max_value=300.0, step=0.5, key="weight"
    )
    cols[1].number_input(
        t("height", lang), min_value=100.0, max_value=250.0, step=1.0, key="height"
    )
    cols[2].number_input(
        t("protein_per_kg", lang), min_value=0.5, max_value=3.0, step=0.1, key="gkg"
    )
    bmr, maintenance, estimate = estimated_targets()
    st.markdown(
        t("tdee_result", lang).format(
            bmr=round(bmr),
            tdee=round(maintenance),
            kcal=round(estimate.kcal),
            protein=round(estimate.protein),
            fat=round(estimate.fat),
            carbs=round(estimate.carbs),
        )
    )
    st.button(t("use_estimate", lang), key="use_estimate", on_click=on_use_estimate)

target_cols = st.columns(4)
target_cols[0].number_input(t("target_kcal", lang), min_value=0, step=10, key="kcal")
target_cols[1].number_input(t("target_carbs", lang), min_value=0, step=5, key="carbs")
target_cols[2].number_input(
    t("target_protein", lang), min_value=0, step=5, key="protein"
)
target_cols[3].number_input(t("target_fat", lang), min_value=0, step=5, key="fat")
targets = current_targets()
if kcal_mismatch(targets) > 0.05:
    st.warning(
        t("kcal_mismatch", lang).format(
            atwater=round(atwater_kcal(targets.carbs, targets.protein, targets.fat)),
            kcal=round(targets.kcal),
        )
    )
sync_to_url()

# The daily summary is filled in once the meals below are known.
summary_slot = st.container()

# ---- menu: one tab per meal, plus the daily extras ----
st.header(t("menu", lang))
nb_meals = st.number_input(
    t("nb_meals", lang), min_value=1, step=1, value=3, key="nb_meals"
)
manual_mode = st.session_state["manual_mode"]
empty_rows = pd.DataFrame({"ingredient": [""] * EDITOR_ROWS})

meal_ids = [f"meal_{i}" for i in range(nb_meals)]
# Tab labels come from the kind selectboxes' state (set on a previous run):
# "🥗 Lunch 2" once a kind is chosen, "Meal 2" until then.
known_kinds = [
    Meal(id=meal_id, kind=st.session_state[f"{meal_id}_kind"])
    for meal_id in meal_ids
    if st.session_state.get(f"{meal_id}_kind")
]
known_numbers = meal_numbers(known_kinds)
known_labels = {
    meal.id: f"{MEAL_ICONS[meal.kind]} {meal_label(meal, known_numbers[meal.id], lang)}"
    for meal in known_kinds
}
tabs = st.tabs(
    [
        known_labels.get(meal_id, t("meal_tab", lang).format(n=i + 1))
        for i, meal_id in enumerate(meal_ids)
    ]
    + [f"{MEAL_ICONS[EXTRAS_ID]} {t('extras', lang)}"]
)

# Pass 1: kinds and inputs. Meals without a kind are skipped; extras always count.
meal_kinds: list[tuple[str, str]] = []
meal_inputs: list[tuple[str, str, list[str]]] = []
for meal_id, tab in zip(meal_ids, tabs):
    with tab:
        kind = st.selectbox(
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
        edited = st.data_editor(
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
with tabs[-1]:
    st.caption(t("extras_help", lang))
    meal_kinds.append((EXTRAS_ID, EXTRAS_ID))
    if not manual_mode:
        edited = st.data_editor(
            empty_rows,
            key=f"{EXTRAS_ID}_rows",
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            column_config={
                "ingredient": st.column_config.TextColumn(t("ingredient", lang))
            },
        )
        meal_inputs.append((EXTRAS_ID, EXTRAS_ID, clean_rows(edited["ingredient"])))

numbers = meal_numbers([Meal(id=meal_id, kind=kind) for meal_id, kind in meal_kinds])
labels = {
    meal_id: meal_label(Meal(id=meal_id, kind=kind), numbers[meal_id], lang)
    for meal_id, kind in meal_kinds
}
tab_of = dict(zip(meal_ids + [EXTRAS_ID], tabs))
meals: list[Meal] = []

if manual_mode:
    for meal_id, kind in meal_kinds:
        with tab_of[meal_id]:
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

    # Pass 2: results inside their tabs.
    results = st.session_state.get("results", {})
    for meal_id, kind, rows in meal_inputs:
        resolved = results.get(meal_id)
        if resolved is None:
            continue
        with tab_of[meal_id]:
            if not resolved.items:
                st.warning(t("parse_failed_meal", lang))
            foods = render_resolved_meal(meal_id, resolved, usda, lang)
            meal = Meal(id=meal_id, kind=kind, items=foods)
            if foods:
                meal_total_line(meal, lang)
            meals.append(meal)

    if st.button(t("compute", lang), key="compute", type="primary", width="stretch"):
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
            new_results: dict[str, ResolvedMeal] = {}
            try:
                with st.spinner("⏳"):
                    for meal_id, kind, rows in meal_inputs:
                        if not rows:
                            continue
                        try:
                            new_results[meal_id] = client.resolve_meal(rows, lang)
                        except ParseFailed:
                            new_results[meal_id] = ResolvedMeal(
                                items=[], failed_rows=list(enumerate(rows, start=1))
                            )
                        clear_overrides(meal_id)
                st.session_state["results"] = new_results
                st.session_state["results_fingerprint"] = fingerprint
                st.session_state["llm_calls"] = llm_calls_used + chain.calls
                st.rerun()  # results render inside the tabs above
            except LLMBudgetExhausted:
                switch_to_manual(t("cap_reached_info", lang).format(cap=cap))
            except LLMUnavailable as exc:
                switch_to_manual(t("llm_unavailable_info", lang).format(reason=exc))
            except UsdaError:
                st.error(t("usda_error", lang))
            finally:
                st.session_state["llm_calls"] = llm_calls_used + chain.calls

render_summary(summary_slot, meals, labels, targets, lang)
render_downloads(meals, labels, targets, lang)

st.divider()
st.caption(t("footer", lang))
st.caption(t("disclaimer", lang))
