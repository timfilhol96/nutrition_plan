# NUTRITION PLAN

App link (🇬🇧/🇫🇷): https://nutrition-plan.streamlit.app/

Build a daily menu from free-text ingredients and compare the totals to your
macro targets. A free LLM turns your text into food items and gram weights;
**every nutrition value comes from [USDA FoodData Central](https://fdc.nal.usda.gov/)**.
The LLM never produces nutrition numbers.

## TUTORIAL
- Enter your daily kcal and macros intake
- Create your daily meals by listing all the ingredients and quantities using natural language (English or French)
- Generate your macros: each line is parsed, matched to a USDA food and weighed in grams
- Adjust any match or weight; totals update instantly
- Download your menu as a csv file

If no AI provider is available (no key, outage, or the per-session cap of 30
parsing calls), the app switches to **manual mode**: search USDA foods and
enter grams yourself. Manual mode can also be toggled in the sidebar.

## SETUP

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # app
pip install -r requirements-dev.txt    # + black, pytest
```

Create `.streamlit/secrets.toml` (never commit it):

```toml
FDC_API_KEY = "..."          # required — free key: https://fdc.nal.usda.gov/api-key-signup
GROQ_API_KEY = "..."         # optional — primary LLM provider (free tier)
OPENROUTER_API_KEY = "..."   # optional — fallback LLM provider (free models only)

# Optional overrides (defaults in nutrition/config.py)
# GROQ_MODEL = "llama-3.3-70b-versatile"
# OPENROUTER_MODEL = "google/gemma-4-31b-it:free"
# LLM_SESSION_CAP = 30
```

On Streamlit Community Cloud, paste the same keys in the app's *Secrets* settings.

Run the app:

```bash
streamlit run app.py
```

## HOW IT WORKS

1. **Parsing** — one LLM call per meal (`nutrition/parser.py`). Rows are sent
   with their numbers; the answer is validated with Pydantic as
   `{"items": [{"row", "name_en", "usda_query", "grams", "assumption"}]}`.
   An invalid answer is retried once with the validation error; rows that
   still fail are offered for manual search. Parses are cached globally by
   normalized text, so repeated meals cost nothing.
2. **Providers** — tried in order: **Groq** (`GROQ_MODEL`), then **OpenRouter**
   (`OPENROUTER_MODEL`, a `:free` model). A provider is skipped for a cooldown
   after a 429, and on 5xx / timeout / invalid JSON the next one is tried.
   Missing keys simply remove that provider from the chain.
3. **Nutrition** — `nutrition/usda.py` searches FDC (Foundation + SR Legacy,
   values per 100 g) and scales by grams. Energy uses nutrient 1008, falling
   back to the Atwater energies (2048, 2047), kJ (1062), then computed Atwater.
4. **Guardrails** — 120 characters per row, 20 rows per meal, 30 LLM calls per
   session (cache hits are free).

Ingredient text is sent to the configured AI provider for parsing only.

## DEVELOPMENT

```bash
pytest              # all HTTP and LLM calls are mocked
black --check .
```

### Parser evaluation (real providers, run manually)

`eval/cases.jsonl` holds ~44 labelled French and English rows (household
units, raw vs cooked, brands, multi-food lines, ambiguous portions).

```bash
python eval/parser_eval.py              # uses env vars or .streamlit/secrets.toml
python eval/parser_eval.py --no-usda    # LLM only
python eval/parser_eval.py --lang fr --limit 10
```

It reports the JSON failure rate, the median absolute grams error and the
top-1 USDA match accuracy, then lists every mismatch. It is never run by
`pytest`.

---
This app was made using [streamlit](https://streamlit.io/), [USDA FoodData Central](https://fdc.nal.usda.gov/), [Groq](https://groq.com/) and [OpenRouter](https://openrouter.ai/).
