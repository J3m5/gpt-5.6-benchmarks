from __future__ import annotations

import copy
import json
import unittest
from collections.abc import Iterable, Mapping

from scripts.update_benchmarks import (
    API_PRICING_RAW_PATH,
    GENE_BENCH_PRO_MAX_REASONING_TITLE,
    GENE_BENCH_PRO_RAW_PATH,
    GENE_BENCH_PRO_SCALING_TITLE,
    GENE_BENCH_PRO_SOURCE_URL,
    RAW_PATH,
    ValidationError,
    build_raw_document,
    extract_api_pricing,
    extract_specs_from_html,
    normalize_api_pricing_raw,
    normalize_gene_bench_pro_raw,
    normalize_raw,
)


class ExtractionTests(unittest.TestCase):
    def flight_html(self, specs: Iterable[Mapping[str, object]]) -> str:
        records = "".join(
            f"{index:x}:"
            + json.dumps(
                ["$", "component", None, {"vegaLiteSpec": spec}],
                separators=(",", ":"),
            )
            + "\n"
            for index, spec in enumerate(specs, start=1)
        )
        envelope = json.dumps([1, records], separators=(",", ":"))
        return (
            "<!doctype html><script>"
            f"(self.__next_f=self.__next_f||[]).push({envelope})"
            "</script>"
        )

    def test_extracts_required_specs_from_react_flight(self) -> None:
        specs = [
            {"title": {"text": title}, "data": {"values": [{"row": title}]}}
            for title in ("GeneBench v1", "ExploitGym", "TerminalBench 2.1")
        ]

        extracted = extract_specs_from_html(self.flight_html(specs))

        self.assertEqual(
            {"GeneBench v1", "ExploitGym", "TerminalBench 2.1"},
            set(extracted),
        )
        self.assertEqual(
            "ExploitGym", extracted["ExploitGym"]["data"]["values"][0]["row"]
        )

    def test_rejects_missing_specs(self) -> None:
        spec = {
            "title": {"text": "GeneBench v1"},
            "data": {"values": [{"eval_id": "genebench_v1"}]},
        }

        with self.assertRaisesRegex(ValidationError, "Missing Vega specs"):
            extract_specs_from_html(self.flight_html([spec]))

    def test_extracts_gene_bench_pro_list_and_string_titles(self) -> None:
        specs = [
            {
                "title": [GENE_BENCH_PRO_SCALING_TITLE],
                "data": {"values": [{"chart": "scaling"}]},
            },
            {
                "title": GENE_BENCH_PRO_MAX_REASONING_TITLE,
                "data": {"values": [{"chart": "max reasoning"}]},
            },
        ]

        extracted = extract_specs_from_html(
            self.flight_html(specs),
            (
                GENE_BENCH_PRO_SCALING_TITLE,
                GENE_BENCH_PRO_MAX_REASONING_TITLE,
            ),
        )

        self.assertEqual(
            {
                GENE_BENCH_PRO_SCALING_TITLE,
                GENE_BENCH_PRO_MAX_REASONING_TITLE,
            },
            set(extracted),
        )

    def test_extracts_api_pricing(self) -> None:
        litellm_cost_map = {
            "gpt-5.2": {
                "litellm_provider": "openai",
                "input_cost_per_token": 0.00000175,
                "cache_read_input_token_cost": 0.000000175,
                "output_cost_per_token": 0.000014,
            },
            "gpt-5.4": {
                "litellm_provider": "openai",
                "input_cost_per_token": 0.0000025,
                "cache_read_input_token_cost": 0.00000025,
                "output_cost_per_token": 0.000015,
            },
            "gpt-5.5": {
                "litellm_provider": "openai",
                "input_cost_per_token": 0.000005,
                "cache_read_input_token_cost": 0.0000005,
                "output_cost_per_token": 0.00003,
            },
            "claude-fable-5": {
                "litellm_provider": "anthropic",
                "input_cost_per_token": 0.00001,
                "cache_read_input_token_cost": 0.000001,
                "cache_creation_input_token_cost": 0.0000125,
                "output_cost_per_token": 0.00005,
            },
            "claude-opus-4-8": {
                "litellm_provider": "anthropic",
                "input_cost_per_token": 0.000005,
                "cache_read_input_token_cost": 0.0000005,
                "cache_creation_input_token_cost": 0.00000625,
                "output_cost_per_token": 0.000025,
            },
            "gemini/gemini-3.1-pro-preview": {
                "litellm_provider": "gemini",
                "input_cost_per_token": 0.000002,
                "cache_read_input_token_cost": 0.0000002,
                "output_cost_per_token": 0.000012,
                "input_cost_per_token_above_200k_tokens": 0.000004,
                "cache_read_input_token_cost_above_200k_tokens": 0.0000004,
                "output_cost_per_token_above_200k_tokens": 0.000018,
            },
        }
        openai_article = (
            "Sol is $5 input / $30 output; "
            "Terra is $2.50 input / $15 output; "
            "and Luna is $1 input / $6 output. "
            "Cache writes are billed at 1.25x the model's uncached input rate, "
            "while cache reads continue to receive the 90% cached-input discount."
        )
        anthropic_article = (
            "Pricing for both models is $10 per million input tokens "
            "and $50 per million output tokens."
        )

        raw = extract_api_pricing(litellm_cost_map, openai_article, anthropic_article)
        pricing = normalize_api_pricing_raw(raw)

        self.assertEqual(11, len(pricing["models"]))
        by_model = {row["model"]: row for row in pricing["models"]}
        self.assertEqual(
            [14, 15, 30, 6, 15, 30],
            [
                by_model[model]["outputUsdPerMillionTokens"]
                for model in (
                    "GPT-5.2",
                    "GPT-5.4",
                    "GPT-5.5",
                    "GPT-5.6 Luna",
                    "GPT-5.6 Terra",
                    "GPT-5.6 Sol",
                )
            ],
        )
        self.assertEqual(
            (5, 0.5, 6.25, 30),
            tuple(
                by_model["GPT-5.6 Sol"][field]
                for field in (
                    "inputUsdPerMillionTokens",
                    "cachedInputUsdPerMillionTokens",
                    "cacheWriteUsdPerMillionTokens",
                    "outputUsdPerMillionTokens",
                )
            ),
        )
        self.assertEqual("GPT-5.6 Sol", by_model["GPT-5.6 Sol Ultra"]["pricingModel"])
        self.assertEqual(
            (10, 1, 12.5, 50),
            tuple(
                by_model["Claude Mythos 5"][field]
                for field in (
                    "inputUsdPerMillionTokens",
                    "cachedInputUsdPerMillionTokens",
                    "cacheWriteUsdPerMillionTokens",
                    "outputUsdPerMillionTokens",
                )
            ),
        )
        self.assertEqual(
            {
                "thresholdTokens": 200_000,
                "inputUsdPerMillionTokens": 4,
                "cachedInputUsdPerMillionTokens": 0.4,
                "outputUsdPerMillionTokens": 18,
            },
            by_model["Gemini 3.1 Pro Preview"]["longContextPricing"],
        )
        self.assertEqual("standard-api-token-pricing", pricing["basis"])
        self.assertEqual("generated-output-tokens-only", pricing["estimateBasis"])

    def test_normalizes_the_committed_snapshot(self) -> None:
        raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
        data = normalize_raw(copy.deepcopy(raw))

        self.assertEqual(22, len(data["geneBench"]))
        self.assertEqual(32, len(data["exploitGym"]))
        self.assertEqual(9, len(data["terminalBench"]))
        run = next(
            row
            for row in data["exploitGym"]
            if (
                row["model"],
                row["duration"],
                row["effort"],
            )
            == ("GPT-5.6 Sol", "6h", "max")
        )
        self.assertEqual(138.11910208, run["apiCostUsd"])
        self.assertEqual(33.7, run["scorePercent"])

    def test_normalizes_the_committed_gene_bench_pro_snapshot(self) -> None:
        raw = json.loads(GENE_BENCH_PRO_RAW_PATH.read_text(encoding="utf-8"))
        data = normalize_gene_bench_pro_raw(copy.deepcopy(raw))

        self.assertEqual(GENE_BENCH_PRO_SOURCE_URL, data["source"]["url"])
        self.assertEqual(33, len(data["geneBenchProScaling"]))
        self.assertEqual(18, len(data["geneBenchProMaxReasoning"]))

        scaling = next(
            row
            for row in data["geneBenchProScaling"]
            if (row["model"], row["reasoning"]) == ("GPT-5.6 Sol", "max")
        )
        self.assertEqual(960, scaling["reasoningBudget"])
        self.assertEqual(33168.297416020665, scaling["meanNonmaskedSollen"])
        self.assertEqual(28.733850129198967, scaling["passratePercent"])

        max_reasoning = next(
            row
            for row in data["geneBenchProMaxReasoning"]
            if row["model"] == "GPT-5.6 Sol (Pro)"
        )
        self.assertEqual("GPT Pro", max_reasoning["group"])
        self.assertEqual(31.472868217054266, max_reasoning["passratePercent"])

    def test_normalizes_the_committed_api_pricing_snapshot(self) -> None:
        raw = json.loads(API_PRICING_RAW_PATH.read_text(encoding="utf-8"))
        pricing = normalize_api_pricing_raw(raw)

        self.assertEqual(11, len(pricing["models"]))
        self.assertEqual(
            30,
            next(
                row["outputUsdPerMillionTokens"]
                for row in pricing["models"]
                if row["model"] == "GPT-5.6 Sol"
            ),
        )

    def test_rejects_inconsistent_gene_bench_pro_passrate(self) -> None:
        raw = json.loads(GENE_BENCH_PRO_RAW_PATH.read_text(encoding="utf-8"))
        spec = raw["specs"][GENE_BENCH_PRO_SCALING_TITLE]
        spec["data"]["values"][0]["passratePct"] = 99
        raw = build_raw_document(raw["specs"], GENE_BENCH_PRO_SOURCE_URL)

        with self.assertRaisesRegex(ValidationError, "Inconsistent"):
            normalize_gene_bench_pro_raw(raw)

    def test_rejects_an_incomplete_metric_group(self) -> None:
        raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
        spec = raw["specs"]["ExploitGym"]
        spec["data"]["values"] = spec["data"]["values"][:-1]
        raw = build_raw_document(raw["specs"])

        with self.assertRaisesRegex(ValidationError, "Missing metrics"):
            normalize_raw(raw)


if __name__ == "__main__":
    unittest.main()
