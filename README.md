# GPT-5.6 Benchmark Visualizations

Interactive, dependency-free visualizations of the GeneBench v1, ExploitGym,
and TerminalBench 2.1 results published in OpenAI's
[GPT-5.6 Sol preview](https://openai.com/index/previewing-gpt-5-6-sol/).

## Live page

https://j3m5.github.io/gpt-5.6-benchmarks/

## Included views

- GeneBench v1 score, output-token, and API-cost comparison
- GeneBench v1 score versus API-cost scatter plot
- ExploitGym intended-exploit rate versus API-cost scatter plot
- Sortable GeneBench v1 data table
- TerminalBench 2.1 scores with reasoning levels

The page has no build step or runtime dependencies. Open `index.html` directly
in a browser for local use; its generated data file also supports `file://`.

## Data maintenance

Benchmark values are extracted from the Vega-Lite specifications embedded in
the source article's HTML. The extractor validates and normalizes the data
before updating the browser artifact.

```bash
mise run data:update          # fetch and regenerate
mise run data:verify          # validate committed data without network access
mise run data:check-upstream  # report whether the source changed
mise run test                 # run verification and unit tests
```

GitHub Actions verifies committed artifacts on every change and checks the
source weekly. Upstream changes are proposed through an automated pull request.
