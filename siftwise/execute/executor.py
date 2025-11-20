import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable, Tuple, List, Dict, Any
from siftwise.analyze.analyzer import Result


def _normalize_action(action_str: str, is_residual: bool = False) -> str:
    """
    Normalize action string to canonical values.

    Returns one of: Move, Copy, Skip, Suggest
    """
    if not action_str:
        # Default to Skip for residuals, Move for non-residuals
        return "Skip" if is_residual else "Move"

    action = action_str.strip().lower()

    # Map to canonical values
    if action in ("move", "mv"):
        return "Move"
    elif action in ("copy", "cp"):
        return "Copy"
    elif action in ("skip", "ignore"):
        return "Skip"
    elif action in ("suggest", "review"):
        return "Suggest"
    else:
        # Unknown action - safer to skip
        return "Skip"


def _normalize_is_residual(residual_str: str) -> bool:
    """
    Normalize IsResidual field to boolean.

    Accepts: true, True, 1, yes, y, Y -> True
    Everything else -> False
    """
    if not residual_str:
        return False

    normalized = residual_str.strip().lower()
    return normalized in ("true", "1", "yes", "y")


def execute(results: Iterable[Result], what_if: bool, log_dir: Path) -> Path:
    """
    Execute file operations based on analyzer results.
    Respects the Action field - Skip/Suggest files are not moved.

    This is the legacy results-based executor, kept for compatibility.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"RunLog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    # Counters for accurate reporting
    moved = 0
    copied = 0
    skipped_by_action = 0
    skipped_residuals = 0
    skipped_by_error = 0

    with log_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['Time', 'Action', 'Status', 'SourcePath', 'DestPath', 'Label', 'Confidence',
                                          'Why', 'Note'])
        w.writeheader()

        for r in results:
            status, note = 'OK', ''

            # Normalize action
            is_residual = getattr(r, 'is_residual', False)
            action = _normalize_action(r.action, is_residual)

            # Determine destination
            dest = None
            if action in ('Move', 'Copy'):
                dest = Path(r.target_path) / Path(r.path).name

            try:
                if is_residual:
                    # Residuals always stay in place
                    status = 'Residual'
                    note = 'residual/unsorted - left in place'
                    skipped_residuals += 1

                elif action in ('Skip', 'Suggest'):
                    # Explicit skip/suggest actions
                    status = action
                    skipped_by_action += 1

                elif action in ('Move', 'Copy'):
                    # Check if operation is possible
                    src_path = Path(r.path)
                    if not src_path.exists():
                        status = 'Error'
                        note = 'Source not found'
                        skipped_by_error += 1
                    elif dest and dest.exists():
                        status = 'Error'
                        note = 'Destination already exists'
                        skipped_by_error += 1
                    elif not what_if:
                        # Perform actual operation
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        if action == 'Move':
                            shutil.move(str(src_path), str(dest))
                            moved += 1
                        else:  # Copy
                            shutil.copy2(str(src_path), str(dest))
                            copied += 1
                    else:
                        # Dry run
                        if action == 'Move':
                            moved += 1
                        else:
                            copied += 1

                elif action == 'Delete':
                    # Handle delete action (rarely used)
                    if not what_if:
                        Path(r.path).unlink(missing_ok=True)
                    status = 'Deleted'

                else:
                    status = 'Unknown'
                    skipped_by_action += 1

                # Log the action
                w.writerow({
                    'Time': datetime.now().isoformat(),
                    'Action': action,
                    'Status': status,
                    'SourcePath': str(r.path),
                    'DestPath': str(dest) if dest else '',
                    'Label': r.label,
                    'Confidence': f"{r.confidence:.2f}",
                    'Why': r.why,
                    'Note': note
                })

            except Exception as e:
                w.writerow({
                    'Time': datetime.now().isoformat(),
                    'Action': action,
                    'Status': 'Error',
                    'SourcePath': str(r.path),
                    'DestPath': str(dest) if dest else '',
                    'Label': r.label,
                    'Confidence': f"{r.confidence:.2f}",
                    'Why': r.why,
                    'Note': str(e)
                })
                skipped_by_error += 1

    # Print summary
    print(f"\nLegacy executor summary:")
    print(f"  Moved: {moved}")
    print(f"  Copied: {copied}")
    print(f"  Skipped by action: {skipped_by_action}")
    print(f"  Skipped by error: {skipped_by_error}")
    print(f"  Residuals left in place: {skipped_residuals}")

    return log_path


def _index_tree_paths(node: Dict, prefix_parts: List[str] = None, idx: Dict[str, Path] = None) -> Dict[str, Path]:
    """
    Build {node_id: relative_path} mapping from TreePlan.json.

    Returns dict mapping node IDs to relative Path objects.
    """
    if idx is None:
        idx = {}
    if prefix_parts is None:
        prefix_parts = []

    # Guard against bad node types
    if not isinstance(node, dict):
        raise TypeError(f"_index_tree_paths expected dict node, got {type(node)}: {node!r}")

    name = node.get("name", "").strip()
    node_id = node.get("id")

    # Skip including the artificial root name in the path; children hang below dest_root
    if node_id == "n_root":
        rel_parts = prefix_parts  # Root stays at destination base
    else:
        rel_parts = [*prefix_parts, name] if name else prefix_parts

    if node_id:
        idx[node_id] = Path(*rel_parts) if rel_parts else Path(".")

    # Recurse into children
    for child in node.get("children", []):
        _index_tree_paths(child, rel_parts, idx)

    return idx

def _index_paths_from_nodes(plan: Dict[str, Any]) -> Dict[str, Path]:
    """
    Build {node_id: relative_path} mapping from a plan in this format:

    {
        "root": "C:\\...\\Sorted",
        "root_id": "n_root",
        "nodes": [
            {"id": "n_root", "name": "Sorted", "parent": None},
            {"id": "n_documents", "name": "Documents", "parent": "n_root"},
            ...
        ]
    }
    """
    nodes = plan.get("nodes") or []
    root_id = plan.get("root_id", "n_root")

    # Index basic relationships
    id_to_node = {n["id"]: n for n in nodes if "id" in n}
    parent_map = {n["id"]: n.get("parent") for n in nodes if "id" in n}
    name_map = {n["id"]: n.get("name", "") for n in nodes if "id" in n}

    node_paths: Dict[str, Path] = {}

    for node_id in id_to_node.keys():
        if node_id == root_id:
            node_paths[node_id] = Path(".")
            continue

        parts: List[str] = []
        cur_id = node_id

        # Walk up parents until root
        while cur_id and cur_id in name_map:
            if cur_id == root_id:
                break
            name = name_map.get(cur_id, "")
            if name:
                parts.append(name)
            cur_id = parent_map.get(cur_id)

        parts.reverse()
        node_paths[node_id] = Path(*parts) if parts else Path(".")

    return node_paths

def execute_from_plan(
    plan: Dict[str, Any],
    mapping_rows: List[Dict[str, str]],
    dest_root: Path,
    what_if: bool = False,
):
    """
    Execute moves using a global plan with accurate counting and robust normalization.
    """

    # If we somehow got a JSON string, parse it.
    if isinstance(plan, str):
        print("[sift][debug] plan is a string; parsing JSON...")
        try:
            plan = json.loads(plan)
        except Exception as e:
            raise ValueError(
                f"Plan must be a dict or JSON string; got str that could not be parsed: {e}"
            )

    if not isinstance(plan, dict):
        raise TypeError(f"Plan must be a dict; got {type(plan)}")

    # NEW: handle node-list style plan (your current build_plan format)
    if "nodes" in plan:
        print("[sift][debug] using node-list TreePlan format")
        node_paths = _index_paths_from_nodes(plan)
    else:
        # Fallback: hierarchical tree with embedded children
        root_node = plan.get("root", plan)
        print(f"[sift][debug] root_node type = {type(root_node)}")
        node_paths = _index_tree_paths(root_node)

    # Ensure root exists
    if "n_root" not in node_paths:
        node_paths["n_root"] = Path(".")

    # Add fallback for uncategorized
    if "n_uncategorized" not in node_paths:
        node_paths["n_uncategorized"] = Path("Uncategorized")

    # Prepare filesystem
    dest_root.mkdir(parents=True, exist_ok=True)

    # Prepare operation lists and counters
    operations: List[Tuple[Path, Path, str]] = []
    skipped_residuals = 0
    skipped_by_action = 0

    print("Reading mapping rows from memory...")
    row_count = 0

    for row in mapping_rows:
        row_count += 1

        # Skip empty rows
        source_path = (row.get("SourcePath") or "").strip()
        if not source_path:
            continue

        # Skip header row if it somehow got duplicated
        if source_path == "SourcePath":
            continue

        src = Path(source_path)

        # Normalize IsResidual
        is_residual = _normalize_is_residual(row.get("IsResidual", ""))

        # Normalize Action
        action = _normalize_action(row.get("Action", ""), is_residual)

        # Get node ID for destination
        node_id = (row.get("NodeID") or "").strip()
        if not node_id:
            # Try to determine from label as a fallback
            label = (row.get("Label") or "").lower()
            if "document" in label:
                node_id = "n_documents"
            elif "archive" in label:
                node_id = "n_archives"
            elif "media" in label:
                node_id = "n_media"
            elif "code" in label:
                node_id = "n_code"
            elif "data" in label:
                node_id = "n_data"
            else:
                node_id = "n_uncategorized"

        # Decision logic
        if is_residual:
            # Residuals ALWAYS stay in place
            skipped_residuals += 1
            if what_if:
                print(f"[residual] Will leave in place: {src}")
            continue

        if action in ("Skip", "Suggest"):
            # Explicit skip/suggest actions
            skipped_by_action += 1
            if what_if:
                print(f"[{action.lower()}] Will skip: {src}")
            continue

        if action in ("Move", "Copy"):
            # Prepare operation
            rel_path = node_paths.get(node_id, Path("uncategorized"))
            dst_dir = dest_root / rel_path
            dst = dst_dir / src.name
            operations.append((src, dst, action))

    print(f"Processed {row_count} mapping entries")
    print(f"  - {len(operations)} files to process")
    print(f"  - {skipped_residuals} residuals to leave in place")
    print(f"  - {skipped_by_action} files to skip by action\n")

    # Execute operations
    moved = 0
    copied = 0
    skipped_by_error = 0

    for src, dst, action in operations:
        # Check source exists
        if not src.exists():
            print(f"[skip] missing source: {src}")
            skipped_by_error += 1
            continue

        # Check destination doesn't exist
        if dst.exists():
            print(f"[skip] already exists: {dst}")
            skipped_by_error += 1
            continue

        # Print action
        if what_if:
            print(f"DRY: {action} {src}  ->  {dst}")
        else:
            print(f"{action.upper()}: {src}  ->  {dst}")

        # Perform action if not dry run
        if not what_if:
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                if action == "Copy":
                    shutil.copy2(str(src), str(dst))
                    copied += 1
                else:  # Move
                    shutil.move(str(src), str(dst))
                    moved += 1
            except Exception as e:
                print(f"  ERROR: {e}")
                skipped_by_error += 1
        else:
            # In dry run, count what would happen
            if action == "Copy":
                copied += 1
            else:
                moved += 1

    # Calculate total skipped (excluding residuals for clarity)
    total_skipped = skipped_by_action + skipped_by_error

    # Print final summary with clear, honest counts
    print(f"\n{'=' * 60}")
    print(f"Execution Summary:")
    print(f"  Moved:                    {moved}")
    print(f"  Copied:                   {copied}")
    print(f"  Skipped (action/suggest): {skipped_by_action}")
    print(f"  Skipped (errors):         {skipped_by_error}")
    print(f"  Skipped (total):          {total_skipped}")
    print(f"  Residuals left in place:  {skipped_residuals}")
    print(f"\nDestination: {dest_root}")
    print(f"Mode: {'DRY RUN - no actual changes made' if what_if else 'LIVE - files were processed'}")
    print(f"{'=' * 60}")
