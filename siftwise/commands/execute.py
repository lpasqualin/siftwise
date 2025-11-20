from pathlib import Path
import sys

from ..state.io import get_sift_dir, load_treeplan, load_mapping
from ..execute.executor import execute_from_plan


def run(args):
    """
    Execute command entry point - validates inputs and calls executor.

    Args:
        args: argparse namespace with:
            - dest_root: destination root directory
            - plan: optional path to TreePlan.json
            - mapping: optional path to Mapping.csv
            - what_if: dry-run flag (True = no changes)
    """
    # Resolve destination root
    dest_root = Path(args.dest_root).resolve()

    # Get sift directory (<dest_root>/.sift) and validate it exists
    sift_dir = get_sift_dir(dest_root)

    # Resolve plan path (either user-provided or default)
    if args.plan:
        plan_path = Path(args.plan).resolve()
    else:
        plan_path = sift_dir / "TreePlan.json"
        print(f"Using default plan: {plan_path}")

    # Resolve mapping path (either user-provided or default)
    if args.mapping:
        mapping_path = Path(args.mapping).resolve()
    else:
        mapping_path = sift_dir / "Mapping.csv"
        print(f"Using default mapping: {mapping_path}")

    # Validate plan exists
    if not plan_path.exists():
        print(f"❌ Error: Missing plan file: {plan_path}")
        print("\nPlease run 'sift draft-structure' first, or provide a valid --plan path.")
        sys.exit(1)

    # Validate mapping exists
    if not mapping_path.exists():
        print(f"❌ Error: Missing mapping file: {mapping_path}")
        print("\nPlease run 'sift draft-structure' first, or provide a valid --mapping path.")
        sys.exit(1)

    # Ensure destination root exists
    dest_root.mkdir(parents=True, exist_ok=True)

    # Load artifacts into in-memory structures
    plan = load_treeplan(sift_dir, override_path=str(plan_path))
    mapping_rows = load_mapping(sift_dir, override_path=str(mapping_path))

    # Print execution header
    print(f"\n{'=' * 60}")
    print("Executing plan:")
    print(f"  Plan:       {plan_path}")
    print(f"  Mapping:    {mapping_path}")
    print(f"  Dest root:  {dest_root}")
    print(
        "  Mode:       "
        + ("DRY RUN (no changes will be made)" if args.what_if else "LIVE (files will be moved/copied)")
    )
    print(f"{'=' * 60}\n")

    # Execute the plan using in-memory data
    try:
        execute_from_plan(plan, mapping_rows, dest_root, what_if=args.what_if)
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        sys.exit(1)
