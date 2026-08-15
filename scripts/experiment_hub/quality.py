"""Conservative data-quality checks. Flags are never deletion instructions."""

from __future__ import annotations

import math
import statistics
import uuid
from collections import Counter
from typing import Any, Dict, List, Sequence, Tuple

from .common import UNKNOWN, is_missing, now_iso
from .excel import TableData, normalize_label


def make_issue(
    severity: str, category: str, message: str, source_sheet: str = "",
    source_row: Any = "", source_column: str = "", suggested_action: str = "Review and confirm",
) -> Dict[str, Any]:
    return {
        "Issue_ID": "QA-" + uuid.uuid4().hex[:12].upper(),
        "Severity": severity,
        "Category": category,
        "Message": message,
        "Source_Sheet": source_sheet,
        "Source_Row": source_row,
        "Source_Column": source_column,
        "Suggested_Action": suggested_action,
        "Detected_At": now_iso(),
        "Resolved": "No",
        "Resolution_Notes": "",
    }


def validate_tables(
    tables: Sequence[TableData], metadata: Dict[str, Any], max_row_issues: int = 100,
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    if metadata.get("Experiment_Date") in {None, "", UNKNOWN}:
        issues.append(make_issue(
            "MEDIUM", "Incomplete Metadata", "Experiment date is not provided",
            suggested_action="Provide the actual experiment date; do not substitute file modification time",
        ))
    if metadata.get("Experiment_Nature") in {None, "", UNKNOWN, "未分类实验"}:
        issues.append(make_issue(
            "MEDIUM", "Incomplete Metadata", "Experiment nature is unclassified",
            suggested_action="Provide a short experiment name or nature",
        ))
    if not tables:
        issues.append(make_issue(
            "HIGH", "No Data Table", "No non-empty tabular region was detected",
            suggested_action="Inspect the source workbook and identify the intended data sheet",
        ))
        return issues

    for table in tables:
        if not table.validate:
            continue
        for warning in table.warnings:
            issues.append(make_issue(
                "LOW", "Naming Inconsistency", warning, table.source_sheet,
                suggested_action="Confirm the renamed organized-copy header",
            ))
        if not table.rows:
            issues.append(make_issue(
                "MEDIUM", "Empty Table", "Header detected but no data rows found",
                table.source_sheet, table.header_row,
            ))
            continue
        issues.extend(_missingness_issues(table))
        issues.extend(_duplicate_issues(table, max_row_issues))
        issues.extend(_type_issues(table))
        issues.extend(_range_and_outlier_issues(table, max_row_issues))
        issues.extend(_unit_issues(table))
    return issues


def _missingness_issues(table: TableData) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    total = len(table.rows)
    for header in table.headers:
        missing = sum(1 for row in table.rows if is_missing(row.get(header)))
        if not missing:
            continue
        ratio = missing / float(total)
        severity = "MEDIUM" if ratio >= 0.5 else "LOW"
        issues.append(make_issue(
            severity, "Missing Values",
            "Column '{}' has {} missing of {} rows ({:.1%})".format(header, missing, total, ratio),
            table.source_sheet, source_column=header,
            suggested_action="Confirm whether missing, not measured, failed, and true zero are distinct",
        ))
    return issues


def _duplicate_issues(table: TableData, limit: int) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    seen: Dict[Tuple[str, ...], int] = {}
    for row in table.rows:
        key = tuple(str(row.get(header, "")).strip() for header in table.headers)
        source_row = row.get("Source_Row", "")
        if key in seen and len(issues) < limit:
            issues.append(make_issue(
                "MEDIUM", "Duplicate Record",
                "Row duplicates source row {} within the detected table".format(seen[key]),
                table.source_sheet, source_row,
                suggested_action="Verify whether this is an intentional replicate or an accidental duplicate",
            ))
        else:
            seen[key] = source_row
    return issues


def _type_issues(table: TableData) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    for header in table.headers:
        kinds = Counter()
        for row in table.rows:
            value = row.get(header)
            if is_missing(value):
                continue
            if isinstance(value, bool):
                kinds["boolean"] += 1
            elif isinstance(value, (int, float)):
                kinds["numeric"] += 1
            else:
                kinds["text"] += 1
        if kinds["numeric"] and kinds["text"]:
            issues.append(make_issue(
                "LOW", "Mixed Data Type",
                "Column '{}' mixes numeric and text values".format(header),
                table.source_sheet, source_column=header,
                suggested_action="Check for embedded units, failure labels, or malformed numeric cells",
            ))
    return issues


def _range_and_outlier_issues(table: TableData, limit: int) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    for header in table.headers:
        numeric: List[Tuple[int, float]] = []
        for row in table.rows:
            value = row.get(header)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if not math.isfinite(float(value)):
                issues.append(make_issue(
                    "HIGH", "Impossible Value", "Non-finite numeric value detected",
                    table.source_sheet, row.get("Source_Row", ""), header,
                    "Inspect the source cell; do not silently replace it",
                ))
                continue
            numeric.append((int(row.get("Source_Row", 0) or 0), float(value)))
        normalized = normalize_label(header)
        for source_row, value in numeric:
            if normalized in {"ph", "p h"} and (value < 0 or value > 14):
                issues.append(make_issue(
                    "HIGH", "Impossible Value", "pH value {} is outside 0-14".format(value),
                    table.source_sheet, source_row, header,
                    "Confirm the value and whether the column is truly pH",
                ))
            if "temperature" in normalized or normalized == "温度":
                if value < -273.15:
                    issues.append(make_issue(
                        "HIGH", "Impossible Value", "Temperature {} is below absolute zero".format(value),
                        table.source_sheet, source_row, header,
                        "Confirm the value and unit",
                    ))
        if len(numeric) < 4:
            continue
        values = [value for _, value in numeric]
        sorted_values = sorted(values)
        lower_half = sorted_values[: len(sorted_values) // 2]
        upper_half = sorted_values[(len(sorted_values) + 1) // 2 :]
        q1 = statistics.median(lower_half)
        q3 = statistics.median(upper_half)
        iqr = q3 - q1
        if iqr <= 0:
            continue
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        for source_row, value in numeric:
            if (value < lower or value > upper) and len(issues) < limit:
                issues.append(make_issue(
                    "LOW", "Potential Outlier",
                    "Value {} is outside the IQR fence [{:.6g}, {:.6g}]".format(value, lower, upper),
                    table.source_sheet, source_row, header,
                    "Review in domain context; flag only and do not delete automatically",
                ))
    return issues


def _unit_issues(table: TableData) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    unit_header = None
    for header in table.headers:
        if normalize_label(header) in {"unit", "单位"}:
            unit_header = header
            break
    if not unit_header:
        return issues
    units = {
        str(row.get(unit_header)).strip().casefold()
        for row in table.rows if not is_missing(row.get(unit_header))
    }
    if len(units) > 1:
        issues.append(make_issue(
            "MEDIUM", "Unit Inconsistency",
            "Unit column contains multiple units: {}".format(", ".join(sorted(units))),
            table.source_sheet, source_column=unit_header,
            suggested_action="Confirm metric-specific units before cross-experiment comparison",
        ))
    return issues


def issue_counts(issues: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for issue in issues:
        severity = str(issue.get("Severity", "LOW")).upper()
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def apply_outlier_flags(records: List[Dict[str, Any]], issues: Sequence[Dict[str, Any]]) -> None:
    flagged = {
        (str(issue.get("Source_Sheet", "")), str(issue.get("Source_Row", "")), str(issue.get("Source_Column", "")))
        for issue in issues if issue.get("Category") == "Potential Outlier"
    }
    for record in records:
        key = (
            str(record.get("Source_Sheet", "")), str(record.get("Source_Row", "")),
            str(record.get("Source_Column", "")),
        )
        record["Outlier_Flag"] = "Suspected" if key in flagged else "No"
