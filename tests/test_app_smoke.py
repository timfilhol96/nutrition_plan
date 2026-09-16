"""AppTest smoke tests. The LLM and USDA HTTP calls are mocked."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from conftest import fake_usda_get, items_json
from nutrition.llm import ProviderTimeout

APP = str(Path(__file__).resolve().parent.parent / "app.py")

ANSWERS = {
    "1: 2 eggs and toast": items_json(
        (1, "egg", "egg, whole, cooked, fried", 100, "eggs assumed fried"),
        (1, "toast", "bread, white, toasted", 30),
    ),
    "1: 150g rice\n2: kale": items_json(
        (1, "rice", "rice, white, cooked", 150), (2, "kale", "nonsense", 40)
    ),
}


class FakeLLM:
    """Stands in for OpenAICompatibleProvider.complete_json and counts calls."""

    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def __call__(self, provider, system, user):
        self.calls += 1
        if self.fail:
            raise ProviderTimeout(f"{provider.name}: timeout")
        for rows, answer in ANSWERS.items():
            if rows in user:
                return answer
        raise AssertionError(f"unexpected rows in prompt: {user!r}")


def patch_llm(llm):
    # A plain function so Python binds `provider` as `self`.
    return patch(
        "nutrition.llm.OpenAICompatibleProvider.complete_json",
        lambda provider, system, user: llm(provider, system, user),
    )


def make_app(**session_state):
    at = AppTest.from_file(APP, default_timeout=30)
    at.secrets["FDC_API_KEY"] = "fdc"
    at.secrets["GROQ_API_KEY"] = "groq"
    for key, value in session_state.items():
        at.session_state[key] = value
    return at


def editor_stub(frames):
    def fake_editor(self, data, key, **kwargs):
        return frames.get(key, data)

    return fake_editor


@pytest.fixture
def usda():
    with patch("nutrition.usda.httpx.get", side_effect=fake_usda_get):
        yield


def test_missing_fdc_key_shows_error():
    at = AppTest.from_file(APP, default_timeout=30)
    at.secrets["GROQ_API_KEY"] = "groq"
    at.run()
    assert not at.exception
    assert at.error and "FDC_API_KEY" in at.error[0].value


def test_no_llm_key_forces_manual_mode(usda):
    at = AppTest.from_file(APP, default_timeout=30)
    at.secrets["FDC_API_KEY"] = "fdc"
    at.run()
    assert not at.exception
    assert at.session_state["manual_mode"] is True
    assert at.sidebar.toggle(key="manual_mode").disabled
    assert at.info


@pytest.mark.parametrize("lang", ["en", "fr"])
def test_free_text_mode_end_to_end(usda, lang):
    llm = FakeLLM()
    frames = {
        "meal_0_rows": pd.DataFrame({"ingredient": ["2 eggs and toast", None, "  "]}),
        "meal_1_rows": pd.DataFrame({"ingredient": ["150g rice", "kale"]}),
    }
    with (
        patch_llm(llm),
        patch(
            "streamlit.delta_generator.DeltaGenerator.data_editor", editor_stub(frames)
        ),
    ):
        at = make_app().run()
        at.sidebar.radio(key="lang").set_value(lang).run()
        at.selectbox(key="meal_0_kind").select("lunch")
        at.selectbox(key="meal_1_kind").select("lunch").run()
        at.button(key="compute").click().run()
        assert not at.exception, at.exception

        # One LLM call per meal, two meals, numbered headers.
        assert llm.calls == 2
        lunch = {"en": "Lunch", "fr": "Déjeuner"}[lang]
        assert [h.value for h in at.subheader] == [f"{lunch} 1", f"{lunch} 2"]

        # Multi-food row -> two items with their own match selectbox.
        assert at.selectbox(key="meal_0_ov_r1_i0_match").value == 1001
        assert at.selectbox(key="meal_0_ov_r1_i1_match").value == 1002
        assert any("eggs assumed fried" in c.value for c in at.caption)
        # "kale" was not found: a manual search widget is offered.
        assert at.text_input(key="meal_1_ov_r2_i1_q").value == "kale"

        # egg 100 g (196) + toast 30 g (87.9) + rice 150 g (195) = 478.9
        assert at.metric[0].value == "479 kcal"
        assert at.session_state["llm_calls"] == 2

        # Editing grams recomputes locally: no new LLM call.
        at.number_input(key="meal_0_ov_r1_i0_grams").set_value(200.0).run()
        assert not at.exception
        assert at.metric[0].value == "675 kcal"
        # Picking another USDA match too.
        at.selectbox(key="meal_0_ov_r1_i1_match").select(1002).run()
        assert llm.calls == 2
        assert at.session_state["llm_calls"] == 2
        assert at.get("download_button")

        # Same rows again: the parse cache answers, the cap is not charged.
        at.button(key="compute").click().run()
        assert llm.calls == 2 and at.session_state["llm_calls"] == 2

        # A changed row makes the results stale.
        frames["meal_1_rows"] = pd.DataFrame({"ingredient": ["150g rice"]})
        at.run()
        assert not at.subheader and not at.metric


def test_llm_unavailable_switches_to_manual_mode(usda):
    frames = {"meal_0_rows": pd.DataFrame({"ingredient": ["2 eggs and toast"]})}
    with (
        patch_llm(FakeLLM(fail=True)),
        patch(
            "streamlit.delta_generator.DeltaGenerator.data_editor", editor_stub(frames)
        ),
    ):
        at = make_app().run()
        at.selectbox(key="meal_0_kind").select("breakfast").run()
        assert at.session_state["manual_mode"] is False
        at.button(key="compute").click().run()
        assert not at.exception, at.exception
        assert at.session_state["manual_mode"] is True
        assert at.sidebar.toggle(key="manual_mode").value is True
        assert at.info and "timeout" in at.info[0].value
        assert at.text_input(key="meal_0_manual_q")  # manual search is shown


def test_session_cap_switches_to_manual_mode(usda):
    llm = FakeLLM()
    frames = {"meal_0_rows": pd.DataFrame({"ingredient": ["2 eggs and toast"]})}
    with (
        patch_llm(llm),
        patch(
            "streamlit.delta_generator.DeltaGenerator.data_editor", editor_stub(frames)
        ),
    ):
        at = make_app(llm_calls=30).run()
        at.selectbox(key="meal_0_kind").select("breakfast").run()
        at.button(key="compute").click().run()
        assert not at.exception, at.exception
        assert llm.calls == 0
        assert at.session_state["manual_mode"] is True
        assert at.info and "30" in at.info[0].value


def test_row_guardrails_block_the_llm_call(usda):
    llm = FakeLLM()
    frames = {"meal_0_rows": pd.DataFrame({"ingredient": ["x" * 121]})}
    with (
        patch_llm(llm),
        patch(
            "streamlit.delta_generator.DeltaGenerator.data_editor", editor_stub(frames)
        ),
    ):
        at = make_app().run()
        at.selectbox(key="meal_0_kind").select("breakfast").run()
        at.button(key="compute").click().run()
        assert at.error and "121" in at.error[0].value
        assert llm.calls == 0

        frames["meal_0_rows"] = pd.DataFrame({"ingredient": ["a"] * 21})
        at.button(key="compute").click().run()
        assert at.error and "21" in at.error[0].value
        assert llm.calls == 0


@pytest.mark.parametrize("lang", ["en", "fr"])
def test_manual_mode_end_to_end(usda, lang):
    llm = FakeLLM()
    with patch_llm(llm):
        at = make_app().run()
        at.sidebar.radio(key="lang").set_value(lang)
        at.sidebar.toggle(key="manual_mode").set_value(True).run()
        at.selectbox(key="meal_0_kind").select("dinner").run()
        assert not at.exception, at.exception

        at.text_input(key="meal_0_manual_q").set_value("chicken breast").run()
        assert at.selectbox(key="meal_0_manual_sel").value == 1004
        at.number_input(key="meal_0_manual_grams").set_value(200.0)
        at.button(key="meal_0_manual_add").click().run()
        assert not at.exception, at.exception

        assert at.metric[0].value == "330 kcal"  # 165 kcal/100 g * 200 g
        assert at.get("download_button")
        assert llm.calls == 0

        at.button(key="meal_0_manual_rm_0").click().run()
        assert not at.metric
