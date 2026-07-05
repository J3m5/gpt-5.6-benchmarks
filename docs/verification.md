# Verification

This document defines the observable behavior that changes must preserve and
the checks used to prove it.

## Required Commands

Run:

```bash
mise run test
mise run browser:test
```

`mise run test` installs locked dependencies, validates benchmark data, runs
Python and Vitest suites, checks Oxlint, Oxfmt, and Ruff, type-checks the
frontend with TypeScript and Python with ty, and builds `dist/`. It is a
compatibility alias for the canonical non-browser `mise run qa` task.

`mise run browser:test` builds the site, reuses a compatible Vite server on
port 5173 when available, and otherwise starts a temporary preview on a free
port. It then runs programmatic desktop and mobile assertions in Helium through
browser-harness. Set `BROWSER_TEST_URL` to probe another preferred server URL.

## API Pricing Contract

- The pricing table appears before the first chart and contains every model
  family rendered by GeneBench v1, GeneBench-Pro, ExploitGym, or TerminalBench:
  eleven rows in total.
- Columns are model, input, cached input, cache write, and output. Prices use
  standard processing in USD per million tokens.
- Cache-write pricing is shown for GPT-5.6 with its 30-minute minimum and for
  Claude with its 5-minute TTL. Other rows display an accessible not-applicable
  marker.
- Gemini 3.1 Pro Preview displays separate prices for requests at or below
  200K tokens and above 200K tokens. Its separately billed cache storage is
  explained outside the token-price columns.
- GPT-5.6 Sol Ultra is a distinct benchmark row but explicitly reuses the Sol
  API token rate.
- The table scrolls inside its own container on narrow viewports without
  widening the document.

## Benchmark Contracts

### GeneBench v1

- It contains 22 model/effort configurations.
- One card exposes eight accessible tabs: score versus API cost, latency, or
  output tokens; score, API-cost, latency, or output-token bar rankings; and
  the data table. It defaults to score versus API cost.
- Bar rankings sort every metric ascending.
- The table defaults to score descending, keeps its sort state across tab
  changes, and retains sortable columns.
- The resource/score chart switches its horizontal axis between API cost,
  latency, and output tokens and between logarithmic and linear scales. It
  defaults to logarithmic.
- One combined model/effort multi-select filters scatter, bar, and table views
  consistently and allows an empty selection.
- Its model families can be selected or cleared in one action. Family
  checkboxes expose complete, partial, and empty selection states; child rows
  show only reasoning effort and use checkbox color without a second swatch.
  Family labels use stronger typography; effort rows are indented beneath them
  with a subtle vertical guide.
- Scatter-only controls and the attractive-quadrant legend are hidden in bar
  and table views. The selector and model legend remain visible.
- Tabs support ArrowLeft, ArrowRight, Home, and End and scroll horizontally on
  narrow viewports.

### ExploitGym

- It contains 17 selectable model/effort configurations.
- The duration control is the only place where 2 h and 6 h are selected. It
  displays 17 points for 2 h and 15 points for 6 h while preserving
  multi-select state.
- GPT-5.4 and GPT-5.5 are disabled in the multi-select at 6 h because no source
  runs exist for them at that duration.
- Its model selector uses the shared selectable family hierarchy: family
  checkboxes select or clear every available effort, expose tri-state status,
  and contain indented effort-only rows without redundant swatches.
- Every resource metric supports logarithmic and linear horizontal scales. The
  chart defaults to logarithmic.

### ExploitBench

- The normalized snapshot contains 23 GPT series points across GPT-5.6 Sol,
  Terra, Luna, GPT-5.5, and GPT-5.4.
- The chart connects each model family's points in reasoning-effort order and
  preserves the exact source output-token and cap-percent values.
- Mythos Preview and Opus 4.7 appear as standalone comparison points. Mythos 5
  and Opus 4.8 appear as horizontal reference lines at 78% and 40%.
