"""Generate lightweight evidence-first Markdown and HTML reports from the database."""

from __future__ import annotations

import html
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .analysis import create_analysis_package, filter_experiments, load_sheet_records
from .common import UNKNOWN, ensure_directory, parse_iso_date
from .storage import initialize_project


REPORT_TYPES = {"weekly", "monthly", "quarterly", "semester", "stage", "project", "custom"}


def generate_report(
    project_root: Path, report_type: str, start: Optional[str] = None,
    end: Optional[str] = None, month: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    report_type = report_type.lower()
    if report_type not in REPORT_TYPES:
        raise ValueError("Unsupported report type: {}".format(report_type))
    start_date, end_date = resolve_period(report_type, start, end, month)
    paths = initialize_project(project_root)
    index_all = load_sheet_records(paths.database_workbook, "Experiment_Index")
    index_records = filter_experiments(index_all, start_date, end_date)
    selected_ids = {str(record.get("Experiment_ID")) for record in index_records}
    raw_records = [record for record in load_sheet_records(paths.database_workbook, "Raw_Data") if str(record.get("Experiment_ID")) in selected_ids]
    summary_records = [record for record in load_sheet_records(paths.database_workbook, "Summary") if str(record.get("Experiment_ID")) in selected_ids]
    qa_records = [record for record in load_sheet_records(paths.database_workbook, "QA_QC") if str(record.get("Experiment_ID")) in selected_ids]
    knowledge_records = [record for record in load_sheet_records(paths.database_workbook, "Experiment_Knowledge") if str(record.get("Experiment_ID")) in selected_ids]
    evidence = create_analysis_package(
        project_root, start=start_date, end=end_date,
        package_name="report_evidence_{}_{}_{}".format(report_type, start_date or "all", end_date or "all"),
    )
    report_title = title or _default_title(report_type, start_date, end_date)
    markdown = _build_report_markdown(
        report_title, report_type, start_date, end_date, index_records, raw_records,
        summary_records, qa_records, knowledge_records, index_all,
    )
    ensure_directory(paths.reports_dir)
    base_name = "{}_{}_{}".format(report_type, start_date or "all", end_date or "all")
    markdown_path = paths.reports_dir / "{}.md".format(base_name)
    html_path = paths.reports_dir / "{}.html".format(base_name)
    markdown_path.write_text(markdown, encoding="utf-8", newline="\n")
    html_path.write_text(_markdown_to_html(report_title, markdown), encoding="utf-8", newline="\n")
    return {
        "status": "created",
        "report_type": report_type,
        "start": start_date,
        "end": end_date,
        "markdown": str(markdown_path),
        "html": str(html_path),
        "evidence_package": evidence["output_dir"],
        "experiment_count": len(index_records),
        "measurement_count": len(raw_records),
    }


def resolve_period(
    report_type: str, start: Optional[str], end: Optional[str], month: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    today = date.today()
    if start or end:
        parsed_start = parse_iso_date(start) if start else None
        parsed_end = parse_iso_date(end) if end else None
        if start and not parsed_start:
            raise ValueError("Invalid --start date")
        if end and not parsed_end:
            raise ValueError("Invalid --end date")
        return parsed_start, parsed_end
    if report_type == "weekly":
        period_start = today - timedelta(days=today.weekday())
        return period_start.isoformat(), today.isoformat()
    if report_type == "monthly":
        if month:
            try:
                period_start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
            except ValueError:
                raise ValueError("--month must use YYYY-MM")
        else:
            period_start = today.replace(day=1)
        next_month = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return period_start.isoformat(), (next_month - timedelta(days=1)).isoformat()
    if report_type == "quarterly":
        start_month = ((today.month - 1) // 3) * 3 + 1
        period_start = date(today.year, start_month, 1)
        next_quarter = date(today.year + (start_month + 3 > 12), ((start_month + 2) % 12) + 1, 1)
        return period_start.isoformat(), (next_quarter - timedelta(days=1)).isoformat()
    if report_type == "semester":
        start_month = 1 if today.month <= 6 else 7
        period_start = date(today.year, start_month, 1)
        period_end = date(today.year, 6 if start_month == 1 else 12, 30 if start_month == 1 else 31)
        return period_start.isoformat(), period_end.isoformat()
    return None, None


def _default_title(report_type: str, start: Optional[str], end: Optional[str]) -> str:
    labels = {
        "weekly": "科研实验周报", "monthly": "科研实验月报", "quarterly": "科研实验季度报告",
        "semester": "科研实验学期报告", "stage": "科研实验阶段报告",
        "project": "科研项目实验报告", "custom": "科研实验自定义报告",
    }
    return "{}（{} 至 {}）".format(labels[report_type], start or "全部", end or "全部")


def _build_report_markdown(
    title: str, report_type: str, start: Optional[str], end: Optional[str],
    index_records: Sequence[Dict[str, Any]], raw_records: Sequence[Dict[str, Any]],
    summary_records: Sequence[Dict[str, Any]], qa_records: Sequence[Dict[str, Any]],
    knowledge_records: Sequence[Dict[str, Any]], index_all: Sequence[Dict[str, Any]],
) -> str:
    families = sorted({str(record.get("Experiment_Family") or UNKNOWN) for record in index_records})
    failed = [record for record in index_records if str(record.get("Outcome") or "").casefold() in {"failed", "negative"}]
    qa_counts = {level: sum(1 for record in qa_records if str(record.get("Severity")).upper() == level) for level in ("HIGH", "MEDIUM", "LOW")}
    lines: List[str] = [
        "# {}".format(title), "",
        "## Evidence scope", "",
        "- Period: {} to {}".format(start or "All available data", end or "All available data"),
        "- Experiments: {}".format(len(index_records)),
        "- Measurements: {}".format(len(raw_records)),
        "- Experiment families: {}".format(", ".join(families) if families else "None"),
        "- QA issues: HIGH {}, MEDIUM {}, LOW {}".format(qa_counts["HIGH"], qa_counts["MEDIUM"], qa_counts["LOW"]),
        "",
        "## What was done", "",
    ]
    if index_records:
        for record in index_records:
            lines.append("- **Measured record:** {} — {} — {} — outcome: {}".format(
                record.get("Experiment_ID", UNKNOWN), record.get("Experiment_Date", UNKNOWN),
                record.get("Experiment_Name", UNKNOWN), record.get("Outcome", UNKNOWN),
            ))
    else:
        lines.append("- No experiments matched this period.")
    lines.extend(["", "## Quantitative results", ""])
    if summary_records:
        for record in summary_records[:40]:
            lines.append("- **Calculated:** {} / {} / {}: mean={}, SD={}, biological n={}, unit={}".format(
                record.get("Experiment_ID", UNKNOWN), record.get("Group", UNKNOWN),
                record.get("Metric", UNKNOWN), _fmt(record.get("Mean")), _fmt(record.get("SD")),
                record.get("Biological_N", 0), record.get("Unit", UNKNOWN),
            ))
        if len(summary_records) > 40:
            lines.append("- Additional calculated rows are available in the evidence package.")
    else:
        lines.append("- No numeric summary rows were available.")
    lines.extend([
        "", "## Interpretation boundary", "",
        "- **Inferred:** no causal or mechanistic conclusion is generated automatically.",
        "- **Hypothesis:** researcher input is required before proposing causes or next mechanisms.",
        "- Statistical significance is not inferred from technical replicates or incomplete designs.",
        "- A historical best result is not selected until the metric direction is defined.",
        "", "## Failed or negative experiments", "",
    ])
    if failed:
        for record in failed:
            lines.append("- {} — {} — {}".format(record.get("Experiment_ID"), record.get("Experiment_Name"), record.get("Outcome")))
    else:
        lines.append("- None recorded in this period.")
    lines.extend(["", "## Data quality", ""])
    for record in qa_records[:30]:
        lines.append("- {} — {}: {}".format(record.get("Severity"), record.get("Category"), record.get("Message")))
    if not qa_records:
        lines.append("- No recorded QA issues in scope.")
    lines.extend(["", "## Research knowledge and next steps", ""])
    if knowledge_records:
        for record in knowledge_records:
            lines.append("- {}: conclusion={}, next={}".format(
                record.get("Experiment_ID"), record.get("Conclusion", UNKNOWN), record.get("Next_Experiment", UNKNOWN),
            ))
    else:
        lines.append("- Not Provided. Add interpretation and next-experiment notes after researcher review.")
    if report_type in {"monthly", "quarterly", "semester", "stage", "project"}:
        lines.extend([
            "", "## Stage narrative scaffold", "",
            "- Scientific question: Not Provided",
            "- Initial hypothesis: Not Provided",
            "- Experimental strategy: see Experiment Families and evidence package",
            "- Screening and optimization history: derive from dated experiments after researcher confirmation",
            "- Current conclusion: Not Provided",
            "- Limitations and open questions: review QA report and missing metadata",
        ])
    lines.extend([
        "", "## Companion Skill handoff", "",
        "- Use `nature-statistics` for design-aware inferential analysis.",
        "- Use `nature-figure` for publication-grade scientific figures.",
        "- Use `documents`, `pdf`, or `presentations` for final document formats.",
        "- Always pass the newly generated evidence package instead of concatenating old reports.",
        "",
    ])
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, (int, float)):
        return "{:.6g}".format(value)
    return str(value)


def _markdown_to_html(title: str, markdown: str) -> str:
    body: List[str] = []
    in_list = False
    for line in markdown.splitlines():
        if line.startswith("# "):
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append("<h1>{}</h1>".format(html.escape(line[2:])))
        elif line.startswith("## "):
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append("<h2>{}</h2>".format(html.escape(line[3:])))
        elif line.startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            escaped = html.escape(line[2:]).replace("**", "")
            body.append("<li>{}</li>".format(escaped))
        elif line.strip():
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append("<p>{}</p>".format(html.escape(line)))
    if in_list:
        body.append("</ul>")
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
body{{font-family:Arial,"Microsoft YaHei",sans-serif;background:#f4f7fa;color:#183247;margin:0}}
main{{max-width:1000px;margin:32px auto;background:white;padding:40px 56px;box-shadow:0 4px 20px #16324f18}}
h1{{color:#123b5d;border-bottom:3px solid #2b7a9b;padding-bottom:14px}}h2{{color:#1f5d7a;margin-top:32px}}
li{{margin:8px 0;line-height:1.55}}p{{line-height:1.65}}@media(max-width:700px){{main{{margin:0;padding:24px}}}}
</style></head><body><main>{body}</main></body></html>""".format(
        title=html.escape(title), body="\n".join(body),
    )
