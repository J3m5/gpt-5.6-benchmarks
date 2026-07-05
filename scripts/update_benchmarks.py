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
GENE_BENCH_PRO_SOURCE_URL = "https://openai.com/index/introducing-genebench-pro/"
RAW_PATH = ROOT / "data" / "raw" / "openai-vega-specs.json"
GENE_BENCH_PRO_RAW_PATH = ROOT / "data" / "raw" / "openai-genebench-pro-vega-specs.json"
API_PRICING_RAW_PATH = ROOT / "data" / "raw" / "api-pricing.json"
DATA_PATH = ROOT / "data" / "benchmarks.json"
LITELLM_COST_MAP_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)
ANTHROPIC_PRICING_URL = "https://www.anthropic.com/news/claude-fable-5-mythos-5"
ANTHROPIC_CACHE_PRICING_URL = (
    "https://platform.claude.com/docs/en/build-with-claude/prompt-caching"
)
GOOGLE_PRICING_URL = "https://ai.google.dev/gemini-api/docs/pricing"
TARGET_TITLES = (
    "GeneBench v1",
    "ExploitBench",
    "ExploitGym",
    "TerminalBench 2.1",
)
GENE_BENCH_PRO_SCALING_TITLE = "GeneBench-Pro: Test-time compute scaling on GPT models"
GENE_BENCH_PRO_MAX_REASONING_TITLE = "GeneBench-Pro: Model passrates at max reasoning"
GENE_BENCH_PRO_TARGET_TITLES = (
    GENE_BENCH_PRO_SCALING_TITLE,
    GENE_BENCH_PRO_MAX_REASONING_TITLE,
)
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
EXPLOIT_BENCH_EFFORTS = {
    "GPT-5.6 Sol": ("low", "medium", "high", "xhigh", "max"),
    "GPT-5.6 Terra": ("low", "medium", "high", "xhigh", "max"),
    "GPT-5.6 Luna": ("low", "medium", "high", "xhigh", "max"),
    "GPT-5.5": ("low", "medium", "high", "xhigh"),
    "GPT-5.4": ("low", "medium", "high", "xhigh"),
}
LITELLM_PRICING_MODELS = {
    "GPT-5.5": ("gpt-5.5", "openai", "OpenAI"),
    "GPT-5.4": ("gpt-5.4", "openai", "OpenAI"),
    "GPT-5.2": ("gpt-5.2", "openai", "OpenAI"),
    "Claude Fable 5": ("claude-fable-5", "anthropic", "Anthropic"),
    "Claude Opus 4.8": ("claude-opus-4-8", "anthropic", "Anthropic"),
    "Gemini 3.1 Pro Preview": (
        "gemini/gemini-3.1-pro-preview",
        "gemini",
        "Google",
    ),
}
API_PRICING_MODEL_ORDER = (
    "GPT-5.6 Sol Ultra",
    "GPT-5.6 Sol",
    "GPT-5.6 Terra",
    "GPT-5.6 Luna",
    "GPT-5.5",
    "GPT-5.4",
    "GPT-5.2",
    "Claude Mythos 5",
    "Claude Fable 5",
    "Claude Opus 4.8",
    "Gemini 3.1 Pro Preview",
)
GENE_BENCH_PRO_PRICING_MODELS = frozenset(
    {
        "GPT-5.2",
        "GPT-5.4",
        "GPT-5.5",
        "GPT-5.6 Luna",
        "GPT-5.6 Terra",
        "GPT-5.6 Sol",
    }
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


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def spec_title(spec: dict[str, Any]) -> str | None:
    title = spec.get("title")
    if isinstance(title, str):
        return title
    if isinstance(title, list) and len(title) == 1 and isinstance(title[0], str):
        return title[0]
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
        except json.JSONDecodeError as error:
            if "vegaLiteSpec" in serialized:
                raise ValidationError(
                    "Could not decode a Flight record containing Vega"
                ) from error


def extract_specs_from_html(
    html: str, target_titles: tuple[str, ...] = TARGET_TITLES
) -> dict[str, dict[str, Any]]:
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
                if title not in target_titles:
                    continue
                if title in specs and canonical_bytes(specs[title]) != canonical_bytes(
                    spec
                ):
                    raise ValidationError(f"Conflicting Vega specs found for {title}")
                specs[title] = spec

    missing = sorted(set(target_titles) - specs.keys())
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


def price_per_million(
    model: dict[str, Any],
    model_id: str,
    field: str,
    *,
    required: bool = True,
) -> float | None:
    value = model.get(field)
    if value is None and not required:
        return None
    price = finite_number(value, f"LiteLLM {model_id} {field}")
    if price <= 0:
        raise ValidationError(f"LiteLLM {model_id} {field} must be positive")
    return round(price * 1_000_000, 12)


def litellm_pricing_entry(
    display_name: str,
    model_id: str,
    expected_provider: str,
    provider_name: str,
    litellm_cost_map: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    model = litellm_cost_map.get(model_id)
    if (
        not isinstance(model, dict)
        or model.get("litellm_provider") != expected_provider
    ):
        raise ValidationError(
            f"LiteLLM has no {expected_provider} pricing for {model_id}"
        )

    cache_write = price_per_million(
        model,
        model_id,
        "cache_creation_input_token_cost",
        required=False,
    )
    long_context_fields = {
        "inputUsdPerMillionTokens": "input_cost_per_token_above_200k_tokens",
        "cachedInputUsdPerMillionTokens": (
            "cache_read_input_token_cost_above_200k_tokens"
        ),
        "outputUsdPerMillionTokens": "output_cost_per_token_above_200k_tokens",
    }
    long_context_values = {
        output_field: price_per_million(model, model_id, source_field, required=False)
        for output_field, source_field in long_context_fields.items()
    }
    populated_long_context = [
        value is not None for value in long_context_values.values()
    ]
    if any(populated_long_context) and not all(populated_long_context):
        raise ValidationError(f"Incomplete LiteLLM long-context pricing for {model_id}")
    long_context = (
        {"thresholdTokens": 200_000, **long_context_values}
        if all(populated_long_context)
        else None
    )

    consumed_fields = (
        "litellm_provider",
        "input_cost_per_token",
        "cache_read_input_token_cost",
        "cache_creation_input_token_cost",
        "output_cost_per_token",
        *long_context_fields.values(),
    )
    return (
        {
            "model": display_name,
            "provider": provider_name,
            "inputUsdPerMillionTokens": price_per_million(
                model, model_id, "input_cost_per_token"
            ),
            "cachedInputUsdPerMillionTokens": price_per_million(
                model, model_id, "cache_read_input_token_cost"
            ),
            "cacheWriteUsdPerMillionTokens": cache_write,
            "cacheWriteTtlMinutes": 5 if cache_write is not None else None,
            "outputUsdPerMillionTokens": price_per_million(
                model, model_id, "output_cost_per_token"
            ),
            "longContextPricing": long_context,
            "pricingModel": None,
            "source": "litellm",
            "sourceModelId": model_id,
        },
        {field: model.get(field) for field in consumed_fields},
    )


def extract_api_pricing(
    litellm_cost_map: dict[str, Any],
    gpt56_article_html: str,
    anthropic_article_html: str,
) -> dict[str, Any]:
    rates: dict[str, dict[str, Any]] = {}
    consumed_litellm_pricing: dict[str, dict[str, Any]] = {}
    for display_name, (
        model_id,
        expected_provider,
        provider_name,
    ) in LITELLM_PRICING_MODELS.items():
        entry, consumed = litellm_pricing_entry(
            display_name,
            model_id,
            expected_provider,
            provider_name,
            litellm_cost_map,
        )
        rates[display_name] = entry
        consumed_litellm_pricing[model_id] = consumed

    gpt56_pattern = re.compile(
        r"Sol is \$([0-9.]+) input / \$([0-9.]+) output; "
        r"Terra is \$([0-9.]+) input / \$([0-9.]+) output; "
        r"and Luna is \$([0-9.]+) input / \$([0-9.]+) output"
    )
    gpt56_matches = set(gpt56_pattern.findall(gpt56_article_html))
    if len(gpt56_matches) != 1 or not re.search(
        r"cache writes are billed at 1\.25x.*90% cached-input discount",
        gpt56_article_html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        raise ValidationError(
            "Could not identify one consistent GPT-5.6 pricing and caching statement"
        )
    sol_input, sol_output, terra_input, terra_output, luna_input, luna_output = (
        finite_number(float(value), "GPT-5.6 pricing")
        for value in next(iter(gpt56_matches))
    )
    for model, input_price, output_price in (
        ("GPT-5.6 Sol", sol_input, sol_output),
        ("GPT-5.6 Terra", terra_input, terra_output),
        ("GPT-5.6 Luna", luna_input, luna_output),
    ):
        rates[model] = {
            "model": model,
            "provider": "OpenAI",
            "inputUsdPerMillionTokens": input_price,
            "cachedInputUsdPerMillionTokens": input_price * 0.1,
            "cacheWriteUsdPerMillionTokens": input_price * 1.25,
            "cacheWriteTtlMinutes": 30,
            "outputUsdPerMillionTokens": output_price,
            "longContextPricing": None,
            "pricingModel": None,
            "source": "openai",
            "sourceModelId": model.lower().replace(" ", "-"),
        }

    rates["GPT-5.6 Sol Ultra"] = {
        **rates["GPT-5.6 Sol"],
        "model": "GPT-5.6 Sol Ultra",
        "pricingModel": "GPT-5.6 Sol",
    }

    anthropic_pattern = re.compile(
        r"Pricing for both models is \$([0-9.]+) per million input tokens "
        r"and \$([0-9.]+) per million output tokens"
    )
    anthropic_matches = set(anthropic_pattern.findall(anthropic_article_html))
    if len(anthropic_matches) != 1:
        raise ValidationError(
            "Could not identify one consistent Claude Fable/Mythos pricing statement"
        )
    mythos_input, mythos_output = (
        finite_number(float(value), "Claude Mythos 5 pricing")
        for value in next(iter(anthropic_matches))
    )
    fable = rates["Claude Fable 5"]
    if (
        fable["inputUsdPerMillionTokens"] != mythos_input
        or fable["outputUsdPerMillionTokens"] != mythos_output
    ):
        raise ValidationError("LiteLLM Claude Fable 5 pricing disagrees with Anthropic")
    rates["Claude Mythos 5"] = {
        **fable,
        "model": "Claude Mythos 5",
        "pricingModel": None,
        "source": "anthropic",
        "sourceModelId": None,
    }

    return {
        "schemaVersion": 2,
        "basis": "standard-api-token-pricing",
        "estimateBasis": "generated-output-tokens-only",
        "currency": "USD",
        "unitTokens": 1_000_000,
        "sources": {
            "litellm": {
                "url": LITELLM_COST_MAP_URL,
                "pricingSha256": content_hash(consumed_litellm_pricing),
            },
            "openai": {"url": SOURCE_URL},
            "anthropic": {
                "url": ANTHROPIC_PRICING_URL,
                "cacheUrl": ANTHROPIC_CACHE_PRICING_URL,
            },
            "google": {"url": GOOGLE_PRICING_URL},
        },
        "models": [rates[model] for model in API_PRICING_MODEL_ORDER],
    }


def normalize_api_pricing_raw(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("schemaVersion") != 2:
        raise ValidationError("Unsupported API pricing raw schema version")
    if (
        raw.get("basis") != "standard-api-token-pricing"
        or raw.get("estimateBasis") != "generated-output-tokens-only"
        or raw.get("currency") != "USD"
        or raw.get("unitTokens") != 1_000_000
    ):
        raise ValidationError("Unexpected API pricing basis")
    sources = raw.get("sources")
    if not isinstance(sources, dict):
        raise ValidationError("API pricing raw document has no sources")
    litellm_source = sources.get("litellm")
    openai_source = sources.get("openai")
    anthropic_source = sources.get("anthropic")
    google_source = sources.get("google")
    if (
        not isinstance(litellm_source, dict)
        or litellm_source.get("url") != LITELLM_COST_MAP_URL
        or not isinstance(litellm_source.get("pricingSha256"), str)
        or not isinstance(openai_source, dict)
        or openai_source.get("url") != SOURCE_URL
        or not isinstance(anthropic_source, dict)
        or anthropic_source.get("url") != ANTHROPIC_PRICING_URL
        or anthropic_source.get("cacheUrl") != ANTHROPIC_CACHE_PRICING_URL
        or not isinstance(google_source, dict)
        or google_source.get("url") != GOOGLE_PRICING_URL
    ):
        raise ValidationError("Unexpected API pricing source")

    models = raw.get("models")
    if not isinstance(models, list):
        raise ValidationError("API pricing raw document has no models")
    normalized = []
    seen: set[str] = set()
    for row in models:
        if not isinstance(row, dict):
            raise ValidationError("API pricing model must be an object")
        model = row.get("model")
        if not isinstance(model, str) or model in seen:
            raise ValidationError("API pricing model names must be unique")
        seen.add(model)
        prices = {}
        for field in (
            "inputUsdPerMillionTokens",
            "cachedInputUsdPerMillionTokens",
            "outputUsdPerMillionTokens",
        ):
            price = finite_number(row.get(field), f"{model} {field}")
            if price <= 0:
                raise ValidationError(f"{model} {field} must be positive")
            prices[field] = price
        cache_write_value = row.get("cacheWriteUsdPerMillionTokens")
        cache_write = (
            None
            if cache_write_value is None
            else finite_number(cache_write_value, f"{model} cache write")
        )
        cache_write_ttl = row.get("cacheWriteTtlMinutes")
        if (cache_write is None) != (cache_write_ttl is None):
            raise ValidationError(f"{model} cache-write price and TTL must agree")
        if cache_write is not None and (
            cache_write <= 0
            or isinstance(cache_write_ttl, bool)
            or not isinstance(cache_write_ttl, int)
            or cache_write_ttl <= 0
        ):
            raise ValidationError(f"{model} cache-write pricing must be positive")

        long_context_value = row.get("longContextPricing")
        long_context = None
        if long_context_value is not None:
            if not isinstance(long_context_value, dict):
                raise ValidationError(f"{model} long-context pricing must be an object")
            threshold = long_context_value.get("thresholdTokens")
            if (
                isinstance(threshold, bool)
                or not isinstance(threshold, int)
                or threshold <= 0
            ):
                raise ValidationError(
                    f"{model} long-context threshold must be positive"
                )
            long_context = {"thresholdTokens": threshold}
            for field in prices:
                price = finite_number(
                    long_context_value.get(field), f"{model} long-context {field}"
                )
                if price <= 0:
                    raise ValidationError(
                        f"{model} long-context {field} must be positive"
                    )
                long_context[field] = price

        provider = row.get("provider")
        if provider not in {"OpenAI", "Anthropic", "Google"}:
            raise ValidationError(f"Unexpected API provider for {model}")
        source = row.get("source")
        if source not in {"litellm", "openai", "anthropic"}:
            raise ValidationError(f"Unexpected pricing source for {model}")
        pricing_model = row.get("pricingModel")
        if pricing_model is not None and not isinstance(pricing_model, str):
            raise ValidationError(f"{model} pricingModel must be a string or null")
        entry = {
            "model": model,
            "provider": provider,
            **prices,
            "cacheWriteUsdPerMillionTokens": cache_write,
            "cacheWriteTtlMinutes": cache_write_ttl,
            "longContextPricing": long_context,
            "pricingModel": pricing_model,
            "source": source,
            "sourceModelId": row.get("sourceModelId"),
        }
        if source == "litellm":
            source_model_id = row.get("sourceModelId")
            mapping = LITELLM_PRICING_MODELS.get(model)
            if mapping is None or source_model_id != mapping[0]:
                raise ValidationError(f"Unexpected LiteLLM model ID for {model}")
        normalized.append(entry)

    if tuple(row["model"] for row in normalized) != API_PRICING_MODEL_ORDER:
        raise ValidationError("Unexpected API pricing model coverage or order")
    return {
        "basis": raw["basis"],
        "estimateBasis": raw["estimateBasis"],
        "currency": raw["currency"],
        "unitTokens": raw["unitTokens"],
        "sources": copy.deepcopy(sources),
        "models": normalized,
    }


def nonnegative_integer(value: Any, field: str) -> int:
    number = finite_number(value, field)
    if not number.is_integer() or number < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    return int(number)


def bounded_fraction(value: Any, field: str) -> float:
    fraction = finite_number(value, field)
    if not 0 <= fraction <= 1:
        raise ValidationError(f"{field} out of range: {fraction}")
    return fraction


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
    fraction = bounded_fraction(row.get("score"), "score")
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
        if (
            not isinstance(model, str)
            or not isinstance(duration, str)
            or not isinstance(duration_label, str)
            or not isinstance(effort, str)
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


def layer_rows(
    spec: dict[str, Any], title: str, mark_type: str
) -> list[list[dict[str, Any]]]:
    layers = spec.get("layer")
    if not isinstance(layers, list):
        raise ValidationError(f"{title} has no layers")

    matching_rows = []
    for layer in layers:
        if not isinstance(layer, dict):
            raise ValidationError(f"{title} contains a non-object layer")
        mark = layer.get("mark")
        resolved_mark_type = mark.get("type") if isinstance(mark, dict) else mark
        if resolved_mark_type != mark_type:
            continue
        matching_rows.append(require_rows(layer, f"{title} {mark_type} layer"))
    return matching_rows


def normalize_exploit_bench(spec: dict[str, Any]) -> dict[str, Any]:
    line_layers = layer_rows(spec, "ExploitBench", "line")
    if len(line_layers) != 1:
        raise ValidationError(
            f"ExploitBench must contain exactly one line layer, found {len(line_layers)}"
        )

    series = []
    seen_series: set[tuple[str, str]] = set()
    for row in line_layers[0]:
        if row.get("eval_id") != "exploitbench":
            raise ValidationError("Unexpected ExploitBench eval_id")
        if row.get("x_metric") != "output_tokens":
            raise ValidationError("Unexpected ExploitBench horizontal metric")
        model = row.get("model")
        effort = row.get("juice_level")
        if not isinstance(model, str) or not isinstance(effort, str):
            raise ValidationError("ExploitBench model and effort must be strings")
        key = (model, effort)
        if key in seen_series:
            raise ValidationError(
                f"Duplicate ExploitBench series point: {' / '.join(key)}"
            )
        seen_series.add(key)
        output_tokens = finite_number(
            row.get("x_value"), "ExploitBench output_tokens x_value"
        )
        if output_tokens <= 0:
            raise ValidationError("ExploitBench output tokens must be positive")
        series.append(
            {
                "model": model,
                "effort": effort,
                "outputTokens": output_tokens,
                **shared_score(row),
            }
        )

    series.sort(
        key=lambda item: (
            ordered_index(item["model"], EXPLOIT_MODEL_ORDER),
            ordered_index(item["effort"], EFFORT_ORDER),
        )
    )
    expected_series = {
        (model, effort)
        for model, efforts in EXPLOIT_BENCH_EFFORTS.items()
        for effort in efforts
    }
    if seen_series != expected_series:
        raise ValidationError("Unexpected ExploitBench series coverage")

    comparison_points = []
    seen_comparisons: set[str] = set()
    for rows in layer_rows(spec, "ExploitBench", "point"):
        for row in rows:
            model = row.get("model")
            shape = row.get("shape")
            if not isinstance(model, str) or shape not in {"diamond", "square"}:
                raise ValidationError("Invalid ExploitBench comparison point")
            if model in seen_comparisons:
                raise ValidationError(f"Duplicate ExploitBench comparison: {model}")
            seen_comparisons.add(model)
            output_tokens = finite_number(
                row.get("x_value"), f"ExploitBench {model} x_value"
            )
            score_fraction = bounded_fraction(
                row.get("score"), f"ExploitBench {model} score"
            )
            if output_tokens <= 0:
                raise ValidationError(
                    f"ExploitBench {model} output tokens must be positive"
                )
            comparison_points.append(
                {
                    "model": model,
                    "outputTokens": output_tokens,
                    "scoreFraction": score_fraction,
                    "scorePercent": score_fraction * 100,
                    "shape": shape,
                }
            )
    if not comparison_points:
        raise ValidationError("ExploitBench has no comparison points")
    if seen_comparisons != {"Mythos Preview", "Opus 4.7"}:
        raise ValidationError("Unexpected ExploitBench comparison coverage")
    comparison_points.sort(key=lambda item: item["model"])

    reference_lines = []
    seen_references: set[str] = set()
    for rows in layer_rows(spec, "ExploitBench", "rule"):
        for row in rows:
            model = row.get("model")
            detail = row.get("detail")
            if not isinstance(model, str) or not isinstance(detail, str):
                raise ValidationError("Invalid ExploitBench reference line")
            if model in seen_references:
                raise ValidationError(f"Duplicate ExploitBench reference: {model}")
            seen_references.add(model)
            x_start = finite_number(row.get("x_start"), f"ExploitBench {model} x_start")
            x_end = finite_number(row.get("x_end"), f"ExploitBench {model} x_end")
            score_fraction = bounded_fraction(
                row.get("score"), f"ExploitBench {model} score"
            )
            if x_start < 0 or x_end <= x_start:
                raise ValidationError(f"Invalid ExploitBench {model} reference range")
            reference_lines.append(
                {
                    "model": model,
                    "detail": detail,
                    "xStart": x_start,
                    "xEnd": x_end,
                    "scoreFraction": score_fraction,
                    "scorePercent": score_fraction * 100,
                }
            )
    if not reference_lines:
        raise ValidationError("ExploitBench has no reference lines")
    if seen_references != {"Mythos 5", "Opus 4.8"}:
        raise ValidationError("Unexpected ExploitBench reference coverage")
    reference_lines.sort(key=lambda item: item["model"])

    return {
        "series": series,
        "comparisonPoints": comparison_points,
        "referenceLines": reference_lines,
    }


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


def normalize_gene_bench_pro_scaling(
    spec: dict[str, Any],
) -> list[dict[str, Any]]:
    entries = []
    seen: set[tuple[str, str]] = set()
    expected_efforts = {
        "GPT-5.2": ("none", "low", "medium", "high", "xhigh"),
        "GPT-5.4": ("none", "low", "medium", "high", "xhigh"),
        "GPT-5.5": ("none", "low", "medium", "high", "xhigh"),
        "GPT-5.6 Luna": ("none", "low", "medium", "high", "xhigh", "max"),
        "GPT-5.6 Terra": ("none", "low", "medium", "high", "xhigh", "max"),
        "GPT-5.6 Sol": ("none", "low", "medium", "high", "xhigh", "max"),
    }

    for row in require_rows(spec, GENE_BENCH_PRO_SCALING_TITLE):
        model = row.get("model")
        reasoning = row.get("reasoning")
        source_experiment_ids = row.get("sourceExperimentIds")
        if (
            not isinstance(model, str)
            or not model
            or not isinstance(reasoning, str)
            or not reasoning
            or not isinstance(source_experiment_ids, str)
            or not source_experiment_ids
        ):
            raise ValidationError(
                "GeneBench-Pro scaling model, reasoning, and source IDs "
                "must be non-empty strings"
            )
        key = (model, reasoning)
        if key in seen:
            raise ValidationError(
                f"Duplicate GeneBench-Pro scaling point: {' / '.join(key)}"
            )
        seen.add(key)

        point_order = nonnegative_integer(row.get("pointOrder"), "pointOrder")
        if point_order < 1:
            raise ValidationError("pointOrder must be at least 1")
        reasoning_budget = nonnegative_integer(row.get("juice"), "juice")
        mean_nonmasked_sollen = finite_number(
            row.get("nonmaskedSollen"), "nonmaskedSollen"
        )
        if mean_nonmasked_sollen <= 0:
            raise ValidationError("nonmaskedSollen must be positive")

        passrate_fraction = bounded_fraction(row.get("passrate"), "passrate")
        passrate_percent = finite_number(row.get("passratePct"), "passratePct")
        if not math.isclose(
            passrate_percent,
            passrate_fraction * 100,
            rel_tol=0,
            abs_tol=1e-9,
        ):
            raise ValidationError(
                f"Inconsistent GeneBench-Pro passrate for {' / '.join(key)}"
            )

        entries.append(
            {
                "model": model,
                "reasoning": reasoning,
                "reasoningBudget": reasoning_budget,
                "pointOrder": point_order,
                "meanNonmaskedSollen": mean_nonmasked_sollen,
                "passrateFraction": passrate_fraction,
                "passratePercent": passrate_percent,
                "validCompletedSamples": nonnegative_integer(
                    row.get("validCompletedSamples"), "validCompletedSamples"
                ),
                "problemsWithValidSamples": nonnegative_integer(
                    row.get("problemsWithValidSamples"),
                    "problemsWithValidSamples",
                ),
                "validSamplesWithNonmaskedSollen": nonnegative_integer(
                    row.get("validSamplesWithNonmaskedSollen"),
                    "validSamplesWithNonmaskedSollen",
                ),
                "problemsWithNonmaskedSollen": nonnegative_integer(
                    row.get("problemsWithNonmaskedSollen"),
                    "problemsWithNonmaskedSollen",
                ),
                "sourceExperimentIds": source_experiment_ids,
            }
        )

    actual_efforts = {
        model: tuple(
            entry["reasoning"]
            for entry in sorted(
                (item for item in entries if item["model"] == model),
                key=lambda item: item["pointOrder"],
            )
        )
        for model in expected_efforts
    }
    if actual_efforts != expected_efforts or {
        entry["model"] for entry in entries
    } != set(expected_efforts):
        raise ValidationError(
            "Unexpected GeneBench-Pro scaling model or reasoning coverage"
        )

    entries.sort(
        key=lambda item: (
            list(expected_efforts).index(item["model"]),
            item["pointOrder"],
        )
    )
    return entries


def normalize_gene_bench_pro_max_reasoning(
    spec: dict[str, Any],
) -> list[dict[str, Any]]:
    entries = []
    seen_models: set[str] = set()
    expected_groups = {"GPT": 6, "GPT Pro": 6, "Other models": 6}

    for row in require_rows(spec, GENE_BENCH_PRO_MAX_REASONING_TITLE):
        group = row.get("group")
        model = row.get("model")
        if not isinstance(group, str) or not isinstance(model, str):
            raise ValidationError(
                "GeneBench-Pro max-reasoning group and model must be strings"
            )
        if model in seen_models:
            raise ValidationError(
                f"Duplicate GeneBench-Pro max-reasoning model: {model}"
            )
        seen_models.add(model)
        order = nonnegative_integer(row.get("order"), "order")
        if order < 1:
            raise ValidationError("order must be at least 1")
        passrate_fraction = bounded_fraction(row.get("passrate"), "passrate")
        entries.append(
            {
                "group": group,
                "model": model,
                "order": order,
                "passrateFraction": passrate_fraction,
                "passratePercent": passrate_fraction * 100,
            }
        )

    group_counts = {
        group: sum(entry["group"] == group for entry in entries)
        for group in expected_groups
    }
    if group_counts != expected_groups or {entry["group"] for entry in entries} != set(
        expected_groups
    ):
        raise ValidationError("Unexpected GeneBench-Pro max-reasoning group coverage")
    if sorted(entry["order"] for entry in entries) != list(range(1, 19)):
        raise ValidationError(
            "GeneBench-Pro max-reasoning order must contain 1 through 18"
        )

    entries.sort(key=lambda item: item["order"])
    return entries


def specs_hash(specs: dict[str, dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_bytes(specs)).hexdigest()


def build_raw_document(
    specs: dict[str, dict[str, Any]], source_url: str = SOURCE_URL
) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "source": {
            "url": source_url,
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
        "exploitBench": normalize_exploit_bench(specs["ExploitBench"]),
        "exploitGym": normalize_exploit(specs["ExploitGym"]),
        "terminalBench": normalize_terminal(specs["TerminalBench 2.1"]),
    }


def normalize_gene_bench_pro_raw(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("schemaVersion") != 1:
        raise ValidationError("Unsupported GeneBench-Pro raw schema version")
    specs = raw.get("specs")
    if not isinstance(specs, dict):
        raise ValidationError("GeneBench-Pro raw document has no specs object")
    missing = sorted(set(GENE_BENCH_PRO_TARGET_TITLES) - specs.keys())
    if missing:
        raise ValidationError(
            f"GeneBench-Pro raw document is missing: {', '.join(missing)}"
        )
    expected_hash = raw.get("source", {}).get("specSha256")
    actual_hash = specs_hash(specs)
    if expected_hash != actual_hash:
        raise ValidationError(
            "GeneBench-Pro raw Vega spec hash does not match its contents"
        )

    return {
        "source": {
            "url": raw["source"]["url"],
            "specSha256": actual_hash,
        },
        "geneBenchProScaling": normalize_gene_bench_pro_scaling(
            specs[GENE_BENCH_PRO_SCALING_TITLE]
        ),
        "geneBenchProMaxReasoning": normalize_gene_bench_pro_max_reasoning(
            specs[GENE_BENCH_PRO_MAX_REASONING_TITLE]
        ),
    }


def combine_normalized_data(
    legacy: dict[str, Any],
    gene_bench_pro: dict[str, Any],
    api_pricing: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schemaVersion": 4,
        "sources": {
            "gpt56SolPreview": legacy["source"],
            "geneBenchPro": gene_bench_pro["source"],
        },
        "apiPricing": api_pricing,
        "geneBench": legacy["geneBench"],
        "exploitBench": legacy["exploitBench"],
        "exploitGym": legacy["exploitGym"],
        "terminalBench": legacy["terminalBench"],
        "geneBenchProScaling": gene_bench_pro["geneBenchProScaling"],
        "geneBenchProMaxReasoning": gene_bench_pro["geneBenchProMaxReasoning"],
    }


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


def source_document(
    url: str,
    target_titles: tuple[str, ...],
    source_html: Path | None,
) -> tuple[str, dict[str, dict[str, Any]]]:
    html = (
        source_html.read_text(encoding="utf-8")
        if source_html is not None
        else fetch_html(url)
    )
    return html, extract_specs_from_html(html, target_titles)


def fetch_litellm_cost_map() -> dict[str, Any]:
    try:
        value = json.loads(fetch_html(LITELLM_COST_MAP_URL))
    except json.JSONDecodeError as error:
        raise ValidationError(f"Invalid LiteLLM cost map: {error}") from error
    if not isinstance(value, dict):
        raise ValidationError("LiteLLM cost map must be an object")
    return value


def data_summary(data: dict[str, Any]) -> str:
    return (
        f"{len(data['geneBench'])} GeneBench configurations, "
        f"{len(data['exploitBench']['series'])} ExploitBench series points, "
        f"{len(data['exploitBench']['comparisonPoints'])} ExploitBench comparison points, "
        f"{len(data['exploitBench']['referenceLines'])} ExploitBench references, "
        f"{len(data['exploitGym'])} ExploitGym runs, "
        f"{len(data['terminalBench'])} TerminalBench models, "
        f"{len(data['geneBenchProScaling'])} GeneBench-Pro scaling points, "
        f"{len(data['geneBenchProMaxReasoning'])} GeneBench-Pro max-reasoning models, "
        f"{len(data['apiPricing']['models'])} API model prices"
    )


def diff_summary(before: dict[str, Any] | None, after: dict[str, Any]) -> str:
    if before is None:
        return f"Created dataset: {data_summary(after)}"

    parts = []
    key_fields = {
        "geneBench": ("model", "effort"),
        "exploitGym": ("model", "duration", "effort"),
        "terminalBench": ("model",),
        "geneBenchProScaling": ("model", "reasoning"),
        "geneBenchProMaxReasoning": ("model",),
    }
    for collection, fields in key_fields.items():
        old = {
            tuple(row[field] for field in fields): row
            for row in before.get(collection, [])
        }
        new = {tuple(row[field] for field in fields): row for row in after[collection]}
        added = len(new.keys() - old.keys())
        removed = len(old.keys() - new.keys())
        modified = sum(old[key] != new[key] for key in old.keys() & new.keys())
        parts.append(f"{collection}: +{added} -{removed} ~{modified}")
    for collection, fields in {
        "series": ("model", "effort"),
        "comparisonPoints": ("model",),
        "referenceLines": ("model",),
    }.items():
        old = {
            tuple(row[field] for field in fields): row
            for row in before.get("exploitBench", {}).get(collection, [])
        }
        new = {
            tuple(row[field] for field in fields): row
            for row in after["exploitBench"][collection]
        }
        added = len(new.keys() - old.keys())
        removed = len(old.keys() - new.keys())
        modified = sum(old[key] != new[key] for key in old.keys() & new.keys())
        parts.append(f"exploitBench.{collection}: +{added} -{removed} ~{modified}")
    old_pricing = {
        row["model"]: row for row in (before.get("apiPricing") or {}).get("models", [])
    }
    new_pricing = {row["model"]: row for row in after["apiPricing"]["models"]}
    parts.append(
        "apiPricing: "
        f"+{len(new_pricing.keys() - old_pricing.keys())} "
        f"-{len(old_pricing.keys() - new_pricing.keys())} "
        f"~{sum(old_pricing[key] != new_pricing[key] for key in old_pricing.keys() & new_pricing.keys())}"
    )
    return "; ".join(parts)


def command_update(
    source_html: Path | None,
    gene_bench_pro_source_html: Path | None,
    anthropic_pricing_html: Path | None,
) -> int:
    source_page, specs = source_document(SOURCE_URL, TARGET_TITLES, source_html)
    raw = build_raw_document(specs, SOURCE_URL)
    _, gene_bench_pro_specs = source_document(
        GENE_BENCH_PRO_SOURCE_URL,
        GENE_BENCH_PRO_TARGET_TITLES,
        gene_bench_pro_source_html,
    )
    gene_bench_pro_raw = build_raw_document(
        gene_bench_pro_specs, GENE_BENCH_PRO_SOURCE_URL
    )
    anthropic_pricing_page = (
        anthropic_pricing_html.read_text(encoding="utf-8")
        if anthropic_pricing_html is not None
        else fetch_html(ANTHROPIC_PRICING_URL)
    )
    api_pricing_raw = extract_api_pricing(
        fetch_litellm_cost_map(), source_page, anthropic_pricing_page
    )
    data = combine_normalized_data(
        normalize_raw(copy.deepcopy(raw)),
        normalize_gene_bench_pro_raw(copy.deepcopy(gene_bench_pro_raw)),
        normalize_api_pricing_raw(copy.deepcopy(api_pricing_raw)),
    )
    previous = load_json(DATA_PATH) if DATA_PATH.exists() else None
    changed = [
        path
        for path, content in (
            (RAW_PATH, json_text(raw)),
            (GENE_BENCH_PRO_RAW_PATH, json_text(gene_bench_pro_raw)),
            (API_PRICING_RAW_PATH, json_text(api_pricing_raw)),
            (DATA_PATH, json_text(data)),
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
    gene_bench_pro_raw = load_json(GENE_BENCH_PRO_RAW_PATH)
    api_pricing_raw = load_json(API_PRICING_RAW_PATH)
    data = combine_normalized_data(
        normalize_raw(copy.deepcopy(raw)),
        normalize_gene_bench_pro_raw(copy.deepcopy(gene_bench_pro_raw)),
        normalize_api_pricing_raw(copy.deepcopy(api_pricing_raw)),
    )
    expected_json = json_text(data)
    failures = []
    if not DATA_PATH.exists() or DATA_PATH.read_text(encoding="utf-8") != expected_json:
        failures.append(str(DATA_PATH.relative_to(ROOT)))
    if failures:
        raise ValidationError(
            "Generated artifacts are stale: "
            + ", ".join(failures)
            + ". Run `mise run data:update`."
        )
    print(f"Data verified: {data_summary(data)}")
    return 0


def command_check_upstream(
    source_html: Path | None,
    gene_bench_pro_source_html: Path | None,
    anthropic_pricing_html: Path | None,
) -> int:
    source_page, specs = source_document(SOURCE_URL, TARGET_TITLES, source_html)
    _, gene_bench_pro_specs = source_document(
        GENE_BENCH_PRO_SOURCE_URL,
        GENE_BENCH_PRO_TARGET_TITLES,
        gene_bench_pro_source_html,
    )
    anthropic_pricing_page = (
        anthropic_pricing_html.read_text(encoding="utf-8")
        if anthropic_pricing_html is not None
        else fetch_html(ANTHROPIC_PRICING_URL)
    )
    current = load_json(DATA_PATH)
    candidate = combine_normalized_data(
        normalize_raw(build_raw_document(specs, SOURCE_URL)),
        normalize_gene_bench_pro_raw(
            build_raw_document(gene_bench_pro_specs, GENE_BENCH_PRO_SOURCE_URL)
        ),
        normalize_api_pricing_raw(
            extract_api_pricing(
                fetch_litellm_cost_map(), source_page, anthropic_pricing_page
            )
        ),
    )
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
        help="Read a saved GPT-5.6 Sol source response instead of downloading it.",
    )
    parser.add_argument(
        "--gene-bench-pro-source-html",
        type=Path,
        help="Read a saved GeneBench-Pro response instead of downloading it.",
    )
    parser.add_argument(
        "--anthropic-pricing-html",
        type=Path,
        help="Read a saved Anthropic pricing response instead of downloading it.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command == "update":
            return command_update(
                args.source_html,
                args.gene_bench_pro_source_html,
                args.anthropic_pricing_html,
            )
        if args.command == "verify":
            return command_verify()
        return command_check_upstream(
            args.source_html,
            args.gene_bench_pro_source_html,
            args.anthropic_pricing_html,
        )
    except (OSError, ValidationError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
