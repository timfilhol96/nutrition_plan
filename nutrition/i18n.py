LANGUAGES = ("en", "fr")

STRINGS = {
    "en": {
        "language": "English 🇬🇧",
        "app_title": "Nutrition plan",
        "sidebar": """
# Macros calculator
---
## Tutorial
- Enter your daily kcal and macros intake
- Create your daily meals by listing all the ingredients and quantities using natural language
- Generate your macros
- Easily adjust the quantities of any ingredient to exactly hit your daily macros
- Download your menu as a csv file
---
This app was made by [Timothée Filhol](https://www.linkedin.com/in/timothee-filhol) using [streamlit](https://streamlit.io/) and [USDA FoodData Central](https://fdc.nal.usda.gov/).

---
Source code: [GitHub](https://github.com/timfilhol96/nutrition_plan)

---
""",
        "missing_secrets": (
            "Missing USDA credentials: set `FDC_API_KEY` in `.streamlit/secrets.toml` "
            "(or the app's secrets on Streamlit Cloud). Get a free key at "
            "https://fdc.nal.usda.gov/api-key-signup."
        ),
        "manual_mode": "Manual mode",
        "manual_mode_help": "Search USDA foods yourself instead of typing free text.",
        "no_llm_configured": (
            "No AI provider is configured (`GROQ_API_KEY` / `OPENROUTER_API_KEY`), "
            "so only manual mode is available."
        ),
        "llm_unavailable_info": (
            "The AI parser is unavailable right now ({reason}). "
            "Switched to manual mode: search each food and enter its weight."
        ),
        "cap_reached_info": (
            "This session has used its {cap} AI parsing calls. "
            "Switched to manual mode: search each food and enter its weight."
        ),
        "row_too_long": "Row {row} is {length} characters long; please keep rows under {max}.",
        "too_many_rows": "A meal has {count} rows; please keep it under {max}.",
        "parse_failed_meal": (
            "The AI could not read this meal. Search the foods manually below."
        ),
        "usda_error": "USDA FoodData Central is unreachable right now. Please retry.",
        "not_found": "No USDA match",
        "search_food": "Search a USDA food",
        "no_results": "No results",
        "match": "USDA match",
        "text": "Your text",
        "add": "Add",
        "remove": "Remove",
        "meal_total": "Meal total",
        "footer": (
            "Ingredient text is sent to a third-party AI provider (Groq, with "
            "OpenRouter as fallback) for parsing only. Nutrition data comes from "
            "USDA FoodData Central."
        ),
        "daily_macros": "Daily targets",
        "plan": "Choose a calorie plan:",
        "plan_maintenance": "Maintenance",
        "plan_cut": "Cut",
        "plan_extra_cut": "Extra cut",
        "target_kcal": "Daily kcal",
        "target_carbs": "Daily carbohydrates (g)",
        "target_protein": "Daily proteins (g)",
        "target_fat": "Daily fats (g)",
        "menu": "Menu",
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
        "compute": "Get macros",
        "fill_one_table": "Please fill in at least 1 table 🦖",
        "no_match": "No match found for '{text}', skipping it.",
        "total": "Total",
        "target": "Ideal",
        "diff": "Diff",
        "summary": "Summary",
        "download": "Download menu (CSV)",
        "download_long": "Download detailed CSV",
        "meal_tab": "Meal {n}",
        "extras": "Daily extras",
        "extras_help": "Anything eaten outside meals: supplements, a protein scoop, a snack bar…",
        "tdee_expander": "Estimate my needs (TDEE)",
        "sex": "Sex",
        "male": "Male",
        "female": "Female",
        "age": "Age",
        "weight": "Weight (kg)",
        "height": "Height (cm)",
        "activity": "Activity level",
        "activity_sedentary": "Sedentary (little or no exercise)",
        "activity_light": "Light (1–3 days/week)",
        "activity_moderate": "Moderate (3–5 days/week)",
        "activity_active": "Active (6–7 days/week)",
        "activity_very_active": "Very active (hard daily training)",
        "protein_per_kg": "Protein (g per kg bodyweight)",
        "tdee_result": (
            "Mifflin–St Jeor: BMR **{bmr} kcal**, maintenance **{tdee} kcal**. "
            "With the selected plan: **{kcal} kcal**, {protein} g protein, "
            "{fat} g fat (30% of kcal), {carbs} g carbohydrates (the rest)."
        ),
        "use_estimate": "Use this estimate",
        "kcal_mismatch": (
            "Your macros add up to {atwater} kcal (4·carbs + 4·protein + 9·fat), "
            "which differs from the {kcal} kcal target by more than 5%."
        ),
        "summary_title": "Today vs. targets",
        "left": "{diff} {unit} left",
        "over": "{diff} {unit} over",
        "on_target": "on target",
        "disclaimer": "Estimates only, not medical or dietary advice.",
    },
    "fr": {
        "language": "Français 🇫🇷",
        "app_title": "Plan nutritionnel",
        "sidebar": """
# Calculateur de macros
---
## Tutoriel
- Entrez vos calories et macros quotidiens
- Créez vos repas en listant les ingrédients et quantités
- Générez vos macros
- Ajustez facilement les quantités pour arriver à vos objectifs
- Téléchargez votre menu
---
Cette application a été créée par [Timothée Filhol](https://www.linkedin.com/in/timothee-filhol) grâce à [streamlit](https://streamlit.io/) et [USDA FoodData Central](https://fdc.nal.usda.gov/).

---
Code source : [GitHub](https://github.com/timfilhol96/nutrition_plan)

---
""",
        "missing_secrets": (
            "Identifiant USDA manquant : définissez `FDC_API_KEY` dans "
            "`.streamlit/secrets.toml` (ou dans les secrets de l'application sur "
            "Streamlit Cloud). Clé gratuite sur https://fdc.nal.usda.gov/api-key-signup."
        ),
        "manual_mode": "Mode manuel",
        "manual_mode_help": "Cherchez vous-même les aliments USDA au lieu de saisir du texte libre.",
        "no_llm_configured": (
            "Aucun fournisseur d'IA n'est configuré (`GROQ_API_KEY` / "
            "`OPENROUTER_API_KEY`) : seul le mode manuel est disponible."
        ),
        "llm_unavailable_info": (
            "L'analyse par IA est indisponible pour le moment ({reason}). "
            "Passage en mode manuel : cherchez chaque aliment et saisissez son poids."
        ),
        "cap_reached_info": (
            "Cette session a utilisé ses {cap} analyses par IA. "
            "Passage en mode manuel : cherchez chaque aliment et saisissez son poids."
        ),
        "row_too_long": "La ligne {row} fait {length} caractères ; limitez-vous à {max}.",
        "too_many_rows": "Un repas contient {count} lignes ; limitez-vous à {max}.",
        "parse_failed_meal": (
            "L'IA n'a pas pu lire ce repas. Cherchez les aliments manuellement ci-dessous."
        ),
        "usda_error": "USDA FoodData Central est injoignable pour le moment. Réessayez.",
        "not_found": "Aucune correspondance USDA",
        "search_food": "Chercher un aliment USDA",
        "no_results": "Aucun résultat",
        "match": "Correspondance USDA",
        "text": "Votre texte",
        "add": "Ajouter",
        "remove": "Retirer",
        "meal_total": "Total du repas",
        "footer": (
            "Le texte des ingrédients est envoyé à un fournisseur d'IA tiers (Groq, "
            "puis OpenRouter en secours) uniquement pour l'analyse. Les données "
            "nutritionnelles proviennent de USDA FoodData Central."
        ),
        "daily_macros": "Objectifs journaliers",
        "plan": "Choisissez un plan calorique :",
        "plan_maintenance": "Maintenance",
        "plan_cut": "Sèche",
        "plan_extra_cut": "Sèche intense",
        "target_kcal": "Calories journalières (kcal)",
        "target_carbs": "Glucides journaliers (g)",
        "target_protein": "Protéines journalières (g)",
        "target_fat": "Lipides journaliers (g)",
        "menu": "Menu",
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
        "compute": "Obtenir mes macros",
        "fill_one_table": "Veuillez remplir au moins 1 tableau 🦖",
        "no_match": "Aucun résultat pour '{text}', ingrédient ignoré.",
        "total": "Total",
        "target": "Idéal",
        "diff": "Écart",
        "summary": "Résumé",
        "download": "Télécharger le menu (CSV)",
        "download_long": "Télécharger le CSV détaillé",
        "meal_tab": "Repas {n}",
        "extras": "Extras de la journée",
        "extras_help": "Tout ce qui est pris hors repas : compléments, dose de protéines, barre…",
        "tdee_expander": "Estimer mes besoins (TDEE)",
        "sex": "Sexe",
        "male": "Homme",
        "female": "Femme",
        "age": "Âge",
        "weight": "Poids (kg)",
        "height": "Taille (cm)",
        "activity": "Niveau d'activité",
        "activity_sedentary": "Sédentaire (peu ou pas d'exercice)",
        "activity_light": "Léger (1 à 3 jours/semaine)",
        "activity_moderate": "Modéré (3 à 5 jours/semaine)",
        "activity_active": "Actif (6 à 7 jours/semaine)",
        "activity_very_active": "Très actif (entraînement intense quotidien)",
        "protein_per_kg": "Protéines (g par kg de poids)",
        "tdee_result": (
            "Mifflin–St Jeor : métabolisme de base **{bmr} kcal**, maintenance "
            "**{tdee} kcal**. Avec le plan choisi : **{kcal} kcal**, {protein} g de "
            "protéines, {fat} g de lipides (30 % des kcal), {carbs} g de glucides (le reste)."
        ),
        "use_estimate": "Utiliser cette estimation",
        "kcal_mismatch": (
            "Vos macros totalisent {atwater} kcal (4·glucides + 4·protéines + 9·lipides), "
            "soit plus de 5 % d'écart avec l'objectif de {kcal} kcal."
        ),
        "summary_title": "Aujourd'hui vs. objectifs",
        "left": "{diff} {unit} restants",
        "over": "{diff} {unit} en trop",
        "on_target": "objectif atteint",
        "disclaimer": "Estimations uniquement, pas un avis médical ni diététique.",
    },
}


def t(key: str, lang: str) -> str:
    return STRINGS[lang][key]
