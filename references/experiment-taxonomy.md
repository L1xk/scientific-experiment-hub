# Experiment taxonomy

Use this reference when assigning or reviewing `Experiment_Nature` and `Experiment_Family`.

## Classification contract

Apply information in this order:

1. User-confirmed name or Family.
2. Explicit labeled metadata inside the source workbook.
3. An active rule in `Family_Rules`.
4. A unique keyword candidate from the filename or sheet name.
5. `未分类实验` / `Unknown`.

Never choose among multiple plausible Families silently. Record the source and confidence of every automatic classification.

## Family logic

Treat experiments as the same Family when they address the same scientific question with compatible method and response metric, while allowing different dates, batches, operators, and optimization conditions.

Use these factors:

- objective and experiment type;
- substrate, enzyme, strain, plasmid, or biological system;
- measurement method and metric;
- core variable under investigation;
- control structure and experimental design.

Example Families:

```text
LTA-Enzyme-Screening
LTA-pH-Optimization
LTA-Temperature-Optimization
LTA-Substrate-Optimization
```

## Confidence

- `HIGH`: confirmed by the user or explicit labeled metadata.
- `MEDIUM`: one unambiguous active rule or keyword candidate.
- `LOW`: incomplete or competing evidence; keep provisional or unclassified.

## Renaming and merging

- Keep a mapping from old Family names to the confirmed canonical name.
- Do not rewrite archived source files.
- Update structured index/database fields through a versioned maintenance operation.
- Recalculate comparison outputs after a Family merge or split.

## Status and outcome

Keep workflow status separate from scientific outcome.

Statuses:

```text
Idea, Planned, Running, Completed, Failed, Needs Repeat,
Optimizing, Validated, Archived
```

Outcomes:

```text
Positive, Negative, Inconclusive, Failed, Optimization, Validation
```

Never delete a failed or negative experiment. It is evidence for historical queries and experimental planning.

