from __future__ import annotations

import copy
import json
import unittest

from scripts.update_benchmarks import (
    RAW_PATH,
    ValidationError,
    build_raw_document,
    extract_specs_from_html,
    normalize_raw,
)


class ExtractionTests(unittest.TestCase):
    def flight_html(self, specs: list[dict[str, object]]) -> str:
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

    def test_rejects_an_incomplete_metric_group(self) -> None:
        raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
        spec = raw["specs"]["ExploitGym"]
        spec["data"]["values"] = spec["data"]["values"][:-1]
        raw = build_raw_document(raw["specs"])

        with self.assertRaisesRegex(ValidationError, "Missing metrics"):
            normalize_raw(raw)


if __name__ == "__main__":
    unittest.main()
