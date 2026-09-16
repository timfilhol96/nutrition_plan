LANGUAGES = ("en", "fr")

STRINGS = {
    "en": {
        "language": "English 🇬🇧",
        "app_title": "NUTRITION PLAN",
        "sidebar": """
# MACROS CALCULATOR
---
## TUTORIAL
- Enter your daily kcal and macros intake
- Create your daily meals by listing all the ingredients and quantities using natural language
- Generate your macros
- Easily adjust the quantities of any ingredient to exactly hit your daily macros
- Download your menu as a csv file
---
- Check out the *Zero To Hero* fitness [program](https://raptorcoaching.pro/?ref=Ms9zfyaB_yaBS8)🦖🇫🇷.
- Get **17%** off on any purchase with my promo code: **TIFI96V0yNLM**

---
This app was made by [Timothée Filhol](https://www.linkedin.com/in/timothee-filhol) using [streamlit](https://streamlit.io/) and [Nutritionix](https://www.nutritionix.com/).

---
Source code: [GitHub](https://github.com/timfilhol96/nutrition_plan)

---
""",
        "missing_secrets": (
            "Missing Nutritionix credentials: set `NIX_APP_ID` and `NIX_API_KEY` "
            "in `.streamlit/secrets.toml` (or the app's secrets on Streamlit Cloud)."
        ),
        "daily_macros": "DAILY MACROS",
        "plan": "Choose a calorie plan:",
        "plan_maintenance": "Maintenance",
        "plan_cut": "Cut",
        "plan_extra_cut": "Extra cut",
        "target_kcal": "Daily kcal",
        "target_carbs": "Daily carbohydrates (g)",
        "target_protein": "Daily proteins (g)",
        "target_fat": "Daily fats (g)",
        "menu": "MENU",
        "nb_meals": "Select number of daily meals:",
        "meal_kind": "Meal type",
        "meal_kind_placeholder": "Select meal type...",
        "breakfast": "Breakfast",
        "lunch": "Lunch",
        "snack": "Snack",
        "dinner": "Dinner",
        "ingredient": "Ingredient",
        "food": "Food name",
        "grams": "Weight (g)",
        "kcal": "kcal",
        "carbs": "Carbohydrates",
        "protein": "Proteins",
        "fat": "Fats",
        "fiber": "Fiber",
        "compute": "GET MACROS",
        "fill_one_table": "Please fill in at least 1 table 🦖",
        "no_match": "No match found for '{text}', skipping it.",
        "total": "Total",
        "target": "Ideal",
        "diff": "Diff",
        "summary": "Summary",
        "download": "DOWNLOAD MENU",
    },
    "fr": {
        "language": "Français 🇫🇷",
        "app_title": "PLAN NUTRITIONNEL",
        "sidebar": """
# CALCULATEUR DE MACROS
---
## TUTORIEL
- Entrez vos calories et macros quotidiens
- Créez vos repas en listant les ingrédients et quantités
- Générez vos macros
- Ajustez facilement les quantités pour arriver à vos objectifs
- Téléchargez votre menu
---
- N'hésitez pas à consulter le programme fitness [*Zero To Hero*](https://raptorcoaching.pro/?ref=Ms9zfyaB_yaBS8)🦖🇫🇷.
- Obtenez **17%** de réduction sur tout achat avec mon code promotionnel : **TIFI96V0yNLM**

---
Cette application a été créée par [Timothée Filhol](https://www.linkedin.com/in/timothee-filhol) grâce à [streamlit](https://streamlit.io/) et [Nutritionix](https://www.nutritionix.com/).

---
Code source : [GitHub](https://github.com/timfilhol96/nutrition_plan)

---
""",
        "missing_secrets": (
            "Identifiants Nutritionix manquants : définissez `NIX_APP_ID` et "
            "`NIX_API_KEY` dans `.streamlit/secrets.toml` (ou dans les secrets "
            "de l'application sur Streamlit Cloud)."
        ),
        "daily_macros": "MACROS JOURNALIERS",
        "plan": "Choisissez un plan calorique :",
        "plan_maintenance": "Maintenance",
        "plan_cut": "Sèche",
        "plan_extra_cut": "Sèche intense",
        "target_kcal": "Calories journalières (kcal)",
        "target_carbs": "Glucides journaliers (g)",
        "target_protein": "Protéines journalières (g)",
        "target_fat": "Lipides journaliers (g)",
        "menu": "MENU",
        "nb_meals": "Sélectionnez le nombre de repas quotidiens :",
        "meal_kind": "Type de repas",
        "meal_kind_placeholder": "Sélectionnez le type de repas...",
        "breakfast": "Petit-déjeuner",
        "lunch": "Déjeuner",
        "snack": "Collation",
        "dinner": "Dîner",
        "ingredient": "Ingrédient",
        "food": "Aliment",
        "grams": "Poids (g)",
        "kcal": "Calories",
        "carbs": "Glucides",
        "protein": "Protéines",
        "fat": "Lipides",
        "fiber": "Fibres",
        "compute": "OBTENEZ VOS MACROS",
        "fill_one_table": "Veuillez remplir au moins 1 tableau 🦖",
        "no_match": "Aucun résultat pour '{text}', ingrédient ignoré.",
        "total": "Total",
        "target": "Idéal",
        "diff": "Écart",
        "summary": "Résumé",
        "download": "TÉLÉCHARGEZ VOTRE MENU",
    },
}


def t(key: str, lang: str) -> str:
    return STRINGS[lang][key]
