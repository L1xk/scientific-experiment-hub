# Companion Skills

Use this reference when the user asks for work beyond basic organization and descriptive summaries.

## Routing

- `Spreadsheets`: inspect or repair special Excel layouts and visually verify user-facing workbooks.
- `nature-statistics`: design-aware inferential statistics and reporting.
- `nature-figure`: publication-grade scientific figures.
- `nature-writing` or `nature-polishing`: manuscript-quality scientific prose.
- `documents`: DOCX generation and visual verification.
- `pdf`: PDF creation or verification.
- `presentations` or an appropriate Nature presentation Skill: PPTX creation.

## Handoff protocol

Run `hub.py analyze` or `hub.py report` first. Pass the complete current package:

```text
filtered_data.xlsx
analysis_ready.csv
descriptive_summary.csv
data_dictionary.csv
experiment_context.md
qa_report.md
provenance.json
```

Tell the companion Skill:

1. the scientific question;
2. the independent unit and replicate hierarchy, if known;
3. the metric direction and control group, if known;
4. the intended audience/output;
5. that unknown information must remain unknown.

Do not pass only a screenshot, chart, or old report when the database is available.
