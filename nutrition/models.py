from dataclasses import dataclass, field

MEAL_KINDS = ("breakfast", "lunch", "snack", "dinner")


@dataclass(frozen=True)
class FoodItem:
    name: str
    grams: float
    kcal: float
    carbs: float
    protein: float
    fat: float
    fiber: float = 0.0
    # The ingredient text this item was looked up from. One line of text can
    # yield several items (e.g. "2 eggs and toast").
    source: str = ""


@dataclass
class Meal:
    id: str
    kind: str  # one of MEAL_KINDS
    items: list[FoodItem] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.items


@dataclass(frozen=True)
class DailyTargets:
    kcal: float
    carbs: float
    protein: float
    fat: float
