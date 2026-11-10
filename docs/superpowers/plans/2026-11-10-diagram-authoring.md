# Diagram Authoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent skill that turns technical material into an editable HTML diagram and a verified 2x PNG.

**Architecture:** A thin `SKILL.md` drives semantic HTML authoring. Shared CSS and JavaScript provide the visual language and arrows, while a standard-library Python renderer performs two local Chromium passes and validates the result.

**Tech Stack:** Markdown, YAML, JSON, HTML/CSS/JavaScript, Python 3 standard library, Chromium or Chrome, unittest.

---

## File map

- `SKILL.md`: triggers, mandatory artifact contract, authoring and verification workflow.
- `references/authoring.md`: layout primitives, color semantics, arrow options, common mistakes.
- `assets/diagram.css`: shared white-canvas visual system.
- `assets/diagram.js`: SVG arrows and `data-height` measurement.
- `scripts/render_diagram.py`: browser discovery, DOM metadata parsing, rendering, size validation.
- `examples/agent-turn.html` and `examples/agent-turn.png`: complete reference example.
- `tests/test_render_diagram.py`: offline renderer and metadata tests.
- `tests/test_metadata.py`: manifest consistency checks.
- `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `.cursor-plugin/plugin.json`: package metadata.
- `README.md`, `AGENTS.md`, `LICENSE`, `.gitignore`: usage, maintenance and repository hygiene.

### Task 1: Package contract and metadata tests

**Files:**
- Create: `tests/test_metadata.py`
- Create: `SKILL.md`
- Create: `.claude-plugin/plugin.json`
- Create: `.codex-plugin/plugin.json`
- Create: `.cursor-plugin/plugin.json`

- [ ] **Step 1: Write failing metadata tests**

```python
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class MetadataTests(unittest.TestCase):
    def test_manifest_names_versions_and_descriptions_match(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        name = re.search(r"^name: (.+)$", skill, re.M).group(1).strip()
        version = re.search(r"^  version: (.+)$", skill, re.M).group(1).strip()
        description = re.search(r"^description: >\n((?:  .+\n)+)", skill, re.M).group(1)
        description = " ".join(line.strip() for line in description.splitlines())
        for relative in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".cursor-plugin/plugin.json"):
            data = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            self.assertEqual(data["name"], name)
            self.assertEqual(data["version"], version)
            self.assertEqual(data["description"], description)

    def test_claude_manifest_has_no_category(self):
        data = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertNotIn("category", data)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python3 -m unittest tests.test_metadata -v`
Expected: FAIL because `SKILL.md` does not exist.

- [ ] **Step 3: Add the minimal package files**

Use name `diagram-authoring`, version `1.0.0`, and this exact description in `SKILL.md` and all manifests:

```text
Use when the user asks to create, draw, render, or update a technical diagram, architecture scheme, process flow, lifecycle, or system map from supplied information and expects editable source plus a finished image.
```

The Codex manifest contains `"skills": "./"`. The Claude manifest contains no `category` and no `skills` key. `SKILL.md` initially contains only valid frontmatter and the heading `# Diagram Authoring`.

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `python3 -m unittest tests.test_metadata -v`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add SKILL.md .claude-plugin .codex-plugin .cursor-plugin tests/test_metadata.py
git commit -m "feat: add diagram skill package contract"
```

### Task 2: Renderer tests and implementation

**Files:**
- Create: `tests/test_render_diagram.py`
- Create: `scripts/render_diagram.py`

- [ ] **Step 1: Write failing renderer tests**

```python
import unittest
from scripts import render_diagram

