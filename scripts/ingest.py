#!/usr/bin/env python3
"""Compatibility entry point for one-file ingestion."""

import sys
from experiment_hub.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["ingest"] + sys.argv[1:]))
