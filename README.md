# diagram-authoring

Turn technical material (architecture notes, process descriptions, lifecycle
specs) into an **editable HTML diagram plus a rendered 2x PNG**, drawn with a
shared visual language and rendered by a local headless Chromium. No diagram
service, no CDN, no Mermaid: the HTML source stays editable forever, the PNG
is verified by size and dimensions.

The skill drives an agent through the whole loop: extract facts, lay the
diagram out with the shared CSS primitives, draw arrows with `wires([...])`,
render, inspect the image, and fix until it is right.

## Invocation

Load the skill and hand it the material, e.g.:

> Draw the request lifecycle of this service as a diagram for our docs.

It writes `OUTPUT/name.html` next to copies of `assets/diagram.css` and
`assets/diagram.js`, renders it, and returns both paths. See
[SKILL.md](SKILL.md) for the workflow and
[examples/agent-turn.html](examples/agent-turn.html) with its rendered
[examples/agent-turn.png](examples/agent-turn.png) for a complete reference.

## Requirements

- Python 3 (standard library only);
- Chromium, Chrome or Edge (found on `PATH`, in the usual locations, or via
  `--chrome PATH` / the `CHROME` environment variable);
- the **Noto Sans** font (on Debian/Ubuntu: `apt-get install fonts-noto-core`);
- optional: `optipng` to compress the PNG below the 1 MB limit.

## Rendering a diagram by hand

```bash
python3 scripts/render_diagram.py examples/agent-turn.html
```

Expected output (the example renders at 1200 CSS px wide, 2x scale):

```
examples/agent-turn.png: 2400x1790, <N> bytes
```

Options: `--output PATH`, `--chrome PATH`, `--scale N`.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The suite is offline except one smoke test that renders the reference example
with a real Chromium and skips itself when no browser binary exists.

## Install

The repo root is the skill folder: copy or symlink it into your agent's skills
directory (`~/.claude/skills/diagram-authoring`, `~/.cursor/skills/...`,
`~/.agents/skills/...`). Part of the
**[rpa-skills](https://github.com/EvilFreelancer/rpa-skills)** marketplace;
the catalog entry is updated only after this repository is published.
