import requests
import streamlit as st


@st.cache_data(show_spinner="Generating macros..⏳")
def api_call(url, headers, query):
    return requests.request("POST", url, headers=headers, data=query)


def convert_df(df, **kwargs):
    return df.to_csv(**kwargs).encode("utf-8-sig")


def get_macros(response, query):
    dict_ = response.json()["foods"][0]
    return {
        "Ingredient": query,
        "Serving weight (g)": dict_["serving_weight_grams"],
        "Food name": dict_["food_name"],
        "kcal": round(dict_["nf_calories"]),
        "Carbohydrates": round(dict_["nf_total_carbohydrate"]),
        "Proteins": round(dict_["nf_protein"]),
        "Fats": round(dict_["nf_total_fat"]),
    }
