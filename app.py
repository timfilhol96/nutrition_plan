# TODO: fix special characters when saving as csv

# white = #faf7f7
# black = #080808
# gold = #CE9E5E

import streamlit as st
import os
from app_english import run_english_app
from app_french import run_french_app

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
    page_title="Nutrition Plan",
    page_icon="🦖",
    layout="wide",
    initial_sidebar_state="auto",
)
with st.sidebar:
    language = st.radio(" ", ("English 🇬🇧", "Français 🇫🇷"))

if language == "English 🇬🇧":
    run_english_app(my_maintenance_macros, URL, headers)
elif language == "Français 🇫🇷":
    run_french_app(my_maintenance_macros, URL, headers)