class RendererTests(unittest.TestCase):
    def test_reads_dimensions_from_dumped_dom(self):
        dom = '<html data-height="744"><body style="--width: 1280px">'
        self.assertEqual(render_diagram.read_dimensions(dom), (1280, 744))

    def test_default_width_is_1200(self):
        self.assertEqual(render_diagram.read_dimensions('<html data-height="600">'), (1200, 600))

    def test_missing_height_is_actionable_error(self):
        with self.assertRaisesRegex(render_diagram.RenderError, "wires"):
            render_diagram.read_dimensions("<html><body></body></html>")

    def test_rejects_non_positive_dimensions(self):
        with self.assertRaises(render_diagram.RenderError):
            render_diagram.read_dimensions('<html data-height="0">')

    def test_png_dimensions_follow_scale(self):
        self.assertEqual(render_diagram.pixel_dimensions((1280, 744), 2), (2560, 1488))

    def test_oversized_output_is_rejected(self):
        with self.assertRaisesRegex(render_diagram.RenderError, "1 MB"):
            render_diagram.check_size(1_000_001)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python3 -m unittest tests.test_render_diagram -v`
Expected: FAIL because `scripts/render_diagram.py` does not exist.

- [ ] **Step 3: Implement the minimal renderer**

Implement these public functions with the tested behavior:

```python
class RenderError(RuntimeError):
    pass

def read_dimensions(dom):
    height_match = re.search(r'data-height=["\'](\d+)["\']', dom)
    if not height_match:
        raise RenderError("the source recorded no height; call wires([...]) after diagram.js")
    width_match = re.search(r"--width\s*:\s*(\d+)px", dom)
    width = int(width_match.group(1)) if width_match else 1200
    height = int(height_match.group(1))
    if width <= 0 or height <= 0:
        raise RenderError("diagram dimensions must be positive")
    return width, height

def pixel_dimensions(css_dimensions, scale):
    width, height = css_dimensions
    return width * scale, height * scale

def check_size(size_bytes):
    if size_bytes > 1_000_000:
        raise RenderError("rendered PNG exceeds 1 MB; simplify the diagram or run optipng")
```

Add a CLI accepting `source`, `--output`, `--chrome`, and `--scale` (default 2). Resolve the browser from the flag, `CHROME`, then platform candidates. Run a DOM dump followed by a screenshot using a temporary profile and the same Chromium flags as the Coddy renderer. Require a regular source file, check Noto Sans with `fc-list` where available, optionally run `optipng -quiet -o2`, call `check_size`, and print `<output>: <pixel width>x<pixel height>, <bytes> bytes`. Convert expected failures to `RenderError` and exit 1 with a clear message.

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `python3 -m unittest tests.test_render_diagram -v`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/render_diagram.py tests/test_render_diagram.py
git commit -m "feat: render diagrams with local Chromium"
```

### Task 3: Shared visual assets and reference example

**Files:**
- Create: `assets/diagram.css`
- Create: `assets/diagram.js`
- Create: `examples/agent-turn.html`
- Create: `examples/agent-turn.png`
- Modify: `tests/test_render_diagram.py`

- [ ] **Step 1: Add a failing real-render test**

```python
def test_example_renders_at_twice_css_size(self):
    source = ROOT / "examples" / "agent-turn.html"
    output = ROOT / "examples" / "agent-turn.png"
    render_diagram.render(source, output, scale=2)
    self.assertLessEqual(output.stat().st_size, 1_000_000)
    self.assertEqual(render_diagram.png_dimensions(output), (2400, render_diagram.png_dimensions(output)[1]))
```

Skip only when no Chromium binary exists. Add a small stdlib PNG-header reader named `png_dimensions` that validates the PNG signature and reads the IHDR width and height.

- [ ] **Step 2: Run the test and verify RED**

Run: `python3 -m unittest tests.test_render_diagram.RendererTests.test_example_renders_at_twice_css_size -v`
Expected: FAIL because the assets and example do not exist.

- [ ] **Step 3: Add the shared assets and example**

Port `docs/assets/diagrams/diagram.css` and `diagram.js` from Coddy without changing their public class names or `wires` options. Write `examples/agent-turn.html` with `--width: 1200px`, an English title and lead, three numbered stages, semantic colors, local `../assets/diagram.css` and `../assets/diagram.js` references, and a final `wires([...])` call connecting the input surfaces, session manager, agent, tools, stored session, and background wake path.

