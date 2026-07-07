import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager

from browser_harness.helpers import cdp, goto_url, js, new_tab, wait, wait_for_load

METRICS = ("cost", "latency", "tokens")
APP_MARKER = "<title>GPT-5.6 Benchmark Comparison</title>"
DEFAULT_SERVER_URLS = ("http://localhost:5173/", "http://127.0.0.1:5173/")


def find_free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def wait_for_server(port, process, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Vite preview exited with status {process.returncode}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"Vite preview did not start on port {port}")


def reusable_server_url():
    configured_url = os.environ.get("BROWSER_TEST_URL")
    candidate_urls = (configured_url,) if configured_url else DEFAULT_SERVER_URLS

    for url in candidate_urls:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                document = response.read(8192).decode("utf-8", errors="replace")
            if APP_MARKER in document:
                return url
        except (OSError, urllib.error.URLError):
            continue
    return None


@contextmanager
def app_server():
    existing_url = reusable_server_url()
    if existing_url:
        print(f"Reusing existing Vite server: {existing_url}")
        yield existing_url
        return

    port = find_free_port()
    process = subprocess.Popen(
        [
            "aube",
            "run",
            "preview",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--strictPort",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_server(port, process)
        preview_url = f"http://127.0.0.1:{port}/"
        print(f"Started temporary Vite preview: {preview_url}")
        yield preview_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def inspect_scatter(selector):
    return js(
        f"""(() => {{
          const svg = document.querySelector({selector!r});
          const svgRect = svg.getBoundingClientRect();
          const plotPoints = [...svg.querySelectorAll(
            'g.benchmark-point [aria-label]'
          )];
          const points = plotPoints.length
            ? plotPoints
            : [...svg.querySelectorAll('[data-point-id]')];
          const plotLabels = [...svg.querySelectorAll(
            'g.benchmark-point-label text'
          )];
          const labels = (
            plotLabels.length
              ? plotLabels
              : [...svg.querySelectorAll('[data-point-label]')]
          ).map((label) => {{
            const labelRect = label.getBoundingClientRect();
            const nativeId = label.getAttribute('aria-label');
            const point = plotLabels.length
              ? (() => {{
                  const segments = nativeId.split('|');
                  const effort = segments.pop();
                  if (/^\\d+h$/.test(segments.at(-1))) segments.pop();
                  const family = segments.join('|');
                  const prefix = `${{family}}, reasoning effort ${{effort}},`;
                  return points.find((candidate) =>
                    candidate.getAttribute('aria-label').startsWith(prefix)
                  );
                }})()
              : svg.querySelector(
                  `[data-point-id="${{CSS.escape(label.dataset.pointLabel)}}"]`
                );
            const style = getComputedStyle(label);
            return {{
              id: label.dataset.pointLabel || nativeId,
              label: labelRect.toJSON(),
              point: point.getBoundingClientRect().toJSON(),
              anchor: label.getAttribute('text-anchor') || style.textAnchor,
              weight: label.getAttribute('font-weight') || style.fontWeight
            }};
          }});
          const overlaps = [];
          for (let i = 0; i < labels.length; i += 1) {{
            for (let j = i + 1; j < labels.length; j += 1) {{
              const a = labels[i].label;
              const b = labels[j].label;
              const overlapX = Math.min(a.right, b.right) - Math.max(a.left, b.left);
              const overlapY = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
              if (overlapX > 2 && overlapY > 2) {{
                overlaps.push({{
                  a: labels[i].id,
                  b: labels[j].id,
                  overlapX,
                  overlapY,
                  aRect: a,
                  bRect: b
                }});
              }}
            }}
          }}
          const attractive = svg.querySelector(
            'g.benchmark-quadrant-attractive rect, [data-quadrant="attractive"]'
          );
          const opposite = svg.querySelector(
            'g.benchmark-quadrant-opposite rect, [data-quadrant="opposite"]'
          );
          const nativeGridLines = [...svg.querySelectorAll(
            'g.benchmark-grid-minor line, g.benchmark-grid-axis line'
          )];
          const gridLines = nativeGridLines.length
            ? nativeGridLines
            : [...svg.querySelectorAll('[data-grid-line]')];
          const invalidGridLines = gridLines
            .filter((line) => {{
              const owner = line.closest(
                '.benchmark-grid-axis, .benchmark-grid-minor'
              );
              const axis = owner
                ? owner.classList.contains('benchmark-grid-axis')
                : line.dataset.gridLine === 'axis';
              const source = owner || line;
              return source.getAttribute('stroke')
                  !== (axis ? '#d4d7dc' : '#eef0f2')
                || Number(source.getAttribute('stroke-width'))
                  !== (axis ? 0.9 : 0.65)
                || Number(source.getAttribute('stroke-opacity') ?? 1) !== 1;
            }})
            .length;
          const familyLineCount = svg.querySelectorAll(
            'g.benchmark-family-line, [data-family-line]'
          ).length;
          return {{
            pointCount: points.length,
            pointNames: points.map((point) => point.getAttribute('aria-label')),
            labelCount: labels.length,
            familyLineCount,
            viewBox: svg.getAttribute('viewBox'),
            renderedWidth: svgRect.width,
            renderedHeight: svgRect.height,
            quadrantCount: Number(Boolean(attractive)) + Number(Boolean(opposite)),
            attractive: {{
              x: Number(attractive.getAttribute('x')),
              y: Number(attractive.getAttribute('y')),
              width: Number(attractive.getAttribute('width')),
              height: Number(attractive.getAttribute('height')),
              fill:
                attractive.getAttribute('fill')
                || attractive.parentElement.getAttribute('fill')
            }},
            opposite: {{
              x: Number(opposite.getAttribute('x')),
              y: Number(opposite.getAttribute('y')),
              width: Number(opposite.getAttribute('width')),
              height: Number(opposite.getAttribute('height')),
              fill:
                opposite.getAttribute('fill')
                || opposite.parentElement.getAttribute('fill')
            }},
            xMin: Number(svg.dataset.xMin),
            xMax: Number(svg.dataset.xMax),
            xMetric: svg.dataset.xMetric,
            xScale: svg.dataset.xScale,
            pointLabels: svg.dataset.pointLabels,
            familyLines: svg.dataset.familyLines,
            yMin: Number(svg.dataset.yMin),
            yMax: Number(svg.dataset.yMax),
            quadrantX: Number(svg.dataset.quadrantX),
            quadrantY: Number(svg.dataset.quadrantY),
            invalidGridLines,
            overlaps,
            invalidLabels: labels
              .filter((item) =>
                item.anchor !== 'start'
                || item.weight !== '400'
                || item.label.left < item.point.right + 2
                || item.label.right > svgRect.right + 1
              )
              .map((item) => item.id)
          }};
        }})()"""
    )


def inspect_exploit_bench():
    return js(
        """(() => {
          const svg = document.querySelector('#exploitbench-chart');
          const symbols = [...svg.querySelectorAll(
            'g.benchmark-point path[aria-label]'
          )];
          const comparisons = symbols.filter((point) => {
            const label = point.getAttribute('aria-label');
            return label.startsWith('Mythos Preview,')
              || label.startsWith('Opus 4.7,');
          });
          const points = symbols.filter((point) => !comparisons.includes(point));
          const references = [...svg.querySelectorAll(
            'g.benchmark-reference-line line[aria-label]'
          )];
          const labels = [...svg.querySelectorAll(
            'g.benchmark-point-label text'
          )];
          return {
            pointCount: points.length,
            comparisonCount: comparisons.length,
            referenceCount: references.length,
            familyLineCount: svg.querySelectorAll(
              'g.benchmark-family-line'
            ).length,
            labelCount: labels.length,
            symbolCount: symbols.length,
            comparisonModels: comparisons.map(
              (point) => point.getAttribute('aria-label').split(',')[0]
            ),
            referenceModels: references.map(
              (line) => line.getAttribute('aria-label').split(',')[0]
            ),
            accessibleSymbols: symbols.every(
              (symbol) => Boolean(symbol.getAttribute('aria-label'))
            ),
            keyboardTargets: symbols.filter(
              (symbol) => symbol.tabIndex >= 0
            ).length,
            whitePointStrokes: symbols.filter(
              (symbol) => getComputedStyle(symbol).stroke === 'rgb(255, 255, 255)'
            ).length,
            referencesAreHorizontal: references.every((line) =>
              Number(line.getAttribute('x2')) > Number(line.getAttribute('x1'))
              && Number(line.getAttribute('y1')) === Number(line.getAttribute('y2'))
            ),
            quadrantCount: svg.querySelectorAll(
              'g.benchmark-quadrant-attractive, g.benchmark-quadrant-opposite'
            ).length,
            tipMarks: svg.querySelectorAll('g[aria-label="tip"]').length,
            svgCount: document.querySelectorAll(
              '#exploitbench-chart-scroll > svg'
            ).length,
            xScale: svg.dataset.xScale,
            pointLabels: svg.dataset.pointLabels,
            familyLines: svg.dataset.familyLines,
            solMax: (() => {
              const point = points.find((candidate) =>
                candidate.getAttribute('aria-label').startsWith(
                  'GPT-5.6 Sol, reasoning effort max,'
                )
              );
              return point?.getAttribute('aria-label');
            })(),
            width: svg.getBoundingClientRect().width,
            height: svg.getBoundingClientRect().height,
            containerWidth: document
              .querySelector('#exploitbench-chart-scroll')
              .getBoundingClientRect().width
          };
        })()"""
    )


def verify_exploit_bench():
    result = inspect_exploit_bench()
    assert result["pointCount"] == 23, result
    assert result["comparisonCount"] == 2, result
    assert result["referenceCount"] == 2, result
    assert result["symbolCount"] == 25, result
    assert result["labelCount"] == 25, result
    assert result["familyLineCount"] == 0, result
    assert result["xScale"] == "log", result
    assert result["pointLabels"] == "true", result
    assert result["familyLines"] == "false", result
    assert result["comparisonModels"] == ["Mythos Preview", "Opus 4.7"], result
    assert result["referenceModels"] == ["Mythos 5", "Opus 4.8"], result
    assert result["accessibleSymbols"], result
    assert result["keyboardTargets"] == 0, result
    assert result["whitePointStrokes"] == 0, result
    assert result["referencesAreHorizontal"], result
    assert result["quadrantCount"] == 0, result
    assert result["tipMarks"] == 1, result
    assert result["svgCount"] == 1, result
    assert "120,458 output tokens" in result["solMax"], result
    assert "cap percent 73.5%" in result["solMax"], result
    assert result["width"] >= result["containerWidth"], result
    assert result["height"] == 560, result

    logarithmic_distance = horizontal_point_distance(
        "#exploitbench-chart", "GPT-5.6 Sol|low", "GPT-5.6 Sol|medium"
    )
    set_checkbox("#exploitbench-log-toggle", False)
    linear = inspect_exploit_bench()
    linear_distance = horizontal_point_distance(
        "#exploitbench-chart", "GPT-5.6 Sol|low", "GPT-5.6 Sol|medium"
    )
    assert linear["xScale"] == "linear", linear
    assert linear["symbolCount"] == 25, linear
    assert logarithmic_distance > linear_distance, (
        logarithmic_distance,
        linear_distance,
    )
    set_checkbox("#exploitbench-log-toggle", True)

    set_checkbox("#exploitbench-labels-toggle", False)
    without_labels = inspect_exploit_bench()
    assert without_labels["labelCount"] == 0, without_labels
    assert without_labels["symbolCount"] == 25, without_labels
    assert without_labels["pointLabels"] == "false", without_labels
    set_checkbox("#exploitbench-labels-toggle", True)

    set_checkbox("#exploitbench-family-lines-toggle", True)
    with_lines = inspect_exploit_bench()
    line_state = inspect_family_lines("#exploitbench-chart")
    assert with_lines["familyLineCount"] == 5, with_lines
    assert line_state["count"] == 5, line_state
    assert line_state["valid"], line_state
    set_checkbox("#exploitbench-family-lines-toggle", False)

    trigger = "#exploitbench-selection-trigger"
    panel = "#exploitbench-selection-panel"
    js(f"document.querySelector({trigger!r}).click()")
    verify_selection_hierarchy(
        inspect_selection_hierarchy(panel),
        [
            "GPT-5.6 Sol",
            "GPT-5.6 Terra",
            "GPT-5.6 Luna",
            "GPT-5.5",
            "GPT-5.4",
        ],
        23,
    )
    sol_selector = f'{panel} [data-selection-group-toggle="GPT-5.6 Sol"]'
    js(f"document.querySelector({sol_selector!r}).click()")
    filtered = inspect_exploit_bench()
    assert filtered["pointCount"] == 18, filtered
    assert filtered["comparisonCount"] == 2, filtered
    assert filtered["symbolCount"] == 20, filtered
    assert js(
        "document.querySelector('#exploitbench-selection-summary').textContent"
    ) == ("18 / 23 models")
    set_checkbox("#exploitbench-family-lines-toggle", True)
    filtered_lines = inspect_family_lines("#exploitbench-chart")
    assert filtered_lines["count"] == 4, filtered_lines
    assert filtered_lines["valid"], filtered_lines
    set_checkbox("#exploitbench-family-lines-toggle", False)
    js(f"document.querySelector({sol_selector!r}).click()")

    set_checkbox("#exploitbench-pareto-toggle", True)
    pareto = inspect_exploit_bench()
    assert pareto["symbolCount"] == 8, pareto
    assert pareto["pointCount"] == 7, pareto
    assert pareto["comparisonCount"] == 1, pareto
    assert "Pareto" in js("document.querySelector('#exploitbench-count').textContent")
    set_checkbox("#exploitbench-family-lines-toggle", True)
    pareto_lines = inspect_family_lines("#exploitbench-chart", allow_gaps=True)
    assert pareto_lines["count"] == 1, pareto_lines
    assert pareto_lines["valid"], pareto_lines
    set_checkbox("#exploitbench-family-lines-toggle", False)
    set_checkbox("#exploitbench-pareto-toggle", False)
    js(f"document.querySelector({trigger!r}).click()")

    tooltip_text = js(
        """(async () => {
          const svg = document.querySelector('#exploitbench-chart');
          const point = [...svg.querySelectorAll(
            'g.benchmark-point path[aria-label]'
          )].find((candidate) =>
            candidate.getAttribute('aria-label').startsWith(
              'GPT-5.6 Sol, reasoning effort max,'
            )
          );
          const bounds = point.getBoundingClientRect();
          svg.dispatchEvent(new PointerEvent('pointermove', {
            bubbles: true,
            clientX: bounds.left + bounds.width / 2,
            clientY: bounds.top + bounds.height / 2
          }));
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
          return svg.querySelector('g[aria-label="tip"]').textContent;
        })()"""
    )
    assert "GPT-5.6 Sol" in tooltip_text, tooltip_text
    assert "Output tokens: 120,458" in tooltip_text, tooltip_text
    assert "Cap percent: 73.5%" in tooltip_text, tooltip_text

    for view, metric, expected_count in (
        ("bar-score", "score", 25),
        ("bar-tokens", "tokens", 25),
    ):
        activate_exploitbench_view(view)
        bars = js(
            """[...document.querySelectorAll(
              '#exploitbench-bars g.benchmark-bar rect[aria-label]'
            )].map((bar) => ({
              label: bar.getAttribute('aria-label'),
              value: bar.getBoundingClientRect().height
            }))"""
        )
        values = [bar["value"] for bar in bars]
        assert len(bars) == expected_count, (view, bars)
        assert all(bar["label"] for bar in bars), (view, bars)
        assert values == sorted(values), (view, values)
        assert js("document.querySelector('#exploitbench-scatter-controls').hidden")
        assert (
            js("document.querySelector('#exploitbench-bars').dataset.metric") == metric
        )
        if metric == "tokens":
            text_labels = js(
                """[...document.querySelectorAll('#exploitbench-bars text')]
                  .map((label) => label.textContent.trim())
                  .filter(Boolean)"""
            )
            assert "350k" in text_labels, text_labels
            assert "500k" not in text_labels, text_labels

    activate_exploitbench_view("table")
    assert js("document.querySelectorAll('#exploitbench-table-body tr').length") == 27
    assert js("document.querySelector('#exploitbench-scatter-controls').hidden")
    js(
        """document.querySelector(
          '#exploitbench-table-panel .sort-button[data-sort-key="tokens"]'
        ).click()"""
    )
    token_order = js(
        """[...document.querySelectorAll('#exploitbench-table-body tr')].map(
          (row) => Number(row.dataset.tokens)
        )"""
    )
    assert token_order == sorted(token_order, reverse=True), token_order
    activate_exploitbench_view("scatter")
    assert not js("document.querySelector('#exploitbench-scatter-controls').hidden")


def inspect_family_lines(selector, allow_gaps=False):
    return js(
        f"""(() => {{
          const svg = document.querySelector({selector!r});
          const effortOrder = ['none', 'low', 'medium', 'high', 'xhigh', 'max'];
          const plotLines = [...svg.querySelectorAll('g.benchmark-family-line')];
          const plotPoints = [...svg.querySelectorAll(
            'g.benchmark-point [aria-label]'
          )];
          const center = (point) => {{
            const rect = point.getBoundingClientRect();
            return {{
              x: rect.left + rect.width / 2,
              y: rect.top + rect.height / 2
            }};
          }};
          const nativeLines = plotLines.map((line) => {{
            const path = line.querySelector('path');
            const matrix = path.getScreenCTM();
            const coordinates = [...path.getAttribute('d').matchAll(
              /[ML](-?\\d+(?:\\.\\d+)?),(-?\\d+(?:\\.\\d+)?)/g
            )].map((match) => {{
              const point = new DOMPoint(Number(match[1]), Number(match[2]))
                .matrixTransform(matrix);
              return {{ x: point.x, y: point.y }};
            }});
            const points = coordinates.map((coordinate) =>
              plotPoints.reduce((closest, candidate) => {{
                const pointCenter = center(candidate);
                const distance = Math.hypot(
                  pointCenter.x - coordinate.x,
                  pointCenter.y - coordinate.y
                );
                return !closest || distance < closest.distance
                  ? {{ point: candidate, distance }}
                  : closest;
              }}, null)
            );
            const pointIds = points.map((match) => {{
              const label = match.point.getAttribute('aria-label');
              const parsed = label.match(
                /^(.*), reasoning effort ([^,]+),/
              );
              return parsed ? `${{parsed[1]}}|${{parsed[2]}}` : label;
            }});
            const efforts = pointIds.map((id) => id.split('|').at(-1));
            const ordered = efforts.every((effort, index) => {{
              if (index === 0) return true;
              const previousRank = effortOrder.indexOf(efforts[index - 1]);
              const rank = effortOrder.indexOf(effort);
              return rank > previousRank
                && ({str(allow_gaps).lower()} || rank === previousRank + 1);
            }});
            const positioned = points.every((match) => match.distance < 1.1);
            const stroke = getComputedStyle(line).stroke;
            const colored = points.every(
              (match) => getComputedStyle(match.point).fill === stroke
            );
            const layered = points.every((match) =>
              Boolean(
                line.compareDocumentPosition(match.point)
                & Node.DOCUMENT_POSITION_FOLLOWING
              )
            );
            const styled =
              line.getAttribute('fill') === 'none'
              && Number(line.getAttribute('stroke-width')) === 1.25
              && Number(line.getAttribute('stroke-opacity')) === 0.45
              && line.getAttribute('stroke-linecap') === 'round'
              && line.getAttribute('stroke-linejoin') === 'round'
              && line.getAttribute('pointer-events') === 'none'
              && line.getAttribute('aria-hidden') === 'true';
            return {{
              family: pointIds[0]?.split('|').slice(0, -1).join('|'),
              pointIds,
              ordered,
              positioned,
              colored,
              layered,
              styled
            }};
          }});
          const legacyLines = [...svg.querySelectorAll('[data-family-line]')].map(
            (line) => {{
              const pointIds = JSON.parse(line.dataset.pointIds);
              const points = pointIds.map((id) =>
                svg.querySelector(`[data-point-id="${{CSS.escape(id)}}"]`)
              );
              const coordinates = [...line.points].map((coordinate) => ({{
                x: coordinate.x,
                y: coordinate.y
              }}));
              const efforts = pointIds.map((id) => id.split('|').at(-1));
              const ordered = efforts.every((effort, index) => {{
                if (index === 0) return true;
                const previousRank = effortOrder.indexOf(efforts[index - 1]);
                const rank = effortOrder.indexOf(effort);
                return rank > previousRank
                  && ({str(allow_gaps).lower()} || rank === previousRank + 1);
              }});
              const positioned = points.every((point, index) => {{
                if (!point || !coordinates[index]) return false;
                const pointCenter = point.tagName === 'circle'
                  ? {{
                      x: Number(point.getAttribute('cx')),
                      y: Number(point.getAttribute('cy'))
                    }}
                  : {{
                      x:
                        Number(point.getAttribute('x'))
                        + Number(point.getAttribute('width')) / 2,
                      y:
                        Number(point.getAttribute('y'))
                        + Number(point.getAttribute('height')) / 2
                    }};
                return Math.abs(pointCenter.x - coordinates[index].x) < 0.001
                  && Math.abs(pointCenter.y - coordinates[index].y) < 0.001;
              }});
              const stroke = line.getAttribute('stroke');
              const colored = points.every(
                (point) => point?.getAttribute('fill') === stroke
              );
              const layered = points.every((point) =>
                point
                && Boolean(
                  line.compareDocumentPosition(point)
                  & Node.DOCUMENT_POSITION_FOLLOWING
                )
              );
              const styled =
                line.getAttribute('fill') === 'none'
                && Number(line.getAttribute('stroke-width')) === 1.25
                && Number(line.getAttribute('stroke-opacity')) === 0.45
                && line.getAttribute('stroke-linecap') === 'round'
                && line.getAttribute('stroke-linejoin') === 'round'
                && line.getAttribute('pointer-events') === 'none'
                && line.getAttribute('aria-hidden') === 'true';
              return {{
                family: line.dataset.familyLine,
                pointIds,
                ordered,
                positioned,
                colored,
                layered,
                styled
              }};
            }}
          );
          const lines = plotLines.length ? nativeLines : legacyLines;
          return {{
            enabled: svg.dataset.familyLines,
            count: lines.length,
            lines,
            valid: lines.every((line) =>
              line.pointIds.length >= 2
              && line.ordered
              && line.positioned
              && line.colored
              && line.layered
              && line.styled
            )
          }};
        }})()"""
    )


def set_select(selector, value):
    js(
        f"""(() => {{
          const input = document.querySelector({selector!r});
          input.value = {value!r};
          input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }})()"""
    )


def set_checkbox(selector, checked):
    js(
        f"""(() => {{
          const input = document.querySelector({selector!r});
          input.checked = {str(checked).lower()};
          input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }})()"""
    )


def plot_point_expression(selector, point_id):
    family, effort = point_id.rsplit("|", 1)
    aria_prefix = f"{family}, reasoning effort {effort},"
    return f"""(() => {{
      const svg = document.querySelector({selector!r});
      return [...svg.querySelectorAll('g.benchmark-point [aria-label]')].find(
        (point) => point.getAttribute('aria-label').startsWith({aria_prefix!r})
      ) || svg.querySelector(
        `[data-point-id="${{CSS.escape({point_id!r})}}"]`
      );
    }})()"""


def activate_gene_view(view):
    js(
        f"""document.querySelector(
          {f'#gene-view-tabs [data-gene-view="{view}"]'!r}
        ).click()"""
    )
    active = js(
        "document.querySelector('#gene-view-tabs [aria-selected=\"true\"]').dataset.geneView"
    )
    assert active == view, active


def activate_gene_bench_pro_view(view):
    js(
        f"""document.querySelector(
          {f'#genebench-pro-view-tabs [data-genebench-pro-view="{view}"]'!r}
        ).click()"""
    )
    active = js(
        "document.querySelector('#genebench-pro-view-tabs "
        '[aria-selected="true"]\').dataset.genebenchProView'
    )
    assert active == view, active


def activate_exploitgym_view(view):
    js(
        f"""document.querySelector(
          {f'#exploitgym-view-tabs [data-exploitgym-view="{view}"]'!r}
        ).click()"""
    )
    active = js(
        "document.querySelector('#exploitgym-view-tabs "
        '[aria-selected="true"]\').dataset.exploitgymView'
    )
    assert active == view, active


def activate_exploitbench_view(view):
    js(
        f"""document.querySelector(
          {f'#exploitbench-view-tabs [data-exploitbench-view="{view}"]'!r}
        ).click()"""
    )
    active = js(
        "document.querySelector('#exploitbench-view-tabs "
        '[aria-selected="true"]\').dataset.exploitbenchView'
    )
    assert active == view, active


def set_duration(duration):
    selector = f'input[name="exploitgym-duration"][value="{duration}"]'
    js(
        f"""(() => {{
          const input = document.querySelector({selector!r});
          input.checked = true;
          input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }})()"""
    )


def verify_gene_bench_workspace():
    expected_views = [
        "scatter-cost",
        "scatter-latency",
        "scatter-tokens",
        "bar-score",
        "bar-cost",
        "bar-latency",
        "bar-tokens",
        "table",
    ]
    tabs = js(
        """[...document.querySelectorAll('#gene-view-tabs [role="tab"]')].map(
          (tab) => ({
            view: tab.dataset.geneView,
            selected: tab.getAttribute('aria-selected'),
            tabIndex: tab.tabIndex,
            controls: tab.getAttribute('aria-controls')
          })
        )"""
    )
    assert [tab["view"] for tab in tabs] == expected_views, tabs
    assert tabs[0]["selected"] == "true" and tabs[0]["tabIndex"] == 0, tabs
    assert all(
        tab["selected"] == "false" and tab["tabIndex"] == -1 for tab in tabs[1:]
    ), tabs
    if js("window.innerWidth") <= 390:
        tab_widths = js(
            """(() => {
              const tabList = document.querySelector('#gene-view-tabs');
              return {
                client: tabList.clientWidth,
                scroll: tabList.scrollWidth
              };
            })()"""
        )
        assert tab_widths["scroll"] > tab_widths["client"], tab_widths

    js(
        """document.querySelector(
          '#gene-view-tabs [data-gene-view="scatter-cost"]'
        ).dispatchEvent(new KeyboardEvent('keydown', {
          key: 'ArrowRight',
          bubbles: true
        }))"""
    )
    assert (
        js(
            "document.querySelector('#gene-view-tabs [aria-selected=\"true\"]').dataset.geneView"
        )
        == "scatter-latency"
    )
    activate_gene_view("scatter-cost")

    for view, metric in (
        ("scatter-cost", "cost"),
        ("scatter-latency", "latency"),
        ("scatter-tokens", "tokens"),
    ):
        activate_gene_view(view)
        state = inspect_scatter("#gene-scatter")
        assert state["pointCount"] == 22, (view, state)
        assert state["xMetric"] == metric, (view, state)
        assert not js("document.querySelector('#gene-scatter-controls').hidden")
        assert not js("document.querySelector('#gene-quadrant-legend').hidden")
        assert not js("document.querySelector('#gene-scatter-panel').hidden")

    activate_gene_view("scatter-cost")
    plot_geometry = js(
        """(() => {
          const svg = document.querySelector('#gene-scatter');
          const horizontalGrid = [...svg.querySelectorAll(
            'g.benchmark-grid-minor line, g.benchmark-grid-axis line'
          )].find(
            (line) => Number(line.getAttribute('x1')) !== Number(line.getAttribute('x2'))
          );
          return {
            width: svg.viewBox.baseVal.width,
            plotRight: Number(horizontalGrid.getAttribute('x2'))
          };
        })()"""
    )
    assert plot_geometry["width"] - plot_geometry["plotRight"] == 70, plot_geometry
    set_checkbox("#gene-scatter-log-toggle", False)
    linear_cost_labels = js(
        """[...document.querySelectorAll('#gene-scatter text')]
          .map((label) => label.textContent.trim())
          .filter(Boolean)"""
    )
    assert "$2" in linear_cost_labels, linear_cost_labels
    assert "$2.5" not in linear_cost_labels, linear_cost_labels
    set_checkbox("#gene-scatter-log-toggle", True)

    for view, _metric in (
        ("bar-score", "score"),
        ("bar-cost", "cost"),
        ("bar-latency", "latency"),
        ("bar-tokens", "tokens"),
    ):
        activate_gene_view(view)
        bars = js(
            """[...document.querySelectorAll(
              '#chart g.benchmark-bar rect[aria-label]'
            )].map(
              (bar) => ({
                label: bar.getAttribute('aria-label'),
                value: bar.getBoundingClientRect().height
              })
            )"""
        )
        values = [bar["value"] for bar in bars]
        assert len(bars) == 22, (view, bars)
        assert all(bar["label"] for bar in bars), (view, bars)
        assert values == sorted(values), (view, values)
        assert js("document.querySelector('#gene-scatter-controls').hidden")
        assert js("document.querySelector('#gene-quadrant-legend').hidden")
        assert not js("document.querySelector('#gene-bars-panel').hidden")

    activate_gene_view("table")
    assert js("document.querySelectorAll('#data-table-body tr').length") == 22
    assert js("document.querySelector('#gene-scatter-controls').hidden")
    assert js("document.querySelector('#gene-quadrant-legend').hidden")
    js(
        """document.querySelector(
          '#gene-table-panel .sort-button[data-sort-key="tokens"]'
        ).click()"""
    )
    js(
        """document.querySelector(
          '#gene-table-panel .sort-button[data-sort-key="tokens"]'
        ).click()"""
    )
    token_order = js(
        """[...document.querySelectorAll('#data-table-body tr')].map(
          (row) => Number(row.dataset.tokens)
        )"""
    )
    assert token_order == sorted(token_order), token_order
    activate_gene_view("scatter-cost")
    activate_gene_view("table")
    assert (
        js(
            "document.querySelector('#gene-table-panel th[data-sort-key=\"tokens\"]').getAttribute('aria-sort')"
        )
        == "ascending"
    )
    assert (
        js(
            """[...document.querySelectorAll('#data-table-body tr')].map(
              (row) => Number(row.dataset.tokens)
            )"""
        )
        == token_order
    )

    activate_gene_view("scatter-cost")
    trigger = "#gene-selection-trigger"
    panel = "#gene-scatter-selection-panel"
    js(f"document.querySelector({trigger!r}).click()")
    sol_selector = f'{panel} [data-selection-group-toggle="GPT-5.6 Sol"]'
    js(f"document.querySelector({sol_selector!r}).click()")
    js(f"document.querySelector({trigger!r}).click()")
    assert inspect_scatter("#gene-scatter")["pointCount"] == 17
    activate_gene_view("bar-score")
    assert (
        js(
            "document.querySelectorAll("
            "'#chart g.benchmark-bar rect[aria-label]'"
            ").length"
        )
        == 17
    )
    activate_gene_view("table")
    assert js("document.querySelectorAll('#data-table-body tr').length") == 17

    activate_gene_view("scatter-cost")
    js(f"document.querySelector({trigger!r}).click()")
    js(f"document.querySelector({sol_selector!r}).click()")
    js(f"document.querySelector({trigger!r}).click()")
    assert inspect_scatter("#gene-scatter")["pointCount"] == 22

    js(f"document.querySelector({trigger!r}).click()")
    clear_selector = f'{panel} [data-action="clear"]'
    js(f"document.querySelector({clear_selector!r}).click()")
    js(f"document.querySelector({trigger!r}).click()")
    assert inspect_scatter("#gene-scatter")["pointCount"] == 0
    activate_gene_view("bar-score")
    assert (
        js(
            "document.querySelectorAll("
            "'#chart g.benchmark-bar rect[aria-label]'"
            ").length"
        )
        == 0
    )
    activate_gene_view("table")
    assert js("document.querySelectorAll('#data-table-body tr').length") == 0

    activate_gene_view("scatter-cost")
    js(f"document.querySelector({trigger!r}).click()")
    all_selector = f'{panel} [data-action="all"]'
    js(f"document.querySelector({all_selector!r}).click()")
    js(f"document.querySelector({trigger!r}).click()")
    assert inspect_scatter("#gene-scatter")["pointCount"] == 22


def verify_exploitgym_workspace():
    expected_views = [
        "scatter-cost",
        "scatter-latency",
        "scatter-tokens",
        "bar-score",
        "bar-cost",
        "bar-latency",
        "bar-tokens",
        "table",
    ]
    tabs = js(
        """[...document.querySelectorAll(
          '#exploitgym-view-tabs [role="tab"]'
        )].map((tab) => ({
          view: tab.dataset.exploitgymView,
          selected: tab.getAttribute('aria-selected'),
          tabIndex: tab.tabIndex
        }))"""
    )
    assert [tab["view"] for tab in tabs] == expected_views, tabs
    assert tabs[0]["selected"] == "true" and tabs[0]["tabIndex"] == 0, tabs
    assert all(
        tab["selected"] == "false" and tab["tabIndex"] == -1 for tab in tabs[1:]
    ), tabs
    if js("window.innerWidth") <= 390:
        widths = js(
            """(() => {
              const tabs = document.querySelector('#exploitgym-view-tabs');
              return { client: tabs.clientWidth, scroll: tabs.scrollWidth };
            })()"""
        )
        assert widths["scroll"] > widths["client"], widths

    js(
        """document.querySelector(
          '#exploitgym-view-tabs [data-exploitgym-view="scatter-cost"]'
        ).dispatchEvent(new KeyboardEvent('keydown', {
          key: 'ArrowRight',
          bubbles: true
        }))"""
    )
    assert (
        js(
            "document.querySelector('#exploitgym-view-tabs "
            '[aria-selected="true"]\').dataset.exploitgymView'
        )
        == "scatter-latency"
    )

    for view, metric in (
        ("scatter-cost", "cost"),
        ("scatter-latency", "latency"),
        ("scatter-tokens", "tokens"),
    ):
        activate_exploitgym_view(view)
        state = inspect_scatter("#exploitgym-scatter")
        assert state["pointCount"] == 17, (view, state)
        assert state["xMetric"] == metric, (view, state)
        assert not js("document.querySelector('#exploitgym-scatter-controls').hidden")
        assert not js("document.querySelector('#exploitgym-quadrant-legend').hidden")

    for view in ("bar-score", "bar-cost", "bar-latency", "bar-tokens"):
        activate_exploitgym_view(view)
        bars = js(
            """[...document.querySelectorAll(
              '#exploitgym-bars g.benchmark-bar rect[aria-label]'
            )].map((bar) => ({
              label: bar.getAttribute('aria-label'),
              value: bar.getBoundingClientRect().height
            }))"""
        )
        values = [bar["value"] for bar in bars]
        assert len(bars) == 17, (view, bars)
        assert all(bar["label"] for bar in bars), (view, bars)
        assert values == sorted(values), (view, values)
        assert js("document.querySelector('#exploitgym-scatter-controls').hidden")
        assert js("document.querySelector('#exploitgym-quadrant-legend').hidden")

    activate_exploitgym_view("table")
    assert js("document.querySelectorAll('#exploitgym-table-body tr').length") == 17
    js(
        """document.querySelector(
          '#exploitgym-table-panel .sort-button[data-sort-key="tokens"]'
        ).click()"""
    )
    token_order = js(
        """[...document.querySelectorAll('#exploitgym-table-body tr')].map(
          (row) => Number(row.dataset.tokens)
        )"""
    )
    assert token_order == sorted(token_order, reverse=True), token_order
    activate_exploitgym_view("scatter-cost")


def verify_gene_bench_plot_contract():
    activate_gene_view("scatter-cost")
    set_checkbox("#gene-scatter-log-toggle", True)
    set_checkbox("#gene-scatter-labels-toggle", True)
    set_checkbox("#gene-scatter-family-lines-toggle", False)
    set_checkbox("#pareto-toggle", False)

    contract = js(
        """(() => {
          const svg = document.querySelector('#gene-scatter');
          const points = [...svg.querySelectorAll(
            'g.benchmark-point path[aria-label]'
          )];
          return {
            points: points.length,
            accessible: points.every((point) => point.getAttribute('aria-label')),
            keyboardTargets: points.filter((point) => point.tabIndex >= 0).length,
            whitePointStrokes: points.filter(
              (point) => getComputedStyle(point).stroke === 'rgb(255, 255, 255)'
            ).length,
            tipMarks: svg.querySelectorAll('g[aria-label="tip"]').length,
            svgCount: document.querySelectorAll('#gene-scatter-scroll > svg').length,
            controlledLogTicks: Boolean(svg.dataset.xTicks),
            externalRuntimeRequests: performance.getEntriesByType('resource')
              .filter((entry) => new URL(entry.name).origin !== location.origin)
              .map((entry) => entry.name)
          };
        })()"""
    )
    assert contract == {
        "points": 22,
        "accessible": True,
        "keyboardTargets": 0,
        "whitePointStrokes": 0,
        "tipMarks": 1,
        "svgCount": 1,
        "controlledLogTicks": True,
        "externalRuntimeRequests": [],
    }, contract

    tip_content = js(
        """(async () => {
          const svg = document.querySelector('#gene-scatter');
          const point = [...svg.querySelectorAll(
            'g.benchmark-point path[aria-label]'
          )].find((candidate) =>
            candidate.getAttribute('aria-label').startsWith(
              'GPT-5.6 Sol, reasoning effort max,'
            )
          );
          const bounds = point.getBoundingClientRect();
          svg.dispatchEvent(new PointerEvent('pointermove', {
            bubbles: true,
            clientX: bounds.left + bounds.width / 2,
            clientY: bounds.top + bounds.height / 2
          }));
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
          return svg.querySelector('g[aria-label="tip"]').textContent;
        })()"""
    )
    assert "GPT-5.6 Sol" in tip_content, tip_content
    assert "Output tokens:" in tip_content, tip_content

    activate_gene_view("bar-score")
    bar_contract = js(
        """(() => {
          const svg = document.querySelector('#chart');
          const bars = [...svg.querySelectorAll(
            'g.benchmark-bar rect[aria-label]'
          )];
          return {
            bars: bars.length,
            accessible: bars.every((bar) => bar.getAttribute('aria-label')),
            keyboardTargets: bars.filter((bar) => bar.tabIndex >= 0).length,
            tipMarks: svg.querySelectorAll('g[aria-label="tip"]').length
          };
        })()"""
    )
    assert bar_contract == {
        "bars": 22,
        "accessible": True,
        "keyboardTargets": 0,
        "tipMarks": 1,
    }, bar_contract
    activate_gene_view("bar-cost")
    js("window.dispatchEvent(new Event('resize'))")
    activate_gene_view("scatter-cost")

    if js("window.innerWidth") > 500:
        stress = js(
            """(() => {
              window.__genePlotErrors = [];
              window.addEventListener('error', (event) => {
                window.__genePlotErrors.push(event.message);
              }, { once: false });
              const metrics = ['cost', 'latency', 'tokens'];
              const labels = document.querySelector('#gene-scatter-labels-toggle');
              const lines = document.querySelector('#gene-scatter-family-lines-toggle');
              const log = document.querySelector('#gene-scatter-log-toggle');
              const pareto = document.querySelector('#pareto-toggle');
              const selection = document.querySelector(
                '#gene-scatter-selection-panel input[value="GPT-5.5|none"]'
              );
              const change = (input, checked) => {
                input.checked = checked;
                input.dispatchEvent(new Event('change', { bubbles: true }));
              };
              document.activeElement?.blur();
              for (let index = 0; index < 100; index += 1) {
                document.querySelector(
                  `#gene-view-tabs [data-gene-view="scatter-${metrics[index % 3]}"]`
                ).click();
                change(log, index % 2 === 0);
                change(labels, index % 3 !== 0);
                change(lines, index % 4 === 0);
                change(pareto, index % 5 === 0);
                selection.click();
                window.dispatchEvent(new Event('resize'));
              }
              document.querySelector(
                '#gene-view-tabs [data-gene-view="scatter-cost"]'
              ).click();
              change(log, true);
              change(labels, true);
              change(lines, false);
              change(pareto, false);
              document.querySelector('#gene-scatter-scroll').dispatchEvent(
                new Event('scroll')
              );
              return {
                scatterSvgs: document.querySelectorAll(
                  '#gene-scatter-scroll > svg'
                ).length,
                barSvgs: document.querySelectorAll('#chart-scroll > svg').length,
                points: document.querySelectorAll(
                  '#gene-scatter g.benchmark-point path[aria-label]'
                ).length,
                errors: window.__genePlotErrors,
                tipMarks: document.querySelectorAll(
                  '#gene-scatter g[aria-label="tip"]'
                ).length
              };
            })()"""
        )
        assert stress == {
            "scatterSvgs": 1,
            "barSvgs": 1,
            "points": 22,
            "errors": [],
            "tipMarks": 1,
        }, stress


def verify_exploitgym_plot_contract():
    contract = js(
        """(() => {
          const svg = document.querySelector('#exploitgym-scatter');
          const points = [...svg.querySelectorAll(
            'g.benchmark-point path[aria-label]'
          )];
          return {
            points: points.length,
            accessible: points.every((point) => point.getAttribute('aria-label')),
            keyboardTargets: points.filter((point) => point.tabIndex >= 0).length,
            whitePointStrokes: points.filter(
              (point) => getComputedStyle(point).stroke === 'rgb(255, 255, 255)'
            ).length,
            tipMarks: svg.querySelectorAll('g[aria-label="tip"]').length,
            svgCount: document.querySelectorAll(
              '#exploitgym-scatter-scroll > svg'
            ).length,
            controlledLogTicks: Boolean(svg.dataset.xTicks)
          };
        })()"""
    )
    assert contract == {
        "points": 17,
        "accessible": True,
        "keyboardTargets": 0,
        "whitePointStrokes": 0,
        "tipMarks": 1,
        "svgCount": 1,
        "controlledLogTicks": True,
    }, contract


def verify_terminal_bench():
    tabs = js(
        """[...document.querySelectorAll(
          '#terminalbench-view-tabs [role="tab"]'
        )].map((tab) => ({
          view: tab.dataset.terminalbenchView,
          selected: tab.getAttribute('aria-selected'),
          tabIndex: tab.tabIndex
        }))"""
    )
    assert [tab["view"] for tab in tabs] == ["score", "table"], tabs
    assert tabs[0]["selected"] == "true" and tabs[0]["tabIndex"] == 0, tabs
    assert tabs[1]["selected"] == "false" and tabs[1]["tabIndex"] == -1, tabs

    contract = js(
        """(() => {
          const svg = document.querySelector('#terminal-chart');
          const bars = [...svg.querySelectorAll(
            'g.benchmark-bar rect[aria-label]'
          )];
          const categories = [...svg.querySelectorAll(
            'g.benchmark-bar-category text'
          )].map((label) => label.textContent);
          return {
            bars: bars.length,
            accessible: bars.every((bar) => bar.getAttribute('aria-label')),
            keyboardTargets: bars.filter((bar) => bar.tabIndex >= 0).length,
            heights: bars.map((bar) => bar.getBoundingClientRect().height),
            widths: bars.map((bar) => bar.getBoundingClientRect().width),
            categories,
            tipMarks: svg.querySelectorAll('g[aria-label="tip"]').length,
            svgCount: document.querySelectorAll(
              '#terminal-chart-wrap > svg'
            ).length,
            yMin: Number(svg.dataset.yMin),
            yMax: Number(svg.dataset.yMax),
            ticks: JSON.parse(svg.dataset.yTicks),
            containerOverflows:
              document.querySelector('#terminal-chart-wrap').scrollWidth
              > document.querySelector('#terminal-chart-wrap').clientWidth
          };
        })()"""
    )
    assert contract["bars"] == 9, contract
    assert contract["accessible"], contract
    assert contract["keyboardTargets"] == 0, contract
    assert contract["heights"] == sorted(contract["heights"], reverse=True), contract
    assert all(
        height > width
        for height, width in zip(contract["heights"], contract["widths"], strict=True)
    ), contract
    assert len(contract["categories"]) == 9, contract
    assert "ma_ultra" in contract["categories"][0], contract
    assert contract["tipMarks"] == 1, contract
    assert contract["svgCount"] == 1, contract
    assert contract["yMin"] == 50, contract
    assert contract["yMax"] == 100, contract
    assert contract["ticks"] == [50, 75, 100], contract
    assert contract["containerOverflows"] == (js("window.innerWidth") <= 390), contract

    tip_content = js(
        """(async () => {
          const svg = document.querySelector('#terminal-chart');
          const bar = svg.querySelector('g.benchmark-bar rect[aria-label]');
          const bounds = bar.getBoundingClientRect();
          svg.dispatchEvent(new PointerEvent('pointermove', {
            bubbles: true,
            clientX: bounds.left + bounds.width / 2,
            clientY: bounds.top + bounds.height / 2
          }));
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
          return svg.querySelector('g[aria-label="tip"]').textContent;
        })()"""
    )
    assert "GPT-5.6 Sol Ultra" in tip_content, tip_content
    assert "Reasoning: ma_ultra" in tip_content, tip_content
    assert "Score: 91.91%" in tip_content, tip_content

    js("document.querySelector('#terminalbench-tab-table').click()")
    assert js("document.querySelector('#terminalbench-chart-panel').hidden")
    assert not js("document.querySelector('#terminalbench-table-panel').hidden")
    table_contract = js(
        """(() => {
          const rows = [...document.querySelectorAll('#terminalbench-table-body tr')];
          return {
            rows: rows.length,
            scores: rows.map((row) => Number(row.dataset.score)),
            firstModel: rows[0].dataset.model,
            metric: document.querySelector('#terminalbench-metric').textContent,
            count: document.querySelector('#terminalbench-count').textContent
          };
        })()"""
    )
    assert table_contract["rows"] == 9, table_contract
    assert table_contract["scores"] == sorted(table_contract["scores"], reverse=True), (
        table_contract
    )
    assert table_contract["firstModel"] == "GPT-5.6 Sol Ultra", table_contract
    assert table_contract["metric"] == "Coding · sortable table", table_contract
    assert table_contract["count"] == "9 rows", table_contract
    js(
        """document.querySelector(
          '#terminalbench-table-panel .sort-button[data-sort-key="model"]'
        ).click()"""
    )
    model_order = js(
        """[...document.querySelectorAll('#terminalbench-table-body tr')].map(
          (row) => row.dataset.model
        )"""
    )
    expected_model_order = js(
        """[...document.querySelectorAll('#terminalbench-table-body tr')]
          .map((row) => row.dataset.model)
          .toSorted((first, second) => first.localeCompare(second))"""
    )
    assert model_order == expected_model_order, model_order
    js(
        """document.querySelector(
          '#terminalbench-view-tabs [data-terminalbench-view="table"]'
        ).dispatchEvent(new KeyboardEvent('keydown', {
          key: 'ArrowLeft',
          bubbles: true
        }))"""
    )
    assert not js("document.querySelector('#terminalbench-chart-panel').hidden")
    assert js("document.querySelector('#terminalbench-table-panel').hidden")
    assert (
        js("document.querySelector('#terminalbench-count').textContent") == "9 models"
    )


def horizontal_point_distance(selector, first_id, second_id):
    first_expression = plot_point_expression(selector, first_id)
    second_expression = plot_point_expression(selector, second_id)
    return js(
        f"""(() => {{
          const first = ({first_expression}).getBoundingClientRect();
          const second = ({second_expression}).getBoundingClientRect();
          return Math.abs(
            (first.left + first.width / 2) - (second.left + second.width / 2)
          );
        }})()"""
    )


def verify_scatter(
    selector, expected_points, expected_scale="log", allow_label_overlaps=False
):
    result = inspect_scatter(selector)
    assert result["pointCount"] == expected_points, result
    assert result["labelCount"] == expected_points, result
    assert result["xScale"] == expected_scale, result
    assert result["quadrantCount"] == 2, result
    assert result["attractive"]["fill"] == "#e2f7e4", result
    assert result["opposite"]["fill"] == "#f7f7f7", result
    assert abs(result["attractive"]["width"] - result["opposite"]["width"]) < 1e-9, (
        result
    )
    assert abs(result["attractive"]["height"] - result["opposite"]["height"]) < 1e-9, (
        result
    )
    expected_quadrant_x = (
        (result["xMin"] * result["xMax"]) ** 0.5
        if expected_scale == "log"
        else (result["xMin"] + result["xMax"]) / 2
    )
    assert abs(result["quadrantX"] - expected_quadrant_x) < 1e-9, result
    assert abs(result["quadrantY"] - (result["yMin"] + result["yMax"]) / 2) < 1e-9, (
        result
    )
    if not allow_label_overlaps:
        assert not result["overlaps"], result
    assert not result["invalidLabels"], result
    assert result["invalidGridLines"] == 0, result


def verify_grid(selector):
    result = js(
        f"""(() => {{
          const svg = document.querySelector({selector!r});
          const nativeLines = [...svg.querySelectorAll(
            'g.benchmark-grid-minor line, g.benchmark-grid-axis line'
          )];
          const lines = nativeLines.length
            ? nativeLines
            : [...svg.querySelectorAll('[data-grid-line]')];
          return {{
            count: lines.length,
            invalid: lines.filter((line) => {{
              const owner = line.closest(
                '.benchmark-grid-axis, .benchmark-grid-minor'
              );
              const axis = owner
                ? owner.classList.contains('benchmark-grid-axis')
                : line.dataset.gridLine === 'axis';
              const source = owner || line;
              return source.getAttribute('stroke')
                  !== (axis ? '#d4d7dc' : '#eef0f2')
                || Number(source.getAttribute('stroke-width'))
                  !== (axis ? 0.9 : 0.65)
                || Number(source.getAttribute('stroke-opacity') ?? 1) !== 1;
            }}).length
          }};
        }})()"""
    )
    assert result["count"] > 0, result
    assert result["invalid"] == 0, result


def verify_point_label_toggle(toggle_selector, chart_selector, expected_points):
    initial = inspect_scatter(chart_selector)
    assert initial["pointCount"] == expected_points, initial
    assert initial["labelCount"] == expected_points, initial
    assert initial["pointLabels"] == "true", initial

    set_checkbox(toggle_selector, False)
    hidden = inspect_scatter(chart_selector)
    assert hidden["pointCount"] == expected_points, hidden
    assert hidden["labelCount"] == 0, hidden
    assert hidden["pointLabels"] == "false", hidden
    assert hidden["xMin"] == initial["xMin"], (initial, hidden)
    assert hidden["xMax"] == initial["xMax"], (initial, hidden)
    assert hidden["yMin"] == initial["yMin"], (initial, hidden)
    assert hidden["yMax"] == initial["yMax"], (initial, hidden)
    assert hidden["viewBox"] == initial["viewBox"], (initial, hidden)
    assert hidden["renderedWidth"] == initial["renderedWidth"], (initial, hidden)
    assert hidden["renderedHeight"] == initial["renderedHeight"], (initial, hidden)
    accessible_points = js(
        f"""(() => {{
          const svg = document.querySelector({chart_selector!r});
          const plotPoints = [...svg.querySelectorAll(
            'g.benchmark-point [aria-label]'
          )];
          const points = plotPoints.length
            ? plotPoints
            : [...svg.querySelectorAll('[data-point-id]')];
          return points.filter(
            (point) => point.getAttribute('aria-label')
          ).length;
        }})()"""
    )
    assert accessible_points == expected_points, accessible_points

    set_checkbox(toggle_selector, True)
    restored = inspect_scatter(chart_selector)
    assert restored["pointCount"] == expected_points, restored
    assert restored["labelCount"] == expected_points, restored
    assert restored["pointLabels"] == "true", restored


def verify_family_lines_toggle(
    toggle_selector,
    labels_toggle_selector,
    chart_selector,
    expected_points,
    expected_lines,
):
    initial = inspect_scatter(chart_selector)
    assert initial["pointCount"] == expected_points, initial
    assert initial["familyLineCount"] == 0, initial
    assert initial["familyLines"] == "false", initial

    set_checkbox(toggle_selector, True)
    enabled = inspect_scatter(chart_selector)
    line_state = inspect_family_lines(chart_selector)
    assert enabled["pointCount"] == expected_points, enabled
    assert enabled["familyLineCount"] == expected_lines, enabled
    assert enabled["familyLines"] == "true", enabled
    assert line_state["count"] == expected_lines, line_state
    assert line_state["valid"], line_state

    set_checkbox(labels_toggle_selector, False)
    without_labels = inspect_scatter(chart_selector)
    assert without_labels["labelCount"] == 0, without_labels
    assert without_labels["familyLineCount"] == expected_lines, without_labels
    assert inspect_family_lines(chart_selector)["valid"]
    set_checkbox(labels_toggle_selector, True)

    set_checkbox(toggle_selector, False)
    restored = inspect_scatter(chart_selector)
    assert restored["familyLineCount"] == 0, restored
    assert restored["familyLines"] == "false", restored
    assert restored["pointCount"] == initial["pointCount"], (initial, restored)
    assert restored["pointNames"] == initial["pointNames"], (initial, restored)
    assert restored["xMin"] == initial["xMin"], (initial, restored)
    assert restored["xMax"] == initial["xMax"], (initial, restored)
    assert restored["yMin"] == initial["yMin"], (initial, restored)
    assert restored["yMax"] == initial["yMax"], (initial, restored)
    assert restored["viewBox"] == initial["viewBox"], (initial, restored)
    assert restored["renderedWidth"] == initial["renderedWidth"], (initial, restored)
    assert restored["renderedHeight"] == initial["renderedHeight"], (initial, restored)


def verify_control_triggers():
    compact_labels = js(
        """[...document.querySelectorAll('.multi-select-trigger')].map((trigger) => {
          const label = document.getElementById(trigger.getAttribute('aria-labelledby').split(' ')[0]);
          const style = getComputedStyle(label);
          return {
            summary: trigger.querySelector('[id$="selection-summary"]').textContent.trim(),
            label: label.textContent.trim(),
            labelWidth: label.getBoundingClientRect().width,
            labelHeight: label.getBoundingClientRect().height,
            clipPath: style.clipPath
          };
        })"""
    )
    assert all(item["summary"].endswith("models") for item in compact_labels), (
        compact_labels
    )
    assert all(
        item["label"] == "Models and reasoning efforts:"
        and item["labelWidth"] == 1
        and item["labelHeight"] == 1
        and item["clipPath"] == "inset(50%)"
        for item in compact_labels
    ), compact_labels


def verify_workspace_meta_rows():
    layouts = js(
        """[
          '#gene-selection-trigger',
          '#genebench-pro-scaling-selection-trigger',
          '#exploitbench-selection-trigger',
          '#exploitgym-selection-trigger'
        ].map((triggerSelector) => {
          const actions = document.querySelector(triggerSelector)
            .closest('.gene-workspace-actions');
          const meta = actions.closest('.gene-workspace-meta');
          const legend = meta.querySelector('.gene-workspace-legend');
          const modelItems = [
            ...legend.querySelectorAll('.gene-model-legend .legend-item')
          ];
          const modelTops = modelItems.map(
            (item) => item.getBoundingClientRect().top
          );
          return {
            triggerSelector,
            legend: legend.getBoundingClientRect().toJSON(),
            actions: actions.getBoundingClientRect().toJSON(),
            modelTopSpread: Math.max(...modelTops) - Math.min(...modelTops),
            legendScrollable: legend.scrollWidth > legend.clientWidth
          };
        })"""
    )
    assert all(
        layout["legend"]["top"] >= layout["actions"]["bottom"] for layout in layouts
    ), layouts
    assert all(layout["modelTopSpread"] < 1 for layout in layouts), layouts
    if js("window.innerWidth") <= 390:
        assert all(layout["legendScrollable"] for layout in layouts), layouts


def inspect_selection_hierarchy(panel):
    return js(
        f"""(() => {{
          const panel = document.querySelector({panel!r});
          const groups = [...panel.querySelectorAll('[data-selection-group-toggle]')];
          const options = [...panel.querySelectorAll('.selection-option')];
          const hierarchy = groups.map((input) => {{
            const control = input.closest('.selection-group-control');
            const option = input.closest('.selection-group').querySelector('.selection-option');
            const optionInput = option.querySelector('input');
            const controlStyle = getComputedStyle(control);
            const optionStyle = getComputedStyle(option);
            return {{
              indent:
                optionInput.getBoundingClientRect().left
                - input.getBoundingClientRect().left,
              groupFontSize: Number.parseFloat(controlStyle.fontSize),
              groupFontWeight: Number.parseInt(controlStyle.fontWeight, 10),
              optionFontSize: Number.parseFloat(optionStyle.fontSize),
              optionFontWeight: Number.parseInt(optionStyle.fontWeight, 10),
              guideWidth: Number.parseFloat(optionStyle.borderLeftWidth)
            }};
          }});
          return {{
            groupCount: groups.length,
            groupNames: groups.map((input) => input.dataset.selectionGroupToggle),
            checkedGroups: groups.filter((input) => input.checked).length,
            indeterminateGroups: groups.filter((input) => input.indeterminate).length,
            optionCount: options.length,
            optionLabels: options.map((option) =>
              option.querySelector('span:last-child').textContent.trim()
            ),
            swatchCount: panel.querySelectorAll('.swatch').length,
            hierarchy
          }};
        }})()"""
    )


def verify_selection_hierarchy(result, expected_groups, expected_options):
    assert result["groupCount"] == len(expected_groups), result
    assert result["groupNames"] == expected_groups, result
    assert result["checkedGroups"] == len(expected_groups), result
    assert result["indeterminateGroups"] == 0, result
    assert result["optionCount"] == expected_options, result
    assert result["swatchCount"] == 0, result
    assert all(
        "GPT-" not in label and "/" not in label for label in result["optionLabels"]
    ), result
    assert all(item["indent"] >= 20 for item in result["hierarchy"]), result
    assert all(
        item["groupFontSize"] > item["optionFontSize"]
        and item["groupFontWeight"] > item["optionFontWeight"]
        and item["guideWidth"] == 1
        for item in result["hierarchy"]
    ), result


def verify_gene_bench_selection_groups():
    trigger = "#gene-selection-trigger"
    panel = "#gene-scatter-selection-panel"
    js(f"document.querySelector({trigger!r}).click()")
    selector_widths = js(
        f"""(() => {{
          const trigger = document.querySelector({trigger!r}).getBoundingClientRect();
          const panel = document.querySelector({panel!r}).getBoundingClientRect();
          return {{ viewport: window.innerWidth, trigger: trigger.width, panel: panel.width }};
        }})()"""
    )
    if selector_widths["viewport"] > 700:
        assert selector_widths["trigger"] <= 222, selector_widths
    assert abs(selector_widths["trigger"] - selector_widths["panel"]) < 1, (
        selector_widths
    )

    verify_selection_hierarchy(
        inspect_selection_hierarchy(panel),
        [
            "GPT-5.6 Sol",
            "GPT-5.6 Terra",
            "GPT-5.6 Luna",
            "GPT-5.5",
        ],
        22,
    )

    sol_selector = f'{panel} [data-selection-group-toggle="GPT-5.6 Sol"]'
    js(f"document.querySelector({sol_selector!r}).click()")
    assert js("document.querySelector('#gene-selection-summary').textContent") == (
        "17 / 22 models"
    )
    assert inspect_scatter("#gene-scatter")["pointCount"] == 17
    sol_items_are_cleared = js(
        f"""[...document.querySelectorAll({f"{panel} .selection-option input"!r})]
          .filter((input) => input.value.startsWith('GPT-5.6 Sol|'))
          .every((input) => !input.checked)"""
    )
    assert sol_items_are_cleared is True

    js(f"document.querySelector({sol_selector!r}).click()")
    assert js("document.querySelector('#gene-selection-summary').textContent") == (
        "22 / 22 models"
    )
    assert inspect_scatter("#gene-scatter")["pointCount"] == 22

    js(
        f"""[...document.querySelectorAll({f"{panel} .selection-option input"!r})]
          .find((input) => input.value === 'GPT-5.6 Sol|low').click()"""
    )
    partial = js(
        f"""(() => {{
          const input = document.querySelector({sol_selector!r});
          return {{ checked: input.checked, indeterminate: input.indeterminate }};
        }})()"""
    )
    assert partial == {"checked": False, "indeterminate": True}, partial
    assert js("document.querySelector('#gene-selection-summary').textContent") == (
        "21 / 22 models"
    )

    js(f"document.querySelector({sol_selector!r}).click()")
    assert js("document.querySelector('#gene-selection-summary').textContent") == (
        "22 / 22 models"
    )
    js(f"document.querySelector({trigger!r}).click()")


def verify_exploitgym_selection_groups():
    trigger = "#exploitgym-selection-trigger"
    panel = "#exploitgym-scatter-selection-panel"
    js(f"document.querySelector({trigger!r}).click()")

    verify_selection_hierarchy(
        inspect_selection_hierarchy(panel),
        [
            "GPT-5.6 Sol",
            "GPT-5.6 Terra",
            "GPT-5.6 Luna",
            "GPT-5.5",
            "GPT-5.4",
        ],
        17,
    )

    sol_selector = f'{panel} [data-selection-group-toggle="GPT-5.6 Sol"]'
    js(f"document.querySelector({sol_selector!r}).click()")
    assert js(
        "document.querySelector('#exploitgym-selection-summary').textContent"
    ) == ("12 / 17 models")
    assert inspect_scatter("#exploitgym-scatter")["pointCount"] == 12
    activate_exploitgym_view("bar-score")
    assert (
        js(
            "document.querySelectorAll("
            "'#exploitgym-bars g.benchmark-bar rect[aria-label]'"
            ").length"
        )
        == 12
    )
    activate_exploitgym_view("table")
    assert js("document.querySelectorAll('#exploitgym-table-body tr').length") == 12
    activate_exploitgym_view("scatter-cost")

    js(
        f"""[...document.querySelectorAll({f"{panel} .selection-option input"!r})]
          .find((input) => input.value === 'GPT-5.6 Terra|low').click()"""
    )
    terra_state = js(
        f"""(() => {{
          const input = document.querySelector(
            {f'{panel} [data-selection-group-toggle="GPT-5.6 Terra"]'!r}
          );
          return {{ checked: input.checked, indeterminate: input.indeterminate }};
        }})()"""
    )
    assert terra_state == {"checked": False, "indeterminate": True}, terra_state

    terra_selector = f'{panel} [data-selection-group-toggle="GPT-5.6 Terra"]'
    js(f"document.querySelector({terra_selector!r}).click()")
    js(f"document.querySelector({sol_selector!r}).click()")
    assert inspect_scatter("#exploitgym-scatter")["pointCount"] == 17

    set_duration("6h")
    duration_availability = js(
        f"""(() => {{
          const state = {{}};
          document.querySelectorAll(
            {f"{panel} [data-selection-group-toggle]"!r}
          ).forEach((input) => {{
            state[input.dataset.selectionGroupToggle] = {{
              checked: input.checked,
              disabled: input.disabled
            }};
          }});
          return state;
        }})()"""
    )
    assert duration_availability == {
        "GPT-5.6 Sol": {"checked": True, "disabled": False},
        "GPT-5.6 Terra": {"checked": True, "disabled": False},
        "GPT-5.6 Luna": {"checked": True, "disabled": False},
        "GPT-5.5": {"checked": False, "disabled": True},
        "GPT-5.4": {"checked": False, "disabled": True},
    }, duration_availability
    assert js(
        "document.querySelector('#exploitgym-selection-summary').textContent"
    ) == ("15 / 15 models")
    activate_exploitgym_view("bar-score")
    assert (
        js(
            "document.querySelectorAll("
            "'#exploitgym-bars g.benchmark-bar rect[aria-label]'"
            ").length"
        )
        == 15
    )
    activate_exploitgym_view("table")
    assert js("document.querySelectorAll('#exploitgym-table-body tr').length") == 15
    activate_exploitgym_view("scatter-cost")

    js(f"document.querySelector({sol_selector!r}).click()")
    assert inspect_scatter("#exploitgym-scatter")["pointCount"] == 10
    assert js(
        "document.querySelector('#exploitgym-selection-summary').textContent"
    ) == ("10 / 15 models")

    set_duration("2h")
    assert inspect_scatter("#exploitgym-scatter")["pointCount"] == 12
    js(f"document.querySelector({sol_selector!r}).click()")
    assert inspect_scatter("#exploitgym-scatter")["pointCount"] == 17
    js(f"document.querySelector({trigger!r}).click()")


def verify_family_line_gap_handling():
    trigger = "#gene-selection-trigger"
    panel = "#gene-scatter-selection-panel"
    toggle = "#gene-scatter-family-lines-toggle"
    set_checkbox(toggle, True)
    js(f"document.querySelector({trigger!r}).click()")
    high_selector = f'{panel} .selection-option input[value="GPT-5.6 Sol|high"]'
    js(f"document.querySelector({high_selector!r}).click()")

    state = inspect_family_lines("#gene-scatter")
    sol_runs = [
        line["pointIds"] for line in state["lines"] if line["family"] == "GPT-5.6 Sol"
    ]
    assert state["valid"], state
    assert sol_runs == [
        ["GPT-5.6 Sol|low", "GPT-5.6 Sol|medium"],
        ["GPT-5.6 Sol|xhigh", "GPT-5.6 Sol|max"],
    ], state
    assert "GPT-5.6 Sol|high" not in {
        point_id for line in state["lines"] for point_id in line["pointIds"]
    }, state

    js(f"document.querySelector({high_selector!r}).click()")
    restored = inspect_family_lines("#gene-scatter")
    assert restored["count"] == 4, restored
    assert restored["valid"], restored
    js(f"document.querySelector({trigger!r}).click()")
    set_checkbox(toggle, False)


def verify_gene_bench_pareto_lines():
    set_checkbox("#gene-scatter-family-lines-toggle", True)
    set_checkbox("#pareto-toggle", True)
    state = inspect_family_lines("#gene-scatter", allow_gaps=True)
    terra_low = "GPT-5.6 Terra|low"
    terra_max = "GPT-5.6 Terra|max"

    assert state["valid"], state
    assert any(
        any(
            point_ids[index : index + 2] == [terra_low, terra_max]
            for index in range(len(point_ids) - 1)
        )
        for point_ids in (
            line["pointIds"]
            for line in state["lines"]
            if line["family"] == "GPT-5.6 Terra"
        )
    ), state

    set_checkbox("#pareto-toggle", False)
    set_checkbox("#gene-scatter-family-lines-toggle", False)


def verify_gene_bench_pro_interactions():
    selector = "#genebench-pro-scaling"
    expected_views = [
        "scatter-tokens",
        "scatter-cost",
        "bar-score",
        "bar-tokens",
        "bar-cost",
        "table",
    ]
    tabs = js(
        """[...document.querySelectorAll(
          '#genebench-pro-view-tabs [role="tab"]'
        )].map((tab) => ({
          view: tab.dataset.genebenchProView,
          selected: tab.getAttribute('aria-selected'),
          tabIndex: tab.tabIndex
        }))"""
    )
    assert [tab["view"] for tab in tabs] == expected_views, tabs
    assert tabs[0]["selected"] == "true" and tabs[0]["tabIndex"] == 0, tabs
    assert all(
        tab["selected"] == "false" and tab["tabIndex"] == -1 for tab in tabs[1:]
    ), tabs
    js(
        """document.querySelector(
          '#genebench-pro-view-tabs [data-genebench-pro-view="scatter-tokens"]'
        ).dispatchEvent(new KeyboardEvent('keydown', {
          key: 'ArrowRight',
          bubbles: true
        }))"""
    )
    assert (
        js(
            "document.querySelector('#genebench-pro-view-tabs "
            '[aria-selected="true"]\').dataset.genebenchProView'
        )
        == "scatter-cost"
    )
    activate_gene_bench_pro_view("scatter-tokens")
    set_checkbox("#genebench-pro-scaling-family-lines-toggle", True)
    initial = inspect_scatter(selector)
    assert initial["pointCount"] == 33, initial
    assert initial["xMetric"] == "tokens", initial
    assert initial["xScale"] == "log", initial
    y_tick_labels = js(
        """[...document.querySelectorAll('#genebench-pro-scaling text')]
          .map((label) => label.textContent.trim())
          .filter(Boolean)"""
    )
    assert "30%" in y_tick_labels, y_tick_labels
    assert "35%" not in y_tick_labels, y_tick_labels
    plot_contract = js(
        """(() => {
          const container = document.querySelector('#genebench-pro-scaling-scroll');
          const svg = document.querySelector('#genebench-pro-scaling');
          const points = [...svg.querySelectorAll(
            'g.benchmark-point path[aria-label]'
          )];
          return {
            points: points.length,
            accessible: points.every((point) => point.getAttribute('aria-label')),
            keyboardTargets: points.filter((point) => point.tabIndex >= 0).length,
            tipMarks: svg.querySelectorAll('g[aria-label="tip"]').length,
            svgCount: container.querySelectorAll(':scope > svg').length,
            controlledLogTicks: Boolean(svg.dataset.xTicks)
          };
        })()"""
    )
    assert plot_contract["points"] == 33, plot_contract
    assert plot_contract["accessible"], plot_contract
    assert plot_contract["keyboardTargets"] == 0, plot_contract
    assert plot_contract["tipMarks"] == 1, plot_contract
    assert plot_contract["svgCount"] == 1, plot_contract
    assert plot_contract["controlledLogTicks"], plot_contract
    assert (
        js(
            "document.querySelectorAll('#genebench-pro-scaling "
            "g.benchmark-point-label text').length"
        )
        == 33
    )
    assert " ".join(
        js("document.querySelector('#genebench-pro-scaling-title').textContent").split()
    ) == ("GeneBench-Pro: Test-time compute scaling on GPT models")
    assert "Tokens used" in js(
        "document.querySelector('#genebench-pro-scaling-metric').textContent"
    )
    assert (
        js(
            "document.querySelector('#genebench-pro-scaling "
            "g.benchmark-point [aria-label]').getAttribute('aria-label')"
        ).find("tokens used")
        >= 0
    )

    logarithmic_distance = horizontal_point_distance(
        selector, "GPT-5.6 Sol|none", "GPT-5.6 Sol|low"
    )
    set_checkbox("#genebench-pro-scaling-log-toggle", False)
    linear = inspect_scatter(selector)
    assert linear["pointCount"] == 33, linear
    assert linear["xScale"] == "linear", linear
    assert inspect_family_lines(selector)["valid"]
    assert "linear scale" in js(
        "document.querySelector('#genebench-pro-scaling-metric').textContent"
    )
    linear_distance = horizontal_point_distance(
        selector, "GPT-5.6 Sol|none", "GPT-5.6 Sol|low"
    )
    assert logarithmic_distance > linear_distance * 2, (
        linear_distance,
        logarithmic_distance,
    )
    set_checkbox("#genebench-pro-scaling-log-toggle", True)
    restored = inspect_scatter(selector)
    assert restored["xScale"] == "log", restored
    assert restored["xMin"] == initial["xMin"], (initial, restored)
    assert restored["xMax"] == initial["xMax"], (initial, restored)

    activate_gene_bench_pro_view("scatter-cost")
    cost_log = inspect_scatter(selector)
    assert cost_log["pointCount"] == 33, cost_log
    assert cost_log["xMetric"] == "cost", cost_log
    assert cost_log["xScale"] == "log", cost_log
    assert inspect_family_lines(selector)["valid"]
    assert cost_log["xMin"] != initial["xMin"], (initial, cost_log)
    assert "Estimated API cost" in js(
        "document.querySelector('#genebench-pro-scaling-metric').textContent"
    )
    assert "generated output tokens only" in js(
        "document.querySelector('#genebench-pro-cost-note').textContent"
    )
    assert "estimated api cost" in js(
        "document.querySelector('#genebench-pro-scaling "
        "g.benchmark-point [aria-label]').getAttribute('aria-label')"
    )
    tip_text = js(
        """(async () => {
          const svg = document.querySelector('#genebench-pro-scaling');
          const point = [...svg.querySelectorAll(
            'g.benchmark-point path[aria-label]'
          )].find((candidate) =>
            candidate.getAttribute('aria-label').startsWith(
              'GPT-5.6 Sol, reasoning effort max,'
            )
          );
          const bounds = point.getBoundingClientRect();
          svg.dispatchEvent(new PointerEvent('pointermove', {
            bubbles: true,
            clientX: bounds.left + bounds.width / 2,
            clientY: bounds.top + bounds.height / 2
          }));
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
          return svg.querySelector('g[aria-label="tip"]').textContent;
        })()"""
    )
    assert "Output-token price: $30.00 / 1M" in tip_text, tip_text
    assert "Estimated API cost: $0.995" in tip_text, tip_text

    set_checkbox("#genebench-pro-scaling-log-toggle", False)
    cost_linear = inspect_scatter(selector)
    assert cost_linear["pointCount"] == 33, cost_linear
    assert cost_linear["xMetric"] == "cost", cost_linear
    assert cost_linear["xScale"] == "linear", cost_linear
    assert inspect_family_lines(selector)["valid"]
    set_checkbox("#genebench-pro-scaling-log-toggle", True)
    activate_gene_bench_pro_view("scatter-tokens")
    restored = inspect_scatter(selector)
    assert restored["xMetric"] == "tokens", restored
    assert restored["xMin"] == initial["xMin"], (initial, restored)
    assert restored["xMax"] == initial["xMax"], (initial, restored)
    assert inspect_family_lines(selector)["valid"]

    for view in ("bar-score", "bar-tokens", "bar-cost"):
        activate_gene_bench_pro_view(view)
        bars = js(
            """[...document.querySelectorAll(
              '#genebench-pro-bars g.benchmark-bar rect[aria-label]'
            )].map((bar) => ({
              label: bar.getAttribute('aria-label'),
              value: bar.getBoundingClientRect().height
            }))"""
        )
        values = [bar["value"] for bar in bars]
        assert len(bars) == 33, (view, bars)
        assert all(bar["label"] for bar in bars), (view, bars)
        assert values == sorted(values), (view, values)
        assert js("document.querySelector('#genebench-pro-scatter-controls').hidden")
        assert js("document.querySelector('#genebench-pro-quadrant-legend').hidden")
        assert not js("document.querySelector('#genebench-pro-bars-panel').hidden")
        assert js("document.querySelector('#genebench-pro-cost-note').hidden") == (
            view != "bar-cost"
        )

    activate_gene_bench_pro_view("table")
    assert js("document.querySelectorAll('#genebench-pro-table-body tr').length") == 33
    assert js("document.querySelector('#genebench-pro-scatter-controls').hidden")
    assert js("document.querySelector('#genebench-pro-quadrant-legend').hidden")
    assert not js("document.querySelector('#genebench-pro-cost-note').hidden")
    js(
        """document.querySelector(
          '#genebench-pro-table-panel .sort-button[data-sort-key="tokens"]'
        ).click()"""
    )
    token_order = js(
        """[...document.querySelectorAll('#genebench-pro-table-body tr')].map(
          (row) => Number(row.dataset.tokens)
        )"""
    )
    assert token_order == sorted(token_order, reverse=True), token_order
    activate_gene_bench_pro_view("scatter-tokens")
    assert not js("document.querySelector('#genebench-pro-scatter-controls').hidden")
    assert not js("document.querySelector('#genebench-pro-quadrant-legend').hidden")
    assert js("document.querySelector('#genebench-pro-cost-note').hidden")

    js("document.querySelector('#genebench-pro-scaling-selection-trigger').click()")
    panel = "#genebench-pro-scaling-selection-panel"
    verify_selection_hierarchy(
        inspect_selection_hierarchy(panel),
        [
            "GPT-5.2",
            "GPT-5.4",
            "GPT-5.5",
            "GPT-5.6 Luna",
            "GPT-5.6 Terra",
            "GPT-5.6 Sol",
        ],
        33,
    )
    sol_group_selector = f'{panel} [data-selection-group-toggle="GPT-5.6 Sol"]'
    js(f"document.querySelector({sol_group_selector!r}).click()")
    assert inspect_scatter(selector)["pointCount"] == 27
    filtered_lines = inspect_family_lines(selector)
    assert filtered_lines["count"] == 5, filtered_lines
    assert filtered_lines["valid"], filtered_lines
    assert (
        js(
            "document.querySelector('#genebench-pro-scaling-selection-summary').textContent"
        )
        == "27 / 33 models"
    )
    activate_gene_bench_pro_view("bar-score")
    assert (
        js(
            "document.querySelectorAll("
            "'#genebench-pro-bars g.benchmark-bar rect[aria-label]'"
            ").length"
        )
        == 27
    )
    activate_gene_bench_pro_view("table")
    assert js("document.querySelectorAll('#genebench-pro-table-body tr').length") == 27
    activate_gene_bench_pro_view("scatter-tokens")
    js(f"document.querySelector({sol_group_selector!r}).click()")
    assert inspect_scatter(selector)["pointCount"] == 33

    assert not js(
        "document.querySelector('#genebench-pro-scaling-selection-panel').hidden"
    )
    js(
        "document.querySelector('#genebench-pro-scaling-selection-panel "
        '[data-action="clear"]\').click()'
    )
    js(
        """(() => {
          const input = [...document.querySelectorAll(
            '#genebench-pro-scaling-selection-panel input'
          )].find((candidate) => candidate.value === 'GPT-5.6 Sol|max');
          input.click();
        })()"""
    )
    selected = inspect_scatter(selector)
    assert selected["pointCount"] == 1, selected
    assert inspect_family_lines(selector)["count"] == 0
    assert selected["xMin"] != initial["xMin"] or selected["xMax"] != initial["xMax"], (
        initial,
        selected,
    )
    assert (
        js(
            "document.querySelector('#genebench-pro-scaling-selection-summary').textContent"
        )
        == "1 / 33 models"
    )

    js(
        "document.querySelector('#genebench-pro-scaling-selection-panel "
        '[data-action="all"]\').click()'
    )
    js(
        """(() => {
          const input = document.querySelector('#genebench-pro-scaling-pareto-toggle');
          input.checked = true;
          input.dispatchEvent(new Event('change', { bubbles: true }));
        })()"""
    )
    pareto = inspect_scatter(selector)
    assert pareto["pointCount"] == 7, pareto
    assert not js(f"Boolean({plot_point_expression(selector, 'GPT-5.6 Terra|low')})")
    assert js(f"Boolean({plot_point_expression(selector, 'GPT-5.6 Sol|low')})")
    assert pareto["xMin"] != initial["xMin"] or pareto["xMax"] != initial["xMax"], (
        initial,
        pareto,
    )
    assert "Pareto" in js(
        "document.querySelector('#genebench-pro-scaling-count').textContent"
    )
    pareto_lines = inspect_family_lines(selector, allow_gaps=True)
    assert pareto_lines["valid"], pareto_lines
    visible_pareto_ids = set(
        js(
            """[...document.querySelectorAll(
              '#genebench-pro-scaling g.benchmark-point [aria-label]'
            )].map((point) => {
              const match = point.getAttribute('aria-label').match(
                /^(.*), reasoning effort ([^,]+),/
              );
              return `${match[1]}|${match[2]}`;
            })"""
        )
    )
    line_point_ids = {
        point_id for line in pareto_lines["lines"] for point_id in line["pointIds"]
    }
    assert line_point_ids <= visible_pareto_ids, (pareto_lines, visible_pareto_ids)

    js(
        """(() => {
          const input = document.querySelector('#genebench-pro-scaling-pareto-toggle');
          input.checked = false;
          input.dispatchEvent(new Event('change', { bubbles: true }));
          document.querySelector('#genebench-pro-scaling-selection-trigger').click();
        })()"""
    )
    set_checkbox("#genebench-pro-scaling-family-lines-toggle", False)


def verify_api_pricing_table():
    pricing = js(
        """(() => {
          const section = document.querySelector('.pricing-section');
          const table = section.querySelector('.pricing-table');
          const rows = [...table.tBodies[0].rows];
          const row = (model) => {
            const match = rows.find((item) =>
              item.cells[0].querySelector('strong').textContent === model
            );
            return match
              ? [...match.cells].map((cell) =>
                  cell.innerText.replace(/\\s+/g, ' ').trim()
                )
              : null;
          };
          return {
            headers: [...table.tHead.rows[0].cells].map((cell) =>
              cell.textContent.trim()
            ),
            rowCount: rows.length,
            models: rows.map((item) =>
              item.cells[0].querySelector('strong').textContent
            ),
            beforeFirstChart: Boolean(
              section.compareDocumentPosition(
                document.querySelector('#genebench-title').closest('section')
              )
              & Node.DOCUMENT_POSITION_FOLLOWING
            ),
            sourceCount: document.querySelectorAll('#api-pricing-sources a').length,
            notApplicableCount: table.querySelectorAll(
              '.not-applicable[aria-label="Not applicable"]'
            ).length,
            solUltra: row('GPT-5.6 Sol Ultra'),
            mythos: row('Claude Mythos 5'),
            gemini: row('Gemini 3.1 Pro Preview'),
            frameContainsTable:
              table.getBoundingClientRect().right
              <= table.closest('.table-frame').scrollWidth
                + table.closest('.table-frame').getBoundingClientRect().left
                + 1
          };
        })()"""
    )
    assert pricing["headers"] == [
        "Model",
        "Input",
        "Cached input",
        "Cache write",
        "Output",
    ], pricing
    assert pricing["rowCount"] == 11, pricing
    assert set(pricing["models"]) == {
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
    }, pricing
    assert pricing["beforeFirstChart"], pricing
    assert pricing["sourceCount"] == 4, pricing
    assert pricing["notApplicableCount"] == 4, pricing
    assert pricing["frameContainsTable"], pricing
    assert pricing["solUltra"] == [
        "GPT-5.6 Sol Ultra OpenAI Uses GPT-5.6 Sol pricing",
        "$5.00",
        "$0.50",
        "$6.25 30 min",
        "$30.00",
    ], pricing
    assert pricing["mythos"] == [
        "Claude Mythos 5 Anthropic",
        "$10.00",
        "$1.00",
        "$12.50 5 min",
        "$50.00",
    ], pricing
    assert pricing["gemini"] == [
        "Gemini 3.1 Pro Preview Google",
        "$2.00 ≤ 200K $4.00 > 200K",
        "$0.20 ≤ 200K $0.40 > 200K",
        "—",
        "$12.00 ≤ 200K $18.00 > 200K",
    ], pricing


def verify_current_view():
    verify_api_pricing_table()
    verify_exploit_bench()
    verify_gene_bench_workspace()
    verify_gene_bench_plot_contract()
    verify_exploitgym_plot_contract()
    verify_exploitgym_workspace()
    verify_terminal_bench()
    assert js("document.querySelectorAll('.quadrant-legend').length") == 3
    verify_control_triggers()
    verify_workspace_meta_rows()
    verify_family_lines_toggle(
        "#gene-scatter-family-lines-toggle",
        "#gene-scatter-labels-toggle",
        "#gene-scatter",
        22,
        4,
    )
    verify_family_lines_toggle(
        "#genebench-pro-scaling-family-lines-toggle",
        "#genebench-pro-scaling-labels-toggle",
        "#genebench-pro-scaling",
        33,
        6,
    )
    verify_family_lines_toggle(
        "#exploitgym-scatter-family-lines-toggle",
        "#exploitgym-scatter-labels-toggle",
        "#exploitgym-scatter",
        17,
        3,
    )
    verify_family_line_gap_handling()
    verify_gene_bench_pareto_lines()
    verify_gene_bench_selection_groups()
    verify_exploitgym_selection_groups()
    verify_grid("#chart")
    verify_grid("#terminal-chart")
    verify_point_label_toggle("#gene-scatter-labels-toggle", "#gene-scatter", 22)
    verify_point_label_toggle(
        "#genebench-pro-scaling-labels-toggle",
        "#genebench-pro-scaling",
        33,
    )
    verify_point_label_toggle(
        "#exploitgym-scatter-labels-toggle",
        "#exploitgym-scatter",
        17,
    )

    for checked, scale in ((True, "log"), (False, "linear")):
        set_checkbox("#gene-scatter-log-toggle", checked)
        for metric in METRICS:
            activate_gene_view(f"scatter-{metric}")
            set_checkbox("#gene-scatter-family-lines-toggle", True)
            gene_lines = inspect_family_lines("#gene-scatter")
            assert gene_lines["count"] == 4, (metric, scale, gene_lines)
            assert gene_lines["valid"], (metric, scale, gene_lines)
            set_checkbox("#gene-scatter-family-lines-toggle", False)
            verify_scatter(
                "#gene-scatter",
                22,
                scale,
                allow_label_overlaps=not checked,
            )
    activate_gene_view("scatter-cost")
    set_checkbox("#gene-scatter-log-toggle", True)

    verify_scatter(
        "#genebench-pro-scaling",
        33,
        "log",
        allow_label_overlaps=True,
    )
    verify_gene_bench_pro_interactions()

    for duration, expected_points in (("2h", 17), ("6h", 15)):
        set_duration(duration)
        set_checkbox("#exploitgym-scatter-family-lines-toggle", True)
        duration_lines = inspect_family_lines("#exploitgym-scatter")
        assert duration_lines["count"] == 3, (duration, duration_lines)
        assert duration_lines["valid"], (duration, duration_lines)
        set_checkbox("#exploitgym-scatter-family-lines-toggle", False)
        for checked, scale in ((True, "log"), (False, "linear")):
            set_checkbox("#exploitgym-scatter-log-toggle", checked)
            for metric in METRICS:
                activate_exploitgym_view(f"scatter-{metric}")
                set_checkbox("#exploitgym-scatter-family-lines-toggle", True)
                exploit_lines = inspect_family_lines("#exploitgym-scatter")
                assert exploit_lines["count"] == 3, (
                    duration,
                    metric,
                    scale,
                    exploit_lines,
                )
                assert exploit_lines["valid"], (duration, metric, scale, exploit_lines)
                set_checkbox("#exploitgym-scatter-family-lines-toggle", False)
                verify_scatter(
                    "#exploitgym-scatter",
                    expected_points,
                    scale,
                    allow_label_overlaps=not checked,
                )
    set_checkbox("#exploitgym-scatter-log-toggle", True)
    activate_exploitgym_view("scatter-cost")


with app_server() as page_url:
    new_tab(page_url)
    wait_for_load()
    wait(0.2)
    verify_current_view()

    try:
        cdp(
            "Emulation.setDeviceMetricsOverride",
            width=390,
            height=844,
            deviceScaleFactor=1,
            mobile=True,
        )
        goto_url(page_url)
        wait_for_load()
        wait(0.2)
        verify_current_view()
        assert js("document.documentElement.scrollWidth") == 390
    finally:
        cdp("Emulation.clearDeviceMetricsOverride")
        goto_url(page_url)
        wait_for_load()

    print("Browser verification passed: desktop and 390px mobile")
