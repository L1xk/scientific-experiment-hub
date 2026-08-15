# Provenance and conflict handling

Use this reference for every import, update, correction, or merge.

## Raw-data contract

- Copy the uploaded file byte-for-byte into `原始数据/`.
- Calculate SHA-256 before import.
- Never overwrite, delete, rename in place, or save an edited workbook over the archive.
- Store layout cleanup, parsing, conversion, and analysis in derived outputs.

## Idempotency

If the SHA-256 already exists in a successful import ledger entry, return `already_imported` and make no changes.

## Versions

Use the same `Experiment_ID` with an incremented `Data_Version` only when the user intentionally adds a corrected or revised source for the same experiment. Keep every archived source and database snapshot.

## Conflict rule

For the same:

```text
Experiment_ID + Sample_ID + Metric + Biological_Replicate + Technical_Replicate
```

- same value: treat as a duplicate and skip appending;
- different value: record `DATA CONFLICT`, both values, both sources, and timestamp;
- do not select a winner automatically;
- resolve as user-confirmed correction, separate version, or separate sample/replicate identity.

## Audit artifacts

- `import_log.jsonl`: append-only import ledger.
- `import_manifest.json`: per-import manifest.
- `版本快照/`: pre-update database snapshots.
- `QA_QC`: detected quality issues and their resolution state.
- `Data_Conflicts`: unresolved and resolved data conflicts.

Every user-facing conclusion must be traceable back to experiment, source file, sheet, row, and transformation when available.

