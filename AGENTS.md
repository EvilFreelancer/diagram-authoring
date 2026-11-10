# Authoring & maintaining the `diagram-authoring` skill

Agent guide for working **inside this skill repository**. Read it before
editing `SKILL.md`, the README, the shared assets, or any plugin manifest.

## Repository layout

The repo root is the flat skill folder, packaged for **Claude Code**,
**Cursor**, and **OpenAI Codex** (and installs as a plain skill folder for
others). Sibling skill repositories (e.g. `og-preview`) use the same layout.

```
diagram-authoring/
├─ .claude-plugin/plugin.json    # Claude Code manifest (no category, no skills key)
├─ .codex-plugin/plugin.json     # Codex manifest (interface block + skills: "./")
├─ .cursor-plugin/plugin.json    # Cursor manifest (displayName, no homepage/repository)
├─ assets/
│  ├─ diagram.css                # shared visual system, colors carry meaning
│  └─ diagram.js                 # wires([...]) arrows + data-height measurement
├─ scripts/render_diagram.py     # stdlib-only two-pass Chromium renderer
├─ references/authoring.md       # CSS primitives and every wires option
├─ examples/
│  ├─ agent-turn.html            # complete reference diagram (source)
│  └─ agent-turn.png             # rendered reference (generated output)
├─ tests/                        # unittest suite, offline except the smoke test
├─ evals/                        # reusable cross-model/cross-skill eval harness
│  ├─ cases/agent-turn.md        # the technical brief every eval run receives
│  ├─ prompt.md                  # clean-agent template ({{CASE_PATH}}/OUTPUT_DIR/SKILL_PATH)
│  ├─ rubric.md                  # objective checks + visual review checklist
│  ├─ README.md                  # procedure, commands, results table
│  └─ verify.py                  # stdlib-only objective verifier (CLI)
├─ SKILL.md                      # CANONICAL skill: frontmatter + workflow (repo root)
├─ README.md, AGENTS.md, LICENSE, .gitignore
```

## Golden rule: metadata stays synchronized

- `SKILL.md` at the repo root is **canonical**; `assets/`, `scripts/` and
  `references/` live next to it and are referenced by relative path.
- `name`, `version` and `description` must be identical in `SKILL.md`
  frontmatter and in all three manifests (`.claude-plugin`, `.codex-plugin`,
  `.cursor-plugin`).
- The `.claude-plugin/plugin.json` must **not** contain a `category` key and
  must **not** contain a `skills` key.
- The `.codex-plugin/plugin.json` carries `"skills": "./"` and an `interface`
  block: `displayName`, `shortDescription`, `developerName`, `category`,
  `websiteURL`.
- The `.cursor-plugin/plugin.json` carries `displayName` and, following the
  sibling convention, no `homepage` or `repository` key.
- `displayName` in both the Codex interface and the Cursor manifest equals the
  skill name, `diagram-authoring`.
- The **rpa-skills catalog is updated only after this repository is
  published**: never edit catalog files here or in the catalog before the
  first public release of this repo.

`tests/test_metadata.py` holds all of the above; extend it before changing a
manifest shape (TDD: new assertion first, see it fail, then the manifests).

## Code

- `scripts/render_diagram.py` is **standard library only**, no pip installs.
- `assets/diagram.css` and `assets/diagram.js` are copied beside every
  generated diagram, so they must stay self-contained: no remote fonts, no
  CDN references, no build step.
- Colors carry meaning across all diagrams (see the table in `SKILL.md`);
  a new palette color must be added to the CSS, to the `COLORS` map in
  `diagram.js` (arrowheads are guaranteed only for named palette colors), and
  to the documentation in the same commit.
- `examples/agent-turn.png` is generated output: regenerate it with
  `python3 scripts/render_diagram.py examples/agent-turn.html` whenever the
  example or the shared assets change.

## Tests

- The suite is **offline-first**: pure helpers, browser resolution and CLI
  error paths run without a browser. `RealRenderTests` is the deliberate
  exception: it renders the reference example with a **real Chromium** and
  skips itself when no browser binary exists.
- The test run must keep the reference example **read-only**: never let a test
  rewrite `examples/agent-turn.png` in place; renders go to a temporary
  directory.
- Keep secrets out of the repository and out of test fixtures.

## Evaluations

`evals/` is a **reusable** harness for comparing models and diagram skills
against one brief and one output contract; it stays in the repo so any run is
comparable to any other. Model selection is the host agent's job, so the
harness calls no provider API and needs no secrets.

- `evals/cases/agent-turn.md` is the brief; `evals/prompt.md` is the clean-agent
  template (`{{CASE_PATH}}`, `{{OUTPUT_DIR}}`, `{{SKILL_PATH}}` — `NONE` for a
  baseline, or any candidate skill root); `evals/rubric.md` splits objective
  checks from a visual review; `evals/verify.py` enforces the objective half.
- `evals/verify.py` is **standard library only** and imports `render_diagram` by
  path (anchored on `__file__`), so it runs from any cwd. It renders only into a
  temporary directory and never overwrites a committed or candidate PNG.
- Keep the harness free of baseline answers and hints: the rubric states the
  output contract and the six visual questions, nothing about how the reference
  example solved the case. See `evals/README.md` for the procedure.

## Documentation

All technical documentation in this repository is **English**: `SKILL.md`,
`README.md`, `AGENTS.md`, `references/`, code comments.

## Validation commands

Run all of these before every commit:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/render_diagram.py
python3 -m py_compile evals/verify.py
python3 evals/verify.py examples --name agent-turn   # renders fresh and passes
python3 -m json.tool .claude-plugin/plugin.json >/dev/null
python3 -m json.tool .codex-plugin/plugin.json >/dev/null
python3 -m json.tool .cursor-plugin/plugin.json >/dev/null
git diff --check
```

## Commit checklist

- [ ] `SKILL.md` edited where the workflow changed.
- [ ] `version` bumped and identical in `SKILL.md` and all three manifests.
- [ ] `references/authoring.md` documents any new primitive or `wires` option.
- [ ] `examples/agent-turn.png` regenerated when assets or the example moved.
- [ ] README updated for user-visible changes.
- [ ] Conventional commit, e.g. `feat: …` / `fix: …` / `docs: …`, with no
      model or agent attribution trailers.
