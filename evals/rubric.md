# Evaluation rubric

Two halves. The **objective checks** are automated by `evals/verify.py`; run
that first and it must pass before any visual review is worth doing. The
**visual review** is a human (or a reviewing agent) looking at the rendered PNG
and answering the checklist below. Keep the two separate: a diagram can pass
every automated check and still be unreadable, and the verifier never claims to
judge meaning.

## Objective checks (automated)

Run:

```bash
python3 evals/verify.py OUTPUT_DIR --name agent-turn
```

`verify.py` confirms, mechanically:

- `<name>.html` and `<name>.png` both exist in the output directory;
- the HTML declares `--width` inline on the `<body>` and calls `wires(...)`;
- no remote script, stylesheet, font, or image is referenced;
- `diagram.css` and `diagram.js` are referenced locally and resolve on disk;
- visible text carries no Cyrillic (script, style, and comment content is
  ignored), so labels follow the English contract;
- the PNG is a valid PNG under 1 MB whose width is exactly twice the declared
  CSS width and whose height is positive;
- a fresh local re-render of the HTML matches the candidate PNG's dimensions
  (unless `--skip-render`), so the image is not stale or hand-faked.

These are pass/fail gates. A run that fails any of them is not scored on
visual quality; it is sent back.

## Visual review checklist (manual)

Open the PNG and answer each item. Record a short note per item, not just a
check, so runs are comparable. The brief for this case is the agent-turn flow:
surfaces → session manager → agent (rules/skills, LLM, tools/MCP) → stored
session → broadcast back → background wake.

1. **Meaning.** Does the diagram actually depict the brief? Every element the
   brief names should be present and connected as the brief describes: the
   input surfaces, the shared session manager that creates the turn, the agent
   reading rules/skills and calling the LLM and (when needed) tools/MCP, the
   result saved to the file session and broadcast back to all surfaces, and
   background tasks able to wake the agent after the turn ends. Missing or
   invented structure is a defect.
2. **Reading order.** Can a reader follow the flow top-to-bottom or
   left-to-right without hunting? The main path should read as a sequence;
   side paths (background wake, broadcast back) should be visually secondary,
   not competing with the main line.
3. **Clipping.** Is any text cut off, overflowing its box, or running past the
   canvas edge? Are labels truncated? Boxes sized to their content rather than
   fixed and too small?
4. **Collisions.** Do boxes overlap each other? Do arrows pass through boxes
   they do not connect? Do labels sit on top of lines or other text?
5. **Arrows.** Does every arrow start and end on the right elements? Are
   directions correct (input flows toward the agent, results flow back out)?
   Are arrowheads present and legible? Is the background-wake / broadcast-back
   relationship drawn as a return path rather than a stray line?
6. **Color semantics.** Is color used consistently and meaningfully (for
   example surfaces vs. the agent vs. storage vs. an async wake), or is it
   decorative? Does the same kind of thing always get the same color? Is text
   legible against its background in every box?

Score each item as good / acceptable / poor with a one-line reason. When
comparing runs, the objective gate is a hard filter; the visual notes are what
separate two runs that both pass it.

## What this rubric deliberately does not do

It gives no reference answer, no "correct" layout, and no hints about how the
baseline solved the case. The only contract is the output contract in
`evals/prompt.md` and the checks above. That keeps the harness reusable: any
model against any skill is judged on the same objective gates and the same six
visual questions.
