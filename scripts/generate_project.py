"""Backward-compatible entry point for the unified OrthoVideo pipeline."""

from orthovideo.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
