"""
Updated refine-residuals command that uses the strategy layer.

Re-analyzes residual files and uses the strategy layer to update
the plan consistently.
"""

from pathlib import Path
import pandas as pd


def run(args):
    """
    Entry point for refine-residuals command with strategy layer integration.

    Run Protocol v1: Residual-only refinement
    - Only operates on IsResidual == True rows
    - Never touches non-residual decisions
    - Safe to run multiple times
    """
    from siftwise.state.io import (
        get_sift_dir,
        load_mapping,
        update_mapping,
        write_residual_summary,
    )
    from siftwise.analyze.analyzer import analyze_paths
    from siftwise.strategy import replan_residuals

    dest_root = Path(args.dest_root).resolve()
    sift_dir = get_sift_dir(dest_root)
    iteration = getattr(args, "iteration", 2)

    print(f"[sift] refine-residuals starting (iteration {iteration})")
    print(f"[sift]   dest_root = {dest_root}")
    print(f"[sift]   sift_dir  = {sift_dir}")

    # 1) Load current mapping
    mapping_rows = load_mapping(sift_dir)
    print(f"[sift] Loaded {len(mapping_rows)} files from mapping")

    # 2) Filter to residual files only
    def _is_true(v: str) -> bool:
        return str(v).strip().lower() in ("true", "1", "yes", "y")

    residual_rows = [row for row in mapping_rows if _is_true(row.get("IsResidual", ""))]

    if not residual_rows:
        print("[sift] No residual files to refine!")
        return

    print(f"[sift] Found {len(residual_rows)} residual files to re-analyze")

    # 3) Collect residual file paths
    residual_paths = []
    for row in residual_rows:
        path = Path(row["SourcePath"])
        if path.exists():
            residual_paths.append(path)
        else:
            print(f"[sift] Warning: file not found: {path}")

    print(f"[sift] Re-analyzing {len(residual_paths)} files...")

    # 4) Re-analyze with higher iteration number
    results = analyze_paths(
        paths=residual_paths,
        root_out=dest_root,
        refinement_iteration=iteration,
    )

    # 5) Use strategy layer to update the plan
    print("[sift] Updating plan with refined results...")

    existing_pass_ids = [
        int(row.get("PassId"))
        for row in mapping_rows
        if str(row.get("PassId", "")).isdigit()
    ]
    next_pass_id = (max(existing_pass_ids) + 1) if existing_pass_ids else iteration

    # Best-effort scan_root (optional)
    scan_root = getattr(args, "root", None)
    scan_root = Path(scan_root).resolve() if scan_root else None

    config = {
        "use_rules": True,
        "preserve_structure_mode": "SMART",
        "scan_root": scan_root,
        "pass_id": next_pass_id,
    }

    # Look for rules.yaml
    rules_path = sift_dir / "rules.yaml"
    if not rules_path.exists():
        rules_path = dest_root / "rules.yaml"
    if rules_path.exists():
        config["rules_path"] = rules_path

    updated_plan = replan_residuals(
        mapping_rows=mapping_rows,
        updated_results=results,
        dest_root=dest_root,
        config=config,
    )

    # 6) Write updated mapping
    update_mapping(sift_dir, updated_plan["mapping_rows"])

    # 7) Generate and write summary
    stats = updated_plan["stats"]

    summary = {
        "iteration": iteration,
        "total_residuals_analyzed": len(residual_paths),
        "reclassified": stats.get("reclassified", 0),
        "still_residual": stats.get("still_residual", 0),
        "reclassification_rate": (
            stats.get("reclassified", 0) / len(residual_paths) * 100
            if residual_paths else 0
        ),
    }

    write_residual_summary(sift_dir, summary)

    # 8) Print results (ONCE)
    print(f"\n[sift] Refinement complete!")
    print(f"[sift]   Analyzed: {len(residual_paths)} files")
    print(
        f"[sift]   Reclassified: {stats.get('reclassified', 0)} "
        f"({summary['reclassification_rate']:.1f}%)"
    )
    print(f"[sift]   Still residual: {stats.get('still_residual', 0)}")
    print(f"\n[sift] Updated mapping saved to {sift_dir / 'Mapping.csv'}")

    # --- Tip: promote suggested -> move (shows only if Suggest > 0) ---
    try:
        mapping_path = sift_dir / "Mapping.csv"
        df_tip = pd.read_csv(mapping_path)

        if "Action" in df_tip.columns:
            suggest_count = int((df_tip["Action"] == "Suggest").sum())
            if suggest_count > 0:
                print(f"\n[sift] Note: {suggest_count} files are marked Suggest.")
                print("[sift] Tip: If you're confident, promote all Suggest → Move with:")
                print(f'[sift]   sift promote-suggested --dest-root "{sift_dir.parent}"')
    except Exception as e:
        print(f"[sift] (tip skipped) {e}")

    # Residual guidance
    if stats.get("still_residual", 0) > 0:
        print(f"\n[sift] Note: {stats.get('still_residual', 0)} files remain as residuals.")
        print("[sift] Consider:")
        print("[sift]   1. Running another refinement pass")
        print("[sift]   2. Adding custom rules in rules.yaml")
        print("[sift]   3. Using 'sift search' to identify patterns")
