# GPT-5.6 Benchmark Visualizations

## Scope

These instructions apply to this entire project.

## Read First

- Read [docs/architecture.md](docs/architecture.md) before changing data flow,
  chart ownership, tooling, or deployment.
- Read [docs/verification.md](docs/verification.md) before changing visible
  behavior, interactions, responsive layout, or browser tests.

## Project Contract

- The project is a Vite application using strict vanilla TypeScript, HTML, and
  CSS. Production output is the static `dist/` directory.
- Use the local Node LTS, Aube, Python, Ruff, and ty versions declared in
  `mise.toml`.
- Manage JavaScript dependencies only with Aube. Do not generate npm, pnpm,
  Yarn, or Bun lockfiles.
- Pin direct dependencies exactly and commit `aube-lock.yaml`.
- Keep Aube's global virtual store disabled for this Vite project through the
  committed `.npmrc`; do not bypass its Vite compatibility protection.
- Keep Python linting, formatting, and type-checking configuration in
  `pyproject.toml`. Use `mise run lint:python`, `mise run typecheck:python`,
  and `mise run format:python:check` for checks; use
  `mise run lint:python:fix` and `mise run format:python` for explicit writes.
- Benchmark data comes from OpenAI's GPT-5.6 Sol preview and GeneBench-Pro
  articles. API token pricing comes from LiteLLM with official OpenAI and
  Anthropic fallbacks for preview or restricted models. Never estimate values
  from chart pixels or edit `data/` manually; use `mise run data:update`.
- Keep extraction validation and generation deterministic and atomic. Identify
  Vega specifications by semantic title, not payload position or record ID.
- Keep reusable calculations outside DOM rendering and cover them with Vitest.
- Preserve keyboard focus, ARIA labels, SVG titles/descriptions, and tooltip
  content, responsive containment, and stable chart dimensions.
- Update the linked documentation when architecture, behavior, verification,
  or operational risks change.

## Verification

- Run `mise run test`, then `mise run browser:test`. The first command is the
  canonical non-browser suite and includes frontend and Python linting,
  formatting checks, type-checking, unit tests, data verification, and the
  production build.
- Invoke `mise run browser:test` outside the sandbox on the first attempt so it
  can access Helium's CDP session.
- Prefer programmatic DOM, accessibility, dimension, overflow, and geometry
  assertions over screenshots.
- Restore every CDP device-metrics override after mobile verification.
- Follow the complete checklist in
  [docs/verification.md](docs/verification.md).
