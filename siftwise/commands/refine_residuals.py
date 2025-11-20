"""
Updated refine-residuals command that uses the strategy layer.

Re-analyzes residual files and uses the strategy layer to update
the plan consistently.
"""

from pathlib import Path


def run(args):
    """
    Entry point for refine-residuals command with strategy layer integration.
    """
    from siftwise.state.io import get_sift_dir, load_mapping, update_mapping, write_residual_summary
    from siftwise.analyze.analyzer import analyze_paths
    from siftwise.strategy import replan_residuals

    dest_root = Path(args.dest_root).resolve()
    sift_dir = get_sift_dir(dest_root)
    iteration = getattr(args, 'iteration', 2)

    print(f"[sift] refine-residuals starting (iteration {iteration})")
    print(f"[sift]   dest_root = {dest_root}")
    print(f"[sift]   sift_dir  = {sift_dir}")

    # 1. Load current mapping
    mapping_rows = load_mapping(sift_dir)
    print(f"[sift] Loaded {len(mapping_rows)} files from mapping")

    # 2. Filter to residual files
    residual_rows = [
        row for row in mapping_rows
        if row.get('IsResidual', '').lower() == 'true'
    ]

    if not residual_rows:
        print(f"[sift] No residual files to refine!")
        return

    print(f"[sift] Found {len(residual_rows)} residual files to re-analyze")

    # 3. Collect residual file paths
    residual_paths = []
    for row in residual_rows:
        path = Path(row['SourcePath'])
        if path.exists():
            residual_paths.append(path)
        else:
            print(f"[sift] Warning: file not found: {path}")

    print(f"[sift] Re-analyzing {len(residual_paths)} files...")

    # 4. Re-analyze with higher iteration number (may boost confidence)
    results = analyze_paths(
        paths=residual_paths,
        root_out=dest_root,
        refinement_iteration=iteration,
    )

    # 5. Use strategy layer to update the plan
    print(f"[sift] Updating plan with refined results...")

    config = {
        'use_rules': True,  # Apply rules on refinement
        'preserve_structure': True,
    }

    # Look for rules.yaml
    rules_path = dest_root / 'rules.yaml'
    if rules_path.exists():
        config['rules_path'] = rules_path

    updated_plan = replan_residuals(
        mapping_rows=mapping_rows,
        updated_results=results,
        dest_root=dest_root,
        config=config,
    )

    # 6. Write updated mapping
    update_mapping(sift_dir, updated_plan['mapping_rows'])

    # 7. Generate and write summary
    stats = updated_plan['stats']

    summary = {
        'iteration': iteration,
        'total_residuals_analyzed': len(residual_paths),
        'reclassified': stats.get('reclassified', 0),
        'still_residual': stats.get('still_residual', 0),
        'reclassification_rate': (
            stats.get('reclassified', 0) / len(residual_paths) * 100
            if residual_paths else 0
        ),
    }

    write_residual_summary(sift_dir, summary)

    # 8. Print results
    print(f"\n[sift] Refinement complete!")
    print(f"[sift]   Analyzed: {len(residual_paths)} files")
    print(f"[sift]   Reclassified: {stats.get('reclassified', 0)} "
          f"({summary['reclassification_rate']:.1f}%)")
    print(f"[sift]   Still residual: {stats.get('still_residual', 0)}")
    print(f"\n[sift] Updated mapping saved to {sift_dir / 'Mapping.csv'}")

    if stats.get('still_residual', 0) > 0:
        print(f"\n[sift] Note: {stats.get('still_residual', 0)} files remain as residuals.")
        print(f"[sift] Consider:")
        print(f"[sift]   1. Running another refinement pass")
        print(f"[sift]   2. Adding custom rules in rules.yaml")
        print(f"[sift]   3. Using 'sift search' to identify patterns")