- [ ] **Step 4: Render and verify GREEN**

Run: `python3 scripts/render_diagram.py examples/agent-turn.html`
Expected: `examples/agent-turn.png: 2400x<even height>, <under 1000000> bytes`.

Run: `python3 -m unittest tests.test_render_diagram -v`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add assets examples tests/test_render_diagram.py
git commit -m "feat: add shared diagram language and example"
```

### Task 4: Agent instructions and human documentation

**Files:**
- Modify: `SKILL.md`
- Create: `references/authoring.md`
- Create: `README.md`
- Create: `AGENTS.md`
- Create: `LICENSE`
- Create: `.gitignore`

- [ ] **Step 1: Complete the skill workflow**

Document the mandatory sequence: extract facts, choose explicit layout, copy shared assets beside the generated source, write HTML, call `wires`, render, inspect, verify dimensions and size, return both paths. State that prose-only output is incomplete. Include a quick-reference table of color meanings and a common-mistakes section covering missing `wires`, remote assets, stale PNG, unexamined clipping, and Mermaid as the default format.

- [ ] **Step 2: Add the detailed reference and maintenance docs**

`references/authoring.md` lists every CSS primitive and every `wires` option with one compact example. `README.md` shows invocation and renderer commands. `AGENTS.md` defines the flat layout, metadata synchronization, test commands, and the rule that the catalog follows publication. Add the MIT license and ignore Python caches and temporary render profiles.

- [ ] **Step 3: Run all local checks**

Run: `python3 -m unittest discover -s tests -v`
Run: `python3 -m py_compile scripts/render_diagram.py`
Run: `python3 -m json.tool .claude-plugin/plugin.json >/dev/null`
Run: `python3 -m json.tool .codex-plugin/plugin.json >/dev/null`
Run: `python3 -m json.tool .cursor-plugin/plugin.json >/dev/null`
Expected: all commands exit 0.

- [ ] **Step 4: Commit**

```bash
git add SKILL.md references README.md AGENTS.md LICENSE .gitignore
git commit -m "docs: teach complete diagram authoring workflow"
```

### Task 5: Clean-agent acceptance and refactor

> Superseded in part by **Task 7: Reusable evaluation harness**, which moves the
> clean-agent comparison into the repository under `evals/` so it is reusable
> across models and skills rather than a one-off acceptance run. The intent here
> stands; the durable form of it is Task 7.

**Files:**
- Modify only files whose defects the acceptance runs expose.

- [ ] **Step 1: Complete baseline runs**

Collect the baseline artifacts and record which agents produced no artifact, chose an unrelated visual system, omitted checks, or failed to render. Do not show baseline answers to the acceptance agents.

- [ ] **Step 2: Run two clean agents with the skill**

Give each a fresh agent only the new skill path and the same technical brief, with output under separate temporary directories. Require actual HTML and PNG files, English labels, local rendering, and verification. Use independent external models.

- [ ] **Step 3: Verify artifacts directly**

For each output pair run the bundled renderer again, check the PNG signature, dimensions, size, and visual readability. Confirm that no Coddy path or external rendering service was used.

- [ ] **Step 4: Close observed gaps and rerun**

Add only instructions or code that address observed failures, then rerun the affected unit tests and the same clean-agent scenario until both agents satisfy the contract.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test: verify diagram skill with clean agents"
```

### Task 6: Cross-review and final verification

- [ ] **Step 1: Build a self-contained review brief**

Include the intent, final file set and full diff. Exclude rendered PNG bytes while requiring reviewers to assess the HTML and the reported image checks.

- [ ] **Step 2: Run `/crossreview`**

Wait for every reviewer, retry transient failures, and keep reviewers blind to one another.

- [ ] **Step 3: Verify every finding**

Read the named file and reproduce each claimed defect. Classify each as fix, not worth fixing, rejected, or open. Apply confirmed fixes and rerun the relevant tests.

