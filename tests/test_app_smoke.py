from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from nutrition.client import NutritionLookupError
from nutrition.models import FoodItem

APP = str(Path(__file__).resolve().parent.parent / "app.py")

EGG = FoodItem("egg", 50, 71.5, 0.36, 6.28, 4.76, 0.0)
TOAST = FoodItem("toast", 29, 79.2, 14.7, 2.66, 0.97, 0.0)
RICE = FoodItem("rice", 150, 194.6, 42.2, 4.0, 0.4, 0.6)


def fake_lookup(self, text, lang):
    if text == "unknown thing":
        raise NutritionLookupError("no match")
    if text == "2 eggs and toast":
        return [EGG, EGG, TOAST]
    return [RICE]


@pytest.fixture
def app():
    at = AppTest.from_file(APP, default_timeout=30)
    at.secrets["NIX_APP_ID"] = "id"
    at.secrets["NIX_API_KEY"] = "key"
    return at


def test_missing_secrets_shows_error_instead_of_crashing():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert at.error and "NIX_APP_ID" in at.error[0].value


@pytest.mark.parametrize(
    "lang, compute_label, unmatched_label",
    [
        ("en", "GET MACROS", "No match found"),
        ("fr", "OBTENEZ VOS MACROS", "Aucun résultat"),
    ],
)
def test_full_flow_with_mocked_client(app, lang, compute_label, unmatched_label):
    with patch("nutrition.nutritionix.NutritionixClient.lookup", fake_lookup):
        at = app.run()
        at.sidebar.radio(key="lang").set_value(lang).run()
        assert not at.exception, at.exception
        assert at.button(key="compute").label == compute_label

        # Three meals: two lunches (one of them empty) and a dinner.
        at.selectbox(key="meal_0_kind").select("lunch")
        at.selectbox(key="meal_1_kind").select("lunch")
        at.selectbox(key="meal_2_kind").select("dinner").run()

        # AppTest cannot drive st.data_editor, so stub what it returns.
        editors = {
            "meal_0_rows": pd.DataFrame(
                {"ingredient": ["2 eggs and toast", "  ", None]}
            ),
            "meal_1_rows": pd.DataFrame({"ingredient": [None, "   "]}),
            "meal_2_rows": pd.DataFrame({"ingredient": ["150g rice", "unknown thing"]}),
        }

        def fake_editor(self, data, key, **kwargs):
            return editors[key]

        with patch("streamlit.delta_generator.DeltaGenerator.data_editor", fake_editor):
            at.button(key="compute").click().run()
            assert not at.exception, at.exception

            # Unmatched ingredient is reported, not fatal.
            assert len(at.warning) == 1 and unmatched_label in at.warning[0].value
            assert not at.error

            # Both lunches were selected, so the shown one is numbered.
            headers = [md.value for md in at.markdown if md.value.startswith("## ")]
            lunch = {"en": "Lunch", "fr": "Déjeuner"}[lang]
            dinner = {"en": "Dinner", "fr": "Dîner"}[lang]
            assert (
                f"## {lunch} 1" not in headers
            )  # only one non-empty lunch -> unnumbered
            assert f"## {lunch}" in headers and f"## {dinner}" in headers

            # Multi-food line contributed all three items; totals unrounded then rounded.
            expected_kcal = round(71.5 + 71.5 + 79.2 + 194.6)
            assert at.metric[0].value == f"{expected_kcal} kcal"
            assert at.get("download_button"), "download button should be rendered"

            # Results survive a rerun that does not touch the meal inputs (bug 6).
            at.number_input[0].set_value(2000).run()
            assert not at.exception
            assert at.metric[0].value == f"{expected_kcal} kcal"
            assert at.metric[0].delta == f"{expected_kcal - 2000} kcal"

        # Changing a meal input makes the results stale, so they disappear.
        editors["meal_2_rows"] = pd.DataFrame({"ingredient": ["150g rice"]})
        with patch("streamlit.delta_generator.DeltaGenerator.data_editor", fake_editor):
            at.run()
            assert not at.exception
            assert not at.metric


def test_empty_tables_show_error(app):
    with patch("nutrition.nutritionix.NutritionixClient.lookup", fake_lookup):
        at = app.run()
        at.selectbox(key="meal_0_kind").select("breakfast").run()
        at.button(key="compute").click().run()
        assert not at.exception, at.exception
        assert at.error and "🦖" in at.error[0].value
        assert not at.metric
