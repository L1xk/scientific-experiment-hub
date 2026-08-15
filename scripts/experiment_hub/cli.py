"""Command-line interface for Scientific Experiment Hub."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .analysis import create_analysis_package, filter_experiments, load_sheet_records
from .common import json_default, write_json
from .dashboard import build_dashboard
from .ingestion import ingest_file, inspect_and_validate
from .reporting import REPORT_TYPES, generate_report
from .storage import initialize_project
from .templates import create_templates


def default_project_root() -> Path:
    configured = os.environ.get("SEH_PROJECT_ROOT")
    if configured:
        return Path(configured)
    if os.name == "nt" and Path("D:/codex").exists():
        return Path("D:/codex/实验数据中心")
    return Path.cwd() / "实验数据中心"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scientific-experiment-hub",
        description="Archive raw experiment files, generate organized Excel copies, and maintain a traceable database.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize an experiment data center")
    _project_argument(init_parser)

    ingest_parser = subparsers.add_parser("ingest", help="Archive and organize one experiment file")
    ingest_parser.add_argument("source", type=Path)
    _project_argument(ingest_parser)
    ingest_parser.add_argument("--date", help="Actual experiment date, YYYY-MM-DD")
    ingest_parser.add_argument("--nature", help="Short experiment nature/name")
    ingest_parser.add_argument("--experiment-id", help="Existing ID for a new data version; otherwise auto-assigned")
    ingest_parser.add_argument("--family", help="Confirmed Experiment Family")
    ingest_parser.add_argument("--project-id")
    ingest_parser.add_argument("--operator")
    ingest_parser.add_argument("--status", default="Imported")
    ingest_parser.add_argument("--outcome", default="Unknown")
    ingest_parser.add_argument("--notes", default="")

    validate_parser = subparsers.add_parser("validate", help="Read-only source inspection and QA")
    validate_parser.add_argument("source", type=Path)
    validate_parser.add_argument("--output", type=Path, help="Optional JSON result path")

    analyze_parser = subparsers.add_parser("analyze", help="Create an analysis-ready handoff package")
    _project_argument(analyze_parser)
    _filter_arguments(analyze_parser)
    analyze_parser.add_argument("--name", help="Package folder name")

    query_parser = subparsers.add_parser("query", help="Query the experiment index")
    _project_argument(query_parser)
    _filter_arguments(query_parser)
    query_parser.add_argument("--text", help="Case-insensitive search across index fields")
    query_parser.add_argument("--outcome")

    dashboard_parser = subparsers.add_parser("dashboard", help="Regenerate the self-contained HTML dashboard")
    _project_argument(dashboard_parser)
    dashboard_parser.add_argument("--output", type=Path)

    report_parser = subparsers.add_parser("report", help="Generate a fresh report from the database")
    _project_argument(report_parser)
    report_parser.add_argument("--type", required=True, choices=sorted(REPORT_TYPES))
    report_parser.add_argument("--start")
    report_parser.add_argument("--end")
    report_parser.add_argument("--month", help="YYYY-MM for monthly report")
    report_parser.add_argument("--title")

    template_parser = subparsers.add_parser("create-templates", help="Generate reusable Excel templates")
    template_parser.add_argument("--output", type=Path, required=True)
    return parser


def _project_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project", type=Path, default=default_project_root(),
        help="Experiment data center root (default: SEH_PROJECT_ROOT or D:/codex/实验数据中心)",
    )


def _filter_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--nature")
    parser.add_argument("--family")
    parser.add_argument("--experiment-id", action="append", dest="experiment_ids")


def run_command(args: argparse.Namespace) -> Dict[str, Any]:
    if args.command == "init":
        paths = initialize_project(args.project)
        return {
            "status": "initialized", "project": str(paths.root),
            "index_workbook": str(paths.index_workbook),
            "database_workbook": str(paths.database_workbook),
        }
    if args.command == "ingest":
        result = ingest_file(
            args.source, args.project, experiment_date=args.date, nature=args.nature,
            experiment_id=args.experiment_id, family=args.family, project_id=args.project_id,
            operator=args.operator, status=args.status, outcome=args.outcome, notes=args.notes,
        )
        if result.get("status") == "imported":
            result["dashboard"] = build_dashboard(args.project)["dashboard"]
        return result
    if args.command == "validate":
        result = inspect_and_validate(args.source)
        if args.output:
            write_json(args.output, result)
            result["output"] = str(args.output.resolve())
        return result
    if args.command == "analyze":
        return create_analysis_package(
            args.project, start=args.start, end=args.end, nature=args.nature,
            family=args.family, experiment_ids=args.experiment_ids, package_name=args.name,
        )
    if args.command == "query":
        return _query(args)
    if args.command == "dashboard":
        return build_dashboard(args.project, args.output)
    if args.command == "report":
        return generate_report(
            args.project, args.type, start=args.start, end=args.end,
            month=args.month, title=args.title,
        )
    if args.command == "create-templates":
        return create_templates(args.output.resolve())
    raise ValueError("Unknown command: {}".format(args.command))


def _query(args: argparse.Namespace) -> Dict[str, Any]:
    paths = initialize_project(args.project)
    records = load_sheet_records(paths.database_workbook, "Experiment_Index")
    records = filter_experiments(
        records, args.start, args.end, args.nature, args.family, args.experiment_ids,
    )
    if args.outcome:
        records = [record for record in records if str(record.get("Outcome") or "").casefold() == args.outcome.casefold()]
    if args.text:
        needle = args.text.casefold()
        records = [record for record in records if needle in " ".join(str(value) for value in record.values()).casefold()]
    return {"status": "ok", "count": len(records), "experiments": records}


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_command(args)
    except Exception as exc:
        error = {"status": "error", "error_type": type(exc).__name__, "message": str(exc)}
        print(json.dumps(error, ensure_ascii=False, default=json_default), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, default=json_default))
    return 0

