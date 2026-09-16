"""USDA FoodData Central search, restricted to per-100 g data types."""

from dataclasses import dataclass

import httpx
import streamlit as st

from nutrition.config import CACHE_TTL_S
from nutrition.models import FoodItem
from nutrition.plan import atwater_kcal

SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
# Foundation and SR Legacy foods report nutrients per 100 g.
DATA_TYPES = ("Foundation", "SR Legacy")
TIMEOUT_S = 20.0

# FDC nutrient IDs (verified against live search responses).
NUTRIENT_IDS = {
    "kcal": 1008,
    "protein": 1003,
    "fat": 1004,
    "carbs": 1005,
    "fiber": 1079,
}
# Used when 1008 (Energy, kcal) is absent: Atwater specific, Atwater general, then kJ.
ENERGY_ATWATER_IDS = (2048, 2047)
ENERGY_KJ_ID = 1062
KJ_PER_KCAL = 4.184


class UsdaError(Exception):
    """Raised when the FDC API cannot be reached or returns an error."""


@dataclass(frozen=True)
class UsdaCandidate:
    fdc_id: int
    description: str
    per_100g: dict[str, float]  # keys: kcal, carbs, protein, fat, fiber

    def scaled(self, grams: float, source: str = "") -> FoodItem:
        factor = grams / 100
        return FoodItem(
            name=self.description,
            grams=grams,
            kcal=self.per_100g["kcal"] * factor,
            carbs=self.per_100g["carbs"] * factor,
            protein=self.per_100g["protein"] * factor,
            fat=self.per_100g["fat"] * factor,
            fiber=self.per_100g["fiber"] * factor,
            source=source,
        )


def nutrients_per_100g(food_nutrients: list[dict]) -> dict[str, float]:
    by_id = {
        n.get("nutrientId"): float(n["value"])
        for n in food_nutrients
        if n.get("value") is not None
    }
    values = {macro: by_id.get(nid, 0.0) for macro, nid in NUTRIENT_IDS.items()}
    if NUTRIENT_IDS["kcal"] not in by_id:
        values["kcal"] = _energy_fallback(by_id, values)
    return values


def _energy_fallback(by_id: dict[int, float], values: dict[str, float]) -> float:
    for nid in ENERGY_ATWATER_IDS:
        if nid in by_id:
            return by_id[nid]
    if ENERGY_KJ_ID in by_id:
        return by_id[ENERGY_KJ_ID] / KJ_PER_KCAL
    return atwater_kcal(values["carbs"], values["protein"], values["fat"])


def parse_candidate(food: dict) -> UsdaCandidate:
    return UsdaCandidate(
        fdc_id=int(food["fdcId"]),
        description=food["description"],
        per_100g=nutrients_per_100g(food.get("foodNutrients", [])),
    )


# Description prefixes that an ingredient line almost never means. They are
# moved to the end of the candidate list unless the query itself asks for them.
DEMOTED_PREFIXES = {
    "babyfood": ("baby", "babyfood", "infant"),
    "beverages": (
        "beverage",
        "drink",
        "juice",
        "soda",
        "shake",
        "smoothie",
        "coffee",
        "tea",
    ),
    "snacks": ("snack", "bar", "chips", "crisps"),
    "snack": ("snack", "bar"),
    "fast foods": (
        "fast",
        "burger",
        "fries",
        "pizza",
        "nuggets",
        "mcdonald",
        "big mac",
    ),
    "restaurant": ("restaurant",),
    "formulated bar": ("bar",),
}


def rank_candidates(candidates: list[UsdaCandidate], query: str) -> list[UsdaCandidate]:
    """Keep FDC's order but push demoted categories last (stable)."""
    words = set(query.lower().replace(",", " ").split())

    def demoted(candidate: UsdaCandidate) -> bool:
        prefix = candidate.description.split(",")[0].strip().lower()
        hints = DEMOTED_PREFIXES.get(prefix)
        return hints is not None and not any(hint in words for hint in hints)

    return sorted(candidates, key=demoted)


@st.cache_data(ttl=CACHE_TTL_S, show_spinner=False)
def _search_cached(
    api_key: str, query: str, k: int, require_all: bool
) -> list[UsdaCandidate]:
    # Raises on failure so that failures are never cached.
    params = {
        "query": query,
        "dataType": ",".join(DATA_TYPES),
        "pageSize": k,
        "api_key": api_key,
    }
    if require_all:
        # FDC search is OR-based and ranks by term frequency, so a query that
        # is not a real description matches on filler words. Requiring every
        # word turns it into a precision gate: exact hits or nothing.
        params["requireAllWords"] = "true"
    try:
        response = httpx.get(SEARCH_URL, params=params, timeout=TIMEOUT_S)
    except httpx.HTTPError as exc:
        raise UsdaError(str(exc)) from exc
    if response.status_code != 200:
        raise UsdaError(f"HTTP {response.status_code}")
    candidates = [parse_candidate(food) for food in response.json().get("foods", [])]
    return rank_candidates(candidates, query)


class UsdaClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(
        self, query: str, k: int = 5, require_all: bool = False
    ) -> list[UsdaCandidate]:
        query = " ".join(query.split())
        if not query:
            return []
        return _search_cached(self.api_key, query, k, require_all)
