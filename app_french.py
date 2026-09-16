import streamlit as st
import streamlit_ext as ste
import pandas as pd
import requests
from utils import NutritionixError, api_call, convert_df, get_macros
from googletrans import Translator


def run_french_app(my_maintenance_macros, URL, headers):
    translator = Translator()
    with st.sidebar:
        st.write("""
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
                    """)

    st.columns(3)[1].markdown("""
                            # PLAN NUTRITIONNEL
                            """)
    st.markdown(
        """
        ---
        ## MACROS JOURNALIERS
                """
    )  ################################### MACROS ############################################
    calories = ste.selectbox(
        "Choisissez un plan calorique :",
        ("Maintenance", "Cut (-300 kcal)", "Extra cut (-500 kcal)"),
    )

    columns = st.columns(4)

    if calories == "Maintenance":
        daily_kcal = columns[0].number_input(
            "Calories journalières (kcal)", value=my_maintenance_macros["kcal"]
        )
        daily_carbs = columns[1].number_input(
            "Glucides journaliers (g)", value=my_maintenance_macros["carbohydrates"]
        )
    if calories == "Cut (-300 kcal)":
        daily_kcal = columns[0].number_input(
            "Calories journalières (kcal)", value=my_maintenance_macros["kcal"] - 300
        )
        daily_carbs = columns[1].number_input(
            "Glucides journaliers (g)",
            value=my_maintenance_macros["carbohydrates"] - 75,
        )
    if calories == "Extra cut (-500 kcal)":
        daily_kcal = columns[0].number_input(
            "Calories journalières (kcal)", value=my_maintenance_macros["kcal"] - 500
        )
        daily_carbs = columns[1].number_input(
            "Glucides journaliers (g)",
            value=my_maintenance_macros["carbohydrates"] - 125,
        )

    daily_proteins = columns[2].number_input(
        "Protéines journalières (g)", value=my_maintenance_macros["proteins"]
    )
    daily_fats = columns[3].number_input(
        "Lipides journaliers (g)", value=my_maintenance_macros["fats"]
    )

    #####################################################################################
    st.markdown("""
                ## MENU""")

    nb_meals = ste.number_input(
        "Sélectionnez le nombre de repas quotidiens :", min_value=1, step=1, value=3
    )

    meal_columns = st.columns(nb_meals)
    df = pd.DataFrame(data={"Ingrédient": ["" for i in range(15)]})
    meals = {}
    for i, col in enumerate(meal_columns):
        meal_name = col.selectbox(
            "Sélectionnez le type de repas:",
            ("Petit-déjeuner", "Déjeuner", "Collation", "Dîner"),
            key=i,
            label_visibility="collapsed",
            placeholder="Sélectionnez le type de repas...",
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

    def translate_table_columns(df):
        df["Food name"] = df["Food name"].apply(
            lambda x: translator.translate(x, dest="fr").text
        )
        return df.rename(
            columns={
                "Ingredient": "Ingrédient",
                "Serving weight (g)": "Poids (g)",
                "Food name": "Aliment",
                "kcal": "Calories",
                "Carbohydrates": "Glucides",
                "Proteins": "Protéines",
                "Fats": "Lipides",
            }
        )

    def generate_macro_table(edited_df):
        ingredients = [
            str(x).strip()
            for x in edited_df["Ingrédient"]
            if not pd.isna(x) and str(x).strip() != ""
        ]
        if ingredients:
            macros = []
            for ingredient in ingredients:
                query = {
                    "query": translator.translate(ingredient, src="fr", dest="en").text
                }
                try:
                    foods = api_call(URL, headers, query)
                except (NutritionixError, requests.RequestException):
                    st.warning(
                        f"Aucun résultat pour '{ingredient}', ingrédient ignoré."
                    )
                    continue
                macros.append(get_macros(foods, ingredient))

            if not macros:
                return None
            df = translate_table_columns(pd.DataFrame.from_records(macros))
            df.loc["TOTAL"] = {
                "Ingrédient": "TOTAL",
                "Poids (g)": "",
                "Aliment": "",
                **df.iloc[:, 3:].sum().to_dict(),
            }
            return df
        return None

    if st.button("OBTENEZ VOS MACROS", use_container_width=True):
        macros = {}
        for meal, meal_df in meals.items():
            macros[meal] = generate_macro_table(meal_df)

        if all(el is None for el in list(macros.values())):
            st.error("Veuillez remplir au moins 1 tableau 🦖")
            st.stop()

        macro_columns = st.columns(nb_meals)
        for col, (meal, macro_df) in zip(macro_columns, macros.items()):
            if macro_df is not None:
                col.markdown(f"""## {meal.split(' ')[0]}""")
                col.dataframe(macro_df, hide_index=True, use_container_width=True)

        st.markdown("---")

        if any(el is not None for el in list(macros.values())):
            total_df = pd.DataFrame(
                data=[
                    df.loc[df.index[-1], df.columns[3:]]
                    for df in list(macros.values())
                    if df is not None
                ],
                index=[key for key in list(macros.keys()) if macros[key] is not None],
            )
            total_df.loc["TOTAL"] = total_df.sum()
            total_df.loc["IDEAL"] = [
                daily_kcal,
                daily_carbs,
                daily_proteins,
                daily_fats,
            ]
            total_df.loc["DIFF"] = [
                total_df.loc[total_df.index[-2], "Calories"] - daily_kcal,
                total_df.loc[total_df.index[-2], "Glucides"] - daily_carbs,
                total_df.loc[total_df.index[-2], "Protéines"] - daily_proteins,
                total_df.loc[total_df.index[-2], "Lipides"] - daily_fats,
            ]

            col1, col2, col3, col4 = st.columns(4)
            col1.metric(
                "Total Calories",
                f"{round(total_df.loc['TOTAL', 'Calories'])} kcal",
                f"{round(total_df.loc['DIFF', 'Calories'])} kcal",
                delta_color="normal",
            )
            col2.metric(
                "Total Glucides",
                f"{round(total_df.loc['TOTAL', 'Glucides'])} g",
                f"{round(total_df.loc['DIFF', 'Glucides'])} g",
                delta_color="normal",
            )
            col3.metric(
                "Total Protéines",
                f"{round(total_df.loc['TOTAL', 'Protéines'])} g",
                f"{round(total_df.loc['DIFF', 'Protéines'])} g",
                delta_color="normal",
            )
            col4.metric(
                "Total Lipides",
                f"{round(total_df.loc['TOTAL', 'Lipides'])} g",
                f"{round(total_df.loc['DIFF', 'Lipides'])} g",
                delta_color="normal",
            )

            st.markdown("---")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Idéal Calories", f"{daily_kcal} kcal")
            col2.metric("Idéal Glucides", f"{daily_carbs} g")
            col3.metric("Idéal Protéines", f"{daily_proteins} g")
            col4.metric("Idéal Lipides (g)", f"{daily_fats} g")

        regrouped_csv = ""
        for meal, macro_df in macros.items():
            if macro_df is not None:
                regrouped_csv += f"\n{meal.split(' ')[0]},,,,,\n\n{convert_df(macro_df, index=False)}"
        regrouped_csv += f"\n\n{convert_df(total_df.iloc[-3:], index=True)}"

        st.markdown("---")
        st.download_button(
            "TELECHARGEZ VOTRE MENU",
            regrouped_csv.encode("utf-8-sig"),
            "menu.csv",
            mime="text/csv",
            use_container_width=True,
        )
