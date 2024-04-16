# TODO: custom db?
# TODO: possibility to set default meals
# pre-fill based on previous menus
# add custom products (specific sauce and whatnot)

import streamlit as st
import streamlit_ext as ste
import os
import pandas as pd
from utils import api_call, convert_df, get_macros

############
my_maintenance_macros = {
    "kcal": 2510,
    "carbohydrates": 363,
    "proteins": 110,
    "fats": 69,
}

API_ID = os.environ["NIX_APP_ID"]
API_KEY = os.environ["NIX_API_KEY"]
URL = "https://trackapi.nutritionix.com/v2/natural/nutrients"

headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "x-app-id": API_ID,
    "x-app-key": API_KEY,
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
    #     'About': "# "
    # }
)  # collapsed

st.sidebar.write(
    """
# Macros Calculator
---
## Tutorial
- Enter your daily kcal and macros intake
- Create your daily meals by listing all the ingredients and quantities
- Get your macros
- You can easily adjust the quantities of any ingredient to fine-tune your meal plans and exactly hit your daily macros👌
- Download your menu as a csv file
---

This app was made using [streamlit](https://streamlit.io/) and [Nutritionix](https://www.nutritionix.com/).
                 """
)
st.columns(3)[1].header("Nutrition plan - ZTH 🦖")
st.markdown(
    """     ## Daily Macros
            """
)
################################### MACROS ############################################
calories = ste.selectbox(
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

nb_meals = ste.number_input(
    "Select number of daily meals", min_value=1, step=1, value=3
)

meal_columns = st.columns(nb_meals)
df = pd.DataFrame(data={"Ingredient": ["", ""]})
meals = {}
for i, col in enumerate(meal_columns):
    meal_name = col.selectbox(
        "Select meal type:", ("Breakfast", "Lunch", "Snack", "Dinner"), key=i
    )
    meal_df = col.data_editor(
        df.copy(),
        key=i + 0.01,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
    )
    meals[meal_name] = meal_df


def generate_macro_table(edited_df):
    if edited_df.shape[0] != 0:
        ingredients = edited_df["Ingredient"].values
        macros = []
        for ingredient in ingredients:
            query = {"query": ingredient}
            macros.append(get_macros(api_call(URL, headers, query)))

        df = pd.DataFrame.from_records(macros)
        df.loc["Total"] = df.iloc[:, 2:].sum()
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
        total_df = pd.DataFrame(
            data=[
                df.loc[df.index[-1], df.columns[2:]]
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

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Ideal kcal", f"{daily_kcal} kcal")
        col2.metric("Ideal Carbohydrates", f"{daily_carbs} g")
        col3.metric("Ideal Proteins", f"{daily_proteins} g")
        col4.metric("Ideal Fats", f"{daily_fats} g")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric(
            "Total kcal",
            f"{round(total_df.loc['Total'][0])} kcal",
            f"{round(total_df.loc['Diff'][0])} kcal",
            delta_color="normal",
        )
        col2.metric(
            "Total Carbohydrates",
            f"{round(total_df.loc['Total'][1])} g",
            f"{round(total_df.loc['Diff'][1])} g",
            delta_color="normal",
        )
        col3.metric(
            "Total Proteins",
            f"{round(total_df.loc['Total'][2])} g",
            f"{round(total_df.loc['Diff'][2])} g",
            delta_color="normal",
        )
        col4.metric(
            "Total Fats",
            f"{round(total_df.loc['Total'][3])} g",
            f"{round(total_df.loc['Diff'][3])} g",
            delta_color="normal",
        )

    regrouped_csv = ""
    for meal, macro_df in macros.items():
        if macro_df is not None:
            regrouped_csv += f"\n{meal},,,,,\n\n{convert_df(macro_df, index=False)}"
    regrouped_csv += f"\n\n{convert_df(total_df.iloc[-3:], index=True)}"

    ste.download_button(
        "Download my menu 😋", regrouped_csv, "my_macros.csv", mime="csv"
    )
