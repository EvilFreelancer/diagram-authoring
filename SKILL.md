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
   renderer needs; without it the render fails. `fromSide` and `toSide` accept
   only `top`, `right`, `bottom`, `left`; a diagonal such as `top-left` is not
   a side and now throws rather than drawing a wrong arrow. Give every arrow a
   named palette `color` (`blue`, `green`, `amber`, `purple`, `red`, `gray`,
   `ink`) so its arrowhead is drawn.
6. **Render:**

   ```bash
   python3 <skill>/scripts/render_diagram.py OUTPUT/name.html
   ```

   The PNG comes out at 2x scale on a white background.
7. **Rerender after every edit.** Any change to the HTML, CSS or JS invalidates
   the PNG on disk. Render again before you look at anything; never inspect a
   PNG that predates your last edit.
8. **Open the final PNG itself** with an image-capable read or inspection tool
   and look at it. A DOM dump, a canvas preview, an HTML screenshot or reading
   the source is **not** a substitute: only the rendered PNG shows what the
   browser actually drew. Check every label and every arrow endpoint against
   that image - clipped text, a label sitting on a box border or on a wire, a
   colliding box, an arrowhead on the wrong side. Fix the HTML, **rerender**,
   and open the new PNG again; repeat until the image you are looking at
   reflects the last fix.
9. **Verify the final render; do not trust a report or an exit code.** When the
   eval harness is available, run

   ```bash
   python3 <skill>/evals/verify.py OUTPUT_DIR --name STEM
   ```

   and require the fresh-render match it reports. When it is not available,
   render the final source into a temporary path and compare its dimensions to
   the PNG you are shipping (declared width and measured height at 2x, under
   1 MB). A successful agent summary or a zero exit code proves nothing on its
   own: the shipped PNG must equal a fresh render of the shipped HTML.
10. **Return both paths**, the HTML and the PNG.

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
- Trusting a stale PNG from an earlier render: the HTML was edited but the
  image on disk is from before the edit, so a fresh render disagrees with what
  you inspected. Rerender after the last change and open that PNG.
- Inspecting a DOM dump, a canvas preview or the HTML source instead of opening
  the final PNG: none of them show what the browser actually drew.
- Shipping without looking at the image: clipping and collisions are invisible
  to the exit code.
- Putting a label on a box border or on a wire. A label lands on the longest
  segment by default; nudge it clear with `labelShift` so it sits in open space
  and not on the line or a box edge.
- Inventing a diagonal arrow side such as `fromSide: "top-left"`. Only `top`,
  `right`, `bottom`, `left` are sides; a diagonal throws now and silently drew
  a wrong arrow before.
- Reaching for Mermaid as the default format.
- Measuring success from the exit code or an agent's own "done" report alone.

For layout primitives and every `wires` option see
`<skill>/references/authoring.md`; a complete worked diagram is
`<skill>/examples/agent-turn.html`.
