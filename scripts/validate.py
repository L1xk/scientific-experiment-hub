#!/usr/bin/env python3
"""Compatibility entry point for read-only QA."""

import sys
from experiment_hub.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["validate"] + sys.argv[1:]))