- Its grouped selector controls the 23 GPT model/effort configurations.
  Comparison points and horizontal references remain visible independently.
- Its horizontal scale defaults to logarithmic and toggles to linear without
  changing the fixed source domain or selected points.
- Point labels default to visible. Family lines default to hidden and use the
  shared contiguous-effort behavior when enabled.
- Pareto mode filters the selected GPT configurations together with the two
  comparison points while retaining both horizontal references. With every
  configuration selected, the frontier contains eight points.
- Every visible point symbol remains keyboard focusable, has an accessible
  name, and exposes output tokens and cap percent through the shared tooltip.
- The fixed 900 px chart scrolls inside its container on narrow viewports
  without widening the document.

### TerminalBench 2.1

- It contains 9 models, sorted by score descending.
- Every source reasoning level is displayed.
- The score axis runs from 50% to 100%, with ticks at 50%, 75%, and 100%.

### GeneBench-Pro

- The normalized snapshot contains 33 test-time-compute scaling points across
  GPT-5.2, GPT-5.4, GPT-5.5, and the three GPT-5.6 variants.
- GPT-5.2, GPT-5.4, and GPT-5.5 each contain five reasoning levels; GPT-5.6
  Luna, Terra, and Sol each contain six, including `max`.
- The max-reasoning collection contains 18 models: six GPT, six GPT Pro, and
  six other models.
- Passrate fractions and percentages must agree exactly within floating-point
  tolerance.
- The scaling chart renders all 33 points with "Tokens used" on a logarithmic
  horizontal axis by default and passrate on the vertical axis.
- Its horizontal metric selector switches between tokens used and estimated
  API cost. The cost uses generated output tokens only and the snapshotted
  rates: GPT-5.2 $14, GPT-5.4 $15, GPT-5.5 $30, GPT-5.6 Luna $6, Terra $15,
  and Sol $30 per million output tokens.
- Its scale toggle switches between the default strictly positive logarithmic
  domain and a linear domain for either metric without changing the active
  points.
- Its model/reasoning multi-select and Pareto toggle recalculate both axis
  domains from the visible points. All visible points retain persistent labels;
  collisions are accepted because the source's linear domain concentrates most
  configurations near the origin.
- Its model selector uses the same selectable family hierarchy as GeneBench v1:
  prominent family rows and indented, effort-only child rows without swatches.
- Pareto mode treats token differences below 2% as equivalent. Consequently,
  GPT-5.6 Sol / low dominates GPT-5.6 Terra / low: it uses 1.651% more tokens
  but gains 7.916 passrate points.
- The max-reasoning collection remains data-only.

## Shared Scatter Behavior

- Pareto dominance is calculated from the active model, duration, and resource
  selection. By default, a point is removed only when another active point has
  both a strictly higher score and a strictly lower active resource value.
  Benchmark-specific resource tolerance may treat a small resource difference
  as equivalent; GeneBench-Pro uses 2%.
- Pareto mode hides 0% scores; normal mode retains them.
- Resource and score domains are recalculated from currently visible points.
  Every resource axis supports linear and logarithmic scales. All resource
  scatter plots default to logarithmic. Linear resource axes stop at the first
  rounded tick that covers the highest visible value.
- Every resource scatter plot shows point labels by default and provides a
  toggle that removes only the visible label text. Points, accessible names,
  domains, and chart dimensions remain unchanged.
- Every resource scatter plot provides a `Family lines` toggle that is off by
  default and independent from point labels. Enabled lines connect only
  consecutive currently visible efforts in
  `none -> low -> medium -> high -> xhigh -> max` order. Selection and duration
  gaps split a family into separate runs. Pareto mode bridges efforts removed
  by dominance when all intermediate efforts remain selected; GeneBench v1
  therefore connects GPT-5.6 Terra / low directly to Terra / max. Singleton
  runs and unknown efforts do not produce lines.
- Family lines use their family color, are rendered behind points, and are
  decorative rather than keyboard or pointer targets.
