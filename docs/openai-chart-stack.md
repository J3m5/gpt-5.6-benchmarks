# OpenAI Chart Stack

OpenAI's GPT-5.6 benchmark articles publish chart data as Vega-Lite
specifications and render it through a custom React chart layer built on the
official Vega libraries. This document records the upstream implementation
observed on July 3, 2026; package versions and internal components may change
with any OpenAI deployment.

## Observed Stack

```text
Next.js and React Flight content
  -> OpenAI DotcomChart component
  -> Vega-Lite 6.4.2 compilation and OpenAI chart transformations
  -> Vega 6.2.0 specification
  -> react-vega VegaEmbed component
  -> vega-embed and vega-tooltip
  -> SVG
```

The same stack was observed on:

- [Previewing GPT-5.6 Sol](https://openai.com/index/previewing-gpt-5-6-sol/)
- [Introducing GeneBench-Pro](https://openai.com/index/introducing-genebench-pro/)

GeneBench-Pro charts are loaded lazily when they approach the viewport. A DOM
inspection performed before scrolling will therefore not find their Vega
elements.

## Confirmed Evidence

The article's inline React Flight payload contains objects named
`vegaLiteSpec`. Their `$schema` is
`https://vega.github.io/schema/vega-lite/v6.json`, and their semantic titles
identify charts such as GeneBench v1, ExploitGym, and the two GeneBench-Pro
views. ExploitBench is a layered specification: its series, standalone
comparison points, labels, and horizontal references use separate Vega-Lite
layers.

The dynamically loaded chart bundle contains:

- explicit runtime versions `vega: "6.2.0"` and `vegaLite: "6.4.2"`;
- an OpenAI chart capability version of `1.3.0`;
- the official `vega-embed` stylesheet and its `vega-embed-style` identifier;
- the `vega-tooltip` implementation;
- the `react-vega` error prefix and `VegaEmbed` implementation.

React Fiber inspection identifies the rendering component as `VegaEmbed`. Its
props are `spec`, `options`, `onEmbed`, `onError`, and standard `div` props,
matching the public [`react-vega` API](https://github.com/vega/react-vega).
The implementation follows the v8 API. It is likely `react-vega` 8.0.0, but the
exact package metadata is stripped from the production bundle, so the patch
version is not independently confirmed.

The `VegaEmbed` component receives a compiled Vega specification using
`https://vega.github.io/schema/vega/v6.json`, rather than the original
Vega-Lite specification. This confirms that OpenAI's chart layer performs
compilation and transformations before the final embed call.

The resulting DOM contains:

- `div.vega-embed.fit-x.fit-y`;
- `style#vega-embed-style`;
- `form.vega-bindings` when the specification exposes bound parameters;
- `svg.marks` as the rendered chart;
- `role="graphics-document"` and
  `aria-roledescription="visualization"`.

No canvas renderer or Vega global is exposed. Vega, Vega-Lite, and the embed
utilities are bundled into private Next.js chunks. Those chunks did not expose
source maps during the inspection.

## OpenAI's Chart Layer

The bundle calls the integration `DotcomChart`. It accepts content records
containing a `vegaLiteSpec` and optional `dotcomConfig`, then applies OpenAI
presentation and interaction behavior before rendering.

Observed responsibilities include:

- OpenAI chart themes, color tokens, patterns, and typography;
- responsive sizing, minimum dimensions, and horizontal scrolling;
- chart filters backed by Vega parameters;
- custom tooltip and logger configuration;
- optional draw and fade motion cues;
- a custom chart menu and SVG/PNG download actions;
- title, label, and accessibility handling.

OpenAI disables the default Vega-Embed action menu and forces SVG rendering:

```text
actions: false
renderer: "svg"
tooltip: <OpenAI handler>
```

The custom menu therefore belongs to `DotcomChart`, not to Vega-Embed's
standard action UI. Vega-Embed still owns specification embedding, Vega view
lifecycle, generated styles, and tooltip integration. See the official
[Vega-Embed documentation](https://vega.github.io/vega-embed/) for that lower
layer.

## Confidence And Limits

| Finding                              | Confidence      | Basis                                      |
| ------------------------------------ | --------------- | ------------------------------------------ |
| Vega 6.2.0                           | Confirmed       | Explicit bundle runtime version            |
| Vega-Lite 6.4.2                      | Confirmed       | Explicit bundle runtime version            |
| Vega-Embed                           | Confirmed       | Bundle implementation, stylesheet, and DOM |
| Vega Tooltip                         | Confirmed       | Bundle implementation                      |
| React-Vega v8 API                    | Confirmed       | Fiber component and bundled implementation |
| React-Vega 8.0.0                     | High, not exact | v8 implementation; package metadata absent |
| Exact Vega-Embed package version     | Unknown         | Version metadata absent                    |
| `DotcomChart` internal API stability | Not guaranteed  | Private OpenAI component                   |

Minified function names such as `jR` or `jX` are deployment artifacts and
should not be used as durable identifiers. `DotcomChart`, `vegaLiteSpec`,
semantic chart titles, schemas, and DOM signatures are more useful diagnostic
signals.

## Reproducing The Inspection

Use Browser Harness against the live OpenAI article:

1. Open the article in a new tab and wait for page load.
2. Scroll each target chart into the viewport to trigger lazy loading.
3. Check for `.vega-embed`, `#vega-embed-style`, `.vega-bindings`, and
   `svg.marks`.
4. Find the element property beginning with `__reactFiber$` and walk its
   `return` chain. The immediate React component above the embed `div` should
   be `VegaEmbed`.
5. Inspect `VegaEmbed`'s memoized props. The observed options use SVG, disable
   default actions, and provide a custom tooltip handler.
6. Fetch same-origin URLs from `performance.getEntriesByType("resource")` and
   search the JavaScript chunks for `vega-embed`, `vega-tooltip`,
   `[react-vega]`, `vegaLiteSpec`, and `runtimeVersions`.
7. Compare the inline React Flight schema with the final `VegaEmbed` spec:
   the former is Vega-Lite v6 and the latter is compiled Vega v6.

Chunk names and deployment query parameters are content-addressed and will
change. Discover them from the current page rather than persisting them.

## Project Implications

This project does not use Vega at runtime. The extractor reads the upstream
Vega-Lite specifications from React Flight, validates them by semantic title,
and normalizes their data into `data/benchmarks.json`. The frontend then
renders its own SVG charts with strict TypeScript.

The upstream stack explains why the source contains complete, auditable data
instead of only chart pixels. It does not require adding Vega dependencies to
this project. A runtime migration to Vega should be evaluated separately
against bundle size, interaction requirements, accessibility, and the existing
custom scatter behavior.

The main maintenance risk is an OpenAI content or chart-layer migration:

- React Flight serialization may change;
- `vegaLiteSpec` or `dotcomConfig` may be renamed;
- Vega schema versions may advance;
- chart titles or specification structure may change.

The extractor should continue failing atomically when required semantic charts
or fields are missing. Refresh benchmark data only through
`mise run data:update`.
