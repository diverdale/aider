#!/usr/bin/env python

"""
Thread-based, killable spinner utility.

Use it like:

    from aider.waiting import WaitingSpinner

    spinner = WaitingSpinner("Waiting for LLM")
    spinner.start()
    ...  # long task
    spinner.stop()
"""

import sys
import threading
import time

from rich.color import Color, ColorParseError
from rich.console import Console


class Spinner:
    """
    Minimal spinner that scans a single marker back and forth across a line.

    The animation is pre-rendered into a list of frames.  If the terminal
    cannot display unicode the frames are converted to plain ASCII.
    """

    last_frame_idx = 0  # Class variable to store the last frame index

    def __init__(self, text: str, width: int = 14, color: str = None):
        self.text = text
        self.start_time = time.time()
        self.last_update = 0.0
        self.visible = False
        self.is_tty = sys.stdout.isatty()
        self.console = Console()
        self.color = color

        # Pre-render a fade trail animation that sweeps back and forth.
        # Render as solid blocks with intensity-based coloring for a smoother fade.
        self.use_unicode = self._supports_unicode()
        self.use_ansi_color = self._supports_ansi_color()
        self.block_char = "█" if self.use_unicode else "#"
        self.trail_levels = 8
        frames = self._build_fade_frames(width, self.trail_levels)

        # Bounce the scanner back and forth.
        self.frames = frames
        self.frame_idx = Spinner.last_frame_idx  # Initialize from class variable
        self.width = len(frames[0])
        self.animation_len = len(frames[0])
        self.last_display_len = 0  # Length of the last spinner line (frame + text)

    def _build_fade_frames(self, width: int, levels: int) -> list[list[int]]:
        width = max(4, width)

        # Drive the head slightly off-screen so the trail visibly fades in/out at edges.
        min_head = -(levels - 1)
        max_head = (width - 1) + (levels - 1)
        positions = list(range(min_head, max_head + 1)) + list(range(max_head - 1, min_head, -1))

        frames = []
        direction = 1
        prev_head = None
        for head in positions:
            if prev_head is not None:
                if head > prev_head:
                    direction = 1
                elif head < prev_head:
                    direction = -1

            intensity = [0] * width
            for depth in range(levels):
                # Trail follows behind the moving head in either direction.
                pos = head - (depth * direction)
                if 0 <= pos < width:
                    # Highest intensity at head, decreasing toward the tail.
                    intensity[pos] = levels - depth
            frames.append(intensity)
            prev_head = head

        return frames

    def _render_frame(self, intensity: list[int]) -> tuple[str, str]:
        # Visible frame has no ANSI escapes and is used for width calculations.
        visible = "".join(self.block_char if level else " " for level in intensity)

        if not self.use_ansi_color:
            return visible, visible

        color_steps = self._color_steps()

        out = []
        for level in intensity:
            if level:
                escape = color_steps[level - 1]
                out.append(f"{escape}{self.block_char}\033[0m")
            else:
                out.append(" ")

        return "".join(out), visible

    def _color_steps(self) -> list[str]:
        """Build 8 fade levels using either configured color or blue fallback."""
        parsed = self._parse_color(self.color)
        if not parsed:
            # Fallback palette keeps previous behavior.
            return [
                "\033[2;34m",
                "\033[2;34m",
                "\033[34m",
                "\033[34m",
                "\033[1;34m",
                "\033[94m",
                "\033[1;94m",
                "\033[1;94m",
            ]

        mode, value = parsed
        if mode == "ansi":
            normal = value
            return [
                f"\033[2;{normal}m",
                f"\033[2;{normal}m",
                f"\033[{normal}m",
                f"\033[{normal}m",
                f"\033[1;{normal}m",
                f"\033[1;{normal}m",
                f"\033[1;{normal}m",
                f"\033[1;{normal}m",
            ]

        red, green, blue = value
        return [
            f"\033[2;38;2;{red};{green};{blue}m",
            f"\033[2;38;2;{red};{green};{blue}m",
            f"\033[38;2;{red};{green};{blue}m",
            f"\033[38;2;{red};{green};{blue}m",
            f"\033[1;38;2;{red};{green};{blue}m",
            f"\033[1;38;2;{red};{green};{blue}m",
            f"\033[1;38;2;{red};{green};{blue}m",
            f"\033[1;38;2;{red};{green};{blue}m",
        ]

    def _parse_color(self, color: str):
        """Return (mode, value) for ANSI named colors or RGB triplets."""
        if not color:
            return None

        try:
            parsed = Color.parse(color)
        except ColorParseError:
            return None

        if parsed.triplet is not None:
            t = parsed.triplet
            return ("rgb", (t.red, t.green, t.blue))

        if parsed.number is None:
            return None

        # Rich color numbers 0-15 map to ANSI foreground codes.
        num = parsed.number
        ansi = 30 + num if num < 8 else 90 + (num - 8)
        return ("ansi", ansi)

    def _supports_unicode(self) -> bool:
        if not self.is_tty:
            return False
        encoding = (getattr(sys.stdout, "encoding", "") or "").lower()
        return "utf" in encoding

    def _supports_ansi_color(self) -> bool:
        if not self.is_tty:
            return False
        return bool(self.console.color_system)

    def _next_frame(self) -> list[int]:
        frame = self.frames[self.frame_idx]
        self.frame_idx = (self.frame_idx + 1) % len(self.frames)
        Spinner.last_frame_idx = self.frame_idx  # Update class variable
        return frame

    def step(self, text: str = None) -> None:
        if text is not None:
            self.text = text

        if not self.is_tty:
            return

        now = time.time()
        if not self.visible and now - self.start_time >= 0.5:
            self.visible = True
            self.last_update = 0.0
            if self.is_tty:
                self.console.show_cursor(False)

        if not self.visible or now - self.last_update < 0.075:
            return

        self.last_update = now
        frame_intensity = self._next_frame()
        colored_frame, visible_frame = self._render_frame(frame_intensity)

        # Determine the maximum width for the spinner line
        # Subtract 2 as requested, to leave a margin or prevent cursor wrapping issues
        max_spinner_width = self.console.width - 2
        if max_spinner_width < 0:  # Handle extremely narrow terminals
            max_spinner_width = 0

        current_text_payload = f" {self.text}"
        visible_text = current_text_payload

        # Truncate using visible character widths (ignore ANSI sequence lengths).
        if len(visible_frame) + len(visible_text) > max_spinner_width:
            remaining = max_spinner_width
            if remaining <= len(visible_frame):
                frame_intensity = frame_intensity[:remaining]
                colored_frame, visible_frame = self._render_frame(frame_intensity)
                visible_text = ""
            else:
                visible_text = visible_text[: remaining - len(visible_frame)]

        line_to_display = f"{colored_frame}{visible_text}"
        len_line_to_display = len(visible_frame) + len(visible_text)

        # Calculate padding to clear any remnants from a longer previous line
        padding_to_clear = " " * max(0, self.last_display_len - len_line_to_display)

        # Write the spinner frame, text, and any necessary clearing spaces
        sys.stdout.write(f"\r{line_to_display}{padding_to_clear}")
        self.last_display_len = len_line_to_display

        sys.stdout.flush()

    def end(self) -> None:
        if self.visible and self.is_tty:
            clear_len = self.last_display_len  # Use the length of the last displayed content
            sys.stdout.write("\r" + " " * clear_len + "\r")
            sys.stdout.flush()
            self.console.show_cursor(True)
        self.visible = False


class WaitingSpinner:
    """Background spinner that can be started/stopped safely."""

    def __init__(self, text: str = "Waiting for LLM", delay: float = 0.10, color: str = None):
        self.spinner = Spinner(text, color=color)
        self.delay = delay
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        while not self._stop_event.is_set():
            self.spinner.step()
            time.sleep(self.delay)
        self.spinner.end()

    def start(self):
        """Start the spinner in a background thread."""
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self):
        """Request the spinner to stop and wait briefly for the thread to exit."""
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=self.delay)
        self.spinner.end()

    # Allow use as a context-manager
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


def main():
    spinner = Spinner("Running spinner...")
    try:
        for _ in range(100):
            time.sleep(0.15)
            spinner.step()
        print("Success!")
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        spinner.end()


if __name__ == "__main__":
    main()
