import requests
import streamlit as st


class NutritionixError(Exception):
    """Raised when Nutritionix returns an error or no match for a query."""


@st.cache_data(show_spinner="Generating macros..⏳")
def api_call(url, headers, query):
    # Return the parsed list of foods, never the Response object.
    # Raising on failure means st.cache_data does not cache the failure.
    response = requests.request("POST", url, headers=headers, data=query)
    if response.status_code != 200:
        raise NutritionixError(f"HTTP {response.status_code}")
    foods = response.json().get("foods")
    if not foods:
        raise NutritionixError("no match")
    return foods


def convert_df(df, **kwargs):
    return df.to_csv(**kwargs)


def get_macros(foods, query):
    dict_ = foods[0]
    return {
        "Ingredient": query,
        "Serving weight (g)": dict_["serving_weight_grams"],
        "Food name": dict_["food_name"],
        "kcal": round(dict_["nf_calories"]),
        "Carbohydrates": round(dict_["nf_total_carbohydrate"]),
        "Proteins": round(dict_["nf_protein"]),
        "Fats": round(dict_["nf_total_fat"]),
    }
