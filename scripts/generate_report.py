#!/usr/bin/env python3
"""Compatibility entry point for reports."""

import sys
from experiment_hub.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["report"] + sys.argv[1:]))
