from unittest.mock import patch

import pytest

from conftest import FakeProvider, fake_usda_get, items_json
from nutrition.client import NutritionLookupError
from nutrition.hybrid import HybridClient
from nutrition.llm import ProviderChain
from nutrition.parser import MealParser
from nutrition.usda import UsdaClient


def make_client(*answers):
    provider = FakeProvider("groq", answers)
    return (
        HybridClient(MealParser(ProviderChain([provider], {})), UsdaClient("KEY")),
        provider,
    )


def test_resolve_meal_matches_each_item_and_falls_back_to_name_en():
    client, provider = make_client(
        items_json(
            (1, "egg", "egg, whole, cooked, fried", 100),
            (1, "toast", "bread, white, toasted", 30),
            (2, "rice", "nonsense usda descriptor", 150),  # falls back to name_en
            (3, "kale", "nonsense", 40),  # not found at all
        )
    )
    with patch("nutrition.usda.httpx.get", side_effect=fake_usda_get) as get:
        meal = client.resolve_meal(["2 eggs and toast", "150g rice", "kale"], "en")

    assert len(provider.calls) == 1
    assert [(i.row, i.text) for i in meal.items] == [
        (1, "2 eggs and toast"),
        (1, "2 eggs and toast"),
        (2, "150g rice"),
        (3, "kale"),
    ]
    assert meal.items[0].candidates[0].fdc_id == 1001
    assert meal.items[2].candidates[0].description.startswith("Rice")
    assert not meal.items[3].found
    calls = [
        (
            c.kwargs["params"]["query"],
            c.kwargs["params"].get("requireAllWords") == "true",
        )
        for c in get.call_args_list
    ]
    assert calls == [
        ("egg, whole, cooked, fried", True),  # exact descriptor: one precise hit
        ("bread, white, toasted", True),
        ("nonsense usda descriptor", True),  # nothing -> name_en, all words
        ("rice", True),
        ("nonsense", True),  # the full ladder for a food that does not exist
        ("kale", True),
        ("kale", False),
        ("nonsense", False),
    ]
    assert meal.failed_rows == []


def test_precise_search_beats_loose_search_on_a_partial_descriptor():
    # "chicken breast raw" is not in the catalogue verbatim: the all-words
    # search fails and the ladder moves on to name_en (all words), which hits.
    client, _ = make_client(items_json((1, "chicken", "chicken breast raw", 100)))
    with patch("nutrition.usda.httpx.get", side_effect=fake_usda_get) as get:
        meal = client.resolve_meal(["100g raw chicken"], "en")
    assert meal.items[0].candidates[0].description.startswith("Chicken")
    flags = [c.kwargs["params"].get("requireAllWords") for c in get.call_args_list]
    assert flags == ["true", "true"]


def test_failed_rows_carry_their_text():
    client, _ = make_client(items_json((2, "rice", "rice, cooked", 150)))
    with patch("nutrition.usda.httpx.get", side_effect=fake_usda_get):
        meal = client.resolve_meal(["gibberish", "150g rice"], "en")
    assert meal.failed_rows == [(1, "gibberish")]


def test_override_recomputes_locally_without_a_new_llm_call():
    client, provider = make_client(items_json((1, "rice", "rice, cooked", 150)))
    with patch("nutrition.usda.httpx.get", side_effect=fake_usda_get):
        meal = client.resolve_meal(["150g rice"], "en")
    item = meal.items[0]
    default = item.candidates[0].scaled(item.grams, source=item.text)
    assert default.kcal == pytest.approx(195)
    # The user edits the grams: only arithmetic happens.
    edited = item.candidates[0].scaled(300, source=item.text)
    assert edited.kcal == pytest.approx(390)
    assert len(provider.calls) == 1


def test_lookup_protocol_returns_best_matches_or_raises():
    client, _ = make_client(
        items_json(
            (1, "egg", "egg, whole, cooked, fried", 100), (1, "toast", "bread", 30)
        ),
        items_json((1, "kale", "nonsense", 40)),
    )
    with patch("nutrition.usda.httpx.get", side_effect=fake_usda_get):
        foods = client.lookup("2 eggs and toast", "en")
        assert [f.name[:5] for f in foods] == ["Egg, ", "Bread"]
        assert foods[0].kcal == pytest.approx(196)
        with pytest.raises(NutritionLookupError):
            client.lookup("kale", "en")
