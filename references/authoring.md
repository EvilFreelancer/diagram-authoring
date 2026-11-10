# Authoring reference

The shared language of every diagram: `assets/diagram.css` for layout and
color, `assets/diagram.js` for arrows. Copy both files beside the generated
HTML and link them locally. Remote assets and CDNs are never acceptable: the
renderer runs offline and a missing stylesheet renders as an unstyled page.

## Page skeleton

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Diagram title</title>
    <link rel="stylesheet" href="diagram.css" />
    <script src="diagram.js"></script>
  </head>
  <body style="--width: 1200px">
    <h1>Diagram title</h1>
    <p class="lead">One sentence on what the picture shows.</p>
    <!-- sections -->
    <script>
      wires([]);
    </script>
  </body>
</html>
```

The inline `--width` on the body is the deliberate canvas width in CSS pixels;
the renderer reads it and screenshots at exactly that width. `wires([...])`
must be the last call even when there are no arrows: `wires([])` records the
measured page height (`data-height`) that the renderer needs to size the PNG.

## CSS primitives

| Selector | What it is |
| --- | --- |
| `h1`, `.lead` | title and one-sentence summary |
| `h2`, `h3` | section and sub-section headings |
| `.cols` | grid; set `grid-template-columns` inline |
| `.row` | horizontal flex row, 12px gap |
| `.stack` | vertical flex column, 8px gap |
| `.sep` | horizontal rule between sections |
| `.panel` with `.title` | container grouping boxes (a process, a folder) |
| `.box` | a node; add `b` for bold, `<small>` or `.sub` for a second line |
| `.box core/blue/green/gray/amber/purple/red` | color by meaning (see SKILL.md) |
| `.box dashed` | dashed border, white ground: hypothetical or planned |
| `.box faded` | 55% opacity: de-emphasized |
| `.tag`, `.tag.green` | monospace identifier in accent color |
| `.note` (+ `muted italic red blue green purple`) | small explanatory text |
| `.label` (+ color classes) | small bold colored text |
| `.bracket` (+ `left right under over`, color class) | bracket marking a run of boxes |
| `.legend` with `span.core` ... `span.red` | color key at the bottom |
| `.footer` | closing remarks under the diagram |
| `code`, `.mono` | monospace inline |

Colors carry meaning across diagrams, so pick the class by meaning, not
decoration. Arrowheads exist only for the named palette colors
(`ink blue green gray amber purple red`); an arbitrary custom color passed to
`wires` colors the line but draws **no arrowhead**, so prefer a named palette
color whenever the wire needs an arrowhead.

## `wires(options)`

Each object in the list draws one arrow from the element matching `from` to
the element matching `to` (any CSS selector; a missing element throws):

| Option | Default | Meaning |
| --- | --- | --- |
| `from`, `to` | required | selectors of the two elements |
| `fromSide`, `toSide` | `right`, `left` | the side the wire leaves or enters: `top`, `right`, `bottom` or `left` only. A diagonal such as `top-left` or `bottom-right` is **not** a side and throws; there is no corner anchor |
| `color` | `blue` | a palette name (`ink blue green gray amber purple red`) or a CSS color for the line; only palette names get an arrowhead - an arbitrary CSS color draws the line with **no arrowhead**, so use a named palette color whenever an arrowhead is needed |
| `route` | `elbow` | `straight`, `elbow` or `smooth`; smooth draws a cubic Bezier curve whose control points follow the exit and entry sides, useful for feedback paths that should not share orthogonal channels |
| `bend` | `0.5` | 0..1, moves the elbow turn nearer the start or the end, so parallel elbows do not overlap. Applies only when both ends use parallel sides (both horizontal or both vertical); a mixed-axis L-shaped wire has a fixed corner and ignores `bend` |
| `fromShift`, `toShift` | `0` | -0.5..0.5, moves the end along its side by a fraction of the side's length |
| `dash` | off | dashed line |
| `both` | off | arrowhead at both ends |
| `width` | `2` | stroke width in px |
| `label` | none | text drawn on the longest segment, with a white halo |
| `labelShift` | `[0, 0]` | `[dx, dy]` pixels to nudge the label |

A compact example:

```html
<div class="cols" style="grid-template-columns: 1fr 1fr">
  <div class="stack">
    <div class="box amber b" id="in">Prompt</div>
    <div class="box blue b" id="sum">Summary</div>
  </div>
  <div class="stack">
    <div class="box core b" id="loop">Agent loop</div>
    <div class="box green b" id="store">Stored session</div>
  </div>
</div>
<script>
  wires([
    { from: "#in", to: "#loop", color: "amber", label: "starts a turn" },
    { from: "#loop", to: "#sum", color: "blue", route: "straight" },
    { from: "#sum", to: "#store", fromSide: "bottom", toSide: "top",
      color: "green", dash: true, bend: 0.3, label: "on compaction" },
  ]);
</script>
```

## Output verification

Any edit to the HTML, CSS or JS invalidates the PNG on disk, so rerender
before you look at anything. Then, after every render:

1. Open the final PNG itself with an image-capable tool and look at it. A DOM
   dump, a canvas preview, an HTML screenshot or reading the source is not a
   substitute: only the PNG shows what the browser drew. Text clipped by a box,
   a label sitting on a box border or on a wire, or two boxes touching are
   defects the renderer cannot see. Nudge a colliding label clear with
   `labelShift`.
2. Check the printed dimensions: width x 2 by the measured height, matching
   what the diagram declares.
3. Keep the file at most 1 MB (the renderer enforces this; `optipng` helps).
4. Confirm the shipped PNG is a fresh render of the shipped HTML, not a stale
   image from before the last fix. With the eval harness, `evals/verify.py`
   re-renders and compares; without it, render into a temporary path and
   compare dimensions. A zero exit code or an agent's own "done" proves
   nothing.

Fix the HTML, rerender, and open the new PNG again. Never ship a PNG you have
not looked at, and never ship one that predates your last edit.
