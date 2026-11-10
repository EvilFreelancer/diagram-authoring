#!/usr/bin/env python3
"""Verify one candidate output directory against the diagram output contract.

Standard library only. This is the objective half of the reusable
evaluation harness in evals/: a fresh agent (any model, with or without
a skill) writes <name>.html and <name>.png into an output directory,
and this verifier decides whether the pair satisfies the contract that
SKILL.md promises. The subjective half (visual review) lives in
evals/rubric.md.

Checks, in order:
  1. <name>.html and <name>.png exist in the output directory;
  2. the HTML declares --width inline on the body and calls wires(...);
  3. no remote script, stylesheet or asset is referenced;
  4. diagram.css and diagram.js are referenced locally and resolve on
     disk relative to the HTML;
  5. visible text carries no Cyrillic (script, style and comment
     content is ignored), so labels follow the English contract;
  6. the PNG is a valid PNG under 1 MB whose actual width is exactly
     twice the declared CSS width and whose height is positive;
  7. unless --skip-render, the HTML is re-rendered into a temporary
     directory with scripts/render_diagram.py and the fresh dimensions
     must match the candidate PNG.

Usage:
    python3 evals/verify.py OUTPUT_DIR [--name NAME] [--skip-render]

Prints one PASS line per check and exits 0; on any failure prints an
actionable message to stderr and exits 1.
"""

import argparse
import io
import re
import sys
import tempfile
from pathlib import Path

# The renderer lives in the repository's scripts/ folder next to this
# file's parent; anchoring on __file__ keeps the import independent of
# the current working directory.
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import render_diagram

MAX_OUTPUT_BYTES = 1_000_000
EXPECTED_SCALE = 2

# The body's inline --width and the wires call are the two marks of a
# source that follows the skill's contract. BODY_WIDTH_RE is the
# renderer's own anchored pattern: <body style="...--width: Npx">.
BODY_WIDTH_RE = render_diagram.BODY_WIDTH_RE
WIRES_RE = re.compile(r"\bwires\s*\(", re.IGNORECASE)

