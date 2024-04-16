import requests
import streamlit as st

@st.cache_data
def api_call(url, headers, query):
    return requests.request("POST", url, headers=headers, data=query)

def convert_df(df,**kwargs):
    return df.to_csv(**kwargs)

def get_macros(response):
    dict_ = response.json()["foods"][0]
    return {
        "Ingredient": dict_["food_name"],
        # "Quantity": dict_["serving_qty"],
        # "Serving unit": dict_["serving_unit"],
        "Serving weight (g)": dict_["serving_weight_grams"],
        "kcal": round(dict_["nf_calories"]),
        "Carbohydrates": round(dict_["nf_total_carbohydrate"]),
        "Proteins": round(dict_["nf_protein"]),
        "Fats": round(dict_["nf_total_fat"]),
    }
