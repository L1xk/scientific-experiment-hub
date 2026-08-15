"""Create reusable Excel templates shipped with the Skill."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation

from .common import ensure_directory
from .storage import _format_sheet, atomic_save_workbook, create_database_workbook


def create_templates(output_dir: Path) -> Dict[str, Any]:
    ensure_directory(output_dir)
    database_path = output_dir / "experiment_database.xlsx"
    metadata_path = output_dir / "experiment_metadata.xlsx"
    database = create_database_workbook()
    atomic_save_workbook(database, database_path)
    database.close()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Experiment_Metadata"
    headers = [
        "Experiment_Date", "Experiment_Nature", "Project_ID", "Experiment_Family",
        "Operator", "Objective", "Hypothesis", "Control_Group", "Status", "Outcome", "Notes",
    ]
    sheet.append(headers)
    sheet.append([
        "2026-08-14", "pH优化实验", "PROJECT-001", "LTA-pH-Optimization",
        "Not Provided", "Evaluate pH effect", "Not Provided", "Control",
        "Completed", "Inconclusive", "Example row; replace or delete",
    ])
    _format_sheet(sheet)
    status_validation = DataValidation(
        type="list",
        formula1='"Idea,Planned,Running,Completed,Failed,Needs Repeat,Optimizing,Validated,Archived"',
        allow_blank=True,
    )
    outcome_validation = DataValidation(
        type="list",
        formula1='"Positive,Negative,Inconclusive,Failed,Optimization,Validation"',
        allow_blank=True,
    )
    sheet.add_data_validation(status_validation)
    sheet.add_data_validation(outcome_validation)
    status_validation.add("I2:I1000")
    outcome_validation.add("J2:J1000")

    data = workbook.create_sheet("Long_Format_Data")
    data.append([
        "Sample_ID", "Group", "Biological_Replicate", "Technical_Replicate",
        "Metric", "Value", "Unit", "Notes",
    ])
    data.append(["Sample-01", "Control", "B1", "T1", "Product_Titer", 1.25, "g/L", "Example row; replace or delete"])
    _format_sheet(data)
    guide = workbook.create_sheet("填写说明")
    guide.append(["Rule", "Explanation"])
    guide.append(["Raw data", "Do not edit the original source file; this template is optional metadata/data entry."])
    guide.append(["Unknown information", "Use Unknown, Not Provided, or NA. Do not guess units, dates, controls, or replicates."])
    guide.append(["Replicates", "Identify biological and technical replicates separately whenever known."])
    guide.append(["Minimum friction", "If only raw data is available, upload it directly; the Hub will create a pending-metadata sheet."])
    _format_sheet(guide)
    atomic_save_workbook(workbook, metadata_path)
    workbook.close()
    return {"database_template": str(database_path), "metadata_template": str(metadata_path)}
