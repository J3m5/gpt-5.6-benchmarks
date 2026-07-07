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
- `src/charts/` owns chart rendering. Every chart prepares an explicit Plot
  model and renders it through the generic core under `src/charts/plot/`.
  Benchmark controllers retain their source-specific selection and toggles.
- `src/gene-bench/workspace.ts` owns the unified GeneBench tab state and
  coordinates its scatter, bar, and table renderers.
- `src/gene-bench-pro/workspace.ts` owns the equivalent six-view
  GeneBench-Pro workspace.
- `src/exploit-gym/workspace.ts` owns the eight-view, duration-aware
  ExploitGym workspace. The tabbed workspaces share the accessible tab-list
  controller under `src/workspace/`.
- `src/exploit-bench/workspace.ts` owns the four-view ExploitBench workspace.
  It reuses the grouped scatter selection across the scatter, bar, and table
  views.
- `src/terminal-bench/workspace.ts` owns the two-view TerminalBench card.
- `src/controls/` owns reusable configuration and duration input handling.
- `src/table/` owns the sortable benchmark tables and their shared sorting
  controller.
- `src/table/api-pricing-table.ts` renders the non-sortable API pricing table
  from the normalized pricing snapshot.
- `src/utils/` contains stateless DOM and formatting primitives.
- `data/benchmarks.json` is imported directly by Vite and bundled into the
  production JavaScript.

GeneBench v1 uses Observable Plot 0.6.17 for all three scatter and four bar
views; GeneBench-Pro, ExploitGym, and ExploitBench use it for their scatters
and bar rankings, while TerminalBench uses it for vertical bars. Shared pure
scatter preparation keeps explicit source domains, optional quadrants, Pareto
points, family runs, reference annotations, and pixel label offsets, but lets
Plot infer standard ticks whenever visible data exists. Linear resource axes
pass a small numeric tick budget to keep Plot's grid and axis labels
synchronized; logarithmic resource axes keep explicit major ticks because D3
log scales can generate unlabeled intermediate tick positions. Percentage axes
pass a numeric interval so score and passrate ticks remain on stable
5/10/20-point steps. Empty-selection and source-fixed axes keep explicit
fallback ticks. Bar preparation keeps the
sorted items, labels, and values explicit but lets Plot infer standard
value-axis domains and ticks with zero and nice enabled. TerminalBench remains
explicit because its score axis is part of the benchmark contract. The generic
renderers own only SVG construction and delegate selection and toggles to
benchmark controllers, while the GeneBench workspace continues to own active
tabs.
Quadrants, grids, axes, family lines, symbols, labels, bars, and pointer tips
use Plot's native marks and options. Point and bar marks expose per-datum ARIA
labels but are not keyboard targets. Plot's pointer transform owns tip
selection and click-to-stick behavior; tip content is plain text rather than
application HTML. The renderer does not inspect Plot's generated children or
private data. The HTML data table remains independent of Plot.

GeneBench-Pro exposes six mutually exclusive views in one card: passrate versus
tokens or estimated cost, passrate/token/cost vertical bar rankings, and a
sortable data table. Its scatter definition supplies the two resource metrics,
scale fallbacks, passrate axis, tooltip, and 2% Pareto resource tolerance before
delegating to the shared renderer. The grouped selection is owned by the
scatter controller and shared by every view. Scatter controls and the quadrant
legend are contextual; the model legend and selection remain visible. Bar
rankings are ascending, while the table defaults to passrate descending and
retains its sort state. Persistent scatter labels remain right-aligned and
collisions on concentrated linear domains are accepted.

The tabbed workspaces reserve a first full metadata row for selectors and
contextual controls and a more spacious second row for the quadrant and model
legend. Legend items stay horizontal and scroll inside their row on narrow
viewports.

ExploitGym exposes eight views matching GeneBench v1: three resource scatters,
four ascending vertical bar rankings, and a sortable table. Its scatter defines
the three resource metrics, duration-specific label offsets, and
intended-exploit-rate axis before delegating to the shared model and renderer.
The model selector and 2 h/6 h duration control are shared by every view, while
scatter toggles and the quadrant legend remain contextual. Selection IDs are
independent of duration so switching limits preserves selection while
recalculating availability and every active view.

TerminalBench exposes two views in one card: the vertical score ranking and a
sortable data table. Its chart delegates to the shared Plot bar renderer. Its
model fixes the score domain to 50–100%, supplies the three source ticks, sorts
scores descending, and includes each source reasoning level in the category,
accessible label, and native tip.

