"""Build a portable, self-contained experiment overview dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .analysis import load_sheet_records
from .common import ensure_directory, json_default, now_iso
from .storage import initialize_project


DASHBOARD_EXCLUDED_EXPERIMENT_FIELDS = {
    "QA_HIGH", "QA_MEDIUM", "QA_LOW", "Metadata_Completeness",
}


def build_dashboard(project_root: Path, output: Path = None) -> Dict[str, Any]:
    paths = initialize_project(project_root)
    index_records = load_sheet_records(paths.database_workbook, "Experiment_Index")
    summary_records = load_sheet_records(paths.database_workbook, "Summary")
    dashboard_records = [
        {
            key: value for key, value in record.items()
            if key not in DASHBOARD_EXCLUDED_EXPERIMENT_FIELDS
        }
        for record in index_records
    ]
    payload = {
        "generated_at": now_iso(),
        "experiments": dashboard_records,
        "summary": summary_records,
    }
    template_path = Path(__file__).resolve().parents[2] / "assets" / "templates" / "dashboard_template.html"
    if not template_path.exists():
        raise FileNotFoundError("Dashboard template missing: {}".format(template_path))
    template = template_path.read_text(encoding="utf-8")
    data_json = json.dumps(payload, ensure_ascii=False, default=json_default).replace("</", "<\\/")
    html = template.replace("{{DATA_JSON}}", data_json)
    destination = output or (paths.dashboard_dir / "experiment_dashboard.html")
    destination = destination.resolve()
    ensure_directory(destination.parent)
    destination.write_text(html, encoding="utf-8", newline="\n")
    return {
        "status": "created",
        "dashboard": str(destination),
        "experiments": len(index_records),
        "summary_rows": len(summary_records),
    }
