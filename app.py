# Clean my food json
# verify if all ingredients are in grams (especially liquids)
# add tbspoon and tspoon options or equivalent in grams
# pre-fill based on previous menus

# link grocery stores to approximate a weekly shopping basket

import streamlit as st
import os
import requests
import pandas as pd
import numpy as np
import random

############
my_maintenance_macros = {
    "kcal": 2510,
    "carbohydrates": 363,
    "proteins": 110,
    "fats": 69,
}
api_id = os.environ["NIX_APP_ID"]
api_key = os.environ["NIX_API_KEY"]
url = "https://trackapi.nutritionix.com/v2/natural/nutrients"


@st.cache_data
def api_call(url, headers, query):
    return requests.request("POST", url, headers=headers, data=query)


def get_macros(response, quantity):
    dict_ = response.json()["foods"][0]

    def cross_prod(a):
        return round(a * quantity / dict_["serving_weight_grams"])

    return {
        "Ingredient": dict_["food_name"],
        "kcal": cross_prod(dict_["nf_calories"]),
        "Carbohydrates": cross_prod(dict_["nf_total_carbohydrate"]),
        "Proteins": cross_prod(dict_["nf_protein"]),
        "Fats": cross_prod(dict_["nf_total_fat"]),
        "Quantity (g)": cross_prod(dict_["serving_weight_grams"]),
    }


headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "x-app-id": api_id,
    "x-app-key": api_key,
    "x-remote-user-id": "0",
}

#######################

st.set_page_config(
    page_title="Nutrition plan",  # => Quick reference - Streamlit
    page_icon="🦖",
    layout="wide",  # wide
    initial_sidebar_state="auto",
    # menu_items={
    #     'Get Help': 'https://www.extremelycoolapp.com/help',
    #     'Report a bug': "https://www.extremelycoolapp.com/bug",
    #     'About': "# This is a header. This is an *extremely* cool app!"
    # }
)  # collapsed

# st.sidebar.write("# Navigation") # to create a sidebar

st.markdown(
    """
            # 🦖 Nutrition plan - ZTH 🦖

            ## Daily Macros
            """
)
################################### MACROS ############################################
calories = st.selectbox(
    "Choose a calorie plan:",
    ("Maintenance", "Cut (-300 kcal)", "Extra cut (-500 kcal)"),
)

columns = st.columns(4)

if calories == "Maintenance":
    daily_kcal = columns[0].number_input(
        "Daily kcal", value=my_maintenance_macros["kcal"]
    )
    daily_carbs = columns[1].number_input(
        "Daily carbohydrates", value=my_maintenance_macros["carbohydrates"]
    )
if calories == "Cut (-300 kcal)":
    daily_kcal = columns[0].number_input(
        "Daily kcal", value=my_maintenance_macros["kcal"] - 300
    )
    daily_carbs = columns[1].number_input(
        "Daily carbohydrates", value=my_maintenance_macros["carbohydrates"] - 75
    )
if calories == "Extra cut (-500 kcal)":
    daily_kcal = columns[0].number_input(
        "Daily kcal", value=my_maintenance_macros["kcal"] - 500
    )
    daily_carbs = columns[1].number_input(
        "Daily carbohydrates", value=my_maintenance_macros["carbohydrates"] - 125
    )

daily_proteins = columns[2].number_input(
    "Daily proteins", value=my_maintenance_macros["proteins"]
)
daily_fats = columns[3].number_input("Daily fats", value=my_maintenance_macros["fats"])

######################################################################################

st.markdown(
    """
            # Menu"""
)

nb_meals = st.number_input("Select number of daily meals", min_value=1, step=1)

meal_columns = st.columns(nb_meals)
df = pd.DataFrame(columns=["Ingredient", "Quantity"])
meals = {}
for i, col in enumerate(meal_columns):
    meal_name = col.selectbox(
        "Select meal type:", ("Breakfast", "Lunch", "Snack", "Dinner"), key=i
    )
    meal_df = col.data_editor(
        df.copy(),
        column_config={
            "Quantity": st.column_config.NumberColumn(
                "Quantity (g)", default=100, format="%.2f g"
            )
        },
        key=i + 0.01,
        num_rows="dynamic",
        hide_index=True,
    )
    meals[meal_name] = meal_df


def generate_macro_table(edited_df):
    if edited_df.shape[0] != 0:
        foods = edited_df["Ingredient"].values
        quantities = edited_df["Quantity"].values
        macros = []
        for food, quantity in zip(foods, quantities):
            query = {"query": food}
            macros.append(get_macros(api_call(url, headers, query), quantity))

        df = pd.DataFrame.from_records(macros)
        df.loc["Total"] = df.sum()
        df.loc[df.index[-1], "Ingredient"] = "Total"
        return df
    return None


if st.button("Get macros 🍽️"):
    macros = {}
    for meal, meal_df in meals.items():
        macros[meal] = generate_macro_table(meal_df)

    if any(el is not None for el in list(macros.values())):
        st.write(f"Here are the macros for today's menu 😋")
    else:
        st.error("Please fill in at least 1 table 🦖")

    macro_columns = st.columns(nb_meals)
    for col, (meal, macro_df) in zip(macro_columns, macros.items()):
        if macro_df is not None:
            col.markdown(f"""## {meal}""")
            col.dataframe(macro_df, hide_index=True)

    if any(el is not None for el in list(macros.values())):
        # st.markdown("## TOTAL")
        total_df = pd.DataFrame(
            data=[
                df.loc[df.index[-1], df.columns[1:-1]]
                for df in list(macros.values())
                if df is not None
            ],
            index=[key for key in list(macros.keys()) if macros[key] is not None],
        )
        total_df.loc["Total"] = total_df.sum()
        total_df.loc["Ideal"] = [daily_kcal, daily_carbs, daily_proteins, daily_fats]
        total_df.loc["Diff"] = [
            total_df.loc[total_df.index[-2], "kcal"] - daily_kcal,
            total_df.loc[total_df.index[-2], "Carbohydrates"] - daily_carbs,
            total_df.loc[total_df.index[-2], "Proteins"] - daily_proteins,
            total_df.loc[total_df.index[-2], "Fats"] - daily_fats,
        ]
        # st.dataframe(total_df)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric(
            "Total kcal",
            f"{total_df.loc['Total'][0]} kcal",
            f"{total_df.loc['Diff'][0]} kcal",
            delta_color="off",
        )
        col2.metric(
            "Total Carbohydrates",
            f"{total_df.loc['Total'][1]} g",
            f"{total_df.loc['Diff'][1]} g",
            delta_color="off",
        )
        col3.metric(
            "Total Proteins",
            f"{total_df.loc['Total'][2]} g",
            f"{total_df.loc['Diff'][2]} g",
            delta_color="off",
        )
        col4.metric(
            "Total Fats",
            f"{total_df.loc['Total'][3]} g",
            f"{total_df.loc['Diff'][3]} g",
            delta_color="off",
        )
