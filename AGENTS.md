# GPT-5.6 Benchmark Visualizations

## Scope

These instructions apply to this entire project.

## Project Contract

- The project is a standalone static page with no build step or runtime
  dependencies.
- `index.html` must keep working when opened directly through a `file://` URL.
- The source data comes from:
  `https://openai.com/index/previewing-gpt-5-6-sol/`.
- Do not estimate values from chart pixels. Read the embedded Vega-Lite data
  from the source page when refreshing benchmark results.

## Code And Data Map

- `index.html` owns the markup, styles, benchmark data, rendering logic, and
  interactions.
- `groups` is the single source of truth for GeneBench v1. The metric chart,
  cost/score scatter plot, filters, and sortable table must derive from it.
- `terminalData` is the single source of truth for TerminalBench 2.1. Keep the
  source score and `reasoning` level on every entry.
- SVG nodes are rendered at runtime. Do not hand-edit generated SVG output.

## Behavioral Invariants

- GeneBench has 22 model/effort configurations.
- The GeneBench metric selector supports score, output tokens, and API cost.
- The GeneBench bar chart sorts from the lowest to the highest selected metric.
- The GeneBench table defaults to score descending and all columns remain
  sortable.
- GeneBench model filters update both GeneBench charts and the table.
- The GeneBench cost/score plot uses a logarithmic USD cost axis.
- TerminalBench has 9 models, sorts by score descending, and displays each
  source `reasoning` level.
- The TerminalBench score axis starts at 50% and ends at 100%.

## Development Rules

- Keep the page dependency-free unless a new dependency removes substantial
  complexity and still supports direct local opening.
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

There is no build command. Open `index.html` directly through a `file://` URL.

Use `browser-harness` for browser verification. At minimum, confirm:

- 22 GeneBench bars, 22 GeneBench scatter points, and 22 table rows;
- 9 TerminalBench bars;
- GeneBench selector and model filters update the expected views;
- table sorting works in both directions;
- TerminalBench ticks are 50%, 75%, and 100%;
- no incoherent label overlap on desktop;
- the page width matches the viewport on a 390px mobile viewport.

After visual changes, capture both desktop and mobile screenshots. Restore any
CDP device-metrics override after mobile verification.

## Known Risks

- Benchmark values are embedded manually and can become stale if the source
  article changes.
- Scatter-plot labels use per-point offsets; new or changed values may require
  collision adjustments.
- Browser screenshots can show transient rendering artifacts if desktop and
  mobile captures are taken immediately around the same device-metrics change.
