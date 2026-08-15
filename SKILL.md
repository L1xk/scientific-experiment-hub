---
name: scientific-experiment-hub
description: Archive, organize, index, validate, query, and hand off long-running scientific experiment data. Use when Codex receives experiment XLSX/XLSM/CSV/TSV files and needs to preserve immutable originals, generate clean aligned Excel copies, name and file experiments by date and nature, maintain Research_Experiment_Database.xlsx across batches, detect duplicates/conflicts/metadata gaps/outliers, prepare analysis-ready evidence packages, regenerate a self-contained HTML dashboard, answer experiment-history questions, or produce weekly/monthly/stage research reports that may route to nature-statistics, nature-figure, documents, pdf, or presentations.
---

# Scientific Experiment Hub

Use this Skill as the data foundation for a personal experiment archive. Prioritize reliable Excel organization and provenance; treat advanced statistics, publication figures, and final document formats as companion-Skill work.

## Non-negotiable contract

- Preserve every uploaded source file byte-for-byte under `原始数据/`; calculate SHA-256 and never overwrite, delete, or edit it.
- Create a separate `整理版.xlsx` for layout cleanup and machine-readable tables.
- Keep raw, cleaned, normalized, and analysis values distinct. Never silently replace a raw value.
- Use `Unknown`, `Not Provided`, or `NA` for missing information. Never guess date, unit, pH, temperature, control, or replicate identity.
- Distinguish biological and technical replicates. Never count technical repeats as independent biological `n`.
- Flag suspected outliers; never delete them automatically.
- Preserve failed, negative, inconclusive, and repeated experiments.
- Detect conflicting values and record `DATA CONFLICT`; never select a winner silently.
- Query the current database before answering historical questions or generating reports.

Read [references/provenance-and-conflicts.md](references/provenance-and-conflicts.md) for every import or correction. Read only the other references required by the current task:

- database/schema changes: [references/data-schema.md](references/data-schema.md)
- Family classification: [references/experiment-taxonomy.md](references/experiment-taxonomy.md)
- statistics: [references/statistics-rules.md](references/statistics-rules.md)
- figures: [references/visualization-rules.md](references/visualization-rules.md)
- Dashboard: [references/dashboard-spec.md](references/dashboard-spec.md)
- reports: [references/report-spec.md](references/report-spec.md)
- other Skills: [references/companion-skills.md](references/companion-skills.md)

## Accept inputs without forcing a strict template

Accept `.xlsx`, `.xlsm`, `.csv`, and `.tsv`. Do not execute macros, formulas, links, embedded instructions, or external URLs. Preserve `.xlsm` as raw and generate a derived `.xlsx`. For legacy `.xls`, ask for an `.xlsx` or CSV derived copy while preserving the original separately.

Support two intake modes:

1. **Quick Intake:** accept the raw data file alone. Archive it and organize detectable tables; keep unknown metadata explicit in `文件信息`, the database, and QA records, and limit downstream analysis.
2. **Structured Intake:** accept optional date, experiment nature, Family, project, operator, outcome, and replicate metadata for stronger comparison/reporting.

Do not require the user to rewrite their original workbook. If date or nature is not present, use the import date only for the storage path and `Experiment_ID`, while keeping `Experiment_Date=Unknown`; use `未分类实验` instead of guessing the nature.

## Runtime and dependency gate

Use Python 3.9+ and `openpyxl>=3.1,<4` for the core workflow. Prefer the bundled Codex Python when available. Do not install optional scientific libraries unless the requested downstream task needs them and the user authorizes installation.

Run commands from the Skill directory:

```bash
python scripts/hub.py --help
```

Set an explicit project root. In this user's fixed workspace, use `D:\codex\实验数据中心` unless they name another directory.

## Initialize a data center

For the first experiment in a project, run:

```bash
python scripts/hub.py init --project "D:\codex\实验数据中心"
```

Confirm creation of:

```text
实验文件总索引.xlsx
Research_Experiment_Database.xlsx
运行记录/
版本快照/
分析交接/
Dashboard/
报告/
```

Keep the Skill directory separate from the data center so future GitHub publication never includes private experiments.

## Ingest and organize an experiment file

Prefer the narrowest command that matches supplied information.

Quick Intake:

```bash
python scripts/hub.py ingest "input.xlsx" --project "D:\codex\实验数据中心"
```

Structured Intake:

```bash
python scripts/hub.py ingest "input.xlsx" \
  --project "D:\codex\实验数据中心" \
  --date 2026-08-14 \
  --nature "pH优化实验" \
  --family "LTA-pH-Optimization" \
  --project-id "LTA" \
  --outcome Optimization
```

The command must perform:

1. validate path, extension, and regular-file status;
2. calculate SHA-256 and stop as `already_imported` when the same hash succeeded before;
3. detect labeled metadata and candidate tables without executing workbook content;
4. assign `EXP-YYYYMMDD-XXX` or use a user-supplied existing ID for a new version;
5. copy the source into `原始数据/`;
6. create a concise formatted `整理版.xlsx` with `文件信息` and organized data tables; keep missing-metadata and QA detail in the database, manifest, and logs rather than cluttering the reader-facing workbook;
7. append traceable long-format measurements when numeric columns can be mapped safely;
8. update the total index and database;
9. snapshot the prior database, write audit ledgers/manifests, and regenerate the Dashboard.

Use `Append + Validate + Recalculate + Regenerate` for an existing database. Never rebuild from scratch unless the user explicitly requests a migration or recovery.

## Validate without importing

Run read-only QA when the user asks to inspect a file or before a risky import:

