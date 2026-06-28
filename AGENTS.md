# GPT-5.6 Benchmark Visualizations

## Scope

These instructions apply to this entire project.

## Project Contract

- The project is a standalone static page with no build step or runtime
  dependencies.
- `index.html` must keep working when opened directly through a `file://` URL.
- The source data comes from:
  `https://openai.com/index/previewing-gpt-5-6-sol/`.
- Do not estimate values from chart pixels. Refresh benchmark results with
  `mise run data:update`, which reads the embedded Vega-Lite data.

## Code And Data Map

- `index.html` owns the markup, styles, rendering logic, and interactions.
- `data/raw/openai-vega-specs.json` is the auditable snapshot of the three
  source Vega-Lite specifications.
- `data/benchmarks.json` is the normalized source of truth.
- `data/benchmarks.generated.js` is generated from the normalized data and is
  loaded by `index.html` so the page remains compatible with `file://`.
- `scripts/update_benchmarks.py` owns fetching, React Flight decoding,
  validation, normalization, and deterministic generation.
- `groups`, `exploitGymRuns`, and `terminalData` are UI projections of
  `window.BENCHMARK_DATA`; do not place source values back in `index.html`.
- `createCostScoreChart` owns the shared multi-select, Pareto calculation,
  axes, tooltips, and SVG rendering for GeneBench and ExploitGym.
- SVG nodes are rendered at runtime. Do not hand-edit generated SVG output.

## Behavioral Invariants

- GeneBench has 22 model/effort configurations.
- The GeneBench metric selector supports score, output tokens, and API cost.
- The GeneBench bar chart sorts from the lowest to the highest selected metric.
- The GeneBench table defaults to score descending and all columns remain
  sortable.
- GeneBench model filters update both GeneBench charts and the table.
- The GeneBench cost/score plot uses a logarithmic USD cost axis.
- The GeneBench cost/score plot has a combined model/effort multi-select that
  refines the globally visible models and allows an empty selection.
- Its Pareto mode is calculated from the active selection and keeps a point
  unless another active point has both a strictly higher score and a strictly
  lower cost.
- ExploitGym has 17 selectable model/effort configurations. Its duration
  control is the only place where 2 h and 6 h are selected; it shows 17 points
  for 2 h or 15 points for 6 h while preserving multi-select state.
- GPT-5.4 and GPT-5.5 are unavailable and disabled in the ExploitGym
  multi-select while 6 h is active because the source has no 6 h runs for them.
- ExploitGym Pareto mode is calculated only from the selected configurations
  in the active duration.
- Both cost/score charts hide points with a 0% score while Pareto mode is
  active, but retain them in the normal view.
- Both cost/score charts recalculate their logarithmic cost domain and linear
  score domain from the points currently visible after model, duration, and
  Pareto filtering.
- TerminalBench has 9 models, sorts by score descending, and displays each
  source `reasoning` level.
- The TerminalBench score axis starts at 50% and ends at 100%.

## Development Rules

- Keep the page dependency-free unless a new dependency removes substantial
  complexity and still supports direct local opening.
- Do not edit files under `data/` manually. Run `mise run data:update`; use
  `mise run data:verify` for an offline consistency check.
- Identify Vega specifications by their semantic title, not by script position
  or React Flight record identifier.
- Keep data generation deterministic. Retrieval timestamps and unrelated HTML
  metadata must not create diffs when benchmark data is unchanged.
- Preserve keyboard focus, ARIA labels, SVG titles/descriptions, and tooltip
  content when changing chart interactions.
- Keep the document itself within the viewport width. Wide charts and tables
  may scroll inside their own containers on mobile.
- Use stable dimensions for charts so labels, filters, and dynamic values do
  not resize the surrounding layout.
- When adding a benchmark, keep its raw data in one explicit collection and
  render every related view from that collection.
- Update labels and collision offsets after data changes; point labels are
  intentionally positioned separately from their exact coordinates.

## Verification

Run `mise run test`, then open `index.html` directly through a `file://` URL.

Use `browser-harness` for browser verification. At minimum, confirm:

- 22 GeneBench bars, 22 GeneBench scatter points, and 22 table rows;
- 17 ExploitGym points in 2 h mode and 15 in 6 h mode;
- 9 TerminalBench bars;
- GeneBench selector and model filters update the expected views;
- table sorting works in both directions;
- TerminalBench ticks are 50%, 75%, and 100%;
- no incoherent label overlap on desktop;
- the page width matches the viewport on a 390px mobile viewport.

Prefer programmatic assertions over screenshots and image analysis. Verify DOM
counts, control state, rendered data, accessibility attributes, dimensions,
overflow, and element geometry first. Use screenshots only as supplemental
evidence when visual composition cannot be established reliably from those
checks.

After visual changes, verify desktop and mobile behavior programmatically.
Capture screenshots only when they add information beyond the assertions.
Restore any CDP device-metrics override after mobile verification.

## Known Risks

- The upstream React Flight or Vega-Lite structure can change. The extractor
  must fail without replacing committed artifacts when required data is
  missing or inconsistent.
- The source rejects underspecified HTTP clients. Keep browser-compatible
  request headers in the extractor and treat repeated HTTP failures as an
  upstream integration issue.
- The scheduled update proposes changes but does not merge them automatically.
- Scatter-plot labels use per-point offsets; new or changed values may require
  collision adjustments.
- Browser screenshots can show transient rendering artifacts if desktop and
  mobile captures are taken immediately around the same device-metrics change.
