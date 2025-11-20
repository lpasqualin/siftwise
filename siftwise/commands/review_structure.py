import json, os, sys
from pathlib import Path
from ..state.io import get_sift_dir

def _print_ascii(plan):
    def walk(node_id, nodes_by_id, depth=0):
        node = nodes_by_id[node_id]
        print("  " * depth + f"- {node['name']} ({node['id']})")
        for child in [n for n in nodes_by_id.values() if n.get("parent") == node_id]:
            walk(child["id"], nodes_by_id, depth+1)

    nodes_by_id = {n["id"]: n for n in plan["nodes"]}
    root_id = plan.get("root_id", "n_root")
    print("\nProposed Structure:\n")
    walk(root_id, nodes_by_id)
    print("")

def run(args):
    dest_root = Path(args.dest_root).resolve()
    sift_dir = get_sift_dir(dest_root)
    tree_path = sift_dir / "TreePlan.json"
    if not tree_path.exists():
        print(f"Tree plan not found: {tree_path}. Run 'sift draft-structure' first.")
        sys.exit(1)

    plan = json.loads(tree_path.read_text(encoding="utf-8"))
    _print_ascii(plan)

    if getattr(args, "open_yaml", False) or getattr(args, "open_yml", False):
        yml = tree_path.with_suffix(".yaml")
        try:
            os.startfile(yml)  # Windows
        except Exception:
            print(f"Open the YAML here: {yml}")
