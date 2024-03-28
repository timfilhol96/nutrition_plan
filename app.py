# cache the request with st.cache_data

import streamlit as st
import os
import requests
import pandas as pd
import numpy as np
import random

############

api_id = os.environ['NIX_APP_ID']
api_key = os.environ['NIX_API_KEY']
url = 'https://trackapi.nutritionix.com/v2/natural/nutrients'

@st.cache_data
def api_call(url, headers, query):
    return requests.request("POST", url, headers=headers, data=query)

def get_macros(response, quantity):
    dict_ = response.json()['foods'][0]
    def cross_prod(a):
        return round(a*quantity/dict_['serving_weight_grams'])

    return {'Ingredient' : dict_['food_name'],
            'kcal': cross_prod(dict_['nf_calories']),
                                'Carbohydrates':cross_prod(dict_['nf_total_carbohydrate']),
                                'Proteins': cross_prod(dict_['nf_protein']),
                                'Fats': cross_prod(dict_['nf_total_fat']),
                                    'Quantity (g)': cross_prod(dict_['serving_weight_grams'])}



headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'x-app-id': api_id,
            'x-app-key': api_key,
            'x-remote-user-id': '0'
}

#######################

st.set_page_config(
            page_title="Nutrition plan", # => Quick reference - Streamlit
            page_icon="🦖",
            layout="wide", # wide
            initial_sidebar_state="auto") # collapsed

st.markdown('''
            # 🦖 Nutrition plan - ZTH 🦖

            ## Daily Macros
            ''')
# macros
columns = st.columns(4)

daily_kcal = columns[0].number_input("Daily kcal", value=2010)
daily_carbs = columns[1].number_input("Daily carbohydrates", value=238)
daily_proteins = columns[2].number_input("Daily proteins", value=110)
daily_fats = columns[3].number_input("Daily fats", value=69)
#
st.markdown('''
            # Menu''')
col1, col2, col3 = st.columns(3)
df = pd.DataFrame(columns = ['Ingredient','Quantity'])
col1.markdown('''## Lunch''')
lunch_df = col1.data_editor(df.copy(), column_config = {'Quantity': st.column_config.NumberColumn('Quantity (g)', format = "%.2f g")}, key="lunch_df", num_rows="dynamic", hide_index=True)
col2.markdown('''## Snack''')
snack_df = col2.data_editor(df.copy(), column_config = {'Quantity': st.column_config.NumberColumn('Quantity (g)', format = "%.2f g")}, key="snack_df", num_rows="dynamic", hide_index=True)
col3.markdown('''## Dinner''')
dinner_df = col3.data_editor(df.copy(), column_config = {'Quantity': st.column_config.NumberColumn('Quantity (g)', format = "%.2f g")}, key="dinner_df", num_rows="dynamic", hide_index=True)

def generate_macro_table(edited_df):
    if edited_df.shape[0] != 0:
        foods = edited_df['Ingredient'].values
        quantities = edited_df['Quantity'].values
        macros = []
        for food, quantity in zip(foods, quantities):
            query = {
                "query": food
            }
            macros.append(get_macros(api_call(url, headers, query), quantity))

        df = pd.DataFrame.from_records(macros)
        df.loc['Total']= df.sum()
        df.loc[df.index[-1], 'Ingredient'] = 'Total'
        # df.loc['Ideal']= ['Ideal',daily_kcal, daily_carbs, daily_proteins, daily_fats, '']
        # df.loc['Diff']= ['Diff', df.loc[df.index[-2], 'kcal'] - daily_kcal,
        #                 df.loc[df.index[-2], 'Carbohydrates'] - daily_carbs,
        #                 df.loc[df.index[-2], 'Proteins'] - daily_proteins,
        #                 df.loc[df.index[-2], 'Fats'] - daily_fats,
        #                 '']
        return df
    return None

if st.button('Get macros 🍽️'):
    lunch_macros = generate_macro_table(lunch_df)
    snack_macros = generate_macro_table(snack_df)
    dinner_macros = generate_macro_table(dinner_df)

    if any(el is not None for el in [lunch_macros, snack_macros, dinner_macros]):
        st.write(f"Here are the macros for today's menu 😋")
    else:
        st.error('Please fill in at least 1 table 🦖')

    col1, col2, col3 = st.columns(3)
    if lunch_macros is not None:
        col1.markdown('''## Lunch''')
        col1.dataframe(lunch_macros, hide_index=True)
    if snack_macros is not None:
        col2.markdown('''## Snack''')
        col2.dataframe(snack_macros, hide_index=True)
    if dinner_macros is not None:
        col3.markdown('''## Dinner''')
        col3.dataframe(dinner_macros, hide_index=True)

    if any(el is not None for el in [lunch_macros, snack_macros, dinner_macros]):
        st.markdown('## TOTAL')
        total_df = pd.DataFrame(data = [df.loc[df.index[-1], df.columns[1:-1]] for df in [lunch_macros, snack_macros, dinner_macros] if df is not None], index = ['Lunch', 'Snack', 'Dinner'])
        total_df.loc['Total']= total_df.sum()
        total_df.loc['Ideal']= [daily_kcal, daily_carbs, daily_proteins, daily_fats]
        total_df.loc['Diff']= [total_df.loc[total_df.index[-2], 'kcal'] - daily_kcal,
                        total_df.loc[total_df.index[-2], 'Carbohydrates'] - daily_carbs,
                        total_df.loc[total_df.index[-2], 'Proteins'] - daily_proteins,
                        total_df.loc[total_df.index[-2], 'Fats'] - daily_fats]
        st.dataframe(total_df)
