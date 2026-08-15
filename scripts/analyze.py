#!/usr/bin/env python3
"""Compatibility entry point for analysis packages."""

import sys
from experiment_hub.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["analyze"] + sys.argv[1:]))
