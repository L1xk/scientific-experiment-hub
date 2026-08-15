"""Create traceable analysis-ready handoff packages from the database."""

from __future__ import annotations

import csv
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from openpyxl import Workbook, load_workbook

from .common import UNKNOWN, ensure_directory, now_iso, parse_iso_date, write_json
from .storage import ProjectPaths, _format_sheet, atomic_save_workbook, initialize_project


def load_sheet_records(workbook_path: Path, sheet_name: str) -> List[Dict[str, Any]]:
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        if sheet_name not in workbook.sheetnames:
            return []
        sheet = workbook[sheet_name]
        headers = [str(cell.value or "") for cell in sheet[1]]
        records: List[Dict[str, Any]] = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if all(value is None for value in row):
                continue
            records.append({headers[index]: row[index] if index < len(row) else None for index in range(len(headers))})
        return records
    finally:
        workbook.close()


def filter_experiments(
    records: Sequence[Dict[str, Any]], start: Optional[str] = None,
    end: Optional[str] = None, nature: Optional[str] = None,
    family: Optional[str] = None, experiment_ids: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    start_date = parse_iso_date(start) if start else None
    end_date = parse_iso_date(end) if end else None
    allowed_ids = {str(value) for value in experiment_ids or []}
    filtered: List[Dict[str, Any]] = []
    for record in records:
        experiment_id = str(record.get("Experiment_ID") or "")
        if allowed_ids and experiment_id not in allowed_ids:
            continue
        record_date = parse_iso_date(record.get("Experiment_Date"))
        if start_date and (not record_date or record_date < start_date):
            continue
        if end_date and (not record_date or record_date > end_date):
            continue
        record_nature = str(record.get("Experiment_Name") or record.get("Experiment_Type") or "")
        if nature and nature.casefold() not in record_nature.casefold():
            continue
        record_family = str(record.get("Experiment_Family") or "")
        if family and family.casefold() not in record_family.casefold():
            continue
        filtered.append(record)
    return filtered


def create_analysis_package(
    project_root: Path, start: Optional[str] = None, end: Optional[str] = None,
    nature: Optional[str] = None, family: Optional[str] = None,
    experiment_ids: Optional[Iterable[str]] = None, package_name: Optional[str] = None,
) -> Dict[str, Any]:
    paths = initialize_project(project_root)
    index_records = load_sheet_records(paths.database_workbook, "Experiment_Index")
    selected_index = filter_experiments(index_records, start, end, nature, family, experiment_ids)
    selected_ids = {str(record.get("Experiment_ID")) for record in selected_index}
    raw_records = [
        record for record in load_sheet_records(paths.database_workbook, "Raw_Data")
        if str(record.get("Experiment_ID")) in selected_ids
    ]
    summary_records = [
        record for record in load_sheet_records(paths.database_workbook, "Summary")
        if str(record.get("Experiment_ID")) in selected_ids
    ]
    qa_records = [
        record for record in load_sheet_records(paths.database_workbook, "QA_QC")
        if str(record.get("Experiment_ID")) in selected_ids
    ]
    condition_records = [
        record for record in load_sheet_records(paths.database_workbook, "Experiment_Conditions")
        if str(record.get("Experiment_ID")) in selected_ids
    ]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = package_name or "analysis_{}".format(stamp)
    output_dir = _unique_directory(paths.handoff_dir / folder_name)
    ensure_directory(output_dir)
    analysis_csv = output_dir / "analysis_ready.csv"
    summary_csv = output_dir / "descriptive_summary.csv"
    dictionary_csv = output_dir / "data_dictionary.csv"
    _write_csv(analysis_csv, raw_records)
    _write_csv(summary_csv, summary_records)
    _write_csv(dictionary_csv, load_sheet_records(paths.database_workbook, "Data_Dictionary"))
    filtered_workbook = output_dir / "filtered_data.xlsx"
    _write_filtered_workbook(filtered_workbook, {
        "Experiment_Index": selected_index,
        "Experiment_Conditions": condition_records,
        "Raw_Data": raw_records,
        "Summary": summary_records,
        "QA_QC": qa_records,
    })
    context_path = output_dir / "experiment_context.md"
    context_path.write_text(
        _context_markdown(selected_index, raw_records, summary_records, qa_records, start, end),
        encoding="utf-8", newline="\n",
    )
    qa_path = output_dir / "qa_report.md"
    qa_path.write_text(_qa_markdown(qa_records), encoding="utf-8", newline="\n")
    provenance = {
        "package_id": "PKG-" + uuid.uuid4().hex[:12].upper(),
        "generated_at": now_iso(),
        "database": str(paths.database_workbook),
        "filters": {
            "start": start, "end": end, "nature": nature, "family": family,
            "experiment_ids": list(experiment_ids or []),
        },
        "experiment_ids": sorted(selected_ids),
        "record_counts": {
            "experiments": len(selected_index), "measurements": len(raw_records),
            "summary_rows": len(summary_records), "qa_issues": len(qa_records),
        },
        "evidence_labels": {
            "Measured": "Raw_Data.Raw_Value copied from archived source",
            "Calculated": "Summary values recomputed from Raw_Data",
            "Inferred": "Not generated by this lightweight package",
            "Hypothesis": "Not generated from data automatically",
        },
    }
    provenance_path = output_dir / "provenance.json"
    write_json(provenance_path, provenance)
    return {
        "status": "created",
        "output_dir": str(output_dir),
        "filtered_data": str(filtered_workbook),
        "analysis_ready": str(analysis_csv),
        "summary": str(summary_csv),
        "context": str(context_path),
        "qa_report": str(qa_path),
        "provenance": str(provenance_path),
        "record_counts": provenance["record_counts"],
    }


def _unique_directory(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.parent / "{}_{}".format(path.name, counter)
        if not candidate.exists():
            return candidate
        counter += 1


def _write_csv(path: Path, records: Sequence[Dict[str, Any]]) -> None:
    ensure_directory(path.parent)
    headers: List[str] = []
    for record in records:
        for key in record:
            if key not in headers:
                headers.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        if not headers:
            handle.write("")
            return
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def _write_filtered_workbook(path: Path, groups: Dict[str, Sequence[Dict[str, Any]]]) -> None:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for sheet_name, records in groups.items():
        sheet = workbook.create_sheet(sheet_name)
        headers: List[str] = []
        for record in records:
            for key in record:
                if key not in headers:
                    headers.append(key)
        if not headers:
            headers = ["Status"]
            records = [{"Status": "No matching records"}]
        sheet.append(headers)
        for record in records:
            sheet.append([record.get(header, "") for header in headers])
        _format_sheet(sheet)
    atomic_save_workbook(workbook, path)
    workbook.close()


def _context_markdown(
    index_records: Sequence[Dict[str, Any]], raw_records: Sequence[Dict[str, Any]],
    summary_records: Sequence[Dict[str, Any]], qa_records: Sequence[Dict[str, Any]],
    start: Optional[str], end: Optional[str],
) -> str:
    families = sorted({str(record.get("Experiment_Family") or UNKNOWN) for record in index_records})
    metrics = sorted({str(record.get("Metric") or UNKNOWN) for record in raw_records})
    missing_replicates = sum(
        1 for record in raw_records
        if str(record.get("Biological_Replicate") or UNKNOWN) == UNKNOWN
    )
    return "\n".join([
        "# Experiment analysis context",
        "",
        "- Generated from: `Research_Experiment_Database.xlsx`",
        "- Date filter: {} to {}".format(start or "All", end or "All"),
        "- Experiments: {}".format(len(index_records)),
        "- Measurements: {}".format(len(raw_records)),
        "- Summary rows: {}".format(len(summary_records)),
        "- Experiment families: {}".format(", ".join(families) if families else "None"),
        "- Metrics: {}".format(", ".join(metrics) if metrics else "None"),
        "- Measurements missing biological replicate identifiers: {}".format(missing_replicates),
        "- QA issues in scope: {}".format(len(qa_records)),
        "",
        "## Evidence boundaries",
        "",
        "- **Measured:** values in `analysis_ready.csv` and `Raw_Data`.",
        "- **Calculated:** descriptive values in `descriptive_summary.csv`.",
        "- **Inferred:** none; use `nature-statistics` after reviewing design and replication.",
        "- **Hypothesis:** none; hypotheses require researcher input.",
        "",
    ])


def _qa_markdown(records: Sequence[Dict[str, Any]]) -> str:
    lines = ["# Data quality report", "", "Automated flags are review prompts, not deletion rules.", ""]
    if not records:
        lines.append("No QA issues were recorded for the selected experiments.")
        return "\n".join(lines) + "\n"
    for severity in ("HIGH", "MEDIUM", "LOW"):
        matching = [record for record in records if str(record.get("Severity")).upper() == severity]
        lines.extend(["## {} ({})".format(severity, len(matching)), ""])
        for record in matching:
            lines.append("- {} — {} ({}:{} {})".format(
                record.get("Category", "QA"), record.get("Message", ""),
                record.get("Source_Sheet", ""), record.get("Source_Row", ""),
                record.get("Source_Column", ""),
            ))
        lines.append("")
    return "\n".join(lines) + "\n"