- The plot is split at its visual midpoint: the upper-left quadrant is light
  green and the lower-right quadrant is light gray.

## Visual And Interaction Contracts

- Preserve keyboard focus, ARIA labels, SVG titles and descriptions, and
  tooltip content.
- Keep the document within the viewport width. Wide charts and tables may
  scroll inside their containers on mobile.
- Keep chart dimensions stable when labels, filters, and values change.
- Native axis selects and model multi-select triggers share height, border,
  background, typography, focus treatment, and chevron styling.
- Model multi-select triggers use the compact `selected / available models`
  summary, retain a visually hidden accessible label, and open a panel matching
  the trigger width.
- Scatter labels are regular weight, horizontally aligned, and placed to the
  right of points by default. Vertical offsets are targeted collision
  exceptions.
- Secondary grid lines remain thinner and lighter than axis reference lines.

## Automated Browser Assertions

`tests/browser_verify.py` currently verifies:

- the API pricing table's position, headers, exact eleven-model coverage,
  representative OpenAI, Anthropic, and Gemini values, source links, cache
  applicability, long-context tiers, and mobile containment;
- all eight GeneBench tabs, keyboard tab navigation, contextual controls,
  metric-specific scatter and bar rendering, shared configuration selection,
  and persistent table sorting;
- 33 GeneBench-Pro scaling points on linear and logarithmic tokens-used and
  estimated-cost axes;
- 17 ExploitGym points in 2 h mode and 15 in 6 h mode;
- ExploitBench grouped selection, logarithmic/linear scale switching, point
  labels, five correctly positioned optional family lines, eight-point Pareto
  filtering, two comparison points, and two persistent horizontal references;
- 9 TerminalBench bars;
- all resource axes and both ExploitGym durations;
- point-label toggles on all three resource scatter plots, including preserved
  point counts, accessible names, and domains;
- family-line toggles on all three resource scatter plots, including default
  state, counts, colors, effort order, exact point-center geometry, rendering
  order, gap splitting, label-toggle independence, and preserved chart state;
- family-line recalculation across metrics, linear/log scales, configuration filters,
  Pareto mode, and both ExploitGym durations, including the GeneBench v1
  Terra / low to Terra / max Pareto segment;
- linear/logarithmic switching for every GeneBench v1 and ExploitGym resource
  metric;
- GeneBench-Pro model/reasoning selection, Pareto filtering, dynamic domains,
  scale switching, increased low-token separation in log mode, and persistent
  right-aligned point labels;
- GeneBench-Pro selectable families and hierarchical selector presentation;
- GeneBench-Pro estimated-cost methodology note, point accessibility labels,
  unit pricing, and calculated cost tooltip content;
- GeneBench-Pro Pareto mode contains seven points, excludes Terra / low, and
  retains Sol / low;
- quadrant geometry, point-label placement, and grid styling;
- visual parity and containment of axis-select and model-select triggers;
- GeneBench v1 family selection shared across scatter, bar, and table views,
  tri-state updates, effort-only labels, hierarchical typography and
  indentation, and removal of redundant item swatches;
- ExploitGym family selection, hierarchy presentation, tri-state updates, and
  duration-aware family availability;
- no incoherent point-label collisions on desktop for the GeneBench v1 and
  ExploitGym scatter plots in their default logarithmic mode; collisions are
  accepted in optional linear mode while label count and right-side placement
  remain enforced;
- document width equal to the viewport at 390 px.

When a change affects tabs, configuration selection, Pareto mode, or
table sorting, add focused assertions or verify those interactions
programmatically before finishing.

Prefer DOM state, rendered data, accessibility attributes, dimensions,
overflow, and element geometry over screenshots. Use screenshots only when
they add evidence that assertions cannot provide.

Browser verification must run outside the sandbox so it can access Helium's
CDP session. Restore every CDP device-metrics override after mobile checks.
Screenshots taken immediately around a metrics override may contain transient
rendering artifacts.
