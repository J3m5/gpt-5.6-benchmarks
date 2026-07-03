# Architecture

The project builds a static benchmark visualization site from auditable
snapshots of Vega-Lite data embedded in OpenAI's GPT-5.6 Sol and GeneBench-Pro
articles, plus a snapshot of standard API token pricing for every model rendered
by the site.
The observed upstream rendering implementation is documented in
[OpenAI Chart Stack](openai-chart-stack.md).

## Frontend

- `index.html` contains the static document structure and Vite entry points.
- `src/styles.css` owns page and chart styling.
- `src/main.ts` only assembles controllers and coordinates cross-domain
  updates.
- `src/data.ts` imports normalized benchmark data and builds the UI-facing
  projections.
- `src/types.ts` contains contracts shared by multiple domains.
- `src/chart-math.ts` contains pure scale and Pareto calculations.
- `src/chart-series.ts` owns canonical reasoning-effort ordering and pure
  contiguous family-series construction.
- `src/api-cost.ts` contains the pure output-token cost calculation.
- `src/charts/` owns SVG rendering. Benchmark-specific resource chart wrappers
  configure the shared `resource-score.ts` renderer.
- `src/controls/` owns model and duration input handling.
- `src/table/` owns the sortable GeneBench table.
- `src/table/api-pricing-table.ts` renders the non-sortable API pricing table
  from the normalized pricing snapshot.
- `src/ui/` owns stateful shared UI services such as the tooltip.
- `src/utils/` contains stateless DOM/SVG and formatting primitives.
- `data/benchmarks.json` is imported directly by Vite and bundled into the
  production JavaScript.

`createResourceScoreChart` is the shared implementation for the GeneBench,
GeneBench-Pro scaling, and ExploitGym resource/score charts. It owns resource
selection, linear or logarithmic axes, Pareto filtering, dynamic domains, point
tooltips, point-label visibility, optional family lines, and SVG rendering.
Every resource scatter wrapper supplies linear/log, point-label, and family-line
toggles plus scale-specific empty-selection fallbacks. All three resource
scatter plots default to logarithmic with labels visible and family lines
hidden. GeneBench-Pro keeps its source's linear scale available through the
toggle and fixes the shared `tokens` metric label to "Tokens used". Its
horizontal metric selector also exposes an estimated API cost derived from
generated output tokens and snapshotted per-model output rates. It configures a
2% resource tolerance for Pareto dominance; the shared default remains strict.
Persistent labels retain the shared right-of-point placement even though linear
domains can make some label and point collisions unavoidable. The renderer
delegates configuration selection state, panel positioning, and keyboard
dismissal to `controls/configuration-select.ts`. Runtime-generated SVG must not
be edited manually.

Family lines are built after model, duration, and Pareto filtering. Outside
Pareto mode, they connect only consecutive visible efforts in the canonical
`none -> low -> medium -> high -> xhigh -> max` order; efforts absent from the
active selection split a family into separate runs. Pareto mode may bridge
efforts removed by dominance when every intermediate effort was still selected.
This preserves the frontier trajectory without hiding manual selection gaps.
Unknown efforts remain visible as points but do not participate in lines.
Positioned points are calculated once per render and shared by polylines,
symbols, and labels.

Native single-selects and model multi-selects keep distinct interaction
semantics but share the `control-trigger` visual shell in `src/styles.css`.
The `select-trigger` wrapper supplies the same border, typography, focus
treatment, and chevron as `multi-select-trigger`.
The shared configuration selector optionally exposes tri-state family
checkboxes. GeneBench v1 and GeneBench-Pro enable them, use effort-only item
labels, and omit redundant item swatches; ExploitGym retains its existing
grouped list. Triggers use the compact `selected / available models/efforts`
summary while retaining a visually hidden accessible label.

## Module Boundaries

Domain modules own their DOM queries, event listeners, rendering, and
domain-local types. They expose small controllers such as `render`, `resize`,
or `refreshVisibility`; `main.ts` coordinates those controllers without
reaching into their DOM.

`src/types.ts` is intentionally a single file because only a small set of data
contracts crosses domain boundaries. Keep a type beside its owning module until
multiple domains need it. Introduce a `types/` directory only if the shared
contracts grow into distinct cohesive groups.

`src/utils/` is not a home for business logic. Add functions there only when
they are stateless, domain-independent, and reused. Stateful behavior belongs
under `ui/`, `controls/`, `charts/`, or `table/`.

## Data Flow

