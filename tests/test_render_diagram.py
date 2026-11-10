"""Tests for the standard-library diagram renderer.

The offline tests never start a browser: they cover the pure helpers
(read_dimensions, pixel_dimensions, check_size), browser resolution and
the CLI error paths. RealRenderTests is the one exception: it renders the
reference example with a real Chromium and skips itself when no browser
binary exists on this machine.
"""

import contextlib
import io
import os
import struct
import subprocess
import tempfile
import unittest
import unittest.mock
import zlib
from pathlib import Path

from scripts import render_diagram

ROOT = Path(__file__).resolve().parents[1]

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
OPTIPNG_PATH = "/usr/bin/optipng-stub"


def make_png(width, height):
    """A byte string with a valid PNG signature and IHDR chunk, no pixels."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    crc = struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
    return PNG_SIGNATURE + struct.pack(">I", len(ihdr)) + chunk + crc


class BrowserStub:
    """A stand-in for subprocess.run that records argv and fakes the passes."""

    def __init__(self, dump, screenshot="write", png_size=(2560, 1488), optipng=None):
        self.dump = dump
        self.screenshot = screenshot  # "write", "foreign" or "nothing"
        self.png_size = png_size
        self.optipng = optipng  # callable(argv) -> CompletedProcess, or None
        self.calls = []

    def run(self, argv, **kwargs):
        argv = list(argv)
        self.calls.append(argv)
        if any(a == "--dump-dom" for a in argv):
            return subprocess.CompletedProcess(argv, 0, stdout=self.dump, stderr="")
        shot = next((a for a in argv if a.startswith("--screenshot=")), None)
        if shot is not None:
            path = shot.split("=", 1)[1]
            if self.screenshot == "write":
                Path(path).write_bytes(make_png(*self.png_size))
            elif self.screenshot == "foreign":
                Path(path).write_bytes(b"not a png at all, really not")
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        if self.optipng is not None and argv and argv[0] == OPTIPNG_PATH:
            return self.optipng(argv)
        raise AssertionError(f"unexpected browser call: {argv}")


@contextlib.contextmanager
def stubbed_render(stub, optipng=False):
    """Route every subprocess and browser lookup of render() through the stub."""

    def which(name):
        if optipng and name == "optipng":
            return OPTIPNG_PATH
        return None

    with contextlib.ExitStack() as stack:
        stack.enter_context(
            unittest.mock.patch.object(render_diagram.subprocess, "run", stub.run)
        )
        stack.enter_context(
            unittest.mock.patch.object(render_diagram.shutil, "which", side_effect=which)
        )
        stack.enter_context(
            unittest.mock.patch.object(
                render_diagram, "resolve_browser", return_value="/usr/bin/fake-chrome"
            )
        )
        stack.enter_context(
            unittest.mock.patch.object(render_diagram, "check_fonts", lambda: None)
        )
        yield


class ReadDimensionsTests(unittest.TestCase):
    def test_reads_width_and_height_from_dumped_dom(self):
        dom = '<html data-height="744"><body style="--width: 1280px">'
        self.assertEqual(render_diagram.read_dimensions(dom), (1280, 744))

    def test_default_width_is_1200(self):
        self.assertEqual(render_diagram.read_dimensions('<html data-height="600">'), (1200, 600))

    def test_accepts_single_quoted_attributes(self):
        dom = "<html data-height='333'><body style='--width: 800px'>"
        self.assertEqual(render_diagram.read_dimensions(dom), (800, 333))

    def test_tolerates_whitespace_around_the_css_colon(self):
        dom = '<html data-height="200"><body style="--width :  640px">'
        self.assertEqual(render_diagram.read_dimensions(dom), (640, 200))

    def test_missing_height_is_actionable_error(self):
        with self.assertRaisesRegex(render_diagram.RenderError, "wires"):
            render_diagram.read_dimensions("<html><body></body></html>")

    def test_non_numeric_height_is_reported_like_a_missing_one(self):
        with self.assertRaisesRegex(render_diagram.RenderError, "wires"):
            render_diagram.read_dimensions('<html data-height="tall">')

    def test_rejects_zero_height(self):
        with self.assertRaisesRegex(render_diagram.RenderError, "positive"):
            render_diagram.read_dimensions('<html data-height="0">')

    def test_rejects_zero_width(self):
        with self.assertRaisesRegex(render_diagram.RenderError, "positive"):
            render_diagram.read_dimensions('<html data-height="600"><body style="--width: 0px">')


class PixelDimensionsTests(unittest.TestCase):
    def test_png_dimensions_follow_scale(self):
        self.assertEqual(render_diagram.pixel_dimensions((1280, 744), 2), (2560, 1488))

    def test_scale_one_keeps_css_size(self):
        self.assertEqual(render_diagram.pixel_dimensions((1280, 744), 1), (1280, 744))

    def test_rejects_non_positive_scale(self):
        for scale in (0, -2):
            with self.subTest(scale=scale):
                with self.assertRaisesRegex(render_diagram.RenderError, "scale"):
                    render_diagram.pixel_dimensions((100, 100), scale)


class CheckSizeTests(unittest.TestCase):
    def test_oversized_output_is_rejected(self):
        with self.assertRaisesRegex(render_diagram.RenderError, "1 MB"):
            render_diagram.check_size(1_000_001)

    def test_exactly_one_megabyte_passes(self):
        self.assertIsNone(render_diagram.check_size(1_000_000))

    def test_small_output_passes(self):
        self.assertIsNone(render_diagram.check_size(1))


class BrowserResolutionTests(unittest.TestCase):
    def test_missing_explicit_path_is_actionable(self):
        with self.assertRaisesRegex(render_diagram.RenderError, "chrome"):
            render_diagram.resolve_browser(str(ROOT / "no-such-browser"))

    def test_explicit_existing_file_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "fake chrome"  # a path with a space must survive
            fake.write_text("not a browser", encoding="utf-8")
            self.assertEqual(render_diagram.resolve_browser(str(fake)), str(fake))

    def test_chrome_env_pointing_at_nothing_is_actionable(self):
        with unittest.mock.patch.dict(os.environ, {"CHROME": str(ROOT / "no-such-browser")}):
            with self.assertRaisesRegex(render_diagram.RenderError, "CHROME"):
                render_diagram.resolve_browser()

    def test_no_candidate_found_is_actionable(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            with unittest.mock.patch.object(render_diagram, "browser_candidates", return_value=[]):
                with unittest.mock.patch.object(render_diagram.shutil, "which", return_value=None):
                    with self.assertRaisesRegex(render_diagram.RenderError, "CHROME"):
                        render_diagram.resolve_browser()

    def test_linux_candidates_name_the_common_binaries(self):
        with unittest.mock.patch.object(render_diagram.sys, "platform", "linux"):
            with unittest.mock.patch.object(render_diagram.os, "name", "posix"):
                candidates = render_diagram.browser_candidates()
        for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
            self.assertIn(name, candidates)


class RenderValidationTests(unittest.TestCase):
    """render() must reject bad input before it ever touches a browser."""

    def test_missing_source_is_rejected(self):
        with self.assertRaisesRegex(render_diagram.RenderError, "regular file"):
            render_diagram.render(ROOT / "no-such-diagram.html")

    def test_directory_source_is_rejected(self):
        with self.assertRaisesRegex(render_diagram.RenderError, "regular file"):
            render_diagram.render(ROOT / "tests")

    def test_non_positive_scale_is_rejected_before_browser_lookup(self):
        source = ROOT / "SKILL.md"  # any existing regular file
        with self.assertRaisesRegex(render_diagram.RenderError, "scale"):
            render_diagram.render(source, scale=0)


class CliTests(unittest.TestCase):
    def run_cli(self, argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = render_diagram.main(argv)
        return code, err.getvalue()

    def test_missing_source_exits_one_with_a_clear_message(self):
        missing = str(ROOT / "no-such-diagram.html")
        code, message = self.run_cli([missing])
        self.assertEqual(code, 1)
        self.assertIn("no-such-diagram.html", message)

    def test_non_positive_scale_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "diagram with spaces.html"
            source.write_text("<html></html>", encoding="utf-8")
            code, message = self.run_cli([str(source), "--scale", "0"])
        self.assertEqual(code, 1)
        self.assertIn("scale", message)

    def test_scale_defaults_to_two(self):
        parser = render_diagram.build_parser()
        args = parser.parse_args(["diagram.html"])
        self.assertEqual(args.scale, 2)
        self.assertIsNone(args.output)
        self.assertIsNone(args.chrome)


class AnchoredDimensionsTests(unittest.TestCase):
    """data-height belongs to the html tag, --width to the body style."""

    def test_reads_width_and_height_from_the_anchored_attributes(self):
        dom = '<html data-height="744"><body style="--width: 1280px">'
        self.assertEqual(render_diagram.read_dimensions(dom), (1280, 744))

    def test_ignores_a_data_height_decoy_before_the_html_tag(self):
        dom = (
            '<!-- data-height="999" -->'
            '<html data-height="744"><body style="--width: 1280px">'
        )
        self.assertEqual(render_diagram.read_dimensions(dom), (1280, 744))

    def test_ignores_a_data_height_decoy_in_a_script_before_the_real_one(self):
        dom = (
            '<html><head><script>el.setAttribute("data-height", "999");'
            "</script></head>"
            '<html data-height="744"><body style="--width: 1280px">'
        )
        # The first <html ... data-height tag is the real one; the script
        # text carries no <html tag, so the anchor skips it.
        self.assertEqual(render_diagram.read_dimensions(dom), (1280, 744))

    def test_ignores_a_width_decoy_in_a_head_style_before_the_body(self):
        dom = (
            '<html data-height="744"><head><style>.decoy{--width: 111px}'
            '</style></head><body style="--width: 1280px">'
        )
        self.assertEqual(render_diagram.read_dimensions(dom), (1280, 744))

    def test_ignores_a_width_decoy_in_a_nested_element(self):
        dom = '<html data-height="744"><body><div style="--width: 50px">'
        self.assertEqual(render_diagram.read_dimensions(dom), (1200, 744))

    def test_a_nested_data_height_does_not_satisfy_the_contract(self):
        dom = "<html><body><div data-height=\"500\">"
        with self.assertRaisesRegex(render_diagram.RenderError, "wires"):
            render_diagram.read_dimensions(dom)

    def test_data_height_survives_other_attributes_on_the_html_tag(self):
        dom = '<html lang="en" data-height="744"><body style="--width: 1280px">'
        self.assertEqual(render_diagram.read_dimensions(dom), (1280, 744))

    def test_body_width_survives_other_style_properties(self):
        dom = '<html data-height="744"><body style="margin:0;--width: 1280px">'
        self.assertEqual(render_diagram.read_dimensions(dom), (1280, 744))


class DeclaredWidthTests(unittest.TestCase):
    def test_declared_width_reads_the_body_style(self):
        html = '<html><head></head><body style="--width: 1280px">'
        self.assertEqual(render_diagram.declared_width(html), 1280)

    def test_declared_width_defaults_to_1200(self):
        self.assertEqual(render_diagram.declared_width("<html><body>"), 1200)

    def test_declared_width_ignores_decoys_outside_the_body_style(self):
        html = (
            '<html><head><style>.x{--width: 111px}</style></head>'
            "<body><div style=\"--width: 50px\">"
        )
        self.assertEqual(render_diagram.declared_width(html), 1200)


class PngDimensionsTests(unittest.TestCase):
    def test_reads_dimensions_from_a_generated_png_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "diagram.png"
            path.write_bytes(make_png(2560, 1488))
            self.assertEqual(render_diagram.png_dimensions(path), (2560, 1488))

    def test_rejects_data_without_the_png_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "diagram.png"
            path.write_bytes(b"not a png at all, really not")
            with self.assertRaisesRegex(render_diagram.RenderError, "PNG"):
                render_diagram.png_dimensions(path)

    def test_rejects_a_truncated_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "diagram.png"
            path.write_bytes(make_png(2560, 1488)[:10])
            with self.assertRaisesRegex(render_diagram.RenderError, "PNG"):
                render_diagram.png_dimensions(path)

    def test_rejects_a_missing_ihdr_chunk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "diagram.png"
            path.write_bytes(PNG_SIGNATURE + struct.pack(">I", 13) + b"JUNK" + bytes(13))
            with self.assertRaisesRegex(render_diagram.RenderError, "IHDR"):
                render_diagram.png_dimensions(path)

    def test_rejects_a_corrupt_ihdr_crc(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "diagram.png"
            good = make_png(2560, 1488)
            path.write_bytes(good[:-4] + b"\x00\x00\x00\x00")
            with self.assertRaisesRegex(render_diagram.RenderError, "IHDR"):
                render_diagram.png_dimensions(path)


class ScaleValidatorTests(unittest.TestCase):
    def test_bool_scale_is_rejected(self):
        with self.assertRaisesRegex(render_diagram.RenderError, "scale"):
            render_diagram.pixel_dimensions((10, 10), True)

    def test_bool_scale_is_rejected_by_render(self):
        source = ROOT / "SKILL.md"
        with self.assertRaisesRegex(render_diagram.RenderError, "scale"):
            render_diagram.render(source, scale=True)


class OutputValidationTests(unittest.TestCase):
    def make_source(self, tmp):
        source = Path(tmp) / "diagram.html"
        source.write_text("<html><body></body></html>", encoding="utf-8")
        return source

    def test_output_must_end_in_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_source(tmp)
            with self.assertRaisesRegex(render_diagram.RenderError, "\\.png"):
                render_diagram.render(source, output=Path(tmp) / "out.jpg")

    def test_output_may_not_be_an_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_source(tmp)
            with self.assertRaisesRegex(render_diagram.RenderError, "directory"):
                render_diagram.render(source, output=Path(tmp))


class RenderFlowTests(unittest.TestCase):
    """The two passes and the output checks, driven by a browser stub."""

    SOURCE_HTML = (
        '<html><head></head><body style="--width: 1280px"></body></html>'
    )
    DUMP = '<html data-height="744"><body style="--width: 1280px"></body></html>'

    def make_source(self, tmp):
        source = Path(tmp) / "diagram.html"
        source.write_text(self.SOURCE_HTML, encoding="utf-8")
        return source

    def test_dump_and_screenshot_share_the_declared_width(self):
        stub = BrowserStub(self.DUMP)
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_source(tmp)
            output = Path(tmp) / "diagram.png"
            with stubbed_render(stub):
                with contextlib.redirect_stdout(io.StringIO()):
                    render_diagram.render(source, output=output, scale=2)
            dump_call, shot_call = stub.calls
            self.assertIn("--window-size=1280,1200", dump_call)
            self.assertIn("--window-size=1280,744", shot_call)
            self.assertIn("--force-device-scale-factor=2", shot_call)

    def test_stale_output_is_not_accepted(self):
        stub = BrowserStub(self.DUMP, screenshot="nothing")
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_source(tmp)
            output = Path(tmp) / "diagram.png"
            output.write_bytes(make_png(10, 10))  # stale from an earlier run
            with stubbed_render(stub):
                with self.assertRaisesRegex(render_diagram.RenderError, "screenshot"):
                    render_diagram.render(source, output=output, scale=2)
            self.assertFalse(output.exists(), "the stale file must be deleted")

    def test_foreign_output_is_rejected(self):
        stub = BrowserStub(self.DUMP, screenshot="foreign")
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_source(tmp)
            output = Path(tmp) / "diagram.png"
            with stubbed_render(stub):
                with self.assertRaisesRegex(render_diagram.RenderError, "PNG"):
                    render_diagram.render(source, output=output, scale=2)

    def test_success_line_reports_actual_png_dimensions(self):
        stub = BrowserStub(self.DUMP, png_size=(2560, 1488))
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_source(tmp)
            output = Path(tmp) / "diagram.png"
            out = io.StringIO()
            with stubbed_render(stub):
                with contextlib.redirect_stdout(out):
                    render_diagram.render(source, output=output, scale=2)
            expected_bytes = len(make_png(2560, 1488))
            self.assertIn(f"{output}: 2560x1488, {expected_bytes} bytes", out.getvalue())

    def test_wrong_sized_png_is_rejected(self):
        stub = BrowserStub(self.DUMP, png_size=(1280, 744))  # scale was 2
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_source(tmp)
            output = Path(tmp) / "diagram.png"
            with stubbed_render(stub):
                with self.assertRaisesRegex(render_diagram.RenderError, "2560x1488"):
                    render_diagram.render(source, output=output, scale=2)

    def test_optipng_is_invoked_and_keeps_a_valid_png(self):
        def optipng(argv):
            self.assertEqual(argv[1:3], ["-quiet", "-o2"])
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        stub = BrowserStub(self.DUMP, optipng=optipng)
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_source(tmp)
            output = Path(tmp) / "diagram.png"
            with stubbed_render(stub, optipng=True):
                with contextlib.redirect_stdout(io.StringIO()):
                    render_diagram.render(source, output=output, scale=2)
            self.assertEqual(render_diagram.png_dimensions(output), (2560, 1488))

    def test_truncating_optipng_is_rejected(self):
        def optipng(argv):
            Path(argv[-1]).write_bytes(make_png(2560, 1488)[:12])
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        stub = BrowserStub(self.DUMP, optipng=optipng)
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_source(tmp)
            output = Path(tmp) / "diagram.png"
            with stubbed_render(stub, optipng=True):
                with self.assertRaisesRegex(render_diagram.RenderError, "PNG"):
                    with contextlib.redirect_stdout(io.StringIO()):
                        render_diagram.render(source, output=output, scale=2)

    def test_failing_optipng_leaves_the_unoptimized_output_in_place(self):
        def optipng(argv):
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="boom")

        stub = BrowserStub(self.DUMP, optipng=optipng)
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_source(tmp)
            output = Path(tmp) / "diagram.png"
            with stubbed_render(stub, optipng=True):
                with contextlib.redirect_stdout(io.StringIO()):
                    render_diagram.render(source, output=output, scale=2)
            self.assertEqual(render_diagram.png_dimensions(output), (2560, 1488))


class RealRenderTests(unittest.TestCase):
    """Render the reference example with a real Chromium.

    This is the only test that starts a browser. It skips itself when no
    Chromium or Chrome binary exists, so a machine without one still
    passes the suite.
    """

    def setUp(self):
        try:
            render_diagram.resolve_browser()
        except render_diagram.RenderError:
            self.skipTest("no Chromium or Chrome binary on this machine")

    def test_example_renders_at_twice_css_size(self):
        source = ROOT / "examples" / "agent-turn.html"
        output = ROOT / "examples" / "agent-turn.png"
        render_diagram.render(source, output, scale=2)
        self.assertTrue(output.is_file(), "the renderer wrote no PNG")
        self.assertLessEqual(output.stat().st_size, 1_000_000)
        width, height = render_diagram.png_dimensions(output)
        self.assertEqual(width, 2400)
        self.assertGreater(height, 0)


if __name__ == "__main__":
    unittest.main()
