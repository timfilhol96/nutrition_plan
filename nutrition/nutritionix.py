"""DEPRECATED: NutritionClient backed by the Nutritionix natural-language endpoint.

The Nutritionix free tier has been discontinued. nutrition.hybrid.HybridClient
(free LLM parser + USDA FoodData Central) is the default client. This module is
kept for reference only and will be removed. It sends French input untranslated.
"""

import warnings

import requests
import streamlit as st

from nutrition.client import NutritionLookupError
from nutrition.models import FoodItem

URL = "https://trackapi.nutritionix.com/v2/natural/nutrients"
TIMEOUT_S = 20


@st.cache_data(show_spinner=False)
def _fetch_foods(app_id: str, app_key: str, text: str) -> list[dict]:
    # Returns the parsed "foods" list, never the Response object, and raises
    # on failure so that st.cache_data never caches a failed lookup.
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "x-app-id": app_id,
        "x-app-key": app_key,
        "x-remote-user-id": "0",
    }
    try:
        response = requests.post(
            URL, headers=headers, data={"query": text}, timeout=TIMEOUT_S
        )
    except requests.RequestException as exc:
        raise NutritionLookupError(str(exc)) from exc
    if response.status_code != 200:
        raise NutritionLookupError(f"HTTP {response.status_code}")
    foods = response.json().get("foods")
    if not foods:
        raise NutritionLookupError("no match")
    return foods


def parse_food(food: dict, source: str) -> FoodItem:
    """Convert one Nutritionix food dict into a FoodItem (no rounding)."""
    return FoodItem(
        name=food["food_name"],
        grams=float(food.get("serving_weight_grams") or 0),
        kcal=float(food.get("nf_calories") or 0),
        carbs=float(food.get("nf_total_carbohydrate") or 0),
        protein=float(food.get("nf_protein") or 0),
        fat=float(food.get("nf_total_fat") or 0),
        fiber=float(food.get("nf_dietary_fiber") or 0),
        source=source,
    )


class NutritionixClient:
    def __init__(self, app_id: str, app_key: str):
        warnings.warn(
            "NutritionixClient is deprecated; use nutrition.hybrid.HybridClient",
            DeprecationWarning,
            stacklevel=2,
        )
        self.app_id = app_id
        self.app_key = app_key

    def lookup(self, text: str, lang: str) -> list[FoodItem]:
        foods = _fetch_foods(self.app_id, self.app_key, text)
        return [parse_food(food, text) for food in foods]
