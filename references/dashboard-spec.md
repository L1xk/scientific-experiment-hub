# Dashboard specification

Use this reference when generating or extending `experiment_dashboard.html`.

## Role

The Dashboard is a presentation and navigation layer. It consumes the structured database and never becomes the source of truth.

```text
Archived raw data → organized/database layer → analysis → Dashboard
```

## V1 contract

- Generate one self-contained UTF-8 HTML file.
- Require no server, Docker, CDN, or network connection.
- Embed the current structured snapshot as JSON.
- Provide filters for project, Family, experiment type, status, and date range.
- Show experiment count, measurement count, Family count, date range, recent experiments, trend, Family progress, and timeline.
- Do not display, score, summarize, or embed QA/QC issues, missing-value assessments, outlier flags, metadata-completeness scores, or data-quality judgments. Keep them in the database, validation output, analysis package, and reports instead.
- Rebuild after every successful import.

## Best result guardrail

Do not choose a best result until `Metric_Direction` is known:

- `Maximize`
- `Minimize`
- `Target Range`

When it is unknown, display `Not configured` rather than assuming that larger is better.

## Extension path

Add metric, sample, condition, batch, and operator filters when the normalized schema is sufficiently complete. Plotly may be used optionally, but the V1 core must remain offline and dependency-light.
