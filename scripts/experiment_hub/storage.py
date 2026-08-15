"""Project layout, index workbook, database updates, conflicts, and snapshots."""

from __future__ import annotations

import math
import os
import shutil
import statistics
import tempfile
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .common import UNKNOWN, ensure_directory, is_missing, now_iso
from .schema import DATA_DICTIONARY_ROWS, DATABASE_SHEETS, INDEX_HEADERS


@dataclass
class ProjectPaths:
    root: Path

    @property
    def index_workbook(self) -> Path:
        return self.root / "实验文件总索引.xlsx"

    @property
    def database_workbook(self) -> Path:
        return self.root / "Research_Experiment_Database.xlsx"

    @property
    def provenance_dir(self) -> Path:
        return self.root / "运行记录"

    @property
    def import_ledger(self) -> Path:
        return self.provenance_dir / "import_log.jsonl"

    @property
    def snapshots_dir(self) -> Path:
        return self.root / "版本快照"

    @property
    def handoff_dir(self) -> Path:
        return self.root / "分析交接"

    @property
    def reports_dir(self) -> Path:
        return self.root / "报告"

    @property
    def dashboard_dir(self) -> Path:
        return self.root / "Dashboard"

    def experiment_dir(self, storage_date: str, nature: str, experiment_id: str, version: int) -> Path:
        year, month, _ = storage_date.split("-")
        suffix = "_v{}".format(version) if version > 1 else ""
        return self.root / year / "{}-{}".format(year, month) / "{}_{}_{}{}".format(
            storage_date, nature, experiment_id, suffix,
        )


def initialize_project(root: Path) -> ProjectPaths:
    paths = ProjectPaths(root.resolve())
    ensure_directory(paths.root)
    for directory in (
        paths.provenance_dir, paths.snapshots_dir, paths.handoff_dir,
        paths.reports_dir, paths.dashboard_dir,
    ):
        ensure_directory(directory)
    if not paths.index_workbook.exists():
        workbook = create_index_workbook()
        atomic_save_workbook(workbook, paths.index_workbook)
    if not paths.database_workbook.exists():
        workbook = create_database_workbook()
        atomic_save_workbook(workbook, paths.database_workbook)
    return paths


def create_index_workbook() -> Workbook:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Experiment_Index"
    sheet.append(INDEX_HEADERS)
    _format_sheet(sheet)
    attention = workbook.create_sheet("Needs_Attention")
    attention.append(["Experiment_ID", "Issue", "Severity", "Suggested_Action", "Status"])
    _format_sheet(attention)
    dictionary = workbook.create_sheet("Data_Dictionary")
    dictionary.append(["Field", "Meaning"])
    for field_name, meaning in (
        ("Experiment_Date", "Actual experimental date; may be Unknown"),
        ("Experiment_Nature", "Short experiment classification or 未分类实验"),
        ("Raw_Archive", "Immutable copy of the uploaded source file"),
        ("Organized_File", "Derived formatted copy for reading and analysis"),
        ("Metadata_Completeness", "Percent of recommended metadata fields present"),
    ):
        dictionary.append([field_name, meaning])
    _format_sheet(dictionary)
    return workbook


def create_database_workbook() -> Workbook:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for sheet_name, headers in DATABASE_SHEETS.items():
        sheet = workbook.create_sheet(sheet_name)
        sheet.append(headers)
        _format_sheet(sheet)
    dictionary = workbook["Data_Dictionary"]
    for row in DATA_DICTIONARY_ROWS:
        dictionary.append(list(row))
    _format_sheet(dictionary)
    return workbook


def _format_sheet(sheet: Any) -> None:
    sheet.sheet_view.showGridLines = False
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(name="Arial", bold=True, color="FFFFFF")
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name="Arial", size=10)
            cell.alignment = Alignment(horizontal="left", vertical="center")
    for column_index in range(1, sheet.max_column + 1):
        cells = [sheet.cell(row, column_index) for row in range(1, min(sheet.max_row, 200) + 1)]
        width = max(len(str(cell.value or "")) for cell in cells) + 2
        sheet.column_dimensions[get_column_letter(column_index)].width = min(max(width, 10), 34)
    sheet.auto_filter.ref = sheet.dimensions


