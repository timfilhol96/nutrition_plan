from unittest.mock import MagicMock, patch

import pytest

from conftest import fake_usda_get, nutrients
from nutrition.plan import MACROS
from nutrition.usda import (
    UsdaCandidate,
    UsdaClient,
    UsdaError,
    nutrients_per_100g,
    parse_candidate,
)


def test_nutrient_mapping_by_id():
    values = nutrients_per_100g(
        nutrients(kcal=165, protein=31, fat=3.6, carbs=0.5, fiber=0.2)
    )
    assert values == {
        "kcal": 165,
        "protein": 31,
        "fat": 3.6,
        "carbs": 0.5,
        "fiber": 0.2,
    }


def test_missing_nutrients_default_to_zero_and_ignore_nulls():
    entries = [{"nutrientId": 1003, "value": None}, {"nutrientId": 1005, "value": 10}]
    assert nutrients_per_100g(entries) == {
        "kcal": 40,  # Atwater from the macros that exist: 4 * 10 g carbs
        "protein": 0.0,
        "fat": 0.0,
        "carbs": 10.0,
        "fiber": 0.0,
    }


def test_energy_fallback_order():
    macros = dict(protein=10.0, fat=10.0, carbs=10.0)
    # Atwater specific (2048) beats Atwater general (2047).
    assert (
        nutrients_per_100g(nutrients(**macros, **{"2047": 170, "2048": 172}))["kcal"]
        == 172
    )
    assert nutrients_per_100g(nutrients(**macros, **{"2047": 170}))["kcal"] == 170
    # Then the kJ value converted to kcal.
    assert nutrients_per_100g(nutrients(**macros, **{"1062": 711.28}))[
        "kcal"
    ] == pytest.approx(170)
    # Then computed with the Atwater factors.
    assert nutrients_per_100g(nutrients(**macros))["kcal"] == 4 * 10 + 4 * 10 + 9 * 10
    # 1008 always wins when present.
    assert (
        nutrients_per_100g(nutrients(kcal=150, **macros, **{"2048": 172}))["kcal"]
        == 150
    )


def test_gram_scaling():
    candidate = UsdaCandidate(
        1,
        "Rice, cooked",
        {"kcal": 130, "carbs": 28.2, "protein": 2.7, "fat": 0.3, "fiber": 0.4},
    )
    food = candidate.scaled(250, source="250g rice")
    assert food.grams == 250
    assert food.kcal == pytest.approx(325)
    assert food.carbs == pytest.approx(70.5)
    assert food.protein == pytest.approx(6.75)
    assert food.fat == pytest.approx(0.75)
    assert food.fiber == pytest.approx(1.0)
    assert food.name == "Rice, cooked" and food.source == "250g rice"
    assert candidate.scaled(0).kcal == 0


def test_search_restricts_data_types_and_parses_candidates():
    with patch("nutrition.usda.httpx.get", side_effect=fake_usda_get) as get:
        candidates = UsdaClient("KEY").search("  chicken   breast ", k=3)
    params = get.call_args.kwargs["params"]
    assert params["dataType"] == "Foundation,SR Legacy"
    assert params["pageSize"] == 3
    assert params["api_key"] == "KEY"
    assert params["query"] == "chicken breast"
    assert [c.fdc_id for c in candidates] == [1004]
    assert candidates[0].per_100g["protein"] == 31.0


def test_search_is_cached_and_empty_queries_skip_the_network():
    client = UsdaClient("KEY")
    with patch("nutrition.usda.httpx.get", side_effect=fake_usda_get) as get:
        assert client.search("egg") == client.search("egg")
        assert get.call_count == 1
        assert client.search("   ") == []
        assert get.call_count == 1


def test_search_errors_are_raised_not_cached():
    client = UsdaClient("KEY")
    failing = MagicMock()
    failing.status_code = 500
    with patch("nutrition.usda.httpx.get", return_value=failing):
        with pytest.raises(UsdaError):
            client.search("egg")
    with patch("nutrition.usda.httpx.get", side_effect=fake_usda_get) as get:
        assert client.search("egg")[0].description.startswith("Egg")
        assert get.call_count == 1


def test_parse_candidate():
    candidate = parse_candidate(
        {
            "fdcId": "7",
            "description": "Butter, salted",
            "foodNutrients": nutrients(kcal=717),
        }
    )
    assert candidate.fdc_id == 7 and candidate.per_100g["kcal"] == 717


def test_require_all_words_is_passed_through():
    with patch("nutrition.usda.httpx.get", side_effect=fake_usda_get) as get:
        UsdaClient("KEY").search("egg fried", require_all=True)
        UsdaClient("KEY").search("egg fried")
    flags = [c.kwargs["params"].get("requireAllWords") for c in get.call_args_list]
    assert flags == ["true", None]


def _cand(description):
    return UsdaCandidate(
        hash(description) % 10**6, description, {m: 0.0 for m in MACROS}
    )


def test_rank_candidates_demotes_babyfood_beverages_and_snack_bars():
    from nutrition.usda import rank_candidates

    hits = [
        _cand("Snack, Mixed Berry Bar"),
        _cand("Babyfood, banana with mixed berries, strained"),
        _cand("Beverages, POWERADE, Zero, Mixed Berry"),
        _cand("Blueberries, frozen, unsweetened"),
        _cand("Vegetables, mixed, frozen, unprepared"),
    ]
    ranked = [c.description for c in rank_candidates(hits, "mixed berries")]
    assert ranked[:2] == [
        "Blueberries, frozen, unsweetened",
        "Vegetables, mixed, frozen, unprepared",
    ]
    assert ranked[2:] == [
        c.description for c in hits[:3]
    ]  # demoted, original order kept

    # The demotion is lifted when the query asks for that category.
    ranked = [c.description for c in rank_candidates(hits, "mixed berry snack bar")]
    assert ranked[0] == "Snack, Mixed Berry Bar"
    ranked = [c.description for c in rank_candidates(hits, "babyfood banana")]
    assert ranked[0].startswith("Babyfood")
