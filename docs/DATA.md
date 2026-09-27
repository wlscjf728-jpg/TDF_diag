# Data and measurements

| Path under evidence/ | Configuration and purpose |
|---|---|
| diagnosis/recalculated_v2/ | Five 1,000-cell chains; four software reference methods |
| diagnosis/two_dimensional_paper_faithful/ | Explicit square71 and legacy5x1000 topology labels |
| rtl/ | Behavioral diagnosis outputs |
| logger/ | Seven compact-encoder cases |
| timing/ | Setup/hold uncertainty and lock-up skew sweep |
| area/ | Processor baselines and small-design calibration reports |
| verification/ | Captured tests, RTL runs and small software sweeps |
| summaries/ | Packaged data-oriented summaries |

Historical directory names identify experiment versions, not one uniform simulation campaign.

## Diagnosis metrics

Raw rows contain suspect count, true/false positives, false negatives, precision and recall. Ground truth evaluates results; it is not provided as a localization hint to the observation-driven methods.

- Precision = true positives / suspects.
- Recall = true positives / active faults.
- Mean suspect count measures absolute candidate-space size.
- Reciprocal mean precision is not automatically mean per-trial ratio or hardware candidates-per-indication.

For intermittent precision/recall averages, the summary tool excludes opportunities with no active faults and reports their count separately. False-negative counts remain visible so that missed faults are not interpreted as better localization.

The proposed architecture's Nsp granularity is separate from these four reference methods; see [Architecture](ARCHITECTURE.md).

## Compact logger

Baselines are 2,880 full-response bits and 288 raw pattern-hit bits. Records use sixteen bits, with at most 32 stored records. Forty detected events produce 512 stored bits and overflow.

Dense cases can have negative reduction relative to 288 bits. Event encoding benefits sparse evidence; it does not guarantee compression for every input.

## Timing and area

Timing data distinguishes scan-only, scan-MUX, spare-only and lock-up structures. Keep FF-to-latch and latch-to-FF setup/hold checks separate. Some upstream hold checks are negative at larger uncertainty.

Area reports contain processor baselines and small-design calibration structures. Memory macros or estimates can dominate baseline area, so retain the denominator in comparisons. A fresh diagnosis-inserted implementation for every processor is not included.

Technology databases, EDA binaries and third-party processor RTL are excluded. Re-running physical-design experiments needs external setup.

## Provenance

`source_manifest.csv` contains relative original paths, sizes and SHA-256 hashes for unchanged included sources. `python3 scripts/verify_sources.py` checks them. New scripts, summaries and documentation are separate.

The verification record distinguishes completed tests from campaigns not rerun during packaging; it does not imply a new hundred-trial sweep or synthesis/STA campaign.
