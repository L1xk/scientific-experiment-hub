# Report specification

Use this reference for weekly, monthly, quarterly, semester, stage, project, and custom reports.

## Regeneration rule

Always re-query the database for the target date range. Never construct a monthly or stage report by concatenating previous reports.

## Weekly

Answer: what was done this week?

- experiment/sample/measurement counts;
- Families, objectives, conditions, and quantitative results;
- failed experiments and QA issues;
- comparison with the previous equivalent period when available;
- interpretation boundaries and next-week plan.

## Monthly

Answer: what changed this month?

- Family progress and trends;
- best-condition analysis only when direction is defined;
- performance change, reproducibility, failures, unresolved questions, and priorities.

Do not present it as a collection of weekly notes.

## Stage, semester, project

Organize around:

```text
Scientific Question → Initial Hypothesis → Strategy → Screening →
Optimization → Failures → Validation → Current Evidence →
Conclusion Boundary → Next Research Question
```

Include background, objective, major Families, key experiments, evidence figures, optimization history, statistical evidence, limitations, open questions, and future plan.

## Evidence labels

Label claims as `Measured`, `Calculated`, `Inferred`, or `Hypothesis`. Do not manufacture causes when the researcher only supplies observations.

## Output ownership

- Hub V1: Markdown + HTML plus a fresh evidence package.
- `documents`: polished DOCX.
- `pdf`: verified PDF.
- `presentations` or a suitable Nature presentation Skill: PPTX.
- `nature-statistics`: final statistics.
- `nature-figure`: publication-grade figures.

