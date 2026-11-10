"""Offline tests for the standard-library diagram renderer.

These tests never start a browser: they cover the pure helpers
(read_dimensions, pixel_dimensions, check_size), browser resolution and
the CLI error paths. The real-render smoke test arrives with the example
in a later task.
"""

import contextlib
import io
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from scripts import render_diagram

ROOT = Path(__file__).resolve().parents[1]


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


if __name__ == "__main__":
    unittest.main()
