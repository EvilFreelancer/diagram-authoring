"""Tests for the reusable evaluation verifier, evals/verify.py.

The verifier checks one candidate output directory against the diagram
output contract: a same-stem HTML/PNG pair, the inline body width and
the wires call in the HTML, local diagram.css/diagram.js that resolve
on disk, no remote assets, no Cyrillic in visible text, and a PNG whose
actual width is twice the declared CSS width and whose size is under
1 MB. Without --skip-render it re-renders the candidate in a temporary
directory and requires the fresh dimensions to match.

The tests build tiny valid PNG headers with make_png (signature plus a
correct IHDR chunk) and read them back through the renderer's own
png_dimensions, so no renderer logic is duplicated here. FreshRenderTests
is the only case that starts a browser; it skips itself when none
exists and never writes onto the committed reference PNG.
"""

import contextlib
import importlib.util
import io
import shutil
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# evals/verify.py is a CLI script, not a package: load it by path. The
# module itself puts the repository's scripts/ on sys.path from its own
# __file__, so this load works from any cwd.
VERIFY_PATH = ROOT / "evals" / "verify.py"
_spec = importlib.util.spec_from_file_location("eval_verify", VERIFY_PATH)
verify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify)

import sys

sys.path.insert(0, str(ROOT / "scripts"))
import render_diagram

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def make_png(width, height):
    """A byte string with a valid PNG signature and IHDR chunk, no pixels."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    crc = struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
    return PNG_SIGNATURE + struct.pack(">I", len(ihdr)) + chunk + crc


VALID_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>A tiny diagram</title>
    <link rel="stylesheet" href="diagram.css" />
    <script src="diagram.js"></script>
  </head>
  <body style="--width: 1000px">
    <h1>A tiny diagram</h1>
    <script>
      wires([]);
    </script>
  </body>
</html>
"""


def make_candidate(tmp, html=VALID_HTML, png_size=(2000, 600), assets=True):
    """A directory holding name.html, name.png and the local assets."""
    out = Path(tmp)
    (out / "agent-turn.html").write_text(html, encoding="utf-8")
    (out / "agent-turn.png").write_bytes(make_png(*png_size))
    if assets:
        (out / "diagram.css").write_text("body{font-family:sans-serif}", encoding="utf-8")
        (out / "diagram.js").write_text("function wires(){}", encoding="utf-8")
    return out


def run_verify(out, skip_render=True):
    return verify.verify(out, name="agent-turn", skip_render=skip_render)


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = verify.main(argv)
    return code, out.getvalue(), err.getvalue()


class MissingPairTests(unittest.TestCase):
    def test_missing_png_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp)
            (out / "agent-turn.png").unlink()
            with self.assertRaisesRegex(verify.VerifyError, "agent-turn\\.png"):
                run_verify(out)

    def test_missing_html_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp)
            (out / "agent-turn.html").unlink()
            with self.assertRaisesRegex(verify.VerifyError, "agent-turn\\.html"):
                run_verify(out)

    def test_missing_directory_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(verify.VerifyError, "directory"):
                run_verify(Path(tmp) / "no-such-output")


class HtmlContractTests(unittest.TestCase):
    def test_missing_inline_body_width_is_rejected(self):
        html = VALID_HTML.replace(' style="--width: 1000px"', "")
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            with self.assertRaisesRegex(verify.VerifyError, "--width"):
                run_verify(out)

    def test_missing_wires_call_is_rejected(self):
        html = VALID_HTML.replace("wires([]);", "")
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            with self.assertRaisesRegex(verify.VerifyError, "wires"):
                run_verify(out)

    def test_width_in_a_nested_element_is_not_the_body_declaration(self):
        html = VALID_HTML.replace(
            '<body style="--width: 1000px">',
            "<body>",
        ).replace("<h1>", '<div style="--width: 1000px"></div><h1>')
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            with self.assertRaisesRegex(verify.VerifyError, "--width"):
                run_verify(out)


class LocalAssetTests(unittest.TestCase):
    def test_missing_local_css_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp)
            (out / "diagram.css").unlink()
            with self.assertRaisesRegex(verify.VerifyError, "diagram\\.css"):
                run_verify(out)

    def test_missing_local_js_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp)
            (out / "diagram.js").unlink()
            with self.assertRaisesRegex(verify.VerifyError, "diagram\\.js"):
                run_verify(out)

    def test_no_asset_reference_at_all_is_rejected(self):
        html = VALID_HTML.replace('<link rel="stylesheet" href="diagram.css" />', "")
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            with self.assertRaisesRegex(verify.VerifyError, "diagram\\.css"):
                run_verify(out)


