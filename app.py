# TODO: custom db?
# TODO: possibility to set default meals (import csv file?)
# TODO: breakfast, lunch and snack by default
# TODO: keep macros while modifying old menu
# pre-fill based on previous menus

# [theme]
# primaryColor="#080808"
# backgroundColor="#080808"
# secondaryBackgroundColor="#CE9E5E"
# textColor="#faf7f7"
# font="san serif"

# white = #faf7f7
# black = #080808
# gold = #CE9E5E

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
    page_title="Nutrition Plan",  # => Quick reference - Streamlit
    page_icon="🦖",
    layout="wide",  # wide
    initial_sidebar_state="auto",
)
with st.sidebar:
    st.write(
        """
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
This app was made using [streamlit](https://streamlit.io/) and [Nutritionix](https://www.nutritionix.com/).

---
Source code: [GitHub](https://github.com/timfilhol96/nutrition_plan)

---
                 """
    )

st.columns(3)[1].markdown(
    """
                          # NUTRITION PLAN
                          """
)
st.markdown(
    """
    ---
    ## DAILY MACROS
            """
)  ################################### MACROS ############################################
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

#####################################################################################
st.markdown(
    """
            ## MENU"""
)

nb_meals = ste.number_input(
    "Select number of daily meals:", min_value=1, step=1, value=3
)

meal_columns = st.columns(nb_meals)
df = pd.DataFrame(columns=["Ingredient"])
meals = {}
for i, col in enumerate(meal_columns):
    meal_name = col.selectbox(
        "Select meal type:",
        ("Breakfast", "Lunch", "Snack", "Dinner"),
        key=i,
        label_visibility="collapsed",
        placeholder="Select meal type...",
        index=None,
    )
    if meal_name:
        meal_df = col.data_editor(
            df.copy(),
            key=i + 0.01,
            num_rows="dynamic",
            hide_index=True,
            use_container_width=True,
        )
        meals[f"{meal_name} #{i}"] = meal_df

if len(meals) < nb_meals:  # TODO: remove if only 1 meal left
    nb_meals = len(meals)


def generate_macro_table(edited_df):
    if edited_df.shape[0] != 0:
        ingredients = edited_df["Ingredient"].values
        macros = []
        for ingredient in ingredients:
            query = {"query": ingredient}
            macros.append(get_macros(api_call(URL, headers, query)))

        df = pd.DataFrame.from_records(macros)
        df.loc["TOTAL"] = df.iloc[:, 2:].sum()
        df.loc[df.index[-1], "Ingredient"] = "TOTAL"
        return df
    return None


if st.button("GET MACROS", use_container_width=True):
    macros = {}
    for meal, meal_df in meals.items():
        macros[meal] = generate_macro_table(meal_df)

    if all(el is None for el in list(macros.values())):
        st.error("Please fill in at least 1 table 🦖")

    macro_columns = st.columns(nb_meals)
    for col, (meal, macro_df) in zip(macro_columns, macros.items()):
        if macro_df is not None:
            col.markdown(f"""## {meal.split(' ')[0]}""")
            col.dataframe(macro_df, hide_index=True, use_container_width=True)

    st.markdown("---")

    if any(el is not None for el in list(macros.values())):
        total_df = pd.DataFrame(
            data=[
                df.loc[df.index[-1], df.columns[2:]]
                for df in list(macros.values())
                if df is not None
            ],
            index=[key for key in list(macros.keys()) if macros[key] is not None],
        )
        total_df.loc["TOTAL"] = total_df.sum()
        total_df.loc["IDEAL"] = [daily_kcal, daily_carbs, daily_proteins, daily_fats]
        total_df.loc["DIFF"] = [
            total_df.loc[total_df.index[-2], "kcal"] - daily_kcal,
            total_df.loc[total_df.index[-2], "Carbohydrates"] - daily_carbs,
            total_df.loc[total_df.index[-2], "Proteins"] - daily_proteins,
            total_df.loc[total_df.index[-2], "Fats"] - daily_fats,
        ]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric(
            "Total kcal",
            f"{round(total_df.loc['TOTAL'][0])} kcal",
            f"{round(total_df.loc['DIFF'][0])} kcal",
            delta_color="normal",
        )
        col2.metric(
            "Total Carbohydrates",
            f"{round(total_df.loc['TOTAL'][1])} g",
            f"{round(total_df.loc['DIFF'][1])} g",
            delta_color="normal",
        )
        col3.metric(
            "Total Proteins",
            f"{round(total_df.loc['TOTAL'][2])} g",
            f"{round(total_df.loc['DIFF'][2])} g",
            delta_color="normal",
        )
        col4.metric(
            "Total Fats",
            f"{round(total_df.loc['TOTAL'][3])} g",
            f"{round(total_df.loc['DIFF'][3])} g",
            delta_color="normal",
        )

        st.markdown("---")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Ideal kcal", f"{daily_kcal} kcal")
        col2.metric("Ideal Carbohydrates", f"{daily_carbs} g")
        col3.metric("Ideal Proteins", f"{daily_proteins} g")
        col4.metric("Ideal Fats", f"{daily_fats} g")

    regrouped_csv = ""
    for meal, macro_df in macros.items():
        if macro_df is not None:
            regrouped_csv += (
                f"\n{meal.split(' ')[0]},,,,,\n\n{convert_df(macro_df, index=False)}"
            )
    regrouped_csv += f"\n\n{convert_df(total_df.iloc[-3:], index=True)}"

    st.markdown("---")
    st.download_button(
        "DOWNLOAD MENU",
        regrouped_csv,
        "my_macros.csv",
        mime="csv",
        use_container_width=True,
    )
