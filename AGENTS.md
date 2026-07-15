# AGENTS.md

Operational instructions for this OOSM / MDMOT validation project.

## 1. Project Identity

This project validates a time-aware cross-view OOSM tracklet fusion idea.

Do not frame this project as split YOLO, backend semantic fusion, or
communication selector optimization. Those were source-repository history.
Here they are only a source of reusable M3OT, detector, and ReID components.

Core hypotheses:

- A1: delayed cross-view observations contain identity information relevant to
  ID switches.
- A2: backfilling delayed observations to capture time improves identity
  tracking over fusing them at arrival time.

Current stance:

- Do not design the full adaptive OOSM framework before A1/A2 pass.
- `Backfill` is a hypothesis, not the default final method.
- `Fuse-at-current + exp decay` is the required simple alternative.
- The first useful result is a minimum falsification result, not a broad
  method sweep.

## 2. Required Bootstrap

At the start of a new conversation, read these files in order:

1. `AGENTS.md`
2. `README.md`
3. `experiment_validation_plan.md`
4. `summary_md/current_experiment_stage.md` if it exists
5. `summary_md/experiments/INDEX.md` if it exists
6. `summary_md/current_status.md` if it exists
7. `summary_md/migration_manifest.md` only when migration context is needed
8. `git status --short`

If this directory is not a Git worktree, record that fact and continue from the
filesystem state.

When asked about experiment state, inspect:

- the relevant row in `summary_md/experiments/INDEX.md`
- only the specific experiment card needed
- only the specific output directory named by the card or user

Avoid bulk-printing large CSVs, logs, or output trees. Use targeted `head`,
`tail`, `rg`, or short aggregations.

## 3. Directory Map

Tracked / source-like directories:

```text
src/                  reusable Python modules
scripts/              stable CLI entry points
configs/              experiment configs
tests/                regression tests
summary_md/           tracked research notes and handoffs
mermaid/              experiment design flowcharts
README.md             project orientation
AGENTS.md             agent workflow and continuity rules
GLOSSARY.md           experiment terminology (living document)
```

Ignored / local artifact directories:

```text
data/                 symlinks to datasets
weights/              model checkpoints
outputs/              generated experiment outputs
runs/                 optional generated runs
```

Durable conclusions belong in `summary_md/`, not only in `outputs/`.

## 4. Data Rules

Use raw M3OT MOT annotations for A1/A2:

```text
data/M3OT/*/*/*/*/gt/gt.txt
```

YOLO labels do not preserve `track_id` and are not sufficient for identity
metrics.

Default smoke pair:

```text
data/M3OT/1/rgb/val/1-08/img1
data/M3OT/1/rgb/val/1-08/gt/gt.txt
data/M3OT/2/rgb/val/2-08/img1
data/M3OT/2/rgb/val/2-08/gt/gt.txt
```

Before a new dataset or stream is used, verify:

- image count
- GT frame count
- shared `(frame_id, track_id)` count across source views
- whether track IDs are consistent across views
- whether image paths and GT paths refer to the same sequence

## 5. Model Rules

Default migrated checkpoints:

```text
weights/m3ot_detector_best.pt
weights/gem_proj_head_l15.pt
```

`weights/visdrone_detector_best.pt` is a historical baseline only. Do not use
it as the main M3OT detector unless the experiment is explicitly a baseline or
domain-mismatch check.

Record checkpoint paths in every formal experiment card.

## 6. CUDA Rule

Formal detector/ReID runs on this Jetson should use `cuda:0` unless explicitly
marked as CPU smoke. If CUDA appears unavailable inside a sandbox, verify
device nodes outside the restricted sandbox before concluding the Jetson is
CPU-only.

Use:

```bash
YOLO_CONFIG_DIR=/tmp
```

when running Ultralytics.

## 7. Experiment Lifecycle

Every formal experiment should follow:

```text
Idea -> Hypothesis -> Flowchart -> Config/Command -> Smoke -> Full Run -> Metrics -> Structured Analysis -> Decision
```

Before a formal run, define:

- experiment ID
- hypothesis
- source streams
- frame range
- detector checkpoint
- ReID checkpoint or model
- delay distribution and seed
- tracker and association thresholds
- output directory
- pass/fail decision rule

After a formal run, generate an analysis report (see Section 13) following the
7-dimension framework in `summary_md/analysis_framework.md`. The analysis report
must include at least one Mermaid flowchart.

Use stable experiment IDs:

```text
exp_YYYYMMDD_001_short_name
```

Default output root for the first validation:

```text
outputs/20260616_oosm_backfill_validation/
```

## 8. Experiment Records

Maintain:

```text
summary_md/current_experiment_stage.md
summary_md/current_status.md
summary_md/experiments/INDEX.md
summary_md/experiments/YYYY-M-D/exp_*.md
summary_md/codex_notes/YYYYMMDD_topic.md
summary_md/decisions/YYYYMMDD_decision.md
summary_md/code_maps/topic.md
```

A run is not complete until key metrics and the decision are summarized in a
tracked Markdown file.

