# Visualization rules

Use this reference for quick plots and before handing data to `nature-figure`.

## Evidence-first figure contract

Before plotting, state the scientific question, comparison, independent unit, metric, unit, transformation, and uncertainty definition. Use a title that expresses the question or finding rather than `Results`.

## Recommended encodings

- Group comparison: raw points with mean/error, box plot with points, or bar with individual points.
- Time course: line plot with observed points; do not silently connect missing observations.
- Dose response: scatter plus a model only when the model and fit diagnostics are stated.
- Multi-factor: heatmap or grouped comparison with consistent scales.
- Cross-experiment: dated trend, batch comparison, or progression after metric direction is confirmed.

## Non-negotiable rules

- Use a white background, readable labels, explicit units, and a restrained palette.
- Show raw observations when feasible.
- State whether uncertainty is SD, SEM, CI, percentile, or another interval.
- State sample number and the unit of replication when appropriate.
- Avoid decorative 3D, misleading dual axes, and truncated bar baselines.
- Distinguish missing, zero, censored, failed, and excluded values.
- Preserve source data, transformations, exclusions, code, and random seeds.
- Do not claim journal compliance from aesthetics alone.

## Companion Skill

Use `nature-figure` for publication-grade static figures, multi-panel composition, final export, color/accessibility checks, and manuscript-level QA. Pass `analysis_ready.csv`, `descriptive_summary.csv`, `experiment_context.md`, `qa_report.md`, and `provenance.json` together.