def atomic_save_workbook(workbook: Workbook, path: Path) -> None:
    ensure_directory(path.parent)
    handle = tempfile.NamedTemporaryFile(delete=False, dir=str(path.parent), suffix=".xlsx")
    temp_path = Path(handle.name)
    handle.close()
    try:
        workbook.save(temp_path)
        os.replace(str(temp_path), str(path))
    finally:
        if temp_path.exists():
            temp_path.unlink()


def snapshot_database(paths: ProjectPaths) -> Optional[Path]:
    if not paths.database_workbook.exists() or paths.database_workbook.stat().st_size == 0:
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = paths.snapshots_dir / "Research_Experiment_Database_{}.xlsx".format(stamp)
    shutil.copy2(paths.database_workbook, target)
    return target


def next_experiment_id(index_path: Path, storage_date: str) -> str:
    date_token = storage_date.replace("-", "")
    prefix = "EXP-{}-".format(date_token)
    largest = 0
    if index_path.exists():
        workbook = load_workbook(index_path, read_only=True, data_only=True)
        try:
            sheet = workbook["Experiment_Index"]
            for row in sheet.iter_rows(min_row=2, values_only=True):
                value = str(row[0] or "")
                if value.startswith(prefix):
                    try:
                        largest = max(largest, int(value.rsplit("-", 1)[1]))
                    except ValueError:
                        pass
        finally:
            workbook.close()
    return "{}{:03d}".format(prefix, largest + 1)


def next_data_version(index_path: Path, experiment_id: str) -> int:
    count = 0
    if not index_path.exists():
        return 1
    workbook = load_workbook(index_path, read_only=True, data_only=True)
    try:
        sheet = workbook["Experiment_Index"]
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if str(row[0] or "") == experiment_id:
                count += 1
    finally:
        workbook.close()
    return count + 1


def append_index_entry(paths: ProjectPaths, entry: Dict[str, Any], issues: Sequence[Dict[str, Any]]) -> None:
    workbook = load_workbook(paths.index_workbook)
    try:
        index = workbook["Experiment_Index"]
        index.append([entry.get(header, "") for header in INDEX_HEADERS])
        attention = workbook["Needs_Attention"]
        for issue in issues:
            if issue.get("Severity") in {"HIGH", "MEDIUM"}:
                attention.append([
                    entry.get("Experiment_ID"), issue.get("Message"), issue.get("Severity"),
                    issue.get("Suggested_Action"), "Open",
                ])
        for sheet in workbook.worksheets:
            _format_sheet(sheet)
        atomic_save_workbook(workbook, paths.index_workbook)
    finally:
        workbook.close()


def update_database(
    paths: ProjectPaths, entry: Dict[str, Any], raw_records: Sequence[Dict[str, Any]],
    conditions: Sequence[Dict[str, Any]], issues: Sequence[Dict[str, Any]],
    import_record: Dict[str, Any],
) -> Dict[str, int]:
    snapshot_database(paths)
    workbook = load_workbook(paths.database_workbook)
    conflicts = 0
    appended = 0
    duplicates = 0
    try:
        _ensure_database_sheets(workbook)
        _append_row(workbook["Experiment_Index"], _database_index_row(entry))
        for condition in conditions:
            _append_row(workbook["Experiment_Conditions"], condition)
        raw_sheet = workbook["Raw_Data"]
        existing = _existing_measurement_keys(raw_sheet)
        for record in raw_records:
            key = _measurement_key(record)
            if key in existing:
                existing_record = existing[key]
                if _same_value(existing_record.get("Raw_Value"), record.get("Raw_Value")):
                    duplicates += 1
                    continue
                conflicts += 1
                _append_row(workbook["Data_Conflicts"], {
                    "Conflict_ID": "CONFLICT-" + uuid.uuid4().hex[:12].upper(),
                    "Experiment_ID": record.get("Experiment_ID"),
                    "Sample_ID": record.get("Sample_ID"),
                    "Metric": record.get("Metric"),
                    "Biological_Replicate": record.get("Biological_Replicate"),
                    "Technical_Replicate": record.get("Technical_Replicate"),
                    "Existing_Value": existing_record.get("Raw_Value"),
                    "New_Value": record.get("Raw_Value"),
                    "Existing_Source": existing_record.get("Source_File"),
                    "New_Source": record.get("Source_File"),
                    "Detected_At": now_iso(),
                    "Status": "OPEN",
                    "Resolution": "",
                })
                continue
            _append_row(raw_sheet, record)
            existing[key] = record
            appended += 1
        for issue in issues:
            enriched = dict(issue)
            enriched["Experiment_ID"] = entry.get("Experiment_ID")
            _append_row(workbook["QA_QC"], enriched)
        _append_row(workbook["Import_Log"], import_record)
        _rebuild_summary(workbook)
        _rebuild_cross_experiment(workbook)
        for sheet in workbook.worksheets:
            _format_sheet(sheet)
        atomic_save_workbook(workbook, paths.database_workbook)
    finally:
        workbook.close()
    return {"raw_records_appended": appended, "duplicates_skipped": duplicates, "conflicts": conflicts}