## 9. Experiment Card Template

````markdown
# exp_YYYYMMDD_001_short_name

## Purpose

What question this experiment answers.

## Hypothesis

Expected result before running.

## Setup

- Device:
- Detector:
- ReID:
- Base source:
- Support source:
- Frame range:
- Delay distribution:
- Seed:
- Tracker:
- Metrics:

## Command

```bash
...
```

## Output

```text
outputs/...
```

## Key Metrics

| Pipeline | IDF1 | IDSW | MOTA | Latency ms/frame | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| Discard OOSM | | | | | |
| Fuse-at-current | | | | | |
| Backfill | | | | | |
| Fuse-at-current + exp decay | | | | | |

## Interpretation

What changed and why it matters.

## Decision

Accepted / rejected / pending.

## Next Actions

- [ ] ...
````

## 10. Coding Rules

Keep this project small:

- prefer new tracker-focused modules under `src/tracking/`
- keep migrated scripts as references unless they are cleaned up
- do not import old backend-fusion or communication-selection logic
- add tests for delay injection, OOSM ordering, and metric accounting
- keep output schemas stable once Phase 1/2 scripts exist

If a code area becomes important and hard to inspect, create or update a code
map under:

```text
summary_md/code_maps/
```

## 11. Conversation and Handoff Recording

Create or update tracked notes when a conversation:

- changes the research direction
- fixes an environment issue
- establishes a reusable command
- produces a validated smoke/full result
- rejects an idea after evidence
- changes dataset, weights, metrics, or output conventions

At the end of a substantial session, update `summary_md/current_status.md`
with:

- latest research focus
- changed files
- commands run
- outputs created
- verified results
- failed attempts
- exact next command to run

## 12. Mermaid Flowcharts

When designing or explaining experiments, produce a Mermaid flowchart:

- Place new diagrams under `mermaid/exp_YYYYMMDD_NNN/`
- Use the templates in `mermaid/templates/` as starting points
- Embed the diagram directly in the experiment card or analysis report with a
  ````mermaid` code block
- Read `mermaid/README.md` for syntax reference and naming conventions
- Each analysis report (Section 13) must reference at least one flowchart

## 13. Structured Experiment Analysis

After every formal experiment run, follow the 7-dimension analysis framework
defined in `summary_md/analysis_framework.md`. Do not rely on a generic "analyze
the last round" prompt — systematically work through all 7 dimensions.

Analysis reports go under:

```text
summary_md/experiments/YYYY-M-D/exp_XXX_analysis.md
```

Key rules:

- Answer all 7 dimensions even if some show "no signal"
- Include at least one Mermaid flowchart in the report
- The Dimension 7 (next actions) output must include priority-ranked concrete
  next steps with rationale
- Update `summary_md/experiments/INDEX.md` with a link to the analysis report

## 14. Terminology Glossary

Project terminology is maintained in `GLOSSARY.md` at the repo root. Rules:

- Explain terms with a plain-life analogy first, then a precise technical
  definition — see the style guide at the top of `GLOSSARY.md`
- When you introduce a new term in conversation or encounter one not yet in
  the glossary, add it
- When a term's understanding deepens through experiment results, update its
  entry
- Cross-reference related terms with `[[GLOSSARY#term-name]]` links
- Track the term count and last-updated date at the bottom of the file

## 15. Response Style

For experiment design, explain the logic before code changes. For simple
implementation requests, make the change, run the smallest useful verification,
and summarize exact files and commands.


<!-- headroom:rtk-instructions -->
# RTK (Rust Token Killer) - Token-Optimized Commands

When running shell commands, **always prefix with `rtk`**. This reduces context
usage by 60-90% with zero behavior change. If rtk has no filter for a command,
it passes through unchanged — so it is always safe to use.

## Key Commands
```bash
# Git (59-80% savings)
rtk git status          rtk git diff            rtk git log

# Files & Search (60-75% savings)
rtk ls <path>           rtk read <file>         rtk grep <pattern>
rtk find <pattern>      rtk diff <file>

# Test (90-99% savings) — shows failures only
rtk pytest tests/       rtk cargo test          rtk test <cmd>

# Build & Lint (80-90% savings) — shows errors only
rtk tsc                 rtk lint                rtk cargo build
rtk prettier --check    rtk mypy                rtk ruff check

# Analysis (70-90% savings)
rtk err <cmd>           rtk log <file>          rtk json <file>
rtk summary <cmd>       rtk deps                rtk env

# GitHub (26-87% savings)
rtk gh pr view <n>      rtk gh run list         rtk gh issue list

# Infrastructure (85% savings)
rtk docker ps           rtk kubectl get         rtk docker logs <c>

# Package managers (70-90% savings)
rtk pip list            rtk pnpm install        rtk npm run <script>
```

## Rules
- In command chains, prefix each segment: `rtk git add . && rtk git commit -m "msg"`
- For debugging, use raw command without rtk prefix
- `rtk proxy <cmd>` runs command without filtering but tracks usage
<!-- /headroom:rtk-instructions -->
