from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")
import requests

from nutrition.client import NutritionLookupError
from nutrition.models import FoodItem
from nutrition.nutritionix import NutritionixClient, _fetch_foods, parse_food

EGG = {
    "food_name": "egg",
    "serving_weight_grams": 50,
    "nf_calories": 71.5,
    "nf_total_carbohydrate": 0.36,
    "nf_protein": 6.28,
    "nf_total_fat": 4.76,
    "nf_dietary_fiber": 0,
}
TOAST = {
    "food_name": "toast",
    "serving_weight_grams": 29,
    "nf_calories": 79.2,
    "nf_total_carbohydrate": 14.7,
    "nf_protein": 2.66,
    "nf_total_fat": 0.97,
    "nf_dietary_fiber": None,  # Nutritionix returns null for unknown nutrients
}


def _response(status=200, payload=None):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload if payload is not None else {}
    return response


@pytest.fixture(autouse=True)
def clear_cache():
    _fetch_foods.clear()
    yield
    _fetch_foods.clear()


def test_parse_food_keeps_unrounded_values_and_nulls_become_zero():
    item = parse_food(TOAST, source="1 slice of toast")
    assert item == FoodItem(
        name="toast",
        grams=29.0,
        kcal=79.2,
        carbs=14.7,
        protein=2.66,
        fat=0.97,
        fiber=0.0,
        source="1 slice of toast",
    )


def test_lookup_returns_every_food_in_a_multi_food_line():
    with patch("nutrition.nutritionix.requests.post") as post:
        post.return_value = _response(200, {"foods": [EGG, EGG, TOAST]})
        items = NutritionixClient("id", "key").lookup("2 eggs and toast", "en")

    assert [item.name for item in items] == ["egg", "egg", "toast"]
    assert all(item.source == "2 eggs and toast" for item in items)
    post.assert_called_once()
    assert post.call_args.kwargs["data"] == {"query": "2 eggs and toast"}
    assert post.call_args.kwargs["headers"]["x-app-id"] == "id"


@pytest.mark.parametrize(
    "status, payload",
    [(404, {"message": "no food"}), (401, {}), (200, {"foods": []}), (200, {})],
)
def test_lookup_raises_on_http_error_or_missing_foods(status, payload):
    with patch("nutrition.nutritionix.requests.post") as post:
        post.return_value = _response(status, payload)
        with pytest.raises(NutritionLookupError):
            NutritionixClient("id", "key").lookup("nothing", "en")


def test_lookup_wraps_network_errors():
    with patch("nutrition.nutritionix.requests.post") as post:
        post.side_effect = requests.ConnectionError("down")
        with pytest.raises(NutritionLookupError):
            NutritionixClient("id", "key").lookup("egg", "en")


def test_failures_are_not_cached_but_successes_are():
    client = NutritionixClient("id", "key")
    with patch("nutrition.nutritionix.requests.post") as post:
        post.return_value = _response(500, {})
        with pytest.raises(NutritionLookupError):
            client.lookup("egg", "en")
        # The next call must hit the network again and now succeeds.
        post.return_value = _response(200, {"foods": [EGG]})
        assert client.lookup("egg", "en")[0].name == "egg"
        assert client.lookup("egg", "en")[0].name == "egg"
        assert post.call_count == 2