class RemoteAssetTests(unittest.TestCase):
    def test_remote_script_is_rejected(self):
        html = VALID_HTML.replace(
            '<script src="diagram.js"></script>',
            '<script src="https://cdn.example.com/diagram.js"></script>',
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            with self.assertRaisesRegex(verify.VerifyError, "remote"):
                run_verify(out)

    def test_remote_stylesheet_is_rejected(self):
        html = VALID_HTML.replace(
            '<link rel="stylesheet" href="diagram.css" />',
            '<link rel="stylesheet" href="http://cdn.example.com/diagram.css" />',
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            with self.assertRaisesRegex(verify.VerifyError, "remote"):
                run_verify(out)

    def test_protocol_relative_asset_is_rejected(self):
        html = VALID_HTML.replace(
            '<script src="diagram.js"></script>',
            '<script src="//cdn.example.com/diagram.js"></script>',
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            with self.assertRaisesRegex(verify.VerifyError, "remote"):
                run_verify(out)

    def test_remote_font_import_in_a_style_block_is_rejected(self):
        html = VALID_HTML.replace(
            "<title>A tiny diagram</title>",
            "<title>A tiny diagram</title>\n<style>@import url(https://fonts.example.com/f.css);</style>",
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            with self.assertRaisesRegex(verify.VerifyError, "remote"):
                run_verify(out)

    def test_remote_image_is_rejected(self):
        html = VALID_HTML.replace(
            "</body>",
            '<img src="https://cdn.example.com/logo.png" /></body>',
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            with self.assertRaisesRegex(verify.VerifyError, "remote"):
                run_verify(out)

    def test_remote_link_element_is_rejected(self):
        # <link href> fetches a resource (stylesheet, icon, preload), so
        # a remote one is an asset reference even when it is no stylesheet.
        html = VALID_HTML.replace(
            "</head>",
            '<link rel="icon" href="https://cdn.example.com/favicon.ico" />'
            "</head>",
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            with self.assertRaisesRegex(verify.VerifyError, "remote"):
                run_verify(out)

    def test_ordinary_hyperlink_is_not_an_asset(self):
        # <a href> loads nothing: it only navigates when the reader clicks
        # it, so a remote link in the prose is not a remote asset.
        html = VALID_HTML.replace(
            "</body>",
            '<p>See <a href="https://example.com/spec">the spec</a>.</p>'
            "</body>",
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            lines = run_verify(out)
            self.assertTrue(all(l.startswith("PASS") for l in lines))

    def test_remote_stylesheet_in_a_style_block_is_rejected(self):
        # CSS url() loads the resource at parse time: always an asset.
        html = VALID_HTML.replace(
            "</head>",
            "<style>body{background:url(https://cdn.example.com/bg.png)}"
            "</style></head>",
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            with self.assertRaisesRegex(verify.VerifyError, "remote"):
                run_verify(out)


class CyrillicTests(unittest.TestCase):
    def test_cyrillic_visible_text_is_rejected(self):
        html = VALID_HTML.replace("<h1>A tiny diagram</h1>", "<h1>Ход агента</h1>")
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            with self.assertRaisesRegex(verify.VerifyError, "English"):
                run_verify(out)

    def test_cyrillic_in_script_style_and_comment_is_allowed(self):
        html = VALID_HTML.replace(
            "<h1>A tiny diagram</h1>",
            "<!-- заметка о ходе -->\n<h1>A tiny diagram</h1>",
        ).replace(
            "wires([]);",
            "wires([]); // вызов стрелок\nvar label = 'ход';",
        ).replace(
            "<title>A tiny diagram</title>",
            "<title>A tiny diagram</title>\n<style>/* подсказка */ h1{color:red}</style>",
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            lines = run_verify(out)
            self.assertTrue(lines)


class ArrowSideTests(unittest.TestCase):
    """The verifier rejects fromSide/toSide values diagram.js cannot honor.

    diagram.js anchors an arrowhead on one of four sides only (top, right,
    bottom, left). A diagonal such as "top-left" used to fall back silently
    to a default side, so the arrows came out wrong while the render still
    "succeeded". The verifier now refuses those values statically, before
    any browser is started, with a message naming the bad value.
    """

    def _html_with_sides(self, from_side, to_side):
        return VALID_HTML.replace(
            "wires([]);",
            'wires([{ from: "#a", to: "#b", '
            f'fromSide: "{from_side}", toSide: "{to_side}" }}]);',
        )

    def test_diagonal_from_side_is_rejected(self):
        html = self._html_with_sides("top-left", "top")
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            with self.assertRaisesRegex(verify.VerifyError, "top-left"):
                run_verify(out)

    def test_diagonal_to_side_is_rejected(self):
        html = self._html_with_sides("right", "top-right")
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            with self.assertRaisesRegex(verify.VerifyError, "top-right"):
                run_verify(out)

    def test_each_diagonal_combination_is_rejected(self):
        for side in (
            "top-left",
            "top-right",
            "bottom-left",
            "bottom-right",
            "left-top",
            "right-bottom",
        ):
            with self.subTest(side=side):
                html = self._html_with_sides(side, "top")
                with tempfile.TemporaryDirectory() as tmp:
                    out = make_candidate(tmp, html=html)
                    with self.assertRaisesRegex(verify.VerifyError, side):
                        run_verify(out)

    def test_each_valid_direction_is_accepted(self):
        for side in ("top", "right", "bottom", "left"):
            with self.subTest(side=side):
                html = self._html_with_sides(side, side)
                with tempfile.TemporaryDirectory() as tmp:
                    out = make_candidate(tmp, html=html)
                    lines = run_verify(out)
                    self.assertTrue(all(l.startswith("PASS") for l in lines))

    def test_missing_sides_default_and_pass(self):
        # An arrow with no fromSide/toSide is legal: diagram.js defaults to
        # right and left. Only an explicit bad value is refused.
        html = VALID_HTML.replace(
            "wires([]);", 'wires([{ from: "#a", to: "#b" }]);'
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            lines = run_verify(out)
            self.assertTrue(all(l.startswith("PASS") for l in lines))

    def test_error_names_the_allowed_directions(self):
        html = self._html_with_sides("top-left", "top")
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, html=html)
            with self.assertRaises(verify.VerifyError) as ctx:
                run_verify(out)
        message = str(ctx.exception)
        for direction in ("top", "right", "bottom", "left"):
            self.assertIn(direction, message)

    def test_uppercase_side_is_rejected(self):
        # diagram.js accepts only the lowercase sides; the verifier must
        # not be more permissive than the renderer it checks against.
        for side in ("TOP", "Left", "BOTTOM"):
            with self.subTest(side=side):
                html = self._html_with_sides(side, "top")
                with tempfile.TemporaryDirectory() as tmp:
                    out = make_candidate(tmp, html=html)
                    with self.assertRaisesRegex(verify.VerifyError, side):
                        run_verify(out)


class PngContractTests(unittest.TestCase):
    def test_width_mismatch_is_rejected(self):
        # The HTML declares --width: 1000px, so the PNG must be 2000 wide.
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, png_size=(2200, 600))
            with self.assertRaisesRegex(verify.VerifyError, "2000"):
                run_verify(out)

    def test_oversized_png_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp)
            png = out / "agent-turn.png"
            png.write_bytes(make_png(2000, 600) + b"\x00" * 1_000_001)
            with self.assertRaisesRegex(verify.VerifyError, "1 MB"):
                run_verify(out)

    def test_non_png_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp)
            (out / "agent-turn.png").write_bytes(b"not a png at all, really not")
            with self.assertRaisesRegex(verify.VerifyError, "PNG"):
                run_verify(out)


class ValidExampleTests(unittest.TestCase):
    def test_committed_example_passes_with_skip_render(self):
        lines = verify.verify(ROOT / "examples", name="agent-turn", skip_render=True)
        self.assertTrue(lines, "the verifier must report what it checked")
        self.assertTrue(all(line.startswith("PASS") for line in lines))

    def test_cli_exits_zero_for_the_example_with_skip_render(self):
        code, out, err = run_cli(
            [str(ROOT / "examples"), "--name", "agent-turn", "--skip-render"]
        )
        self.assertEqual((code, err), (0, ""))
        self.assertIn("PASS", out)

    def test_cli_exits_one_with_actionable_stderr_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = make_candidate(tmp, png_size=(2200, 600))
            code, _, err = run_cli([str(out), "--name", "agent-turn", "--skip-render"])
            self.assertEqual(code, 1)
            self.assertIn("2000", err)

    def test_name_defaults_to_agent_turn(self):
        args = verify.build_parser().parse_args([str(ROOT / "examples")])
        self.assertEqual(args.name, "agent-turn")
        self.assertFalse(args.skip_render)


def example_copy(tmp):
    """A copy of the reference example with its assets, in a temp tree.

    The example references ../assets/diagram.css and ../assets/diagram.js,
    so the copy keeps the same relative layout: <tmp>/diagram/ holds the
    HTML and <tmp>/assets/ the shared files. Nothing here touches the
    committed examples/ or assets/ folders. Returns the diagram folder.
    """
    diagram_dir = Path(tmp) / "diagram"
    diagram_dir.mkdir()
    assets_dir = Path(tmp) / "assets"
    assets_dir.mkdir()
    shutil.copy(ROOT / "examples" / "agent-turn.html", diagram_dir / "agent-turn.html")
    for name in ("diagram.css", "diagram.js"):
        shutil.copy(ROOT / "assets" / name, assets_dir / name)
    return diagram_dir


class FreshRenderTests(unittest.TestCase):
    """The re-render path with a real Chromium, never on committed files."""

    def setUp(self):
        try:
            render_diagram.resolve_browser()
        except render_diagram.RenderError:
            self.skipTest("no Chromium or Chrome binary on this machine")

    def test_fresh_render_matches_the_committed_example(self):
        # The task's validation command: verify examples/ with rendering.
        lines = verify.verify(ROOT / "examples", name="agent-turn", skip_render=False)
        self.assertTrue(any("render" in line.lower() for line in lines))

    def test_fresh_render_of_a_copy_matches_and_reference_stays_untouched(self):
        reference_before = (ROOT / "examples" / "agent-turn.png").read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            out = example_copy(tmp)
            render_diagram.render(
                out / "agent-turn.html", out / "agent-turn.png", scale=2
            )
            lines = verify.verify(out, name="agent-turn", skip_render=False)
            self.assertTrue(any("render" in line.lower() for line in lines))
        self.assertEqual(
            (ROOT / "examples" / "agent-turn.png").read_bytes(),
            reference_before,
            "the verifier must render into a temporary directory, never onto "
            "the committed reference PNG",
        )

    def test_candidate_with_wrong_height_fails_the_render_comparison(self):
        # The declared width is 1200 CSS px, so a 2400-wide PNG passes the
        # static width check; only the fresh re-render exposes the wrong
        # height (the example measures 1790 px tall at 2x).
        with tempfile.TemporaryDirectory() as tmp:
            out = example_copy(tmp)
            (out / "agent-turn.png").write_bytes(make_png(2400, 999))
            with self.assertRaisesRegex(verify.VerifyError, "999"):
                verify.verify(out, name="agent-turn", skip_render=False)

    def test_same_dimensions_different_content_fails(self):
        # The stale-PNG hole the dimension comparison misses: edit a
        # visible label without moving the layout, so the fresh render is
        # still 2400x1790 but the bytes no longer match the candidate.
        with tempfile.TemporaryDirectory() as tmp:
            out = example_copy(tmp)
            render_diagram.render(
                out / "agent-turn.html", out / "agent-turn.png", scale=2
            )
            html_path = out / "agent-turn.html"
            html_path.write_text(
                html_path.read_text(encoding="utf-8").replace(
                    "<h1>A Coddy agent turn</h1>",
                    "<h1>How one Coddy agent turn travels</h1>",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(verify.VerifyError, "content differs"):
                verify.verify(out, name="agent-turn", skip_render=False)

    def test_unchanged_example_is_byte_identical_to_a_fresh_render(self):
        # The happy path of the content check: a candidate produced by
        # rendering the shipped HTML is accepted byte for byte.
        with tempfile.TemporaryDirectory() as tmp:
            out = example_copy(tmp)
            candidate = render_diagram.render(
                out / "agent-turn.html", out / "agent-turn.png", scale=2
            )
            lines = verify.verify(out, name="agent-turn", skip_render=False)
            self.assertTrue(any("render" in line.lower() for line in lines))
            self.assertEqual(
                candidate.read_bytes(),
                (ROOT / "examples" / "agent-turn.png").read_bytes(),
                "a fresh render of the example must equal the committed PNG "
                "byte for byte, or the content check rejects the reference",
            )


if __name__ == "__main__":
    unittest.main()
