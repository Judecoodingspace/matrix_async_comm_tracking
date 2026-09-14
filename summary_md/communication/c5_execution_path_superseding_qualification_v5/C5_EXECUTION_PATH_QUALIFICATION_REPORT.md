# C5 Q5 cell-local Shadow evidence-path qualification

Q5 binds C3T `9a511c3ce300b5dedb1f2e970f131ddd2522b0c0`, whose parent is Q4 `0722eefa98b350ec3c0a0672db89dd40caca966a`. It corrects the completion validator's Shadow evidence root from the output-base ancestor to the cell's run root, matching the `MIA_C5_SHADOW_CONFIG.output_dir` installed by the formal controlled environment.

The PacketRuntime manifest lifecycle, generated-author source binding, C5 Shadow semantics, exact four-cell matrix, R values, metric allowlist, and fail-closed evidence checks are unchanged. Run 003 is preserved as failed mechanical evidence and was not resumed or used for qualification.

Fresh synthetic/mechanical replay passed: execution gate `40 passed`, Q1–Q4 `42 passed`, combined `82 passed`. The new synthetic four-cell end-to-end regression uses the real controlled environment builder, writes evidence exactly to each configured cell-local Shadow directory, and requires the formal output validator to accept all four cells.

Context and Results hashes are SHA-256 values over exact raw UTF-8 file bytes. The separate Seal payload digest is SHA-256 of sorted-key, compact-separator UTF-8 JSON. No payload contains its own final digest. No scientific data, result counters, tracking evaluation, or intervention was accessed or executed.
