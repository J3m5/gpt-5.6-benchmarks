#!/usr/bin/env python3
"""Extract and normalize benchmark data embedded in the OpenAI article."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://openai.com/index/previewing-gpt-5-6-sol/"
RAW_PATH = ROOT / "data" / "raw" / "openai-vega-specs.json"
DATA_PATH = ROOT / "data" / "benchmarks.json"
JS_PATH = ROOT / "data" / "benchmarks.generated.js"
TARGET_TITLES = ("GeneBench v1", "ExploitGym", "TerminalBench 2.1")
METRICS = ("output_tokens", "latency_min", "api_cost_usd")
EFFORT_ORDER = ("none", "low", "medium", "high", "xhigh", "max", "ma_ultra", "n/a")
GENE_MODEL_ORDER = ("GPT-5.6 Sol", "GPT-5.6 Terra", "GPT-5.6 Luna", "GPT-5.5")
EXPLOIT_MODEL_ORDER = (
    "GPT-5.6 Sol",
    "GPT-5.6 Terra",
    "GPT-5.6 Luna",
    "GPT-5.5",
    "GPT-5.4",
)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)


class ValidationError(RuntimeError):
    """Raised when the upstream payload violates the expected data contract."""


class InlineScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.scripts: list[str] = []
        self._parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "script":
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._parts is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._parts is not None:
            self.scripts.append("".join(self._parts))
            self._parts = None


def json_text(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def spec_title(spec: dict[str, Any]) -> str | None:
    title = spec.get("title")
    if isinstance(title, str):
        return title
    if isinstance(title, dict) and isinstance(title.get("text"), str):
        return title["text"]
    return None


def walk_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_objects(child)


def decode_flight_script(script: str) -> Iterable[Any]:
    text = script.strip()
    marker = ".push("
    marker_index = text.find(marker)
    if "__next_f" not in text or marker_index < 0:
        return

    suffix = text[marker_index + len(marker) :].rstrip()
    if suffix.endswith(";"):
        suffix = suffix[:-1].rstrip()
    if not suffix.endswith(")"):
        return

    try:
        envelope = json.loads(suffix[:-1])
    except json.JSONDecodeError as error:
        raise ValidationError(f"Invalid React Flight envelope: {error}") from error

    if not isinstance(envelope, list) or len(envelope) < 2:
        return
    payload = envelope[1]
    if not isinstance(payload, str):
        return

    for record in payload.splitlines():
        separator = record.find(":")
        if separator < 0:
            continue
        serialized = record[separator + 1 :]
        if not serialized.startswith(("{", "[")):
            continue
        try:
            yield json.loads(serialized)
        except json.JSONDecodeError:
            if "vegaLiteSpec" in serialized:
                raise ValidationError(
                    "Could not decode a Flight record containing Vega"
                )


def extract_specs_from_html(html: str) -> dict[str, dict[str, Any]]:
    parser = InlineScriptParser()
    parser.feed(html)
    specs: dict[str, dict[str, Any]] = {}

    for script in parser.scripts:
        for record in decode_flight_script(script):
            for value in walk_objects(record):
                spec = value.get("vegaLiteSpec")
                if not isinstance(spec, dict):
                    continue
                title = spec_title(spec)
                if title not in TARGET_TITLES:
                    continue
                if title in specs and canonical_bytes(specs[title]) != canonical_bytes(
                    spec
                ):
                    raise ValidationError(f"Conflicting Vega specs found for {title}")
                specs[title] = spec

    missing = sorted(set(TARGET_TITLES) - specs.keys())
    if missing:
        raise ValidationError(f"Missing Vega specs: {', '.join(missing)}")
    return specs


def fetch_html(url: str = SOURCE_URL, attempts: int = 3) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip",
        "Cache-Control": "no-cache",
        "Upgrade-Insecure-Requests": "1",
    }
    request = urllib.request.Request(url, headers=headers)
    last_error: Exception | None = None

    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    payload = gzip.decompress(payload)
                return payload.decode(response.headers.get_content_charset() or "utf-8")
        except (OSError, urllib.error.URLError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(2**attempt)

    raise RuntimeError(f"Could not fetch {url}: {last_error}") from last_error


def require_rows(spec: dict[str, Any], title: str) -> list[dict[str, Any]]:
    data = spec.get("data")
    rows = data.get("values") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValidationError(f"{title} has no inline data.values")
    if not all(isinstance(row, dict) for row in rows):
        raise ValidationError(f"{title} contains a non-object data row")
    return rows


def finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValidationError(f"{field} must be finite")
    return number


def percentage_from_label(label: Any) -> float:
    if not isinstance(label, str):
        raise ValidationError("score_label must be a string")
    match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)%\s*", label)
    if not match:
        raise ValidationError(f"Invalid percentage label: {label!r}")
    return float(match.group(1))


def ordered_index(value: str, order: tuple[str, ...]) -> tuple[int, str]:
    try:
        return (order.index(value), value)
    except ValueError:
        return (len(order), value)


def shared_score(row: dict[str, Any]) -> dict[str, Any]:
    fraction = finite_number(row.get("score"), "score")
    if not 0 <= fraction <= 1:
        raise ValidationError(f"score out of range: {fraction}")
    label = row.get("score_label")
    percent = percentage_from_label(label)
    return {
        "scoreFraction": fraction,
        "scorePercent": percent,
        "scoreLabel": label,
        "scoreUnit": row.get("score_unit"),
    }


def add_metric_row(
    grouped: dict[tuple[str, ...], dict[str, Any]],
    key: tuple[str, ...],
    row: dict[str, Any],
    base: dict[str, Any],
) -> None:
    metric = row.get("x_metric")
    if metric not in METRICS:
        raise ValidationError(f"Unexpected metric {metric!r} for {' / '.join(key)}")
    value = finite_number(row.get("x_value"), f"{metric} x_value")
    if value < 0:
        raise ValidationError(f"{metric} must not be negative for {' / '.join(key)}")

    entry = grouped.setdefault(key, {**base, "_metrics": {}})
    comparable = {name: base[name] for name in base if name.startswith("score")}
    existing = {name: entry[name] for name in comparable}
    if existing != comparable:
        raise ValidationError(f"Inconsistent score fields for {' / '.join(key)}")
    if metric in entry["_metrics"]:
        raise ValidationError(f"Duplicate {metric} row for {' / '.join(key)}")
    entry["_metrics"][metric] = value


def finish_metric_groups(
    grouped: dict[tuple[str, ...], dict[str, Any]],
) -> list[dict[str, Any]]:
    output = []
    for key, entry in grouped.items():
        metric_values = entry.pop("_metrics")
        missing = sorted(set(METRICS) - metric_values.keys())
        if missing:
            raise ValidationError(
                f"Missing metrics for {' / '.join(key)}: {', '.join(missing)}"
            )
        output.append(
            {
                **entry,
                "outputTokens": metric_values["output_tokens"],
                "latencyMinutes": metric_values["latency_min"],
                "apiCostUsd": metric_values["api_cost_usd"],
            }
        )
    return output


def normalize_gene(spec: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in require_rows(spec, "GeneBench v1"):
        if row.get("eval_id") != "genebench_v1":
            raise ValidationError("Unexpected GeneBench eval_id")
        model = row.get("model")
        effort = row.get("juice_level")
        if not isinstance(model, str) or not isinstance(effort, str):
            raise ValidationError("GeneBench model and effort must be strings")
        base = {"model": model, "effort": effort, **shared_score(row)}
        add_metric_row(grouped, (model, effort), row, base)

    entries = finish_metric_groups(grouped)
    entries.sort(
        key=lambda item: (
            ordered_index(item["model"], GENE_MODEL_ORDER),
            ordered_index(item["effort"], EFFORT_ORDER),
        )
    )
    return entries


def normalize_exploit(spec: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in require_rows(spec, "ExploitGym"):
        if row.get("eval_id") != "exploitgym":
            raise ValidationError("Unexpected ExploitGym eval_id")
        model = row.get("model_family")
        duration = row.get("run_duration")
        duration_label = row.get("run_duration_label")
        effort = row.get("juice_level")
        if not all(
            isinstance(value, str)
            for value in (model, duration, duration_label, effort)
        ):
            raise ValidationError("ExploitGym dimensions must be strings")
        if duration not in {"2h", "6h"}:
            raise ValidationError(f"Unexpected ExploitGym duration: {duration}")
        base = {
            "model": model,
            "duration": duration,
            "durationLabel": duration_label,
            "effort": effort,
            **shared_score(row),
        }
        add_metric_row(grouped, (model, duration, effort), row, base)

    entries = finish_metric_groups(grouped)
    entries.sort(
        key=lambda item: (
            ordered_index(item["model"], EXPLOIT_MODEL_ORDER),
            item["duration"],
            ordered_index(item["effort"], EFFORT_ORDER),
        )
    )
    return entries


def normalize_terminal(spec: dict[str, Any]) -> list[dict[str, Any]]:
    entries = []
    seen_models: set[str] = set()
    for row in require_rows(spec, "TerminalBench 2.1"):
        if row.get("eval_id") != "terminal_bench_2_1":
            raise ValidationError("Unexpected TerminalBench eval_id")
        model = row.get("model")
        reasoning = row.get("juice_level")
        if not isinstance(model, str) or not isinstance(reasoning, str):
            raise ValidationError("TerminalBench model and reasoning must be strings")
        if model in seen_models:
            raise ValidationError(f"Duplicate TerminalBench model: {model}")
        seen_models.add(model)
        cost = finite_number(row.get("api_cost_usd"), "TerminalBench api_cost_usd")
        if cost < 0:
            raise ValidationError("TerminalBench api_cost_usd must not be negative")
        entries.append(
            {
                "model": model,
                "reasoning": reasoning,
                "apiCostUsd": cost,
                **shared_score(row),
            }
        )

    entries.sort(key=lambda item: (-item["scoreFraction"], item["model"]))
    return entries


def specs_hash(specs: dict[str, dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_bytes(specs)).hexdigest()


def build_raw_document(specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "source": {
            "url": SOURCE_URL,
            "format": "nextjs-react-flight-inline-vega-lite",
            "specSha256": specs_hash(specs),
        },
        "specs": specs,
    }


def normalize_raw(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("schemaVersion") != 1:
        raise ValidationError("Unsupported raw schema version")
    specs = raw.get("specs")
    if not isinstance(specs, dict):
        raise ValidationError("Raw document has no specs object")
    missing = sorted(set(TARGET_TITLES) - specs.keys())
    if missing:
        raise ValidationError(f"Raw document is missing: {', '.join(missing)}")
    expected_hash = raw.get("source", {}).get("specSha256")
    actual_hash = specs_hash(specs)
    if expected_hash != actual_hash:
        raise ValidationError("Raw Vega spec hash does not match its contents")

    return {
        "schemaVersion": 1,
        "source": {
            "url": raw["source"]["url"],
            "specSha256": actual_hash,
        },
        "geneBench": normalize_gene(specs["GeneBench v1"]),
        "exploitGym": normalize_exploit(specs["ExploitGym"]),
        "terminalBench": normalize_terminal(specs["TerminalBench 2.1"]),
    }


def generated_js(data: dict[str, Any]) -> str:
    payload = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True)
    return f"window.BENCHMARK_DATA = Object.freeze(\n{payload}\n);\n"


def write_atomic(path: Path, content: str) -> bool:
    encoded = content.encode("utf-8")
    if path.exists() and path.read_bytes() == encoded:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return True


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"Could not read {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValidationError(f"{path} must contain a JSON object")
    return value


def source_specs(source_html: Path | None) -> dict[str, dict[str, Any]]:
    html = (
        source_html.read_text(encoding="utf-8")
        if source_html is not None
        else fetch_html()
    )
    return extract_specs_from_html(html)


def data_summary(data: dict[str, Any]) -> str:
    return (
        f"{len(data['geneBench'])} GeneBench configurations, "
        f"{len(data['exploitGym'])} ExploitGym runs, "
        f"{len(data['terminalBench'])} TerminalBench models"
    )


def diff_summary(before: dict[str, Any] | None, after: dict[str, Any]) -> str:
    if before is None:
        return f"Created dataset: {data_summary(after)}"

    parts = []
    key_fields = {
        "geneBench": ("model", "effort"),
        "exploitGym": ("model", "duration", "effort"),
        "terminalBench": ("model",),
    }
    for collection, fields in key_fields.items():
        old = {tuple(row[field] for field in fields): row for row in before[collection]}
        new = {tuple(row[field] for field in fields): row for row in after[collection]}
        added = len(new.keys() - old.keys())
        removed = len(old.keys() - new.keys())
        modified = sum(old[key] != new[key] for key in old.keys() & new.keys())
        parts.append(f"{collection}: +{added} -{removed} ~{modified}")
    return "; ".join(parts)


def command_update(source_html: Path | None) -> int:
    specs = source_specs(source_html)
    raw = build_raw_document(specs)
    data = normalize_raw(copy.deepcopy(raw))
    previous = load_json(DATA_PATH) if DATA_PATH.exists() else None
    changed = [
        path
        for path, content in (
            (RAW_PATH, json_text(raw)),
            (DATA_PATH, json_text(data)),
            (JS_PATH, generated_js(data)),
        )
        if write_atomic(path, content)
    ]
    print(diff_summary(previous, data))
    print(
        "Updated: "
        + (", ".join(str(path.relative_to(ROOT)) for path in changed) or "none")
    )
    return 0


def command_verify() -> int:
    raw = load_json(RAW_PATH)
    data = normalize_raw(copy.deepcopy(raw))
    expected_json = json_text(data)
    expected_js = generated_js(data)
    failures = []
    if not DATA_PATH.exists() or DATA_PATH.read_text(encoding="utf-8") != expected_json:
        failures.append(str(DATA_PATH.relative_to(ROOT)))
    if not JS_PATH.exists() or JS_PATH.read_text(encoding="utf-8") != expected_js:
        failures.append(str(JS_PATH.relative_to(ROOT)))
    if failures:
        raise ValidationError(
            "Generated artifacts are stale: "
            + ", ".join(failures)
            + ". Run `mise run data:update`."
        )
    print(f"Data verified: {data_summary(data)}")
    return 0


def command_check_upstream(source_html: Path | None) -> int:
    specs = source_specs(source_html)
    current = load_json(DATA_PATH)
    candidate = normalize_raw(build_raw_document(specs))
    if canonical_bytes(current) == canonical_bytes(candidate):
        print("Upstream benchmark data is unchanged.")
        return 0
    print(diff_summary(current, candidate))
    return 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("update", "verify", "check-upstream"))
    parser.add_argument(
        "--source-html",
        type=Path,
        help="Read a saved source response instead of downloading the article.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command == "update":
            return command_update(args.source_html)
        if args.command == "verify":
            return command_verify()
        return command_check_upstream(args.source_html)
    except (OSError, ValidationError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