def _ensure_database_sheets(workbook: Workbook) -> None:
    for sheet_name, headers in DATABASE_SHEETS.items():
        if sheet_name not in workbook.sheetnames:
            sheet = workbook.create_sheet(sheet_name)
            sheet.append(headers)
        else:
            sheet = workbook[sheet_name]
            existing_headers = [cell.value for cell in sheet[1]]
            for header in headers:
                if header not in existing_headers:
                    sheet.cell(1, len(existing_headers) + 1, header)
                    existing_headers.append(header)


def _headers(sheet: Any) -> List[str]:
    return [str(cell.value or "") for cell in sheet[1]]


def _append_row(sheet: Any, record: Dict[str, Any]) -> None:
    headers = _headers(sheet)
    sheet.append([record.get(header, "") for header in headers])


def _sheet_records(sheet: Any) -> List[Dict[str, Any]]:
    headers = _headers(sheet)
    records = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if all(value is None for value in row):
            continue
        records.append({headers[index]: row[index] if index < len(row) else None for index in range(len(headers))})
    return records


def _database_index_row(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "Experiment_ID": entry.get("Experiment_ID"),
        "Project_ID": entry.get("Project_ID", UNKNOWN),
        "Experiment_Family": entry.get("Experiment_Family", UNKNOWN),
        "Experiment_Type": entry.get("Experiment_Nature", UNKNOWN),
        "Experiment_Name": entry.get("Experiment_Nature", UNKNOWN),
        "Experiment_Date": entry.get("Experiment_Date", UNKNOWN),
        "Operator": entry.get("Operator", UNKNOWN),
        "Objective": entry.get("Objective", UNKNOWN),
        "Hypothesis": entry.get("Hypothesis", UNKNOWN),
        "Sample_Type": entry.get("Sample_Type", UNKNOWN),
        "Key_Variable": entry.get("Key_Variable", UNKNOWN),
        "Control_Group": entry.get("Control_Group", UNKNOWN),
        "Status": entry.get("Status", "Imported"),
        "Outcome": entry.get("Outcome", UNKNOWN),
        "Source_File": entry.get("Raw_Archive"),
        "Organized_File": entry.get("Organized_File"),
        "File_SHA256": entry.get("File_SHA256"),
        "Import_Date": entry.get("Import_Date"),
        "Data_Version": entry.get("Data_Version"),
        "Metadata_Completeness": entry.get("Metadata_Completeness"),
        "QA_HIGH": entry.get("QA_HIGH"),
        "QA_MEDIUM": entry.get("QA_MEDIUM"),
        "QA_LOW": entry.get("QA_LOW"),
        "Notes": entry.get("Notes", ""),
    }


def _measurement_key(record: Dict[str, Any]) -> Tuple[str, ...]:
    return tuple(str(record.get(field, UNKNOWN)) for field in (
        "Experiment_ID", "Sample_ID", "Metric", "Biological_Replicate", "Technical_Replicate",
    ))


def _existing_measurement_keys(sheet: Any) -> Dict[Tuple[str, ...], Dict[str, Any]]:
    result: Dict[Tuple[str, ...], Dict[str, Any]] = {}
    for record in _sheet_records(sheet):
        result.setdefault(_measurement_key(record), record)
    return result


def _same_value(left: Any, right: Any) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
    return str(left).strip() == str(right).strip()


