"""Compatibility wrapper: 11C is now part of the complete animation."""

from orthovideo.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["--video"]))
