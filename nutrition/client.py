from typing import Protocol

from nutrition.models import FoodItem


class NutritionLookupError(Exception):
    """Raised when a data source cannot resolve an ingredient text."""


class NutritionClient(Protocol):
    def lookup(self, text: str, lang: str) -> list[FoodItem]:
        """Resolve one line of ingredient text into one or more food items.

        Raises NutritionLookupError when nothing matches or the source fails.
        """
        ...