def _numeric(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    try:
        parsed = float(str(value).strip())
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _clear_data_rows(sheet: Any) -> None:
    if sheet.max_row > 1:
        sheet.delete_rows(2, sheet.max_row - 1)


def _rebuild_summary(workbook: Workbook) -> None:
    summary = workbook["Summary"]
    _clear_data_rows(summary)
    grouped: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for record in _sheet_records(workbook["Raw_Data"]):
        value = _numeric(record.get("Raw_Value"))
        if value is None:
            continue
        # Summarize at Experiment × Group × Metric × Unit. Sample_ID commonly
        # identifies an individual biological sample, so grouping by Sample_ID
        # would incorrectly reduce Biological_N to one.
        key = tuple(str(record.get(field, UNKNOWN)) for field in (
            "Experiment_ID", "Group", "Metric", "Unit",
        ))
        copied = dict(record)
        copied["_value"] = value
        grouped[key].append(copied)
    for key, records in grouped.items():
        bio_groups: Dict[str, List[float]] = defaultdict(list)
        unassigned: List[float] = []
        for record in records:
            bio = str(record.get("Biological_Replicate", UNKNOWN) or UNKNOWN)
            if bio not in {UNKNOWN, "Not Provided", "NA", ""}:
                bio_groups[bio].append(record["_value"])
            else:
                unassigned.append(record["_value"])
        if bio_groups:
            analysis_values = [statistics.mean(values) for values in bio_groups.values()]
            biological_n = len(analysis_values)
            technical_aggregation = "Mean within each biological replicate"
        else:
            analysis_values = [record["_value"] for record in records]
            biological_n = 0
            technical_aggregation = "Not separated; descriptive observations only"
        mean_value = statistics.mean(analysis_values)
        median_value = statistics.median(analysis_values)
        sd_value = statistics.stdev(analysis_values) if len(analysis_values) >= 2 else None
        sem_value = sd_value / math.sqrt(len(analysis_values)) if sd_value is not None else None
        cv_value = (sd_value / abs(mean_value) * 100) if sd_value is not None and mean_value != 0 else None
        _append_row(summary, {
            "Experiment_ID": key[0], "Group": key[1], "Sample_ID": "All Samples in Group",
            "Metric": key[2], "Unit": key[3], "Observed_N": len(records),
            "Biological_N": biological_n, "Technical_Aggregation": technical_aggregation,
            "Mean": mean_value, "Median": median_value, "SD": sd_value, "SEM": sem_value,
            "Min": min(analysis_values), "Max": max(analysis_values), "CV_Percent": cv_value,
            "Inference_Eligible": "Yes" if biological_n >= 2 else "No",
            "Notes": "Inferential statistics require design review; technical replicates are not independent n.",
        })


def _rebuild_cross_experiment(workbook: Workbook) -> None:
    sheet = workbook["Cross_Experiment_Comparison"]
    _clear_data_rows(sheet)
    index_records = _sheet_records(workbook["Experiment_Index"])
    family_by_id = {str(record.get("Experiment_ID")): str(record.get("Experiment_Family") or UNKNOWN) for record in index_records}
    date_by_id = {str(record.get("Experiment_ID")): str(record.get("Experiment_Date") or UNKNOWN) for record in index_records}
    grouped: Dict[Tuple[str, str, str], List[Tuple[str, str, float]]] = defaultdict(list)
    for record in _sheet_records(workbook["Summary"]):
        mean_value = _numeric(record.get("Mean"))
        if mean_value is None:
            continue
        experiment_id = str(record.get("Experiment_ID"))
        family = family_by_id.get(experiment_id, UNKNOWN)
        key = (family, str(record.get("Metric") or UNKNOWN), str(record.get("Unit") or UNKNOWN))
        grouped[key].append((experiment_id, date_by_id.get(experiment_id, UNKNOWN), mean_value))
    for key, values in grouped.items():
        dates = sorted(date_value for _, date_value, _ in values if date_value != UNKNOWN)
        _append_row(sheet, {
            "Experiment_Family": key[0], "Metric": key[1], "Unit": key[2],
            "Experiment_Count": len({experiment_id for experiment_id, _, _ in values}),
            "First_Date": dates[0] if dates else UNKNOWN,
            "Latest_Date": dates[-1] if dates else UNKNOWN,
            "Historical_Mean": statistics.mean(value for _, _, value in values),
            "Best_Value": UNKNOWN, "Best_Experiment_ID": UNKNOWN,
            "Metric_Direction": "Not Provided",
            "Reproducibility_Status": "Not Evaluated",
            "Notes": "Best result is not inferred until maximize/minimize/target direction is provided.",
        })
