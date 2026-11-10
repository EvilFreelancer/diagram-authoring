# Diagram Authoring Skill Design

## Purpose

Create an independent `diagram-authoring` skill that turns a technical description into an editable HTML diagram and a rendered PNG. It carries the documentation-diagram conventions of Coddy into a reusable skill without importing or modifying Coddy.

## Repository and packaging

The skill lives in its own repository at `/home/pasha/Repository/skills/diagram-authoring` and follows the flat layout of the other `rpa-skills` repositories:

- `SKILL.md` is the canonical trigger and workflow document;
- `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, and `.cursor-plugin/plugin.json` carry matching names, versions, and descriptions;
- `assets/diagram.css` and `assets/diagram.js` provide the shared visual language and SVG arrows;
- `scripts/render_diagram.py` renders one HTML source into a same-name PNG using only Python's standard library and a local Chromium or Chrome binary;
- `references/authoring.md` holds the detailed layout and arrow reference;
- `examples/` contains one complete HTML/PNG example;
- `tests/` contains offline unit tests and a real-renderer smoke test;
- `README.md`, `AGENTS.md`, `LICENSE`, and `.gitignore` complete the repository.

The `rpa-skills` catalog is deliberately unchanged until the new skill repository is public. Its rules require the skill release to precede the catalog entry.

## Output contract

For every request the agent produces both `<name>.html` and `<name>.png`, then returns their paths. The HTML is the editable source; the PNG is the presentation artifact. A response that only explains how to draw a diagram is incomplete.

The source uses a deliberate CSS width, a title, a one-line lead, numbered sections where they clarify the reading order, real technical names, short explanatory notes, and English labels. It loads the shared CSS and JavaScript and always calls `wires([...])`, including `wires([])` when there are no arrows.

The PNG uses an opaque white background and twice the CSS dimensions. It must be below 1 MB. The agent checks the actual file dimensions and size rather than assuming the renderer succeeded.

## Visual language

The shared CSS carries the Coddy conventions:

- `core` frames the system's own processes;
- blue marks written or derived state;
- green marks retained, approved, or running state;
- gray marks material that is stored but out of play;
- amber marks human or external input;
- purple marks a merge or shared resource;
- red marks refusal, failure, or superseded behavior.

The layout uses explicit HTML and CSS grids rather than automatic graph layout. Reusable primitives cover boxes, panels, columns, stacks, notes, brackets, legends, and footers. `diagram.js` draws straight or elbow SVG arrows between named elements and records the computed body height as `data-height` after fonts are ready.

Mermaid is not the authoring format. A text-first format such as Mermaid may be suggested only when the user explicitly asks for it, outside this skill's default output contract.

## Renderer

The renderer performs two local Chromium passes:

1. Dump the DOM, read the body's `--width`, and require `data-height` from `diagram.js`.
2. Screenshot the exact CSS width and height at scale factor 2 with a temporary browser profile.

The Python script accepts an HTML path and an optional output path. It discovers Chromium or Chrome across Linux, macOS, and Windows, honors `CHROME`, and reports actionable errors for a missing browser, missing source, missing `data-height`, invalid dimensions, browser failure, or an oversized result. Noto Sans is required by the visual contract; missing fonts are reported rather than silently accepted. `optipng` is optional.

No Node installation, package download, external rendering service, or Coddy checkout is needed. Sources must be self-contained and must not load remote assets.

## Agent workflow

1. Extract entities, boundaries, direction, lifecycle, and invariants from the user's material. Ask only when a missing fact would change the meaning of the picture.
2. Choose the smallest layout that makes those relationships readable.
3. Copy the shared assets beside the source or otherwise use the skill's documented local-asset workflow.
4. Write semantic HTML with short labels and notes.
5. Render with the bundled script.
6. Inspect the PNG, verify dimensions and size, and fix clipping, collisions, misleading arrows, or stale output before returning the files.

When the target repository has its own documentation asset convention, the agent places the resulting pair there and runs that repository's checks. The default elsewhere is a user-named output folder or the current workspace.

## Testing

Skill development follows RED-GREEN-REFACTOR:

- clean baseline agents receive a technical description without the skill and must produce an actual diagram;
- the same scenarios are run with only the new skill as added guidance;
- at least two independent clean agents must produce valid HTML and PNG outputs;
- unit tests cover source validation, browser discovery, DOM metadata parsing, error paths, and output-size enforcement;
- a real Chromium smoke test proves that the example renders with the expected 2x dimensions and below 1 MB;
- metadata tests keep the three manifests and `SKILL.md` synchronized;
- independent cross-review checks both the instructions and the implementation, with every finding verified by the orchestrator.

The Coddy repository remains unchanged throughout.
