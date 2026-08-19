# GitHub commands for exp_20260804_001

Run from the authenticated project terminal. The Codex environment cannot perform these operations because its `.git` metadata is unavailable and its isolated `gh` token is invalid.

```bash
git switch -c exp/20260804-001-mdmt-sync-tracklet-association

gh issue create \
  --repo Judecoodingspace/matrix_async_comm_tracking \
  --title "exp_20260804_001: MDMT sync cross-view tracklet association feasibility" \
  --label experiment --label analysis \
  --body-file summary_md/github/20260804_mdmt_sync_cross_view_tracklet_association_issue.md

git add \
  src/tracking/mdmt_global_tracklet_fusion.py \
  src/tracking/mdmt_sync_association.py \
  src/tracking/tracklet_packets.py \
  scripts/phase3_mdmt_sync_cross_view_tracklet_association.py \
  tests/test_mdmt_sync_cross_view_tracklet_association.py \
  summary_md/experiments/2026-8-4/ \
  mermaid/exp_20260804_001_mdmt_sync_cross_view_tracklet_association/ \
  summary_md/github/20260804_mdmt_sync_cross_view_tracklet_association_issue.md \
  summary_md/github/20260804_mdmt_sync_cross_view_tracklet_association_commands.md \
  summary_md/experiments/INDEX.md \
  summary_md/current_experiment_stage.md \
  summary_md/current_status.md \
  mermaid/overall_experiment_design_20260709.mmd \
  GLOSSARY.md

git commit -m "feat: add MDMT synchronous tracklet association audit"
git push -u origin exp/20260804-001-mdmt-sync-tracklet-association

gh pr create \
  --repo Judecoodingspace/matrix_async_comm_tracking \
  --base exp/20260803-002-mdmt-async-tracklet-fusion \
  --head exp/20260804-001-mdmt-sync-tracklet-association \
  --draft \
  --title "exp_20260804_001: synchronous cross-view tracklet association" \
  --body "Implements Oracle headroom, LOSO candidate/appearance calibration, reject-all thresholds, and synchronous transfer gates. Pilot and Formal runs are pending."
```
