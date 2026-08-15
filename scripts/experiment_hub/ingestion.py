"""End-to-end single-file ingestion and archival workflow."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .common import (
    UNKNOWN, append_jsonl, ensure_directory, is_missing, now_iso, parse_iso_date,
    read_jsonl, safe_name, sha256_file, today_iso, write_json,
)
from .excel import build_organized_workbook, inspect_source, tables_to_long_records
from .quality import apply_outlier_flags, issue_counts, validate_tables
from .schema import SUPPORTED_EXTENSIONS
from .storage import (
    ProjectPaths, append_index_entry, atomic_save_workbook, initialize_project,
    next_data_version, next_experiment_id, update_database,
)


def validate_input_file(source: Path) -> Path:
    source = source.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError("Input file not found: {}".format(source))
    if not source.is_file():
        raise ValueError("Input must be a regular file: {}".format(source))
    if source.is_symlink():
        raise ValueError("Symlink input is not accepted; provide the real source file")
    extension = source.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        if extension == ".xls":
            raise ValueError("Legacy .xls is not read directly; save a derived copy as .xlsx or CSV")
        raise ValueError("Unsupported input extension: {}".format(extension))
    return source


def ingest_file(
    source: Path, project_root: Path, experiment_date: Optional[str] = None,
    nature: Optional[str] = None, experiment_id: Optional[str] = None,
    family: Optional[str] = None, project_id: Optional[str] = None,
    operator: Optional[str] = None, status: str = "Imported",
    outcome: str = UNKNOWN, notes: str = "",
) -> Dict[str, Any]:
    """Archive one source file, create an organized copy, and update indexes."""
    source = validate_input_file(source)
    paths = initialize_project(project_root)
    file_hash = sha256_file(source)
    prior = _find_prior_hash(paths, file_hash)
    if prior:
        return {
            "status": "already_imported",
            "message": "Identical file hash is already present; no files were changed",
            "experiment_id": prior.get("Experiment_ID"),
            "organized_file": prior.get("Organized_File"),
            "raw_archive": prior.get("Raw_Archive"),
            "file_sha256": file_hash,
        }

    detected, tables, read_warnings = inspect_source(source)
    actual_date, storage_date, date_source = _resolve_date(experiment_date, detected)
    experiment_nature, nature_source, nature_confidence = _resolve_nature(nature, detected)
    safe_nature = safe_name(experiment_nature)
    if experiment_id:
        resolved_id = safe_name(experiment_id, fallback="EXP-{}-001".format(storage_date.replace("-", "")), max_length=40)
    else:
        resolved_id = next_experiment_id(paths.index_workbook, storage_date)
    data_version = next_data_version(paths.index_workbook, resolved_id)
    resolved_family, family_status = _resolve_family(family, detected, experiment_nature)
    experiment_dir = paths.experiment_dir(storage_date, safe_nature, resolved_id, data_version)
    raw_dir = ensure_directory(experiment_dir / "原始数据")
    organized_dir = ensure_directory(experiment_dir / "整理结果")
    raw_archive = raw_dir / source.name
    organized_file = organized_dir / "{}_{}_整理版.xlsx".format(storage_date, safe_nature)
    if raw_archive.exists():
        raise FileExistsError("Raw archive target already exists: {}".format(raw_archive))
    shutil.copy2(source, raw_archive)

    import_date = now_iso()
    raw_records, conditions = tables_to_long_records(
        tables, resolved_id, source.name, import_date, data_version,
    )
    completeness = _metadata_completeness(
        actual_date, experiment_nature, raw_records,
    )
    organized_metadata: Dict[str, Any] = {
        "Experiment_ID": resolved_id,
        "Experiment_Date": actual_date,
        "Experiment_Nature": experiment_nature,
        "Experiment_Family": resolved_family,
        "Project_ID": project_id or detected.get("project_id") or UNKNOWN,
        "Original_File": source.name,
        "File_SHA256": file_hash,
        "Import_Date": import_date,
        "Data_Version": data_version,
        "Raw_Archive": str(raw_archive),
        "Organized_File": str(organized_file),
        "Metadata_Completeness": completeness,
    }
    issues = validate_tables(tables, organized_metadata)
    for warning in read_warnings:
        if not any(issue.get("Message") == warning for issue in issues):
            issues.append({
                "Issue_ID": "QA-" + uuid.uuid4().hex[:12].upper(),
                "Severity": "LOW", "Category": "Import Warning", "Message": warning,
                "Source_Sheet": "", "Source_Row": "", "Source_Column": "",
                "Suggested_Action": "Review the organized copy", "Detected_At": import_date,
                "Resolved": "No", "Resolution_Notes": "",
            })
    apply_outlier_flags(raw_records, issues)
    counts = issue_counts(issues)
    organized_workbook = build_organized_workbook(organized_metadata, tables, issues)
    atomic_save_workbook(organized_workbook, organized_file)
    organized_workbook.close()

    entry: Dict[str, Any] = {
        "Experiment_ID": resolved_id,
        "Experiment_Date": actual_date,
        "Experiment_Nature": experiment_nature,
        "Experiment_Family": resolved_family,
        "Project_ID": project_id or detected.get("project_id") or UNKNOWN,
        "Status": status,
        "Outcome": outcome,
        "Original_File": source.name,
        "Raw_Archive": str(raw_archive),
        "Organized_File": str(organized_file),
        "File_SHA256": file_hash,
        "Import_Date": import_date,
        "Data_Version": data_version,
        "Metadata_Completeness": completeness,
        "QA_HIGH": counts.get("HIGH", 0),
        "QA_MEDIUM": counts.get("MEDIUM", 0),
        "QA_LOW": counts.get("LOW", 0),
        "Operator": operator or detected.get("operator") or UNKNOWN,
        "Objective": detected.get("objective") or UNKNOWN,
        "Notes": _join_notes(notes, [
            "Experiment date source: {}".format(date_source),
            "Experiment nature source: {} ({})".format(nature_source, nature_confidence),
            "Experiment family status: {}".format(family_status),
        ]),
    }
    import_record = {
        "Import_ID": "IMPORT-" + uuid.uuid4().hex[:12].upper(),
        "Experiment_ID": resolved_id,
        "Source_File": source.name,
        "File_SHA256": file_hash,
        "Import_Date": import_date,
        "Data_Version": data_version,
        "Status": "IMPORTED",
        "Raw_Archive": str(raw_archive),
        "Organized_File": str(organized_file),
        "Message": "Source archived and organized copy generated",
    }
    database_result = update_database(
        paths, entry, raw_records, conditions, issues, import_record,
    )
    append_index_entry(paths, entry, issues)
    ledger_record = dict(import_record)
    ledger_record.update({
        "Original_Path": str(source),
        "Experiment_Date": actual_date,
        "Storage_Date": storage_date,
        "Experiment_Nature": experiment_nature,
        "Experiment_Family": resolved_family,
        "Metadata_Completeness": completeness,
        "QA_Counts": counts,
        "Database_Result": database_result,
    })
    append_jsonl(paths.import_ledger, ledger_record)
    manifest_path = experiment_dir / "import_manifest.json"
    write_json(manifest_path, ledger_record)
    return {
        "status": "imported",
        "experiment_id": resolved_id,
        "experiment_date": actual_date,
        "storage_date": storage_date,
        "experiment_nature": experiment_nature,
        "experiment_family": resolved_family,
        "raw_archive": str(raw_archive),
        "organized_file": str(organized_file),
        "index_workbook": str(paths.index_workbook),
        "database_workbook": str(paths.database_workbook),
        "manifest": str(manifest_path),
        "file_sha256": file_hash,
        "metadata_completeness": completeness,
        "qa_counts": counts,
        "database_result": database_result,
    }


def inspect_and_validate(source: Path) -> Dict[str, Any]:
    """Read-only validation for a source file."""
    source = validate_input_file(source)
    detected, tables, read_warnings = inspect_source(source)
    date_value = parse_iso_date(detected.get("experiment_date")) or UNKNOWN
    nature_value = detected.get("experiment_name") or "未分类实验"
    metadata = {"Experiment_Date": date_value, "Experiment_Nature": nature_value}
    issues = validate_tables(tables, metadata)
    return {
        "source_file": str(source),
        "file_sha256": sha256_file(source),
        "detected_metadata": detected,
        "tables": [
            {
                "source_sheet": table.source_sheet,
                "header_row": table.header_row,
                "columns": table.headers,
                "data_rows": len(table.rows),
            }
            for table in tables
        ],
        "read_warnings": read_warnings,
        "qa_counts": issue_counts(issues),
        "issues": issues,
    }


def _find_prior_hash(paths: ProjectPaths, file_hash: str) -> Optional[Dict[str, Any]]:
    for record in read_jsonl(paths.import_ledger):
        if record.get("File_SHA256") == file_hash and record.get("Status") == "IMPORTED":
            return record
    return None


def _resolve_date(provided: Optional[str], detected: Dict[str, Any]) -> tuple:
    if provided:
        parsed = parse_iso_date(provided)
        if not parsed:
            raise ValueError("--date must be a valid date such as 2026-08-14")
        return parsed, parsed, "User_Provided"
    parsed = parse_iso_date(detected.get("experiment_date"))
    if parsed:
        return parsed, parsed, detected.get("experiment_date_source", "Detected")
    return UNKNOWN, today_iso(), "Import_Date_Fallback_for_Storage_Only"


def _resolve_nature(provided: Optional[str], detected: Dict[str, Any]) -> tuple:
    if provided and provided.strip():
        return provided.strip(), "User_Provided", "HIGH"
    detected_name = detected.get("experiment_name")
    if not is_missing(detected_name):
        return str(detected_name).strip(), detected.get("experiment_name_source", "Detected"), detected.get("nature_confidence", "MEDIUM")
    return "未分类实验", "Not_Provided", "LOW"


def _resolve_family(provided: Optional[str], detected: Dict[str, Any], nature: str) -> tuple:
    if provided and provided.strip():
        return provided.strip(), "Confirmed by user"
    detected_family = detected.get("family")
    if not is_missing(detected_family):
        return str(detected_family).strip(), "Detected from labeled metadata"
    if nature != "未分类实验":
        return nature, "Provisional from experiment nature; review Family_Rules later"
    return UNKNOWN, "Needs confirmation"


def _metadata_completeness(
    experiment_date: str, nature: str, raw_records: List[Dict[str, Any]],
) -> int:
    checks = [
        experiment_date != UNKNOWN,
        nature not in {UNKNOWN, "未分类实验"},
        any(record.get("Sample_ID") not in {None, "", UNKNOWN} for record in raw_records),
        any(record.get("Group") not in {None, "", UNKNOWN} for record in raw_records),
        any(record.get("Metric") not in {None, "", UNKNOWN} for record in raw_records),
        any(record.get("Unit") not in {None, "", UNKNOWN} for record in raw_records),
        any(record.get("Biological_Replicate") not in {None, "", UNKNOWN} for record in raw_records),
        any(record.get("Technical_Replicate") not in {None, "", UNKNOWN} for record in raw_records),
    ]
    return int(round(sum(checks) / float(len(checks)) * 100))


def _join_notes(base: str, parts: List[str]) -> str:
    values = [base.strip()] if base and base.strip() else []
    values.extend(part for part in parts if part)
    return " | ".join(values)
