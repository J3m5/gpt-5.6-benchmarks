# GPT-5.6 Benchmark Visualizations

Interactive visualizations of the GeneBench v1, ExploitGym, and TerminalBench
2.1 results published in OpenAI's
[GPT-5.6 Sol preview](https://openai.com/index/previewing-gpt-5-6-sol/).
The auditable data snapshot also includes the two charts from OpenAI's
[GeneBench-Pro article](https://openai.com/index/introducing-genebench-pro/).

## Live page

https://j3m5.github.io/gpt-5.6-benchmarks/

## Included views

- Standard API input, cached-input, cache-write, and output pricing for every
  model shown in the charts
- GeneBench v1 score, output-token, latency, and API-cost comparison
- GeneBench v1 score versus API cost, latency, or output tokens
- GeneBench-Pro passrate versus tokens used or estimated output-token API cost,
  with configuration and Pareto filters
- ExploitGym intended-exploit rate versus API cost, latency, or output tokens
- Linear/logarithmic horizontal-axis toggles on all resource scatter plots
- Point-label visibility toggles on all resource scatter plots
- Optional family lines connecting consecutive reasoning efforts
- Attractive and opposite quadrants on both resource-efficiency plots
- Sortable GeneBench v1 data table with all resource metrics
- TerminalBench 2.1 scores with reasoning levels

The frontend uses Vite with vanilla TypeScript and CSS. Node LTS and Aube are
pinned through the project `mise.toml`.

## Development

```bash
mise install
mise run dev
```

`mise run dev` starts the Vite development server. Production assets are
generated in `dist/` with:

```bash
mise run build
```

Architecture and maintenance details are documented in
[docs/architecture.md](docs/architecture.md). Behavioral contracts and the
verification checklist are in [docs/verification.md](docs/verification.md).

## Data maintenance

Benchmark values are extracted from the Vega-Lite specifications embedded in
the source articles' HTML. The extractor validates and normalizes the data
before updating `data/benchmarks.json`, which Vite bundles into the frontend.
The API pricing table uses snapshotted standard token rates from
[LiteLLM's cost map](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json)
with official OpenAI and Anthropic fallbacks for preview or restricted models.
GeneBench-Pro cost estimates use only the snapshotted output-token rates. Input
tokens, tool calls, and caching are excluded from that estimate because
GeneBench-Pro does not publish those usage values.
The GeneBench-Pro snapshot contains 33 test-time-compute scaling points and 18
max-reasoning model passrates. The scaling collection is rendered; the
max-reasoning collection is not yet visualized.

```bash
mise run data:update          # fetch and regenerate
mise run data:verify          # validate committed data without network access
mise run data:check-upstream  # report whether the source changed
mise run typecheck            # type-check the frontend
mise run typecheck:python     # type-check Python scripts and tests
mise run lint:fix             # fix supported lint violations
mise run lint:python:fix      # fix supported Python lint violations
mise run format:python        # format Python scripts and tests
mise run qa                   # type-check, build, lint, format-check, and test
mise run test                 # compatibility alias for qa
mise run browser:test         # run desktop and mobile browser assertions
```

Dependencies are managed exclusively with Aube:

```bash
aube add --save-dev --save-exact <package>
aube install --frozen-lockfile
```

GitHub Actions verifies the project, deploys `dist/` to GitHub Pages, and checks
the benchmark source weekly. Upstream data changes are proposed through an
automated pull request.
