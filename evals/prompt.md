# Diagram task prompt (clean-agent template)

A self-contained brief for one fresh agent with no memory of any prior run.
Fill the three placeholders and send the result as the agent's only task. The
same template runs a baseline (no skill) and any candidate skill, so results
across models and skills stay comparable.

Placeholders:

- `{{CASE_PATH}}` — path to the case file with the technical brief, e.g.
  `evals/cases/agent-turn.md`.
- `{{OUTPUT_DIR}}` — a fresh, empty directory this run writes into. It must be
  unique per model+skill run; never reuse a directory from an earlier run.
- `{{SKILL_PATH}}` — either the literal `NONE` (a baseline run: the agent gets
  no skill and relies on its own judgement) or the root folder of any candidate
  skill to evaluate (for example the `diagram-authoring` skill folder, or a
  different diagram skill, or a modified copy of this one). Point it wherever
  you like; the prompt tells the agent to read only that folder.

---

## Task

You are producing one technical diagram from a written brief. Work only from
the files named below. You have no memory of any other run and must not seek
any.

The brief is in this file — read it first:

    {{CASE_PATH}}

Write your artifacts into this directory (create it if it does not exist):

    {{OUTPUT_DIR}}

Your skill for this task is:

    {{SKILL_PATH}}

If `{{SKILL_PATH}}` is `NONE`, you have no skill: rely on your own judgement
about how to build a clear technical diagram. If it names a folder, open that
folder's entry point (for a skill, its `SKILL.md`) and follow its workflow.
Read **only** that folder and the case file. Do **not** open, list, or read any
other skill, any other agent's skills directory, or any file that looks like a
reference answer, example solution, or grading key. Judging happens elsewhere;
your job is only to produce the diagram.

## Output contract (mandatory)

Produce exactly two files in `{{OUTPUT_DIR}}`, sharing one stem:

1. `<stem>.html` — the editable diagram source. It must:
   - declare its width inline on the body, e.g.
     `<body style="--width: 1200px">`;
   - load its stylesheet and its arrow script **from local files** named
     `diagram.css` and `diagram.js` (copy them beside the source or reference
     them by a relative path that resolves on disk);
   - call `wires([...])` after the diagram markup so arrows are drawn and the
     height is measured (`wires([])` is fine when there are no arrows);
   - reference **no remote resource**: no `http://`, `https://`, or `//`
     scripts, stylesheets, fonts, or images. Everything renders offline.
2. `<stem>.png` — the rendered image of that source, produced by rendering the
   HTML **locally** (a headless Chromium or Chrome you run yourself). Do not
   use any external rendering or diagram service. The PNG must be the actual
   render of the HTML you wrote, at 2x the declared CSS width, and under 1 MB.

Use `agent-turn` as the stem unless the case file names another.

## Rules

- **English labels.** The brief may be in another language; every label, title,
  and caption in the diagram must be in English.
- **Local rendering only.** Render with a browser on this machine. No CDN, no
  diagram service, no network fetch of assets.
- **Editable source.** The HTML is the deliverable, not a screenshot of some
  other tool's canvas. Hand-author the markup.
- **Inspect your own output.** After rendering, open or read the PNG and check
  it: is the meaning of the brief captured? Is the reading order clear? Is any
  text clipped or overflowing its box? Do any boxes or arrows collide or
  overlap? Do arrows point the right way and connect the right things? Does
  color carry consistent meaning? Fix the HTML and render again until it is
  genuinely readable — do not ship the first draft unchecked.

## Report back

When you are done, state plainly:

- the full path to the HTML file you wrote;
- the full path to the PNG file you wrote;
- the PNG's pixel dimensions (width x height) and its size in bytes;
- one or two sentences on how you checked the rendered image and what you
  fixed after looking at it.