The GeneBench workspace presents eight mutually exclusive views in one card:
three score/resource scatters, four single-metric bar rankings, and the data
table. Its resource chart owns the shared set of 22 selected configuration IDs;
the bar and table renderers consume the same read-only set. Tab changes select
the scatter metric through the renderer API rather than through a hidden DOM
control. Scatter-only controls and the attractive-quadrant legend are hidden in
bar and table views. Bar rankings use ascending order for every metric, while
table sort state persists across view changes.

Plot SVGs replace the previous SVG in a persistent scroll container on every
render, matching Plot's documented full-rerender interaction model. Controls
and tabs retain their own keyboard behavior, while data marks and tips are
pointer-driven.

Family lines are built after model, duration, and Pareto filtering. Outside
Pareto mode, they connect only consecutive visible efforts in the canonical
`none -> low -> medium -> high -> xhigh -> max` order; efforts absent from the
active selection split a family into separate runs. Pareto mode may bridge
efforts removed by dominance when every intermediate effort was still selected.
This preserves the frontier trajectory without hiding manual selection gaps.
Unknown efforts remain visible as points but do not participate in lines.
The pure model supplies the same abstract coordinates to native Plot line,
symbol, and text marks.

ExploitBench exposes four views in one card: cap percent versus output tokens,
cap-percent and output-token vertical bar rankings, and a sortable table. Its
source-specific scatter model delegates to the shared Plot scatter renderer
with quadrants disabled. Its model fixes both domains, prepares five GPT effort
series, two standalone comparison points, two partial horizontal reference
rules, Pareto filtering, and contiguous family lines. The bar rankings include
the selected GPT series points plus the two persistent comparison points. The
table includes selected GPT series rows, comparison points, and the horizontal
reference rows. Its normalizer locates Vega layers by mark type and validates
their field contracts instead of depending on layer position. The frontend
renders 23 selectable GPT series points, two persistent comparison points, and
two persistent reference lines.

Native single-selects and model multi-selects keep distinct interaction
semantics but share the `control-trigger` visual shell in `src/styles.css`.
The `select-trigger` wrapper supplies the same border, typography, focus
treatment, and chevron as `multi-select-trigger`.
The shared configuration selector optionally exposes tri-state family
checkboxes. GeneBench v1, GeneBench-Pro, ExploitBench, and ExploitGym enable
them, use effort-only item labels, and omit redundant item swatches.
ExploitGym derives family availability from the active duration, disabling
families without runs. Triggers use the compact `selected / available models`
summary while retaining a visually hidden accessible label. The selection
panel matches its trigger width.

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

`src/data.ts` exposes the grouped GeneBench data, the layered ExploitBench
series and references, GeneBench-Pro scaling points, other scatter points, and
TerminalBench rows required by the rendering domains. These are projections of
the normalized JSON; benchmark values must remain in the data files rather than
being duplicated in HTML or TypeScript. The normalized
`geneBenchProMaxReasoning` collection is extracted and verified but does not
yet have a frontend projection.

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
- Fallow 3.2.0 is an exact development dependency. Run its project-local
  binary with `aube run fallow -- <command>`. The matching agent skill under
  `.agents/skills/fallow` is vendored from `fallow-rs/fallow-skills` commit
  `c5bf09bbc789b8145a8e3d7a9bf7cae424f7d17c`.
- `pyproject.toml` configures Ruff linting/formatting and ty type-checking for
  `scripts/` and `tests/`. The browser verification script allows its
  `browser_harness` import because that module is supplied by the
  browser-harness runtime rather than the project Python environment.
- `mise run qa` is the canonical non-browser quality suite; `mise run test`
  remains its compatibility alias. It checks both TypeScript and Python.
  Dedicated `*:python` tasks expose Ruff and ty independently, while
  `typecheck` and `lint:fix` delegate to matching Aube package scripts.
- TypeScript is strict and targets browser APIs.
- Observable Plot and the matching D3 declaration package are exact runtime
  and development dependencies, respectively. Keep `@types/d3` aligned with
  D3's major version when upgrading Plot.
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
- Migrating GeneBench v1 to Plot increased the production JavaScript from
  19.99 kB to 109.46 kB gzip (80.58 kB to 339.22 kB raw). Migrating
  the remaining charts, adding the GeneBench-Pro workspace, and adopting native
  Plot tips brings the bundle to about 111.22 kB gzip (356.96 kB raw) after the
  ExploitGym workspace is added. Plot makes no runtime network requests;
  further chart work should continue using the shared renderer.
- The browser regression script covers counts, resource and duration switching,
  chart geometry, labels, family-line interactions, grids, selector filtering,
  Pareto behavior, and mobile overflow. Table sorting still requires
  change-specific verification.
- The scheduled update proposes changes through a pull request and does not
  merge them automatically.
