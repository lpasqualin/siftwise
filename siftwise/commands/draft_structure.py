"""
Updated draft-structure command that uses the strategy layer.

The strategy layer now owns the "brains" - deciding Action and TargetPath
based on confidence, rules, and entities.
"""

from pathlib import Path
from typing import Dict, Any


def run(args):
    """
    Entry point for draft-structure command with strategy layer integration.
    """
    from siftwise.state.io import ensure_sift_dir, write_treeplan, write_mapping, write_preview
    from siftwise.analyze.analyzer import analyze_paths
    from siftwise.strategy import build_plan, get_plan_summary

    root = Path(args.root).resolve()
    dest_root = Path(args.dest_root).resolve()

    print(f"[sift] draft-structure starting")
    print(f"[sift]   root      = {root}")
    print(f"[sift]   dest_root = {dest_root}")

    sift_dir = ensure_sift_dir(dest_root)
    print(f"[sift]   sift_dir  = {sift_dir}")

    # 1. Collect files
    print(f"[sift] Scanning {root}...")
    paths = [p for p in root.rglob("*") if p.is_file()]
    print(f"[sift] Found {len(paths)} files")

    # 2. Run analyzer (first pass)
    print(f"[sift] Analyzing files...")
    results = analyze_paths(paths=paths, root_out=dest_root, refinement_iteration=1)

    # (Optional) initial residual report based on analyzer flag, still fine
    residual_count = sum(1 for r in results if getattr(r, 'is_residual', False))
    if residual_count > 0:
        print(f"[sift] Identified {residual_count} residual files "
              f"({residual_count / len(results) * 100:.1f}%)")

    # 3. Build plan using strategy layer
    print(f"[sift] Building execution plan...")

    # Pull flags from args
    use_rules = getattr(args, 'use_rules', False)
    # If you later add a CLI flag, wire it here; for now default True
    preserve_structure = getattr(args, 'preserve_structure', True) \
        if hasattr(args, 'preserve_structure') else True

    # Base config for planner
    config: Dict[str, Any] = {
        'use_rules': use_rules,
        'preserve_structure': preserve_structure,
        'scan_root': root,   # 👈 this is what enables structure preservation
    }

    # Optional: look for rules.yaml in dest_root
    rules_path = dest_root / 'rules.yaml'
    if rules_path.exists():
        config['rules_path'] = rules_path
        print(f"[sift] Loading rules from {rules_path}")

    # Call strategy layer with a single, consistent config
    plan = build_plan(
        results=results,
        dest_root=dest_root,
        config=config,
    )

    # 4. Write artifacts
    from_stats = plan['stats']

    # DEBUG: see what we're actually about to write
    tree_plan = plan['tree_plan']
    print(f"[planner] tree_plan type = {type(tree_plan)}")
    print(f"[planner] tree_plan value = {tree_plan!r}")

    write_treeplan(sift_dir, tree_plan)
    write_mapping(sift_dir, plan['mapping_rows'])
    write_preview(sift_dir, from_stats)

    # 5. Print summary
    print(f"\n[sift] Draft complete!")
    print(get_plan_summary(plan))
    print(f"\n[sift] Artifacts saved to {sift_dir}")
    print(f"[sift] Next steps:")
    print(f"[sift]   1. Review: sift review-structure --dest-root \"{dest_root}\"")
    print(f"[sift]   2. Execute: sift execute --dest-root \"{dest_root}\"")

    if from_stats.get('residual_count', 0) > 0:
        print(f"[sift]   3. Refine: sift refine-residuals --dest-root \"{dest_root}\"")
