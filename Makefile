# ----------------------------------
#         RUN STREAMLIT APP
# ----------------------------------

streamlit:
	-@streamlit run app.py

black:
	@black . --extend-exclude \.ipynb
