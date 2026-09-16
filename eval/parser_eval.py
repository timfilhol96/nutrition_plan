"""Evaluate the free-text parser against the REAL providers.

Run it by hand only (it is outside pytest's testpaths and makes network calls):

    python eval/parser_eval.py                # all cases, LLM + USDA matching
    python eval/parser_eval.py --no-usda      # LLM only, skips match accuracy
    python eval/parser_eval.py --lang fr --limit 10

Keys are read from the environment (GROQ_API_KEY, OPENROUTER_API_KEY,
FDC_API_KEY) and fall back to .streamlit/secrets.toml.

Reported metrics:
- JSON failure rate: cases whose row produced no valid item (or no answer).
- median absolute grams error: |parsed - expected| over expected items,
  matched by position within the row.
- match accuracy: expected keyword present in the top-1 USDA description.
"""

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nutrition.config import secret, setting  # noqa: E402
from nutrition.llm import (
    LLMUnavailable,
    OpenAICompatibleProvider,
    ProviderChain,
)  # noqa: E402
from nutrition.parser import MealParser, ParseFailed  # noqa: E402
from nutrition.usda import UsdaClient, UsdaError  # noqa: E402


def key(name: str) -> str | None:
    return os.environ.get(name) or secret(name)


def build_chain() -> ProviderChain:
    providers = []
    if key("GROQ_API_KEY"):
        providers.append(
            OpenAICompatibleProvider(
                "groq",
                setting("GROQ_BASE_URL"),
                key("GROQ_API_KEY"),
                setting("GROQ_MODEL"),
            )
        )
    if key("OPENROUTER_API_KEY"):
        providers.append(
            OpenAICompatibleProvider(
                "openrouter",
                setting("OPENROUTER_BASE_URL"),
                key("OPENROUTER_API_KEY"),
                setting("OPENROUTER_MODEL"),
            )
        )
    if not providers:
        sys.exit("No LLM key found (GROQ_API_KEY / OPENROUTER_API_KEY).")
    print("Providers:", ", ".join(f"{p.name} ({p.model})" for p in providers))
    return ProviderChain(providers, cooldowns={})


def load_cases(path: Path, lang: str | None, limit: int | None) -> list[dict]:
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if lang:
        cases = [case for case in cases if case["lang"] == lang]
    return cases[:limit] if limit else cases


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    args.add_argument(
        "--cases", default=Path(__file__).with_name("cases.jsonl"), type=Path
    )
    args.add_argument("--lang", choices=["en", "fr"])
    args.add_argument("--limit", type=int)
    args.add_argument("--no-usda", action="store_true", help="skip USDA matching")
    args.add_argument(
        "--sleep", type=float, default=0.5, help="pause between LLM calls"
    )
    opts = args.parse_args()

    parser = MealParser(build_chain())
    usda = None
    if not opts.no_usda:
        if not key("FDC_API_KEY"):
            sys.exit("FDC_API_KEY not found; use --no-usda to skip matching.")
        usda = UsdaClient(key("FDC_API_KEY"))

    cases = load_cases(opts.cases, opts.lang, opts.limit)
    json_failures = 0
    grams_errors: list[float] = []
    matches: list[bool] = []
    failures: list[str] = []

    for case in cases:
        text, expected = case["text"], case["expected"]
        try:
            result = parser.parse([text], case["lang"])
            items = [item for item in result.items if item.row == 1]
        except (ParseFailed, LLMUnavailable) as exc:
            items = []
            failures.append(f"[{case['lang']}] {text!r}: {type(exc).__name__}: {exc}")
        if not items:
            json_failures += 1
            continue

        for want, got in zip(expected, items):
            grams_errors.append(abs(got.grams - want["grams"]))
            if usda is None:
                continue
            try:
                candidates = usda.search(got.usda_query) or usda.search(got.name_en)
            except UsdaError as exc:
                failures.append(f"[{case['lang']}] {text!r}: USDA error {exc}")
                candidates = []
            top1 = candidates[0].description if candidates else "<no result>"
            hit = want["keyword"].lower() in top1.lower()
            matches.append(hit)
            if not hit:
                failures.append(
                    f"[{case['lang']}] {text!r}: wanted {want['keyword']!r}, "
                    f"got {top1!r} (query {got.usda_query!r})"
                )
        if len(items) != len(expected):
            failures.append(
                f"[{case['lang']}] {text!r}: expected {len(expected)} item(s), "
                f"got {len(items)}: {[i.name_en for i in items]}"
            )
        time.sleep(opts.sleep)

    print(f"\nCases: {len(cases)}")
    print(
        f"JSON failure rate: {json_failures / len(cases):.1%} ({json_failures} cases)"
    )
    if grams_errors:
        print(f"Median absolute grams error: {statistics.median(grams_errors):.1f} g")
    if matches:
        print(
            f"Match accuracy (top-1): {sum(matches) / len(matches):.1%} ({len(matches)} items)"
        )
    if failures:
        print("\nFailures / mismatches:")
        for line in failures:
            print(" -", line)


if __name__ == "__main__":
    main()
