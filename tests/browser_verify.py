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
          const points = [...svg.querySelectorAll('[data-point-id]')];
          const labels = [...svg.querySelectorAll('[data-point-label]')].map((label) => {{
            const point = svg.querySelector(
              `[data-point-id="${{CSS.escape(label.dataset.pointLabel)}}"]`
            );
            return {{
              id: label.dataset.pointLabel,
              label: label.getBoundingClientRect().toJSON(),
              point: point.getBoundingClientRect().toJSON(),
              anchor: label.getAttribute('text-anchor'),
              weight: label.getAttribute('font-weight')
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
          const attractive = svg.querySelector('[data-quadrant="attractive"]');
          const opposite = svg.querySelector('[data-quadrant="opposite"]');
          const invalidGridLines = [...svg.querySelectorAll('[data-grid-line]')]
            .filter((line) => {{
              const axis = line.dataset.gridLine === 'axis';
              return line.getAttribute('stroke') !== (axis ? '#d4d7dc' : '#eef0f2')
                || Number(line.getAttribute('stroke-width')) !== (axis ? 0.9 : 0.65);
            }})
            .length;
          return {{
            pointCount: points.length,
            pointNames: points.map((point) => point.getAttribute('aria-label')),
            labelCount: labels.length,
            familyLineCount: svg.querySelectorAll('[data-family-line]').length,
            viewBox: svg.getAttribute('viewBox'),
            renderedWidth: svgRect.width,
            renderedHeight: svgRect.height,
            quadrantCount: svg.querySelectorAll('[data-quadrant]').length,
            attractive: {{
              x: Number(attractive.getAttribute('x')),
              y: Number(attractive.getAttribute('y')),
              width: Number(attractive.getAttribute('width')),
              height: Number(attractive.getAttribute('height')),
              fill: attractive.getAttribute('fill')
            }},
            opposite: {{
              x: Number(opposite.getAttribute('x')),
              y: Number(opposite.getAttribute('y')),
              width: Number(opposite.getAttribute('width')),
              height: Number(opposite.getAttribute('height')),
              fill: opposite.getAttribute('fill')
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


def inspect_family_lines(selector, allow_gaps=False):
    return js(
        f"""(() => {{
          const svg = document.querySelector({selector!r});
          const effortOrder = ['none', 'low', 'medium', 'high', 'xhigh', 'max'];
          const center = (point) => point.tagName === 'circle'
            ? {{
                x: Number(point.getAttribute('cx')),
                y: Number(point.getAttribute('cy'))
              }}
            : {{
                x: Number(point.getAttribute('x')) + Number(point.getAttribute('width')) / 2,
                y: Number(point.getAttribute('y')) + Number(point.getAttribute('height')) / 2
              }};
          const lines = [...svg.querySelectorAll('[data-family-line]')].map((line) => {{
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
              const pointCenter = center(point);
              return Math.abs(pointCenter.x - coordinates[index].x) < 0.001
                && Math.abs(pointCenter.y - coordinates[index].y) < 0.001;
            }});
            const stroke = line.getAttribute('stroke');
            const colored = points.every((point) => point?.getAttribute('fill') === stroke);
            const layered = points.every((point) =>
              point
              && Boolean(line.compareDocumentPosition(point) & Node.DOCUMENT_POSITION_FOLLOWING)
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
          }});
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


def set_duration(duration):
    selector = f'input[name="exploitgym-duration"][value="{duration}"]'
    js(
        f"""(() => {{
          const input = document.querySelector({selector!r});
          input.checked = true;
          input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }})()"""
    )


def horizontal_point_distance(selector, first_id, second_id):
    return js(
        f"""(() => {{
          const svg = document.querySelector({selector!r});
          const first = svg.querySelector(
            `[data-point-id="${{CSS.escape({first_id!r})}}"]`
          ).getBoundingClientRect();
          const second = svg.querySelector(
            `[data-point-id="${{CSS.escape({second_id!r})}}"]`
          ).getBoundingClientRect();
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
    assert result["attractive"]["width"] == result["opposite"]["width"], result
    assert result["attractive"]["height"] == result["opposite"]["height"], result
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
          const lines = [...document.querySelectorAll(
            {f"{selector} [data-grid-line]"!r}
          )];
          return {{
            count: lines.length,
            invalid: lines.filter((line) => {{
              const axis = line.dataset.gridLine === 'axis';
              return line.getAttribute('stroke') !== (axis ? '#d4d7dc' : '#eef0f2')
                || Number(line.getAttribute('stroke-width')) !== (axis ? 0.9 : 0.65);
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
        f"""[...document.querySelectorAll(
          {f"{chart_selector} [data-point-id]"!r}
        )].filter((point) => point.getAttribute('aria-label')).length"""
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
    result = js(
        """(() => {
          const pairs = [
            ['#gene-scatter-metric-select', '#scatter-selection-trigger'],
            [
              '#genebench-pro-scaling-metric-select',
              '#genebench-pro-scaling-selection-trigger'
            ],
            [
              '#exploitgym-scatter-metric-select',
              '#exploitgym-selection-trigger'
            ]
          ];
          return pairs.map(([selectSelector, buttonSelector]) => {
            const select = document.querySelector(selectSelector);
            const selectTrigger = select.closest('.control-trigger');
            const button = document.querySelector(buttonSelector);
            const selectStyle = getComputedStyle(selectTrigger);
            const buttonStyle = getComputedStyle(button);
            const selectArrow = getComputedStyle(selectTrigger, '::after');
            const buttonArrow = getComputedStyle(button, '::after');
            const properties = [
              'height',
              'borderTopWidth',
              'borderTopColor',
              'borderRadius',
              'backgroundColor',
              'color',
              'fontSize',
              'fontWeight'
            ];
            return {
              selectSelector,
              buttonSelector,
              mismatches: properties.filter(
                (property) => selectStyle[property] !== buttonStyle[property]
              ),
              selectAppearance: getComputedStyle(select).appearance,
              arrowMismatch:
                selectArrow.width !== buttonArrow.width
                || selectArrow.height !== buttonArrow.height
                || selectArrow.borderRightColor !== buttonArrow.borderRightColor
                || selectArrow.borderRightWidth !== buttonArrow.borderRightWidth,
              buttonOverflow: button.scrollWidth > button.clientWidth
            };
          });
        })()"""
    )
    assert all(not item["mismatches"] for item in result), result
    assert all(item["selectAppearance"] == "none" for item in result), result
    assert all(not item["arrowMismatch"] for item in result), result
    assert all(not item["buttonOverflow"] for item in result), result
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
    assert all(item["summary"].endswith("models/efforts") for item in compact_labels), (
        compact_labels
    )
    assert all(
        item["label"] == "Models and reasoning efforts:"
        and item["labelWidth"] == 1
        and item["labelHeight"] == 1
        and item["clipPath"] == "inset(50%)"
        for item in compact_labels
    ), compact_labels


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
    trigger = "#scatter-selection-trigger"
    panel = "#gene-scatter-selection-panel"
    js(f"document.querySelector({trigger!r}).click()")

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
    assert js("document.querySelector('#scatter-selection-summary').textContent") == (
        "17 / 22 models/efforts"
    )
    assert inspect_scatter("#gene-scatter")["pointCount"] == 17
    sol_items_are_cleared = js(
        f"""[...document.querySelectorAll({f"{panel} .selection-option input"!r})]
          .filter((input) => input.value.startsWith('GPT-5.6 Sol|'))
          .every((input) => !input.checked)"""
    )
    assert sol_items_are_cleared is True

    js(f"document.querySelector({sol_selector!r}).click()")
    assert js("document.querySelector('#scatter-selection-summary').textContent") == (
        "22 / 22 models/efforts"
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
    assert js("document.querySelector('#scatter-selection-summary').textContent") == (
        "21 / 22 models/efforts"
    )

    js(f"document.querySelector({sol_selector!r}).click()")
    assert js("document.querySelector('#scatter-selection-summary').textContent") == (
        "22 / 22 models/efforts"
    )
    js(f"document.querySelector({trigger!r}).click()")


def verify_family_line_gap_handling():
    trigger = "#scatter-selection-trigger"
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
    set_checkbox("#genebench-pro-scaling-family-lines-toggle", True)
    initial = inspect_scatter(selector)
    assert initial["pointCount"] == 33, initial
    assert initial["xMetric"] == "tokens", initial
    assert initial["xScale"] == "log", initial
    assert (
        js(
            "document.querySelectorAll('#genebench-pro-scaling "
            "[data-point-label]').length"
        )
        == 33
    )
    assert js("document.querySelector('#genebench-pro-scaling-title').textContent") == (
        "GeneBench-Pro: Test-time compute scaling on GPT models"
    )
    assert "Tokens used" in js(
        "document.querySelector('#genebench-pro-scaling-metric').textContent"
    )
    assert (
        js(
            "document.querySelector('#genebench-pro-scaling [data-point-id]').getAttribute('aria-label')"
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

    set_select("#genebench-pro-scaling-metric-select", "cost")
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
        "document.querySelector('#genebench-pro-scaling [data-point-id]').getAttribute('aria-label')"
    )
    js(
        "document.querySelector('#genebench-pro-scaling "
        "[data-point-id=\"GPT-5.6 Sol|max\"]').dispatchEvent(new FocusEvent('focus'))"
    )
    tooltip_text = js("document.querySelector('#tooltip').textContent")
    assert "Output-token price: $30.00 / 1M" in tooltip_text, tooltip_text
    assert "Estimated API cost: $0.995" in tooltip_text, tooltip_text

    set_checkbox("#genebench-pro-scaling-log-toggle", False)
    cost_linear = inspect_scatter(selector)
    assert cost_linear["pointCount"] == 33, cost_linear
    assert cost_linear["xMetric"] == "cost", cost_linear
    assert cost_linear["xScale"] == "linear", cost_linear
    assert inspect_family_lines(selector)["valid"]
    set_checkbox("#genebench-pro-scaling-log-toggle", True)
    set_select("#genebench-pro-scaling-metric-select", "tokens")
    restored = inspect_scatter(selector)
    assert restored["xMetric"] == "tokens", restored
    assert restored["xMin"] == initial["xMin"], (initial, restored)
    assert restored["xMax"] == initial["xMax"], (initial, restored)
    assert inspect_family_lines(selector)["valid"]

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
        == "27 / 33 models/efforts"
    )
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
        == "1 / 33 models/efforts"
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
    assert not js(
        "!!document.querySelector('#genebench-pro-scaling "
        '[data-point-id="GPT-5.6 Terra|low"]\')'
    )
    assert js(
        "!!document.querySelector('#genebench-pro-scaling "
        '[data-point-id="GPT-5.6 Sol|low"]\')'
    )
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
              '#genebench-pro-scaling [data-point-id]'
            )].map((point) => point.dataset.pointId)"""
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
              section.compareDocumentPosition(document.querySelector('#chart'))
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
    assert (
        js("document.querySelectorAll('#chart [role=\"graphics-symbol\"]').length")
        == 22
    )
    assert js("document.querySelectorAll('#data-table-body tr').length") == 22
    assert (
        js(
            "document.querySelectorAll('#terminal-chart [role=\"graphics-symbol\"]').length"
        )
        == 9
    )
    assert js("document.querySelectorAll('.quadrant-legend').length") == 3
    verify_control_triggers()
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
            set_select("#gene-scatter-metric-select", metric)
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
                set_select("#exploitgym-scatter-metric-select", metric)
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