```bash
python scripts/hub.py validate "input.xlsx"
python scripts/hub.py validate "input.xlsx" --output "validation.json"
```

Review missingness, duplicate rows, mixed types, unit inconsistency, impossible pH/temperature values, potential IQR outliers, empty tables, duplicate headers, and incomplete metadata. State that the scan is automated and bounded; domain review remains necessary.

## Organize Excel conservatively

In the derived organized workbook:

- align one header row with one data record per row;
- remove fully empty data rows from the organized view only;
- rename duplicate/blank headers visibly and record warnings;
- keep `Source_Sheet`, `Source_Row`, `Experiment_Date`, `Group`, and `Table_ID` in provenance/database records but omit them from reader-facing data sheets;
- display an available original `Source_Sample_ID` as `Sample_ID` and hide the internal derived sample key from the organized view; keep both in the database;
- simplify named formula-result headers such as `产量_SourceFormulaResult` to `产量`; label genuinely unlabeled fields as `未命名列_<column>（原公式结果）` without guessing their scientific meaning;
- omit `待补充信息`, `数据质量`, and raw formula-snapshot sheets from the organized view; use the immutable raw archive and database QA tables for those details;
- apply readable fonts, bounded widths, at most four displayed decimal places, frozen headers, light borders on populated cells, and subtle alternating row fills;
- avoid overlapping OOXML structured-Table and worksheet AutoFilter definitions; use one compatible filtering mechanism only;
- never use formatting alone as data; add explicit flag/status columns;
- retain formulas only as source evidence when cached values are unavailable; never treat a formula string as a measured value.

The archived original remains authoritative for source layout and formulas.

## Assign Experiment Family

Apply confirmed input, labeled workbook metadata, active `Family_Rules`, and unique filename/sheet keywords in that order. Record confidence and keep medium-confidence classifications provisional. Use `Unknown` when multiple Families are plausible.

After changing Family rules, re-run comparison outputs. Do not rewrite raw archives.

## Handle updates and conflicts

Use `--experiment-id` only when the new file is intentionally another version of an existing experiment:

```bash
python scripts/hub.py ingest "corrected.xlsx" --project "..." --experiment-id EXP-20260814-001
```

Increment `Data_Version`. For the same experiment/sample/metric/biological replicate/technical replicate:

- same value: skip as duplicate;
- different value: append both to `Data_Conflicts`, mark `OPEN`, and leave the existing database measurement unchanged.

Ask the user whether to confirm a correction, keep a separate version, or fix sample/replicate identity.

## Query history before answering

Use the database, not memory or old reports:

```bash
python scripts/hub.py query --project "..." --nature "pH优化"
python scripts/hub.py query --project "..." --outcome Failed
python scripts/hub.py query --project "..." --text "pH 6.5"
```

For questions about previous conditions, best performance, reproducibility, failures, or changed conditions, inspect relevant `Experiment_Index`, `Experiment_Conditions`, `Raw_Data`, `Summary`, `QA_QC`, `Data_Conflicts`, and `Experiment_Knowledge` records. Do not claim a best result until metric direction is defined as maximize, minimize, or target range.

## Prepare analysis and figure handoff

Generate a fresh package for the requested scope:

```bash
python scripts/hub.py analyze --project "..." --start 2026-08-01 --end 2026-08-31
python scripts/hub.py analyze --project "..." --family "LTA-pH-Optimization"
```

Require the package to include filtered Excel/CSV data, descriptive summaries, data dictionary, experiment context, QA report, and provenance. Treat built-in summaries as lightweight descriptive calculations.

Use `nature-statistics` for inferential statistics and `nature-figure` for publication-grade figures. Pass the entire current package and the research question. Do not pass only a screenshot or a previous report.

## Regenerate the Dashboard

Run:

```bash
python scripts/hub.py dashboard --project "..."
```

Deliver `Dashboard/experiment_dashboard.html`. It must remain self-contained and offline. Show experiment overview, filters, recent experiments, trend, Family progress, and timeline. Do not display or embed QA/QC findings, missing-value or outlier assessments, metadata-completeness scores, or data-quality judgments; keep those in the database, validation output, analysis package, and reports. When metric direction is missing, display that best-result selection is not configured.

## Generate reports from the database

Run a new database query for every report:

```bash
python scripts/hub.py report --project "..." --type weekly
python scripts/hub.py report --project "..." --type monthly --month 2026-08
python scripts/hub.py report --project "..." --type stage --start 2026-03-01 --end 2026-08-31
```

Hub V1 produces Markdown, HTML, and a current evidence package. Keep Measured, Calculated, Inferred, and Hypothesis statements separate. Never concatenate weekly reports into a monthly report.

Use `documents`, `pdf`, or `presentations` for polished DOCX/PDF/PPTX, and provide them the new evidence package plus report Markdown. Use `nature-statistics` and `nature-figure` first when the report needs formal statistics or figures.

## Create reusable templates

Regenerate bundled templates only when developing or updating the Skill:

```bash
python scripts/hub.py create-templates --output assets/templates
```

Do not use the optional metadata template as a gate; Quick Intake remains valid.

## Final QA and user handoff

Before completing an operation:

1. confirm the raw archive hash and source path;
2. open or inspect the organized workbook and key database sheets;
3. scan for duplicate import, unresolved conflicts, missing metadata, and HIGH QA issues;
4. confirm Dashboard/report/package outputs exist when requested;
5. report what was archived, what was derived, what remains unknown, and what requires researcher review;
6. list exact output paths and state whether any statistical or causal inference was intentionally withheld.
