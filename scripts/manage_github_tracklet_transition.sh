#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-Judecoodingspace/matrix_async_comm_tracking}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

gh auth status
gh repo view "$REPO" >/dev/null

gh label create experiment --repo "$REPO" --color 1D76DB --description "Formal experiment tracking" --force
gh label create analysis --repo "$REPO" --color 5319E7 --description "Experiment analysis and interpretation" --force
gh label create completed --repo "$REPO" --color 0E8A16 --description "Completed and documented" --force
gh label create current-stage --repo "$REPO" --color FBCA04 --description "Active research stage" --force
gh label create research-decision --repo "$REPO" --color D4C5F9 --description "Research scope or direction decision" --force

upsert_issue() {
  local title="$1"
  local body_file="$2"
  shift 2
  local number
  number="$(
    gh issue list --repo "$REPO" --state all --limit 200 \
      --json number,title \
      --jq ".[] | select(.title == \"$title\") | .number" \
      | head -n 1
  )"

  local edit_label_args=()
  local create_label_args=()
  local label
  for label in "$@"; do
    edit_label_args+=(--add-label "$label")
    create_label_args+=(--label "$label")
  done

  if [[ -n "$number" ]]; then
    gh issue edit "$number" --repo "$REPO" \
      --body-file "$body_file" \
      "${edit_label_args[@]}" >/dev/null
    echo "updated: $(gh issue view "$number" --repo "$REPO" --json url --jq .url)"
  else
    gh issue create --repo "$REPO" \
      --title "$title" \
      --body-file "$body_file" \
      "${create_label_args[@]}"
  fi
}

upsert_issue \
  "Milestone: observation-level asynchronous fusion complete" \
  "$ROOT/summary_md/github/20260801_observation_level_milestone_issue.md" \
  experiment analysis completed research-decision

upsert_issue \
  "exp_20260801_002: incremental local-tracklet update foundation" \
  "$ROOT/summary_md/github/20260801_incremental_tracklet_stage_issue.md" \
  experiment analysis completed

upsert_issue \
  "exp_20260802_001: mobile-camera local tracklet readiness" \
  "$ROOT/summary_md/github/20260802_mobile_camera_local_tracklet_readiness_issue.md" \
  experiment analysis completed

upsert_issue \
  "exp_20260802_002: BoT-SORT candidate gate repair" \
  "$ROOT/summary_md/github/20260802_botsort_candidate_gate_repair_issue.md" \
  experiment analysis completed

upsert_issue \
  "exp_20260802_003: OC-SORT motion representation audit" \
  "$ROOT/summary_md/github/20260802_ocsort_motion_representation_audit_issue.md" \
  experiment analysis completed

upsert_issue \
  "exp_20260802_004: local-tracklet lifecycle-stratified readiness" \
  "$ROOT/summary_md/github/20260802_local_tracklet_lifecycle_stratified_issue.md" \
  experiment analysis completed

upsert_issue \
  "exp_20260803_001: MDMT local tracklet readiness" \
  "$ROOT/summary_md/github/20260803_mdmt_local_tracklet_readiness_issue.md" \
  experiment analysis completed

upsert_issue \
  "exp_20260803_002: MDMT asynchronous incremental tracklet fusion" \
  "$ROOT/summary_md/github/20260803_mdmt_async_incremental_tracklet_fusion_issue.md" \
  experiment analysis current-stage

echo "GitHub experiment tracking is synchronized for $REPO"
