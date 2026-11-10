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
decoration. Arrowheads are guaranteed only for the named palette colors
(`ink blue green gray amber purple red`); an arbitrary custom color passed to
`wires` colors the line but falls back to a blue arrowhead.

## `wires(options)`

Each object in the list draws one arrow from the element matching `from` to
the element matching `to` (any CSS selector; a missing element throws):

| Option | Default | Meaning |
| --- | --- | --- |
| `from`, `to` | required | selectors of the two elements |
| `fromSide`, `toSide` | `right`, `left` | `top` / `right` / `bottom` / `left`, the side the wire leaves or enters |
| `color` | `blue` | a palette name (`ink blue green gray amber purple red`) or a CSS color for the line |
| `route` | `elbow` | `straight` or `elbow`; elbow runs along the first side's axis, turns halfway, finishes along the second's |
| `bend` | `0.5` | 0..1, moves the elbow turn nearer the start or the end, so parallel elbows do not overlap |
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

After every render:

1. Open the PNG and look at it. Text clipped by a box, a wire crossing a
   label, or two boxes touching are defects the renderer cannot see.
2. Check the printed dimensions: width x 2 by the measured height, matching
   what the diagram declares.
3. Keep the file at most 1 MB (the renderer enforces this; `optipng` helps).

Fix the HTML and rerender. Never ship a PNG you have not looked at.