# Asset-loading references: src/href attributes and CSS url()/@import.
ATTR_URL_RE = re.compile(r"(?:src|href)\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
CSS_URL_RE = re.compile(r"url\(\s*[\"']?\s*([^)\"']+)", re.IGNORECASE)
CSS_IMPORT_RE = re.compile(r"@import\s+(?:url\()?\s*[\"']?\s*(\S+)", re.IGNORECASE)
REMOTE_PREFIXES = ("http://", "https://", "//")

# Cyrillic letters (Russian and its neighbours) in visible text break
# the English-label contract of the skill.
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
SCRIPT_BLOCK_RE = re.compile(r"<script\b.*?</script\s*>", re.IGNORECASE | re.DOTALL)
STYLE_BLOCK_RE = re.compile(r"<style\b.*?</style\s*>", re.IGNORECASE | re.DOTALL)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

LOCAL_ASSETS = ("diagram.css", "diagram.js")

# diagram.js anchors an arrowhead on one of four sides only. A diagonal
# such as "top-left" is not a side: the browser used to fall back to a
# default silently and drew the wrong arrow, so the verifier refuses any
# fromSide/toSide value outside this set before starting a browser.
VALID_SIDES = ("top", "right", "bottom", "left")
SIDE_VALUE_RE = re.compile(
    r"""(?:fromSide|toSide)\s*:\s*["']([^"']*)["']""",
    re.IGNORECASE,
)


class VerifyError(RuntimeError):
    """A contract violation with a message the operator can act on."""


def _require(condition, message):
    if not condition:
        raise VerifyError(message)


def _asset_references(html):
    """Every URL an asset could load from: src/href attributes and CSS."""
    urls = []
    urls.extend(ATTR_URL_RE.findall(html))
    urls.extend(CSS_URL_RE.findall(html))
    urls.extend(CSS_IMPORT_RE.findall(html))
    return urls


def check_pair(output_dir, name):
    """Return (html_path, png_path) after requiring both to exist."""
    output_dir = Path(output_dir)
    _require(
        output_dir.is_dir(),
        f"the output directory {output_dir} does not exist or is not a "
        "directory; pass the directory the agent wrote its artifacts into",
    )
    html_path = output_dir / f"{name}.html"
    png_path = output_dir / f"{name}.png"
    _require(
        html_path.is_file(),
        f"{html_path} is missing; the contract requires an editable HTML "
        f"source named {name}.html in the output directory",
    )
    _require(
        png_path.is_file(),
        f"{png_path} is missing; the contract requires a rendered PNG "
        f"named {name}.png next to the {name}.html source",
    )
    return html_path, png_path


def check_html_contract(html):
    """Require the inline body --width and the wires call; return the width."""
    width_match = BODY_WIDTH_RE.search(html)
    _require(
        width_match is not None,
        "the HTML declares no inline --width on the body (expected "
        '<body style="--width: 1200px">); the renderer and this verifier '
        "read the diagram width from that declaration, not from a nested "
        "element",
    )
    _require(
        WIRES_RE.search(html) is not None,
        "the HTML never calls wires(...); load diagram.js and call "
        "wires([...]) after the diagram markup (wires([]) when there are "
        "no arrows) so the height is measured and arrows are drawn",
    )
    return int(width_match.group(1))


def check_arrow_sides(html):
    """Reject any fromSide/toSide value that is not one of the four sides.

    diagram.js anchors an arrowhead on top, right, bottom or left only. A
    diagonal such as "top-left" is not a side and used to fall back to a
    default silently, drawing the wrong arrow while the render still
    reported success. Fail the objective gate here, before a browser runs,
    naming each offending value.
    """
    bad = sorted(
        {
            value
            for value in SIDE_VALUE_RE.findall(html)
            if value.lower() not in VALID_SIDES
        }
    )
    _require(
        not bad,
        "the HTML uses arrow side value(s) "
        + ", ".join(f'"{v}"' for v in bad)
        + "; fromSide and toSide accept only "
        + ", ".join(VALID_SIDES)
        + " - a diagonal such as \"top-left\" is not a side and would "
        "draw the wrong arrow",
    )


def check_no_remote_assets(html):
    """Reject any remote script, stylesheet or asset reference."""
    offenders = [
        url
        for url in _asset_references(html)
        if url.lower().startswith(REMOTE_PREFIXES)
    ]
    _require(
        not offenders,
        "the HTML references remote assets: "
        + ", ".join(sorted(set(offenders)))
        + "; sources must be self-contained and load only the local "
        "diagram.css and diagram.js, so the diagram renders offline and "
        "stays editable forever",
    )


def check_local_assets(html, html_path):
    """Require each shared asset to be referenced locally and to resolve."""
    references = {}
    for url in _asset_references(html):
        if url.lower().startswith(REMOTE_PREFIXES):
            continue
        for asset in LOCAL_ASSETS:
            if Path(url).name == asset:
                references.setdefault(asset, []).append(url)
    for asset in LOCAL_ASSETS:
        urls = references.get(asset)
        _require(
            bool(urls),
            f"the HTML does not reference the local {asset}; copy "
            f"assets/{asset} beside the source (or point at it with a "
            "relative path) and load it from the page",
        )
        resolved = [
            (html_path.parent / url).resolve()
            for url in urls
        ]
        _require(
            any(path.is_file() for path in resolved),
            f"the {asset} reference {urls[0]!r} does not resolve on disk "
            f"relative to {html_path}; the file must exist next to the "
            "source for the diagram to render",
        )


def check_visible_text_is_english(html):
    """Reject Cyrillic letters in visible text; scripts, styles, comments pass."""
    visible = COMMENT_RE.sub(" ", html)
    visible = SCRIPT_BLOCK_RE.sub(" ", visible)
    visible = STYLE_BLOCK_RE.sub(" ", visible)
    _require(
        CYRILLIC_RE.search(visible) is None,
        "visible text contains Cyrillic characters; the output contract "
        "requires English labels in the diagram (the brief may be Russian, "
        "the picture must read in English)",
    )


def check_png(png_path, declared_width):
    """Require a valid PNG under 1 MB at exactly 2x the declared width."""
    size = png_path.stat().st_size
    _require(
        size <= MAX_OUTPUT_BYTES,
        f"{png_path} is {size} bytes and exceeds the 1 MB limit; simplify "
        "the diagram or compress it with optipng",
    )
    try:
        width, height = render_diagram.png_dimensions(png_path)
    except render_diagram.RenderError as exc:
        raise VerifyError(str(exc)) from exc
    expected_width = declared_width * EXPECTED_SCALE
    _require(
        width == expected_width,
        f"{png_path} is {width}x{height} px but the HTML declares "
        f"--width: {declared_width}px, which at the required 2x scale "
        f"needs a PNG {expected_width} px wide; re-render with "
        "python3 scripts/render_diagram.py <source>",
    )
    _require(
        height > 0,
        f"{png_path} declares a non-positive height {height}; the file "
        "is not a usable render",
    )
    return width, height


def check_fresh_render(html_path, png_path, name, candidate_dims):
    """Re-render into a temporary directory and require matching dimensions."""
    try:
        with tempfile.TemporaryDirectory(prefix="eval-verify-") as tmp:
            fresh = render_diagram.render(
                html_path, Path(tmp) / f"{name}.png", scale=EXPECTED_SCALE
            )
            fresh_dims = render_diagram.png_dimensions(fresh)
    except render_diagram.RenderError as exc:
        raise VerifyError(
            f"the fresh re-render of {html_path} failed: {exc}"
        ) from exc
    _require(
        fresh_dims == candidate_dims,
        f"the fresh re-render is {fresh_dims[0]}x{fresh_dims[1]} px but the "
        f"candidate PNG is {candidate_dims[0]}x{candidate_dims[1]} px; the "
        "committed image is stale or was not produced from this source, "
        "re-render with python3 scripts/render_diagram.py <source>",
    )
    return fresh_dims


def verify(output_dir, name="agent-turn", skip_render=False):
    """Run every objective check; return the PASS lines or raise VerifyError."""
    html_path, png_path = check_pair(output_dir, name)
    html = html_path.read_text(encoding="utf-8", errors="replace")
    lines = [f"PASS {html_path.name} and {png_path.name} exist"]

    declared_width = check_html_contract(html)
    lines.append(
        f"PASS body declares --width: {declared_width}px and the source "
        "calls wires(...)"
    )

    check_arrow_sides(html)
    lines.append(
        "PASS every fromSide/toSide is one of " + ", ".join(VALID_SIDES)
    )

    check_no_remote_assets(html)
    lines.append("PASS no remote scripts, stylesheets or assets")

    check_local_assets(html, html_path)
    lines.append(
        "PASS " + " and ".join(LOCAL_ASSETS) + " are referenced locally "
        "and resolve on disk"
    )

    check_visible_text_is_english(html)
    lines.append("PASS visible text is English (no Cyrillic outside "
                 "script/style/comments)")

    width, height = check_png(png_path, declared_width)
    size = png_path.stat().st_size
    lines.append(
        f"PASS {png_path.name} is {width}x{height} px ({size} bytes): "
        f"2x the declared {declared_width}px width, under 1 MB"
    )

    if not skip_render:
        fresh_dims = check_fresh_render(html_path, png_path, name, (width, height))
        lines.append(
            f"PASS fresh render matches the candidate: "
            f"{fresh_dims[0]}x{fresh_dims[1]} px"
        )
    else:
        lines.append("PASS render check skipped (--skip-render)")

    return lines


def build_parser():
    parser = argparse.ArgumentParser(
        description="Verify one candidate diagram output directory "
        "against the diagram output contract."
    )
    parser.add_argument(
        "output_dir",
        help="directory the agent wrote <name>.html and <name>.png into",
    )
    parser.add_argument(
        "--name",
        default="agent-turn",
        help="stem shared by the HTML and PNG (default: agent-turn)",
    )
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="skip the fresh re-render comparison (offline check only)",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        lines = verify(args.output_dir, name=args.name, skip_render=args.skip_render)
    except VerifyError as exc:
        print(f"verify: {exc}", file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
