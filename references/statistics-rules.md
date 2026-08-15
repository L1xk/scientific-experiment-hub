# Statistics rules

Use this reference before interpreting summaries, running tests, or handing data to `nature-statistics`.

## Independent unit first

Identify the experimental unit before selecting any inferential method. Never count technical readings, image fields, wells, spectra, cells, or repeated measurements as independent biological `n` without design evidence.

For `3 biological × 3 technical`:

1. Aggregate technical replicates within each biological replicate using a documented rule.
2. Preserve the technical values and aggregation result.
3. Use the three biological replicate aggregates for inference.
4. Report `Observed_N=9` and `Biological_N=3` separately.

## Default outputs

Always report descriptive statistics before tests:

- observed count and biological `n`;
- mean, median, SD, SEM, min, max, CV%;
- missingness and suspected outliers;
- exact estimator and uncertainty definition.

## Test gate

Do not run a test when the design, independent unit, pairing, group definition, or outcome type is unclear. Use descriptive results and mark `AUTHOR_INPUT_NEEDED` instead.

When design facts are adequate, consider:

- two independent continuous groups: Welch t-test or Mann–Whitney;
- paired continuous data: paired t-test or Wilcoxon signed-rank;
- three or more groups: ANOVA/Welch ANOVA or Kruskal–Wallis;
- repeated measures: repeated-measures or mixed model, not ordinary ANOVA;
- relationships: Pearson/Spearman correlation or a regression model with diagnostics;
- multi-factor or batch designs: factorial/mixed models when justified.

Check assumptions and use effect sizes with confidence intervals. Correct planned multiple comparisons. Do not use statistical significance as a synonym for biological importance.

## Outliers

IQR, z-score, Grubbs, or domain rules may flag candidates. Never delete automatically. Report analyses with and without a disputed value only as a sensitivity analysis, with the exclusion rationale and provenance.

## Evidence labels

- `Measured`: copied from the source.
- `Calculated`: deterministic descriptive or transformed value.
- `Inferred`: statistical or scientific inference supported by a specified model/test.
- `Hypothesis`: proposed explanation requiring new evidence.

## Companion Skill

Use `nature-statistics` for final test selection, assumption checks, effect sizes, confidence intervals, reviewer-ready wording, or complex/nested designs. Pass the current `analysis_package`, not an old report or a reformatted chart.
