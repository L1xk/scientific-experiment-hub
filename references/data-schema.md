# Data schema

Use this reference when creating, auditing, or extending the experiment database.

## Storage layers

1. `原始数据/`: immutable source file copied byte-for-byte and identified by SHA-256.
2. `整理结果/`: derived, formatted workbook with source sheet/row provenance.
3. `Research_Experiment_Database.xlsx`: append-oriented structured database.
4. `分析交接/`: filtered evidence packages regenerated from the database.
5. `报告/` and `Dashboard/`: presentation layers; never treat them as databases.

## Experiment identifier

Assign `EXP-YYYYMMDD-XXX`. When the actual experiment date is unknown, use the import date only for the identifier and storage path, while keeping `Experiment_Date=Unknown` and recording the fallback source.

## Core sheets

### Experiment_Index

One row per imported experiment version. Preserve failed, negative, inconclusive, and archived experiments. Required identifiers and provenance include:

- `Experiment_ID`, `Experiment_Date`, `Experiment_Name`, `Experiment_Family`
- `Project_ID`, `Status`, `Outcome`
- `Source_File`, `Organized_File`, `File_SHA256`, `Import_Date`, `Data_Version`
- metadata-completeness and QA counts

### Experiment_Conditions

Keep one row per detected sample/condition combination. Use `Unknown` for missing fields. Never infer pH, temperature, control group, unit, or replicate identity from numeric values alone.

### Raw_Data

Prefer long format. Each row carries:

```text
Record_ID
Experiment_ID
Sample_ID
Group
Biological_Replicate
Technical_Replicate
Metric
Raw_Value
Unit
Outlier_Flag
Source_File
Source_Sheet
Source_Row
Source_Column
Import_Date
Data_Version
```

`Raw_Value` remains the source value. Layout cleanup does not authorize numeric modification.

### Normalized_Data

Create rows only when cleaning, conversion, normalization, or analysis values exist. Preserve:

```text
Raw_Value → Cleaned_Value → Normalized_Value → Analysis_Value
```

Record the exact `Transformation` and `Transformation_Reason`.

### Summary

Aggregate technical replicates within each biological replicate first. Report `Observed_N` separately from `Biological_N`. Mark inference ineligible when the independent unit is unknown or insufficient.

### QA_QC and Data_Conflicts

QA flags are review prompts, not deletion instructions. A conflict is keyed by:

```text
Experiment_ID + Sample_ID + Metric + Biological_Replicate + Technical_Replicate
```

If the key exists with a different value, record both values and sources in `Data_Conflicts`; do not overwrite either silently.

## Missing values

Keep these states distinct whenever the source provides them:

- `Unknown`: value is not known.
- `Not Provided`: expected metadata was not supplied.
- `NA`: not applicable.
- missing measurement, not measured, failed measurement, below detection, and true zero.

Do not collapse these states into zero.

## Extension rules

- Add experiment-specific fields to `Experiment_Conditions` or a new documented sheet.
- Add every new field to `Data_Dictionary`.
- Do not rename or repurpose an existing field without a migration and version note.
- Keep identifiers as text and dates as ISO `YYYY-MM-DD` values.
- Preserve old versions and provenance during schema evolution.