`scripts/update_benchmarks.py` fetches both source articles, decodes their React
Flight payloads, identifies Vega-Lite specifications by semantic title,
validates them, and writes deterministic artifacts atomically:

- `data/raw/openai-vega-specs.json` contains the GPT-5.6 Sol preview specs.
- `data/raw/openai-genebench-pro-vega-specs.json` contains both GeneBench-Pro
  specs.
- `data/raw/api-pricing.json` contains standard input, cached-input, optional
  cache-write, and output-token rates for the eleven rendered model families,
  plus Gemini's long-context tier, source mapping, and a hash limited to the
  consumed LiteLLM entries.
- `data/benchmarks.json` is the normalized source of truth consumed by the UI.

`src/data.ts` exposes the grouped GeneBench data, GeneBench-Pro scaling points,
other scatter points, and TerminalBench rows required by the rendering domains.
These are projections of the normalized JSON; benchmark values must remain in
the data files rather than being duplicated in HTML or TypeScript. The
normalized `geneBenchProMaxReasoning` collection is extracted and verified but
does not yet have a frontend projection.

API pricing extraction reads LiteLLM's public cost map for GPT-5.2, GPT-5.4,
GPT-5.5, Claude Fable 5, Claude Opus 4.8, and Gemini 3.1 Pro Preview. GPT-5.6
rates and cache terms are extracted from OpenAI's preview article. Claude
Mythos 5 pricing is validated against Anthropic's launch article and prompt
caching terms. GPT-5.6 Sol Ultra reuses the Sol API rate because it is a
reasoning configuration, not a separately priced API model. Gemini retains its
separate rates above 200K request tokens.

The GeneBench-Pro cost estimate still covers only `meanNonmaskedSollen`, the
available generated-token measure; it excludes input tokens, tools, and
caching. Pricing is snapshotted during `data:update`, never fetched by the
application.

## Tooling

- `mise.toml` pins Node LTS, Aube, Python, Ruff, and ty and exposes project
  tasks.
- `package.json` and `aube-lock.yaml` own exact frontend dependencies.
- `pyproject.toml` configures Ruff linting/formatting and ty type-checking for
  `scripts/` and `tests/`. The browser verification script allows its
  `browser_harness` import because that module is supplied by the
  browser-harness runtime rather than the project Python environment.
- `mise run qa` is the canonical non-browser quality suite; `mise run test`
  remains its compatibility alias. It checks both TypeScript and Python.
  Dedicated `*:python` tasks expose Ruff and ty independently, while
  `typecheck` and `lint:fix` delegate to matching Aube package scripts.
- TypeScript is strict and targets browser APIs.
- Oxlint runs type-aware rules through `oxlint-tsgolint`.
- Oxfmt formats supported project files.
- Ruff lints and formats Python; ty type-checks it against Python 3.12.
- Vitest covers frontend logic; Python's unittest suite covers extraction and
  normalization.

## Deployment

Vite emits the standalone site under `dist/` with relative asset paths. The
GitHub Pages workflow deploys that directory. Pages must use the GitHub Actions
deployment source; legacy deployment from the repository root would serve
uncompiled TypeScript.

## Change Guidance

- Put reusable calculations in a pure module and cover them with Vitest.
- When adding a benchmark, keep its raw data in one explicit collection and
  render every related view from that collection.
- Refresh source values only with `mise run data:update`.
- Preserve deterministic generation: retrieval timestamps and unrelated source
  metadata must not produce data diffs.

## Known Weak Points

- Upstream React Flight or Vega-Lite structures may change. Extraction must
  fail without replacing committed artifacts when required data is missing or
  inconsistent.
- GeneBench-Pro scaling titles can be encoded as a one-item title array, while
  other charts use string or object titles. All forms remain matched by their
  resolved semantic title.
- The source rejects underspecified HTTP clients, so the extractor requires
  browser-compatible request headers.
- LiteLLM may add GPT-5.6 or change its cost-map schema. Until every rendered
  model has a reliable direct entry, the OpenAI and Anthropic fallbacks and
  exact chart-model coverage validation must remain.
- Scatter labels use targeted per-point offsets and may need adjustment when
  source values change.
- The browser regression script covers counts, resource and duration switching,
  chart geometry, labels, family-line interactions, grids, selector filtering,
  Pareto behavior, and mobile overflow. Table sorting still requires
  change-specific verification.
- The scheduled update proposes changes through a pull request and does not
  merge them automatically.
