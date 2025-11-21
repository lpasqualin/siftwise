"""
Updated refine-residuals command that uses the strategy layer.

Re-analyzes residual files and uses the strategy layer to update
the plan consistently.
"""

from pathlib import Path
from siftwise.state.io import write_entities_csv, aggregate_entities_from_mapping

def run(args):
    """
    Entry point for refine-residuals command with Residual Loop v1.

    Residual Loop v1 Protocol:
    - Only operates on IsResidual == True rows
    - Applies history-based confidence boosting
    - Promotes residuals to SUGGEST/MOVE using deterministic thresholds
    - Chains Previous* history columns across passes
    - Never touches non-residual decisions (pass-through)
    - Safe to run multiple times (deterministic)
    """
    from siftwise.state.io import get_sift_dir, load_mapping, update_mapping, write_residual_summary
    from siftwise.analyze.analyzer import analyze_paths
    from siftwise.strategy.residuals import apply_residual_refinement, build_refinement_stats

    dest_root = Path(args.dest_root).resolve()
    sift_dir = get_sift_dir(dest_root)
    iteration = getattr(args, 'iteration', 2)

    print(f"[sift] refine-residuals starting (Pass {iteration})")
    print(f"[sift]   dest_root = {dest_root}")
    print(f"[sift]   sift_dir  = {sift_dir}")

    # 1. Load current mapping
    mapping_rows = load_mapping(sift_dir)
    print(f"[sift] Loaded {len(mapping_rows)} files from mapping")

    # 2. Filter to residual files (Run Protocol v1: residual-only)
    def _is_true(v: str) -> bool:
        return str(v).strip().lower() in ("true", "1", "yes", "y")

    residual_rows = [row for row in mapping_rows if _is_true(row.get("IsResidual", ""))]
    non_residual_rows = [row for row in mapping_rows if not _is_true(row.get("IsResidual", ""))]

    if not residual_rows:
        print(f"[sift] No residual files to refine!")
        return

    print(f"[sift] Found {len(residual_rows)} residual files to re-analyze")
    print(f"[sift] Pass-through {len(non_residual_rows)} non-residual files unchanged")

    # 3. Collect residual file paths
    residual_paths = []
    residual_path_to_row = {}  # Map path to original row for history lookup
    
    for row in residual_rows:
        path = Path(row['SourcePath'])
        if path.exists():
            residual_paths.append(path)
            residual_path_to_row[str(path)] = row
        else:
            print(f"[sift] Warning: file not found: {path}")

    print(f"[sift] Re-analyzing {len(residual_paths)} files...")

    # 4. Re-analyze with higher iteration number
    results = analyze_paths(
        paths=residual_paths,
        root_out=dest_root,
        refinement_iteration=iteration,
    )

    print(f"[sift] Applying confidence boosts and promotion logic...")

    # 5. Apply boost + promotion to each residual
    updated_residual_rows = []
    
    for result in results:
        source_path_str = str(result.path)
        old_row = residual_path_to_row.get(source_path_str)
        
        if not old_row:
            print(f"[sift] Warning: no old row for {source_path_str}, skipping")
            continue
        
        # Apply Residual Loop v1 refinement
        updated_row = apply_residual_refinement(
            old_mapping_row=old_row,
            new_analysis_result=result,
            pass_id=iteration,
        )
        
        updated_residual_rows.append(updated_row)

    # 6. Build complete mapping: non-residuals (pass-through) + updated residuals
    complete_mapping = non_residual_rows + updated_residual_rows
    
    # 7. Write updated mapping
    update_mapping(sift_dir, complete_mapping)

    # Regenerate Entities.csv from updated mapping
    print(f"[sift] Regenerating entities aggregation...")
    entities_data = aggregate_entities_from_mapping(complete_mapping)
    if entities_data:
        write_entities_csv(sift_dir, entities_data)
    # 8. Generate stats
    stats = build_refinement_stats(
        original_residuals=residual_rows,
        updated_rows=updated_residual_rows,
    )

    # 9. Write summary
    summary = {
        'pass_id': iteration,
        'residuals_in': stats['residuals_in'],
        'reclassified_to_move': stats['reclassified_to_move'],
        'reclassified_to_suggest': stats['reclassified_to_suggest'],
        'still_residual': stats['still_residual'],
        'residual_rate_after': stats['residual_rate_after'],
    }

    write_residual_summary(sift_dir, summary)

    # 10. Print clean receipt (executor-style summary)
    print(f"\n{'='*60}")
    print(f"[sift] RESIDUAL REFINEMENT COMPLETE (Pass {iteration})")
    print(f"{'='*60}")
    print(f"  Residuals In:          {stats['residuals_in']}")
    print(f"  Promoted to MOVE:      {stats['reclassified_to_move']}")
    print(f"  Promoted to SUGGEST:   {stats['reclassified_to_suggest']}")
    print(f"  Still Residual:        {stats['still_residual']}")
    print(f"  Residual Rate After:   {stats['residual_rate_after']:.1f}%")
    print(f"{'='*60}")
    print(f"\n[sift] Updated mapping saved to {sift_dir / 'Mapping.csv'}")

    if stats['still_residual'] > 0:
        print(f"\n[sift] Note: {stats['still_residual']} files remain as residuals.")
        if iteration < 3:
            print(f"[sift] Consider:")
            print(f"[sift]   1. Running another refinement pass (Pass {iteration + 1})")
            print(f"[sift]   2. Adding custom rules in rules.yaml")
            print(f"[sift]   3. Using 'sift search' to identify patterns")
        else:
            print(f"[sift] Multiple passes complete. Remaining residuals may need:")
            print(f"[sift]   - Custom rules (rules.yaml)")
            print(f"[sift]   - Manual review or reclassification")