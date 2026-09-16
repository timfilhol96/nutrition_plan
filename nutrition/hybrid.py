"""Default NutritionClient: free LLM parsing + USDA FoodData Central values."""

from dataclasses import dataclass, field

from nutrition.client import NutritionLookupError
from nutrition.models import FoodItem
from nutrition.parser import MealParser
from nutrition.usda import UsdaCandidate, UsdaClient


@dataclass
class ResolvedItem:
    row: int  # 1-based row in the meal
    text: str  # original row text
    name_en: str
    usda_query: str
    grams: float
    assumption: str | None
    candidates: list[UsdaCandidate] = field(default_factory=list)  # empty: not found

    @property
    def found(self) -> bool:
        return bool(self.candidates)


@dataclass
class ResolvedMeal:
    items: list[ResolvedItem]
    failed_rows: list[tuple[int, str]]  # (row number, text) the parser gave up on


class HybridClient:
    def __init__(self, parser: MealParser, usda: UsdaClient, k: int = 5):
        self.parser = parser
        self.usda = usda
        self.k = k

    def resolve_meal(self, rows: list[str], lang: str) -> ResolvedMeal:
        """One LLM call for the whole meal, then one USDA search per item.

        Raises LLMUnavailable, ParseFailed or UsdaError.
        """
        parsed = self.parser.parse(rows, lang)
        items = []
        for item in parsed.items:
            candidates = self.find_candidates(item.usda_query, item.name_en)
            items.append(
                ResolvedItem(
                    row=item.row,
                    text=rows[item.row - 1],
                    name_en=item.name_en,
                    usda_query=item.usda_query,
                    grams=item.grams,
                    assumption=item.assumption,
                    candidates=candidates,
                )
            )
        failed = [(number, rows[number - 1]) for number in parsed.failed_rows]
        return ResolvedMeal(items=items, failed_rows=failed)

    def find_candidates(self, usda_query: str, name_en: str) -> list[UsdaCandidate]:
        """Precise searches first (every word must match), then looser ones."""
        attempts = [
            (usda_query, True),
            (name_en, True),
            (name_en, False),
            (usda_query, False),
        ]
        tried = set()
        for query, require_all in attempts:
            key = (query.strip().lower(), require_all)
            if key in tried or not query.strip():
                continue
            tried.add(key)
            candidates = self.usda.search(query, self.k, require_all=require_all)
            if candidates:
                return candidates
        return []

    def lookup(self, text: str, lang: str) -> list[FoodItem]:
        """NutritionClient protocol: resolve one line with its best matches."""
        meal = self.resolve_meal([text], lang)
        foods = [
            item.candidates[0].scaled(item.grams, source=text)
            for item in meal.items
            if item.found
        ]
        if not foods:
            raise NutritionLookupError(text)
        return foods
