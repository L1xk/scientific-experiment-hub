#!/usr/bin/env python3
"""Compatibility entry point for the HTML dashboard."""

import sys
from experiment_hub.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["dashboard"] + sys.argv[1:]))
