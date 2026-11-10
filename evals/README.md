# Reusable diagram evaluations

A harness for comparing how well different models, and different diagram
skills, turn one technical brief into a real, editable, rendered diagram. It
lives in this repository on purpose: the case, the prompt, the rubric, and the
verifier are shared so any run can be lined up against any other.

The harness is model-agnostic and skill-agnostic. It calls no provider API and
needs no secrets: **the host agent (you, or whatever orchestrates the runs)
picks the model and starts each fresh agent.** The harness only fixes the
brief, the output contract, and how the result is judged.

## What is here

- `cases/agent-turn.md` — the technical brief (a Russian description of Coddy's
  agent-turn flow). This is the input every run gets.
- `prompt.md` — the clean-agent template with `{{CASE_PATH}}`, `{{OUTPUT_DIR}}`,
  and `{{SKILL_PATH}}` placeholders. It is self-contained and forbids reading
  other skills or any baseline answer.
- `rubric.md` — the objective artifact checks (what `verify.py` enforces) plus a
  six-question visual review checklist.
- `verify.py` — a standard-library CLI that decides whether one output directory
  satisfies the output contract.

## Procedure

For **each** model+skill combination you want to compare:

1. **One fresh agent per run.** Start an agent with no memory of any other run.
   Do not continue a previous conversation, and do not tell the agent anything
   about how other runs solved the case.
2. **A unique output directory.** Give the run its own empty directory, e.g.
   `runs/baseline-gpt-x/` or `runs/diagram-authoring-model-y/`. Never reuse a
   directory; a stale PNG from an earlier run would pass the checks for the
   wrong reason.
3. **No baseline answers in view.** The agent must not see `examples/`, another
   run's output, or any reference solution. The prompt already forbids it; keep
   the working directory clean so nothing leaks in.
4. **Fill the prompt and run it.** Take `prompt.md`, substitute the three
   placeholders, and hand the result to the fresh agent as its only task.
   - For a **baseline** run, set `{{SKILL_PATH}}` to `NONE`.
   - For a **candidate** run, set `{{SKILL_PATH}}` to the root of the skill
     under test.
5. **Run the verifier.** It is the hard gate:

   ```bash
   python3 evals/verify.py runs/<this-run-dir> --name agent-turn
   ```

   It prints one `PASS` line per check and exits 0, or prints an actionable
   message to stderr and exits 1. A run that fails the verifier is sent back,
   not scored on quality.
6. **Then the visual rubric.** Only for runs that pass the verifier, open the
   PNG and answer the six questions in `rubric.md` (meaning, reading order,
   clipping, collisions, arrows, color semantics) with a short note each.

## Commands

Baseline (no skill), rendering checked fresh:

```bash
# 1. prepare a unique output dir
mkdir -p runs/baseline
# 2. fill evals/prompt.md: {{CASE_PATH}}=evals/cases/agent-turn.md,
#    {{OUTPUT_DIR}}=runs/baseline, {{SKILL_PATH}}=NONE
#    and give it to one fresh agent (model chosen by the host).
# 3. verify the artifacts the agent wrote
python3 evals/verify.py runs/baseline --name agent-turn
```

Candidate (a skill under test), rendering checked fresh:

```bash
mkdir -p runs/candidate
# fill evals/prompt.md: {{CASE_PATH}}=evals/cases/agent-turn.md,
# {{OUTPUT_DIR}}=runs/candidate, {{SKILL_PATH}}=/path/to/candidate/skill
# give it to one fresh agent, then:
python3 evals/verify.py runs/candidate --name agent-turn
```

Offline-only check (no browser, skips the fresh re-render):

```bash
python3 evals/verify.py runs/candidate --name agent-turn --skip-render
```

The verifier imports `scripts/render_diagram.py` by path (anchored on its own
location), so it works from any current directory, and it always renders into a
temporary directory — it never overwrites a committed or candidate PNG.

## Results table template

Copy this into your notes and fill one row per run. Keep the objective column
as pass/fail from the verifier; the visual columns are the rubric notes.

| Model | Skill (`NONE` = baseline) | Output dir | Verifier | Meaning | Reading order | Clipping | Collisions | Arrows | Color | Notes |
|-------|---------------------------|------------|----------|---------|---------------|----------|------------|--------|-------|-------|
|       |                           |            | PASS/FAIL |         |               |          |            |        |       |       |
|       |                           |            | PASS/FAIL |         |               |          |            |        |       |       |

## Notes on fairness

- **Model selection is the host's job.** This harness never talks to a model
  provider, so it needs no API key and no network. You decide which model backs
  each fresh agent and start it yourself.
- **Same brief, same contract, same rubric** for every run; only the model and
  the skill change. That is what makes the rows comparable.
- **`{{SKILL_PATH}}` is just a folder.** Point it at this skill, at a modified
  copy, or at a completely different diagram skill; the prompt tells the agent
  to read only that folder and the case, so nothing else leaks in.
