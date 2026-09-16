"""Shared fakes: an in-memory USDA catalogue and scripted LLM providers.

No test in this suite performs a network call.
"""

import json
from unittest.mock import MagicMock

import pytest

from nutrition.llm import ProviderError
from nutrition.parser import _parse_cached
from nutrition.usda import _search_cached


def nutrients(kcal=None, protein=0.0, fat=0.0, carbs=0.0, fiber=0.0, **extra_ids):
    """Build a foodNutrients list; `extra_ids` maps nutrient id -> value."""
    entries = []
    if kcal is not None:
        entries.append({"nutrientId": 1008, "nutrientName": "Energy", "value": kcal})
    entries += [
        {"nutrientId": 1003, "nutrientName": "Protein", "value": protein},
        {"nutrientId": 1004, "nutrientName": "Total lipid (fat)", "value": fat},
        {
            "nutrientId": 1005,
            "nutrientName": "Carbohydrate, by difference",
            "value": carbs,
        },
        {"nutrientId": 1079, "nutrientName": "Fiber, total dietary", "value": fiber},
    ]
    entries += [
        {"nutrientId": int(nid), "value": value} for nid, value in extra_ids.items()
    ]
    return entries


# Per-100 g catalogue. Search matches any keyword contained in the query.
CATALOGUE = {
    "egg": {
        "fdcId": 1001,
        "description": "Egg, whole, cooked, fried",
        "foodNutrients": nutrients(
            kcal=196, protein=13.6, fat=15.0, carbs=0.8, fiber=0
        ),
    },
    "bread": {
        "fdcId": 1002,
        "description": "Bread, white, commercially prepared, toasted",
        "foodNutrients": nutrients(
            kcal=293, protein=9.1, fat=3.6, carbs=54.4, fiber=2.4
        ),
    },
    "rice": {
        "fdcId": 1003,
        "description": "Rice, white, long-grain, regular, cooked",
        "foodNutrients": nutrients(
            kcal=130, protein=2.7, fat=0.3, carbs=28.2, fiber=0.4
        ),
    },
    "chicken": {
        "fdcId": 1004,
        "description": "Chicken, broilers or fryers, breast, meat only, cooked, roasted",
        "foodNutrients": nutrients(kcal=165, protein=31.0, fat=3.6, carbs=0.0, fiber=0),
    },
    "pâté": {
        "fdcId": 1005,
        "description": "Pâté, liver, canned",
        "foodNutrients": nutrients(
            kcal=319, protein=14.2, fat=28.0, carbs=1.5, fiber=0
        ),
    },
}


def fake_usda_get(url, params=None, timeout=None):
    query = params["query"].lower()
    foods = [food for keyword, food in CATALOGUE.items() if keyword in query]
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"foods": foods[: params.get("pageSize", 5)]}
    return response


class FakeProvider:
    """LLM provider that plays back scripted answers (strings or exceptions)."""

    def __init__(self, name, answers):
        self.name = name
        self.answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system, user):
        self.calls.append((system, user))
        if not self.answers:
            raise ProviderError(f"{self.name}: no scripted answer left")
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def items_json(*items):
    """JSON for a parser answer: items are (row, name_en, usda_query, grams[, assumption])."""
    return json.dumps(
        {
            "items": [
                {
                    "row": row,
                    "name_en": name,
                    "usda_query": query,
                    "grams": grams,
                    "assumption": rest[0] if rest else None,
                }
                for row, name, query, grams, *rest in items
            ]
        }
    )


@pytest.fixture(autouse=True)
def clear_streamlit_caches():
    _search_cached.clear()
    _parse_cached.clear()
    yield
    _search_cached.clear()
    _parse_cached.clear()
