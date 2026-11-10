---
name: diagram-authoring
metadata:
  version: 1.0.0
description: >
  Use when the user asks to create, draw, render, or update a technical diagram,
  architecture scheme, process flow, lifecycle, or system map from supplied
  information and expects editable source plus a finished image.
---

# Diagram Authoring

Produce two artifacts every time: an editable HTML source and a rendered PNG.
A prose description or a Mermaid code block alone is an incomplete result.

`<skill>` below means the directory of this loaded skill, not the current
working directory.

## Workflow

1. **Extract facts.** Pull components, flows, states and identifiers from the
   material. Ask only when a missing fact changes the diagram's meaning;
   otherwise choose the simplest reading and note the assumption.
2. **Choose the smallest explicit layout.** Columns, rows, panels, sections -
   whatever shows the material with the fewest boxes. Never default to
   Mermaid or ASCII art.
3. **Create an output directory** and copy `<skill>/assets/diagram.css` and
   `<skill>/assets/diagram.js` beside the HTML you will write. The HTML links
   these local files; never reference remote assets or CDNs.
4. **Write semantic HTML**: a title, a lead sentence, numbered sections where
   useful, real identifiers in `<code>`, short notes. Declare the canvas width
   deliberately on the body: `<body style="--width: 1200px">`. Labels default
   to English.
5. **Always call `wires([...])`** at the end of the body, even with no arrows:
   `wires([])`. The call draws the arrows and records the page height the
   renderer needs; without it the render fails.
6. **Render:**

   ```bash
   python3 <skill>/scripts/render_diagram.py OUTPUT/name.html
   ```

   The PNG comes out at 2x scale on a white background.
7. **Visually inspect the PNG.** Check for clipped text, colliding boxes or
   wires, and mislabeled arrows. A zero exit code proves nothing about how the
   diagram looks.
8. **Verify the rendered PNG.** Confirm the dimensions the renderer prints
   match the intended output (the declared width and the measured height at
   2x) and that the file is at most 1 MB. Fix the HTML and rerender until both
   hold.
9. **Return both paths**, the HTML and the PNG.

When the target repository has its own documentation asset convention (its own
diagram CSS, naming, or checks), follow that convention instead and run its
checks.

## Color quick reference

| Class | Meaning |
| --- | --- |
| `core` | the system's own process, what it runs |
| `blue` | written or derived by the system |
| `green` | retained, approved, running |
| `gray` | stored but out of play |
| `amber` | human input or external |
| `purple` | merged or shared |
| `red` | refused, failed, superseded |

## Common mistakes

- Forgetting `wires([...])` (the render fails).
- Loading assets from a CDN instead of the local copies.
- Trusting a stale PNG from an earlier render.
- Shipping without looking at the image: clipping and collisions are invisible
  to the exit code.
- Reaching for Mermaid as the default format.
- Measuring success from the exit code alone.

For layout primitives and every `wires` option see
`<skill>/references/authoring.md`; a complete worked diagram is
`<skill>/examples/agent-turn.html`.
