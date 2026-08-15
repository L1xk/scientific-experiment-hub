"""Read source files, detect tabular regions, and build organized workbooks."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .common import UNKNOWN, is_missing, normalize_scalar, parse_iso_date, safe_name
from .schema import COLUMN_ALIASES, CONDITION_FIELDS, METADATA_LABELS, NATURE_KEYWORDS


@dataclass
class TableData:
    source_sheet: str
    header_row: int
    headers: List[str]
    rows: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    display_name: Optional[str] = None
    include_in_database: bool = True
    validate: bool = True


def normalize_label(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" :：")


def dedupe_headers(values: Sequence[Any]) -> Tuple[List[str], List[str]]:
    headers: List[str] = []
    warnings: List[str] = []
    counts: Dict[str, int] = {}
    for index, value in enumerate(values, start=1):
        header = str(value).strip() if not is_missing(value) else "Unnamed_{}".format(index)
        key = normalize_label(header) or "unnamed_{}".format(index)
        counts[key] = counts.get(key, 0) + 1
        if counts[key] > 1:
            original = header
            header = "{}_{}".format(header, counts[key])
            warnings.append("Duplicate header '{}' renamed to '{}'".format(original, header))
        headers.append(header)
    return headers, warnings


def _read_delimited(path: Path) -> Tuple[Dict[str, Any], List[TableData], List[str]]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    text = None
    encoding_used = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = path.read_text(encoding=encoding)
            encoding_used = encoding
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("Unable to decode {} as UTF-8 or GB18030".format(path.name))
    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
    if not rows:
        raise ValueError("Input table is empty: {}".format(path.name))
    max_cols = max(len(row) for row in rows)
    padded = [row + [None] * (max_cols - len(row)) for row in rows]
    header_index = _detect_header_index(padded[:30])
    headers, warnings = dedupe_headers(padded[header_index])
    records: List[Dict[str, Any]] = []
    for source_row, values in enumerate(padded[header_index + 1 :], start=header_index + 2):
        if all(is_missing(value) for value in values):
            continue
        record = {headers[i]: normalize_scalar(values[i]) for i in range(len(headers))}
        record["Source_Row"] = source_row
        records.append(record)
    table = TableData(path.stem[:31], header_index + 1, headers, records, warnings)
    return {"source_encoding": encoding_used}, [table], warnings


def _detect_header_index(rows: Sequence[Sequence[Any]]) -> int:
    if not rows:
        return 0
    scored: List[Tuple[float, int]] = []
    for index, row in enumerate(rows):
        non_empty = [value for value in row if not is_missing(value)]
        if not non_empty:
            score = -1.0
        else:
            text_count = sum(1 for value in non_empty if isinstance(value, str))
            unique_count = len({str(value).strip().casefold() for value in non_empty})
            score = len(non_empty) * 2.0 + text_count * 0.5 + unique_count * 0.1 - index * 0.02
        scored.append((score, index))
    return max(scored)[1]


def _sheet_matrix(formula_sheet: Any, value_sheet: Any, max_rows: int, max_cols: int) -> List[List[Any]]:
    row_limit = min(formula_sheet.max_row or 1, max_rows)
    col_limit = min(formula_sheet.max_column or 1, max_cols)
    matrix: List[List[Any]] = []
    for row_index in range(1, row_limit + 1):
        row: List[Any] = []
        for col_index in range(1, col_limit + 1):
            formula_value = formula_sheet.cell(row_index, col_index).value
            cached_value = value_sheet.cell(row_index, col_index).value
            value = cached_value if cached_value is not None else formula_value
            row.append(normalize_scalar(value))
        matrix.append(row)
    return matrix


def _formula_matrix(formula_sheet: Any, max_rows: int, max_cols: int) -> List[List[Any]]:
    """Return displayed source expressions for a provenance-only snapshot."""
    row_limit = min(formula_sheet.max_row or 1, max_rows)
    col_limit = min(formula_sheet.max_column or 1, max_cols)
    return [
        [normalize_scalar(formula_sheet.cell(row_index, col_index).value) for col_index in range(1, col_limit + 1)]
        for row_index in range(1, row_limit + 1)
    ]


def _parse_section_date(value: Any) -> Optional[str]:
    """Parse an explicit compact YYYYMMDD marker without using file timestamps."""
    if is_missing(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        text = str(int(value)) if float(value).is_integer() else str(value)
    else:
        text = str(value)
    match = re.search(r"(?<!\d)(20\d{6})(?!\d)", text)
    if not match:
        return None
    compact = match.group(1)
    try:
        parsed = dt.date(int(compact[:4]), int(compact[4:6]), int(compact[6:8]))
    except ValueError:
        return None
    return parsed.isoformat()


def _is_scientific_header(value: Any) -> bool:
    label = normalize_label(value)
    if not label:
        return False
    compact = label.replace(" ", "")
    return (
        "峰面积" in compact
        or "产量" in compact
        or compact in {"od", "od600", "dcw", "titer", "滴度"}
    )


def _column_has_data(
    matrix: Sequence[Sequence[Any]], column: int, start_row: int, end_row: int, minimum: int = 1,
) -> bool:
    count = 0
    for row_index in range(start_row, min(end_row + 1, len(matrix))):
        if column < len(matrix[row_index]) and not is_missing(matrix[row_index][column]):
            count += 1
            if count >= minimum:
                return True
    return False


def _cluster_columns(columns: Sequence[int], max_gap: int = 2) -> List[List[int]]:
    clusters: List[List[int]] = []
    for column in sorted(columns):
        if not clusters or column - clusters[-1][-1] > max_gap:
            clusters.append([column])
        else:
            clusters[-1].append(column)
    return clusters


def _dated_section_tables(
    source_sheet: str, value_matrix: List[List[Any]], formula_matrix: List[List[Any]],
) -> List[TableData]:
    """Extract explicit dated table blocks from legacy multi-section workbooks.

    This parser activates only when at least two valid YYYYMMDD markers are
    present. It never derives a date from file metadata or numeric results.
    """
    markers: List[Tuple[int, int, str]] = []
    for row_index, row in enumerate(value_matrix):
        for column_index, value in enumerate(row):
            parsed = _parse_section_date(value)
            if parsed:
                markers.append((row_index, column_index, parsed))
    if len(markers) < 2:
        return []

    marker_rows = sorted({row_index for row_index, _, _ in markers})
    tables: List[TableData] = []
    occupied = set()
    for marker_row, marker_column, section_date in markers:
        next_rows = [row for row in marker_rows if row > marker_row]
        end_row = (min(next_rows) - 1) if next_rows else (len(value_matrix) - 1)
        same_row = sorted(column for row, column, _ in markers if row == marker_row)
        next_columns = [column for column in same_row if column > marker_column]
        end_column = (min(next_columns) - 1) if next_columns else (len(value_matrix[marker_row]) - 1)

        candidate_rows = range(marker_row, min(marker_row + 8, end_row + 1))
        scored_rows: List[Tuple[int, int, List[int]]] = []
        for candidate in candidate_rows:
            signal_columns = [
                column for column in range(marker_column, end_column + 1)
                if column < len(value_matrix[candidate]) and _is_scientific_header(value_matrix[candidate][column])
            ]
            if signal_columns:
                scored_rows.append((len(signal_columns), -candidate, signal_columns))
        if not scored_rows:
            continue
        _, neg_header_row, signal_columns = max(scored_rows)
        header_row = -neg_header_row
        clusters = _cluster_columns(signal_columns)

        for block_index, cluster in enumerate(clusters, start=1):
            left = cluster[0]
            right = cluster[-1]
            data_start = header_row + 1
            while left > marker_column and _column_has_data(value_matrix, left - 1, data_start, end_row, minimum=2):
                left -= 1
            while right < end_column and _column_has_data(value_matrix, right + 1, data_start, end_row, minimum=2):
                right += 1

            raw_headers: List[Any] = []
            for column in range(left, right + 1):
                header_value = value_matrix[header_row][column] if column < len(value_matrix[header_row]) else None
                has_text_below = any(
                    column < len(value_matrix[row]) and isinstance(value_matrix[row][column], str)
                    and not is_missing(value_matrix[row][column])
                    for row in range(data_start, min(end_row + 1, len(value_matrix)))
                )
                if column == left and (is_missing(header_value) or not _is_scientific_header(header_value)) and has_text_below:
                    header_value = "Sample_ID"
                elif is_missing(header_value):
                    header_value = "Unlabeled_Column_{}".format(get_column_letter(column + 1))
                formula_present = any(
                    column < len(formula_matrix[row])
                    and isinstance(formula_matrix[row][column], str)
                    and formula_matrix[row][column].startswith("=")
                    for row in range(data_start, min(end_row + 1, len(formula_matrix)))
                )
                if formula_present:
                    header_value = "{}_SourceFormulaResult".format(header_value)
                raw_headers.append(header_value)
            clean_headers, header_warnings = dedupe_headers(raw_headers)
            source_sample_index = clean_headers.index("Sample_ID") if "Sample_ID" in clean_headers else None
            output_headers = [
                "Source_Sample_ID" if header == "Sample_ID" else header for header in clean_headers
            ]
            label_value = value_matrix[header_row][left] if left < len(value_matrix[header_row]) else None
            label_candidate = str(label_value).strip() if not is_missing(label_value) else ""
            label_is_safe = (
                bool(label_candidate)
                and not _is_scientific_header(label_candidate)
                and len(label_candidate) <= 20
                and "=" not in label_candidate
                and "²" not in label_candidate
                and "\n" not in label_candidate
            )
            label = label_candidate if label_is_safe else "Block{}".format(block_index)
            table_id = "{}-B{}-{}".format(section_date, block_index, safe_name(label, max_length=16))
            headers = ["Experiment_Date", "Group", "Table_ID", "Sample_ID"] + output_headers
            rows: List[Dict[str, Any]] = []
            for row_index in range(data_start, min(end_row + 1, len(value_matrix))):
                selected = [
                    value_matrix[row_index][column] if column < len(value_matrix[row_index]) else None
                    for column in range(left, right + 1)
                ]
                if all(is_missing(value) for value in selected):
                    continue
                source_sample = selected[source_sample_index] if source_sample_index is not None else UNKNOWN
                source_sample_missing = (
                    is_missing(source_sample)
                    or str(source_sample).strip().casefold() in {"unknown", "not provided"}
                )
                sample_token = (
                    safe_name(source_sample, fallback="ROW{}".format(row_index + 1), max_length=40)
                    if not source_sample_missing else "ROW{}".format(row_index + 1)
                )
                derived_sample = "{}-{}".format(table_id, sample_token)
                record = {
                    "Experiment_Date": section_date,
                    "Group": section_date,
                    "Table_ID": table_id,
                    "Sample_ID": derived_sample,
                }
                record.update({output_headers[index]: selected[index] for index in range(len(output_headers))})
                record["Source_Row"] = row_index + 1
                rows.append(record)
                for column in range(left, right + 1):
                    occupied.add((row_index, column))
            if not rows:
                continue
            display_name = "{}_{}".format(section_date, safe_name(label, max_length=16))[:31]
            warnings = list(header_warnings)
            warnings.append(
                "Dated section '{}' was split from a legacy multi-table layout; confirm units and experiment boundaries".format(section_date)
            )
            tables.append(TableData(
                source_sheet=source_sheet,
                header_row=header_row + 1,
                headers=headers,
                rows=rows,
                warnings=warnings,
                display_name=display_name,
            ))

    if tables:
        snapshot_headers = ["Column_{}".format(get_column_letter(index + 1)) for index in range(max(len(row) for row in formula_matrix))]
        snapshot_rows: List[Dict[str, Any]] = []
        for row_index, row in enumerate(formula_matrix, start=1):
            if not any(not is_missing(value) for value in row):
                continue
            record = {snapshot_headers[index]: row[index] if index < len(row) else None for index in range(len(snapshot_headers))}
            record["Source_Row"] = row_index
            snapshot_rows.append(record)
        tables.append(TableData(
            source_sheet=source_sheet,
            header_row=1,
            headers=snapshot_headers,
            rows=snapshot_rows,
            warnings=["Formula-preserving source-layout snapshot; use the archived original as authority"],
            display_name="原表公式快照",
            include_in_database=False,
            validate=False,
        ))
    return tables


def _extract_metadata_from_matrices(matrices: Iterable[List[List[Any]]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for matrix in matrices:
        for row_index, row in enumerate(matrix[:30]):
            for col_index, value in enumerate(row[:15]):
                label = normalize_label(value)
                if not label:
                    continue
                for field_name, aliases in METADATA_LABELS.items():
                    if label not in aliases or field_name in result:
                        continue
                    adjacent = row[col_index + 1] if col_index + 1 < len(row) else None
                    below = None
                    if row_index + 1 < len(matrix) and col_index < len(matrix[row_index + 1]):
                        below = matrix[row_index + 1][col_index]
                    candidate = adjacent if not is_missing(adjacent) else below
                    if not is_missing(candidate):
                        result[field_name] = candidate
                        result[field_name + "_source"] = "Workbook_Label"
    return result


def inspect_source(path: Path, max_rows: int = 100000, max_cols: int = 500) -> Tuple[Dict[str, Any], List[TableData], List[str]]:
    """Read an authorized source file without modifying it."""
    extension = path.suffix.lower()
    if extension in {".csv", ".tsv"}:
        metadata, tables, warnings = _read_delimited(path)
        metadata.update(_detect_filename_metadata(path))
        return metadata, tables, warnings
    if extension not in {".xlsx", ".xlsm"}:
        raise ValueError("Unsupported source extension: {}".format(extension))
    formula_book = load_workbook(path, data_only=False, read_only=False, keep_vba=extension == ".xlsm")
    value_book = load_workbook(path, data_only=True, read_only=False, keep_vba=extension == ".xlsm")
    matrices: List[List[List[Any]]] = []
    tables: List[TableData] = []
    warnings: List[str] = []
    try:
        for sheet_name in formula_book.sheetnames:
            formula_sheet = formula_book[sheet_name]
            value_sheet = value_book[sheet_name]
            matrix = _sheet_matrix(formula_sheet, value_sheet, max_rows, max_cols)
            source_formula_matrix = _formula_matrix(formula_sheet, max_rows, max_cols)
            matrices.append(matrix)
            non_empty_rows = [row for row in matrix if any(not is_missing(value) for value in row)]
            if not non_empty_rows:
                warnings.append("Sheet '{}' is empty".format(sheet_name))
                continue
            dated_tables = _dated_section_tables(sheet_name, matrix, source_formula_matrix)
            if dated_tables:
                tables.extend(dated_tables)
                warnings.append(
                    "{}: detected legacy multi-section layout and split explicit dated blocks conservatively".format(sheet_name)
                )
                continue
            header_index = _detect_header_index(matrix[:30])
            headers, header_warnings = dedupe_headers(matrix[header_index])
            records: List[Dict[str, Any]] = []
            for source_row, values in enumerate(matrix[header_index + 1 :], start=header_index + 2):
                if all(is_missing(value) for value in values):
                    continue
                record = {headers[i]: values[i] for i in range(len(headers))}
                record["Source_Row"] = source_row
                records.append(record)
            tables.append(TableData(sheet_name, header_index + 1, headers, records, header_warnings))
            warnings.extend("{}: {}".format(sheet_name, item) for item in header_warnings)
        metadata = _extract_metadata_from_matrices(matrices)
        filename_metadata = _detect_filename_metadata(path)
        for key, value in filename_metadata.items():
            metadata.setdefault(key, value)
        text_context = " ".join([path.stem] + formula_book.sheetnames)
        _detect_nature(metadata, text_context)
        return metadata, tables, warnings
    finally:
        formula_book.close()
        value_book.close()


def _detect_filename_metadata(path: Path) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    detected_date = parse_iso_date(path.stem)
    if detected_date:
        metadata["experiment_date"] = detected_date
        metadata["experiment_date_source"] = "Filename"
    _detect_nature(metadata, path.stem)
    return metadata


def _detect_nature(metadata: Dict[str, Any], text: str) -> None:
    if not is_missing(metadata.get("experiment_name")):
        metadata.setdefault("experiment_name_source", "Workbook_Label")
        metadata.setdefault("nature_confidence", "HIGH")
        return
    lowered = normalize_label(text)
    hits = []
    for keywords, canonical in NATURE_KEYWORDS:
        if any(normalize_label(keyword) in lowered for keyword in keywords):
            hits.append(canonical)
    unique_hits = list(dict.fromkeys(hits))
    if len(unique_hits) == 1:
        metadata["experiment_name"] = unique_hits[0]
        metadata["experiment_name_source"] = "Filename_or_Sheet_Keyword"
        metadata["nature_confidence"] = "MEDIUM"


def find_column(headers: Sequence[str], alias_key: str) -> Optional[str]:
    aliases = COLUMN_ALIASES[alias_key]
    for header in headers:
        if normalize_label(header) in aliases:
            return header
    return None


def extract_unit(header: Any) -> str:
    text = str(header or "")
    matches = re.findall(r"\(([^()]{1,30})\)|\[([^\[\]]{1,30})\]", text)
    if not matches:
        return UNKNOWN
    unit = matches[-1][0] or matches[-1][1]
    return unit.strip() or UNKNOWN


def tables_to_long_records(
    tables: Sequence[TableData], experiment_id: str, source_file: str,
    import_date: str, data_version: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    records: List[Dict[str, Any]] = []
    conditions: List[Dict[str, Any]] = []
    condition_seen = set()
    for table in tables:
        if not table.include_in_database:
            continue
        column_map = {key: find_column(table.headers, key) for key in COLUMN_ALIASES}
        metric_column = column_map["metric"]
        value_column = column_map["value"]
        unit_column = column_map["unit"]
        metadata_columns = {value for key, value in column_map.items() if key not in {"metric", "value", "unit"} and value}
        for row in table.rows:
            context = {
                key: row.get(column_map[key]) if column_map.get(key) else UNKNOWN
                for key in ("sample_id", "group", "biological_replicate", "technical_replicate")
            }
            condition = _condition_record(table, row, column_map, experiment_id)
            condition_key = tuple(str(condition.get(key, UNKNOWN)) for key in sorted(condition))
            if any(not is_missing(condition.get(key)) and condition.get(key) != UNKNOWN for key in condition):
                if condition_key not in condition_seen:
                    condition_seen.add(condition_key)
                    conditions.append(condition)
            if metric_column and value_column:
                raw_value = row.get(value_column)
                if is_missing(raw_value):
                    continue
                metric = row.get(metric_column, UNKNOWN)
                unit = row.get(unit_column, UNKNOWN) if unit_column else extract_unit(metric)
                records.append(_raw_record(
                    experiment_id, table, row, source_file, import_date, data_version,
                    context, metric, raw_value, unit, value_column,
                ))
                continue
            for header in table.headers:
                if header in metadata_columns or header in {metric_column, value_column, unit_column}:
                    continue
                raw_value = row.get(header)
                if is_missing(raw_value):
                    continue
                if not isinstance(raw_value, (int, float)):
                    continue
                records.append(_raw_record(
                    experiment_id, table, row, source_file, import_date, data_version,
                    context, header, raw_value, extract_unit(header), header,
                ))
    return records, conditions


def _raw_record(
    experiment_id: str, table: TableData, row: Dict[str, Any], source_file: str,
    import_date: str, data_version: int, context: Dict[str, Any], metric: Any,
    raw_value: Any, unit: Any, source_column: str,
) -> Dict[str, Any]:
    seed = "|".join([
        experiment_id, table.source_sheet, str(row.get("Source_Row", UNKNOWN)),
        str(metric), str(context.get("sample_id", UNKNOWN)),
        str(context.get("biological_replicate", UNKNOWN)),
        str(context.get("technical_replicate", UNKNOWN)),
    ])
    record_id = "REC-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16].upper()
    return {
        "Record_ID": record_id,
        "Experiment_ID": experiment_id,
        "Sample_ID": context.get("sample_id", UNKNOWN) or UNKNOWN,
        "Group": context.get("group", UNKNOWN) or UNKNOWN,
        "Biological_Replicate": context.get("biological_replicate", UNKNOWN) or UNKNOWN,
        "Technical_Replicate": context.get("technical_replicate", UNKNOWN) or UNKNOWN,
        "Metric": metric if not is_missing(metric) else UNKNOWN,
        "Raw_Value": normalize_scalar(raw_value),
        "Unit": unit if not is_missing(unit) else UNKNOWN,
        "Outlier_Flag": "Not Evaluated",
        "Source_File": source_file,
        "Source_Sheet": table.source_sheet,
        "Source_Row": row.get("Source_Row", UNKNOWN),
        "Source_Column": source_column,
        "Import_Date": import_date,
        "Data_Version": data_version,
        "Notes": "",
    }


def _condition_record(
    table: TableData, row: Dict[str, Any], column_map: Dict[str, Optional[str]], experiment_id: str,
) -> Dict[str, Any]:
    title_map = {
        "sample_id": "Sample_ID", "group": "Group", "treatment": "Treatment",
        "substrate": "Substrate", "enzyme": "Enzyme", "strain": "Strain",
        "gene": "Gene", "plasmid": "Plasmid", "concentration": "Concentration",
        "temperature": "Temperature", "ph": "pH", "reaction_time": "Reaction_Time",
        "culture_time": "Culture_Time", "od600": "OD600", "medium": "Medium",
        "carbon_source": "Carbon_Source", "inducer": "Inducer",
        "reaction_volume": "Reaction_Volume", "biological_replicate": "Biological_Replicate",
        "technical_replicate": "Technical_Replicate",
    }
    result: Dict[str, Any] = {"Experiment_ID": experiment_id}
    for field_name in CONDITION_FIELDS:
        column = column_map.get(field_name)
        result[title_map[field_name]] = row.get(column, UNKNOWN) if column else UNKNOWN
    result.update({
        "Source_Sheet": table.source_sheet,
        "Source_Row": row.get("Source_Row", UNKNOWN),
        "Notes": "",
    })
    return result


HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF")
BODY_FONT = Font(name="Arial", size=10)
TITLE_FILL = PatternFill("solid", fgColor="D9EAF7")
ALT_ROW_FILL = PatternFill("solid", fgColor="F3F8FC")
THIN_BLUE = Side(style="thin", color="9EBCD1")
THIN_GRID = Side(style="thin", color="D9E2F3")
HEADER_BORDER = Border(left=THIN_BLUE, right=THIN_BLUE, top=THIN_BLUE, bottom=THIN_BLUE)
BODY_BORDER = Border(left=THIN_GRID, right=THIN_GRID, top=THIN_GRID, bottom=THIN_GRID)
ORGANIZED_VIEW_EXCLUDED_FIELDS = {
    "Source_Sheet", "Source_Row", "Experiment_Date", "Group", "Table_ID",
}


def _organized_view_columns(headers: Sequence[str]) -> List[Tuple[str, str]]:
    """Map internal provenance headers to concise user-facing display headers."""
    has_source_sample = "Source_Sample_ID" in headers
    columns: List[Tuple[str, str]] = []
    used_display_names: Dict[str, int] = {}
    suffix = "_SourceFormulaResult"
    for header in headers:
        if header in ORGANIZED_VIEW_EXCLUDED_FIELDS:
            continue
        if header == "Sample_ID" and has_source_sample:
            continue
        if header == "Source_Sample_ID":
            display = "Sample_ID"
        elif header.endswith(suffix):
            base = header[:-len(suffix)]
            if base.startswith("Unlabeled_Column_"):
                display = "未命名列_{}（原公式结果）".format(base.rsplit("_", 1)[-1])
            else:
                display = base
        elif header.startswith("Unlabeled_Column_"):
            display = "未命名列_{}".format(header.rsplit("_", 1)[-1])
        else:
            display = header
        count = used_display_names.get(display, 0) + 1
        used_display_names[display] = count
        if count > 1:
            display = "{}_{}".format(display, count)
        columns.append((header, display))
    return columns


def build_organized_workbook(
    metadata: Dict[str, Any], tables: Sequence[TableData], issues: Sequence[Dict[str, Any]],
) -> Workbook:
    """Build a derived, user-readable workbook; never mutate the source workbook."""
    workbook = Workbook()
    info = workbook.active
    info.title = "文件信息"
    info.sheet_view.showGridLines = False
    info.append(["Field", "Value"])
    ordered_fields = [
        "Experiment_ID", "Experiment_Date", "Experiment_Nature", "Experiment_Family",
        "Project_ID", "Original_File", "File_SHA256", "Import_Date", "Data_Version",
        "Raw_Archive", "Organized_File", "Metadata_Completeness",
    ]
    for field_name in ordered_fields:
        info.append([field_name, metadata.get(field_name, UNKNOWN)])
    info.append(["Integrity_Note", "This is a derived organized copy. The archived source file is the immutable record."])
    _style_table_sheet(info)
    info.column_dimensions["A"].width = 26
    info.column_dimensions["B"].width = 80

    used_titles = {sheet.title for sheet in workbook.worksheets}
    for table_index, table in enumerate(tables, start=1):
        if not table.include_in_database:
            continue
        base_title = safe_name(table.display_name or table.source_sheet, fallback="Data", max_length=27)
        title = base_title[:31] if table.display_name else "整理_{}".format(base_title)[:31]
        suffix = 2
        while title in used_titles:
            title = "整理_{}_{}".format(base_title[:20], suffix)[:31]
            suffix += 1
        used_titles.add(title)
        sheet = workbook.create_sheet(title)
        view_columns = _organized_view_columns(table.headers)
        sheet.append([display for _, display in view_columns])
        for row in table.rows:
            sheet.append([row.get(source) for source, _ in view_columns])
        _style_table_sheet(sheet)
    return workbook


def _style_table_sheet(sheet: Any) -> None:
    """Format a used range without overlapping worksheet and Table filters.

    Excel repairs workbooks that define both a worksheet-level AutoFilter and a
    structured Table AutoFilter on the same range.  The organized copy only
    needs a readable grid and filtering, so use one worksheet AutoFilter plus
    explicit cell borders instead of an OOXML structured Table.
    """
    sheet.sheet_view.showGridLines = False
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    sheet.row_dimensions[1].height = 22
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = HEADER_BORDER
    for row_index, row in enumerate(sheet.iter_rows(min_row=2), start=2):
        sheet.row_dimensions[row_index].height = 20
        for cell in row:
            cell.font = BODY_FONT
            cell.border = BODY_BORDER
            if row_index % 2 == 0:
                cell.fill = ALT_ROW_FILL
            if isinstance(cell.value, (int, float)):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                if cell.number_format == "General":
                    cell.number_format = "0.####"
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=False)
    for column_cells in sheet.iter_cols(1, sheet.max_column):
        width = max(len(str(cell.value or "")) for cell in column_cells[: min(sheet.max_row, 200)]) + 2
        sheet.column_dimensions[get_column_letter(column_cells[0].column)].width = min(max(width, 10), 40)