- [ ] **Step 4: Run the final gate**

Run: `python3 -m unittest discover -s tests -v`
Run: `git status --short --branch` in both `diagram-authoring` and `coddy-agent`.
Expected: tests pass, the new repository contains only intended changes, and Coddy remains unchanged.

- [ ] **Step 5: Commit and report**

Commit any review fixes with `fix: address diagram skill review findings`. Report the new skill path, artifact example, clean-agent results, cross-review verdict, test evidence, and the deliberate absence of a catalog entry until publication.

### Task 7: Reusable evaluation harness

The user asked to keep the clean-agent comparison in the repository so that
other models and other skills can be measured against the same brief and the
same contract. This task turns the one-off acceptance run of Task 5 into a
reusable harness under `evals/`, developed test-first.

**Files:**
- Create: `evals/cases/agent-turn.md`
- Create: `evals/prompt.md`
- Create: `evals/rubric.md`
- Create: `evals/README.md`
- Create: `evals/verify.py`
- Create: `tests/test_eval_verify.py`
- Modify: `README.md`, `AGENTS.md`, this plan, and the design spec

- [x] **Step 1: Write the verifier tests first**

`tests/test_eval_verify.py` uses `unittest` and temporary directories and covers
the objective contract: a missing HTML/PNG pair, a remote asset, Cyrillic in
visible text, an unresolved local asset, the committed example passing with
`--skip-render`, a width mismatch, and a real fresh-render comparison that never
overwrites the committed reference PNG. It reuses `scripts/render_diagram.png_dimensions`
and a tiny generated-PNG helper rather than duplicating renderer logic. Observe
RED before `evals/verify.py` exists.

- [x] **Step 2: Implement the standard-library verifier**

`evals/verify.py` is a CLI (`python3 evals/verify.py OUTPUT_DIR --name agent-turn
[--skip-render]`) that validates the same-stem pair, the inline body `--width`
and `wires(...)` call, local `diagram.css`/`diagram.js` resolving on disk, the
absence of remote assets, the absence of Cyrillic in visible text (ignoring
script/style/comments), a valid PNG under 1 MB at twice the declared CSS width
with positive height, and — unless `--skip-render` — a fresh re-render into a
temporary directory whose dimensions match the candidate. It imports
`render_diagram` by adding the repository `scripts/` directory to `sys.path`
based on `__file__`, independent of the current directory, and uses no
third-party packages. It prints concise `PASS` lines and exits 0, or an
actionable message to stderr and exit 1. Reach GREEN.

- [x] **Step 3: Write the case, prompt, rubric, and procedure**

`evals/cases/agent-turn.md` holds the exact Russian technical brief.
`evals/prompt.md` is the self-contained clean-agent template with `{{CASE_PATH}}`,
`{{OUTPUT_DIR}}`, and `{{SKILL_PATH}}` (the last is `NONE` for a baseline or the
root of any candidate skill), forbidding other skills and baseline answers and
requiring editable HTML, a real PNG, English labels, local rendering, no external
service, visual inspection, and returned paths and dimensions. `evals/rubric.md`
splits objective artifact checks from a six-question visual review and carries no
baseline solution. `evals/README.md` gives the exact procedure (one fresh agent
per model+skill, a unique output directory, no baseline answers, verifier first,
then the visual rubric), baseline and candidate commands, a results table
template, and the note that model selection is the host agent's job, so no
provider API or secrets are needed.

- [x] **Step 4: Document the harness and validate**

Add the eval commands and layout to `README.md` and `AGENTS.md`, and a concise
eval-harness section to the design spec and this plan, reflecting the added
requirement without rewriting earlier decisions. Run
`python3 -m unittest discover -s tests -v`, `python3 -m py_compile evals/verify.py`,
`python3 evals/verify.py examples --name agent-turn` (renders fresh and passes),
and `git diff --check`.

- [x] **Step 5: Commit**

```bash
git add -A
git commit -m "test: add reusable diagram evaluations"
```
