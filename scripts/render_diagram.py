#!/usr/bin/env python3
"""Render one HTML diagram into a PNG with a local Chromium or Chrome.

Standard library only. The renderer performs two headless passes with a
throwaway browser profile:

1. Dump the DOM at a generous window size so diagram.js can measure the
   body and record ``data-height``; read the CSS ``--width`` from the
   body and the recorded height out of the dump.
2. Screenshot the page at exactly those CSS dimensions with the
   requested device-scale factor and an opaque white background.

The result is optionally compressed with optipng when it is installed,
then checked against the 1 MB output contract.

Usage:
    python3 scripts/render_diagram.py SOURCE [--output PATH]
        [--chrome PATH] [--scale N]
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import re
from pathlib import Path

MAX_OUTPUT_BYTES = 1_000_000
DEFAULT_WIDTH = 1200
DEFAULT_SCALE = 2
DUMP_WINDOW_SIZE = (1600, 1200)
BROWSER_TIMEOUT_SECONDS = 120

# Flags shared by both passes. --allow-file-access-from-files lets the
# source load its local diagram.css and diagram.js; the virtual-time
# budget gives diagram.js room to draw arrows and stamp data-height.
BASE_FLAGS = [
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--hide-scrollbars",
    "--no-first-run",
    "--disable-extensions",
    "--allow-file-access-from-files",
    "--virtual-time-budget=3000",
]

HEIGHT_RE = re.compile(r'data-height=["\'](\d+)["\']')
WIDTH_RE = re.compile(r'--width\s*:\s*(\d+)px')


class RenderError(RuntimeError):
    """An expected failure with a message the operator can act on."""


def read_dimensions(dom):
    """Return (css_width, css_height) read from a dumped DOM.

    The height must have been recorded by diagram.js (a wires([...])
    call); the width falls back to DEFAULT_WIDTH when the body does not
    declare one.
    """
    height_match = HEIGHT_RE.search(dom)
    if not height_match:
        raise RenderError(
            "the source recorded no data-height; load diagram.js and call "
            "wires([...]) after the diagram markup (wires([]) when there "
            "are no arrows) so the renderer learns the measured height"
        )
    width_match = WIDTH_RE.search(dom)
    width = int(width_match.group(1)) if width_match else DEFAULT_WIDTH
    height = int(height_match.group(1))
    if width <= 0 or height <= 0:
        raise RenderError(
            "diagram dimensions must be positive integers, got "
            f"{width}x{height}; check the body's --width and the "
            "data-height recorded by diagram.js"
        )
    return width, height


def pixel_dimensions(css_dimensions, scale):
    """Return the PNG size for CSS dimensions at the given scale."""
    if not isinstance(scale, int) or scale <= 0:
        raise RenderError(f"scale must be a positive integer, got {scale!r}")
    width, height = css_dimensions
    return width * scale, height * scale


def check_size(size_bytes):
    """Fail when the rendered PNG is larger than the 1 MB contract."""
    if size_bytes > MAX_OUTPUT_BYTES:
        raise RenderError(
            f"rendered PNG is {size_bytes} bytes and exceeds the 1 MB "
            "limit; simplify the diagram, lower the scale, or install "
            "optipng so the renderer can compress it"
        )


def browser_candidates():
    """Return browser executables to try, in order, for this platform."""
    if sys.platform.startswith("darwin"):
        return [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Chromium Browser.app/Contents/MacOS/Chromium Browser",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    if os.name == "nt":
        program_files = [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
        ]
        candidates = []
        for root in program_files:
            if not root:
                continue
            candidates.extend(
                [
                    os.path.join(root, "Google", "Chrome", "Application", "chrome.exe"),
                    os.path.join(root, "Chromium", "Application", "chrome.exe"),
                    os.path.join(root, "Microsoft", "Edge", "Application", "msedge.exe"),
                ]
            )
        return candidates
    # Linux and other POSIX systems: names on PATH, most generic first.
    return [
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "microsoft-edge",
    ]


def _usable_browser(path, origin):
    expanded = Path(os.path.expanduser(path))
    if expanded.is_file():
        return str(expanded)
    raise RenderError(
        f"browser not found: {path!r} (from {origin}); pass --chrome PATH "
        "to a Chromium or Chrome executable, or point CHROME at one"
    )


def resolve_browser(explicit=None):
    """Find a browser: --chrome flag, then CHROME, then local candidates."""
    if explicit:
        return _usable_browser(explicit, "--chrome")
    env_value = os.environ.get("CHROME")
    if env_value:
        return _usable_browser(env_value, "the CHROME environment variable")
    for candidate in browser_candidates():
        found = shutil.which(candidate)
        if found:
            return found
        path = Path(os.path.expanduser(candidate))
        if path.is_absolute() and path.is_file():
            return str(path)
    raise RenderError(
        "no Chromium or Chrome binary found; install one, pass --chrome "
        "PATH, or set CHROME to the executable's path"
    )


def check_fonts():
    """Require Noto Sans where fc-list can answer; stay quiet without it."""
    fc_list = shutil.which("fc-list")
    if not fc_list:
        return
    try:
        result = subprocess.run(
            [fc_list, "--format", "%{family}\n"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except OSError as exc:
        # fc-list vanished or refused to run: the utility is unreliable
        # here, not the font, so do not fail the render over it.
        print(f"note: could not run fc-list ({exc}); skipping the font check",
              file=sys.stderr)
        return
    if result.returncode != 0:
        return
    families = (result.stdout or "").casefold()
    if "noto sans" not in families:
        raise RenderError(
            "Noto Sans is required by the diagram visual contract but "
            "fontconfig does not know it; install it (on Debian and "
            "Ubuntu: apt-get install fonts-noto-core) and render again"
        )


def _run_browser(argv, phase):
    """Run one browser pass, returning stdout; surface stderr on failure."""
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, timeout=BROWSER_TIMEOUT_SECONDS
        )
    except FileNotFoundError as exc:
        raise RenderError(f"browser vanished before the {phase} pass: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RenderError(
            f"the browser did not finish the {phase} pass within "
            f"{BROWSER_TIMEOUT_SECONDS} s; the page may hang or load "
            "remote assets, which sources must not do"
        ) from exc
    except OSError as exc:
        raise RenderError(f"could not start the browser for the {phase} pass: {exc}") from exc
    if result.returncode != 0:
        tail = (result.stderr or "").strip()
        if len(tail) > 2000:
            tail = tail[-2000:]
        raise RenderError(
            f"the browser failed the {phase} pass with exit code "
            f"{result.returncode}"
            + (f"; its output:\n{tail}" if tail else "")
        )
    return result.stdout or ""


def _source_uri(source):
    return Path(source).resolve().as_uri()


def render(source, output=None, chrome=None, scale=DEFAULT_SCALE):
    """Render the HTML diagram at ``source`` into a PNG and return its path."""
    source = Path(source)
    if not source.is_file():
        raise RenderError(
            f"source must be an existing regular file, got {source}; "
            "check the path (a directory does not render)"
        )
    if not isinstance(scale, int) or scale <= 0:
        raise RenderError(f"scale must be a positive integer, got {scale!r}")
    browser = resolve_browser(chrome)
    check_fonts()

    if output is None:
        output = source.with_suffix(".png")
    output = Path(output)
    if output.parent != Path(""):
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RenderError(f"could not create the output folder {output.parent}: {exc}") from exc

    uri = _source_uri(source)
    with tempfile.TemporaryDirectory(prefix="diagram-render-") as profile_root:
        dump_profile = os.path.join(profile_root, "dump")
        shot_profile = os.path.join(profile_root, "shot")

        dump = _run_browser(
            [browser]
            + BASE_FLAGS
            + [
                f"--user-data-dir={dump_profile}",
                "--window-size={},{}".format(*DUMP_WINDOW_SIZE),
                "--dump-dom",
                uri,
            ],
            "DOM dump",
        )
        if not dump.strip():
            raise RenderError(
                "the browser dumped an empty DOM; the source may be empty "
                "or fail to parse"
            )
        css_width, css_height = read_dimensions(dump)
        pixel_width, pixel_height = pixel_dimensions((css_width, css_height), scale)

        _run_browser(
            [browser]
            + BASE_FLAGS
            + [
                f"--user-data-dir={shot_profile}",
                f"--window-size={css_width},{css_height}",
                f"--force-device-scale-factor={scale}",
                "--default-background-color=FFFFFFFF",
                f"--screenshot={output}",
                uri,
            ],
            "screenshot",
        )
    if not output.is_file():
        raise RenderError(
            f"the browser reported success but wrote no screenshot at {output}"
        )

    optimize(output)

    size = output.stat().st_size
    check_size(size)
    print(f"{output}: {pixel_width}x{pixel_height}, {size} bytes")
    return output


def optimize(output):
    """Run optipng over the PNG when it is installed; never fail the render."""
    optipng = shutil.which("optipng")
    if not optipng:
        return
    try:
        subprocess.run(
            [optipng, "-quiet", "-o2", str(output)],
            capture_output=True,
            text=True,
            timeout=BROWSER_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        # Compression is a bonus; the uncompressed PNG already passed.
        pass


def build_parser():
    parser = argparse.ArgumentParser(
        description="Render an HTML diagram into a PNG with a local Chromium."
    )
    parser.add_argument("source", help="path to the HTML diagram source")
    parser.add_argument(
        "--output",
        default=None,
        help="PNG to write (default: the source name with a .png suffix)",
    )
    parser.add_argument(
        "--chrome",
        default=None,
        help="path to a Chromium or Chrome executable (else CHROME, "
        "then the usual locations)",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=DEFAULT_SCALE,
        help="device-scale factor for the PNG (default: 2)",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        render(args.source, output=args.output, chrome=args.chrome, scale=args.scale)
    except RenderError as exc:
        print(f"render_diagram: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
