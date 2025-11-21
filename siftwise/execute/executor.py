import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable, Tuple, List, Dict, Any
from siftwise.execute.journaling import get_journal
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


def _resolve_collision(dst: Path) -> Tuple[Path, int]:
    """
    If dst exists, produce dst with __dupN appended before suffix.
    Returns (new_path, dup_index). dup_index is 0 if no collision.
    """
    if not dst.exists():
        return dst, 0

    parent = dst.parent
    stem = dst.stem
    suffix = dst.suffix

    i = 1
    while True:
        candidate = parent / f"{stem}__dup{i}{suffix}"
        if not candidate.exists():
            return candidate, i
        i += 1


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

    with log_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "Time", "Action", "Status", "SourcePath", "DestPath",
                "Label", "Confidence", "Why", "Note"
            ],
        )
        w.writeheader()

        for r in results:
            status, note = "OK", ""

            # Normalize action
            is_residual = getattr(r, "is_residual", False)
            action = _normalize_action(getattr(r, "action", ""), is_residual)

            # Determine destination
            dest = None
            if action in ("Move", "Copy"):
                dest = Path(r.target_path) / Path(r.path).name

            try:
                if is_residual:
                    # Residuals always stay in place
                    status = "Residual"
                    note = "residual/unsorted - left in place"
                    skipped_residuals += 1

                elif action in ("Skip", "Suggest"):
                    # Explicit skip/suggest actions
                    status = action
                    skipped_by_action += 1

                elif action in ("Move", "Copy"):
                    # Check if operation is possible
                    src_path = Path(r.path)
                    if not src_path.exists():
                        status = "Error"
                        note = "Source not found"
                        skipped_by_error += 1
                    else:
                        # Collision-safe destination
                        final_dest, dup_index = _resolve_collision(dest)

                        if dup_index > 0:
                            note = f"collision rename -> {final_dest.name}"

                        if not what_if:
                            final_dest.parent.mkdir(parents=True, exist_ok=True)
                            if action == "Move":
                                shutil.move(str(src_path), str(final_dest))
                                moved += 1
                            else:  # Copy
                                shutil.copy2(str(src_path), str(final_dest))
                                copied += 1
                        else:
                            # Dry run
                            if action == "Move":
                                moved += 1
                            else:
                                copied += 1

                        dest = final_dest  # for logging

                elif action == "Delete":
                    # Handle delete action (rarely used)
                    if not what_if:
                        Path(r.path).unlink(missing_ok=True)
                    status = "Deleted"

                else:
                    status = "Unknown"
                    skipped_by_action += 1

                # Log the action
                w.writerow(
                    {
                        "Time": datetime.now().isoformat(),
                        "Action": action,
                        "Status": status,
                        "SourcePath": str(r.path),
                        "DestPath": str(dest) if dest else "",
                        "Label": getattr(r, "label", ""),
                        "Confidence": f"{getattr(r, 'confidence', 0.0):.2f}",
                        "Why": getattr(r, "why", ""),
                        "Note": note,
                    }
                )

            except Exception as e:
                w.writerow(
                    {
                        "Time": datetime.now().isoformat(),
                        "Action": action,
                        "Status": "Error",
                        "SourcePath": str(r.path),
                        "DestPath": str(dest) if dest else "",
                        "Label": getattr(r, "label", ""),
                        "Confidence": f"{getattr(r, 'confidence', 0.0):.2f}",
                        "Why": getattr(r, "why", ""),
                        "Note": str(e),
                    }
                )
                skipped_by_error += 1

    # Print summary
    print("\nLegacy executor summary:")
    print(f"  Moved: {moved}")
    print(f"  Copied: {copied}")
    print(f"  Skipped by action/suggest: {skipped_by_action}")
    print(f"  Skipped by error: {skipped_by_error}")
    print(f"  Residuals left in place: {skipped_residuals}")

    return log_path


def _index_tree_paths(
    node: Dict, prefix_parts: List[str] = None, idx: Dict[str, Path] = None
) -> Dict[str, Path]:
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
        raise TypeError(
            f"_index_tree_paths expected dict node, got {type(node)}: {node!r}"
        )

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
    Execute moves using mapping with accurate counting and robust normalization.

    Run Protocol v1: Action-driven execution
    - Only moves files with Action == "Move" (or Copy)
    - Uses TargetPath from mapping (never invents paths)
    - Residuals (IsResidual=True) always stay in place
    - Skip/Suggest actions are not executed

    Args:
        plan: TreePlan dict (used for validation/context, but TargetPath is primary)
        mapping_rows: List of mapping row dicts from Mapping.csv
        dest_root: Destination root directory
        what_if: If True, dry-run mode (no actual file operations)
    """
    # NEW: Initialize journal
    journal = get_journal(dest_root)

    # Extract pass_id early for journaling
    pass_ids = [
        row.get("PassId")
        for row in mapping_rows
        if row.get("PassId") and str(row.get("PassId")).isdigit()
    ]
    pass_id = max((int(p) for p in pass_ids), default=None)
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

    start_time = datetime.now()

    # Prepare operation lists and counters
    operations: List[Tuple[Path, Path, str]] = []

    skipped_residuals = 0
    skipped_by_action = 0
    suggested = 0
    collision_renames = 0

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

        # Decision logic (Run Protocol v1: trust the mapping)
        if is_residual:
            skipped_residuals += 1
            if what_if:
                print(f"[residual] Will leave in place: {src}")
            else:
                journal.log_skip(src, "Residual - left in place", pass_id)  # NEW
            continue

        if action in ("Skip", "Suggest"):
            if action == "Suggest":
                suggested += 1
            else:
                skipped_by_action += 1

            if not what_if:
                journal.log_skip(src, f"Action={action}", pass_id)  # NEW

            if what_if:
                print(f"[{action.lower()}] Will skip: {src}")
            continue
        if is_residual:
            # Residuals ALWAYS stay in place
            skipped_residuals += 1
            if what_if:
                print(f"[residual] Will leave in place: {src}")
            continue

        if action in ("Skip", "Suggest"):
            # Explicit skip/suggest actions
            if action == "Suggest":
                suggested += 1
            else:
                skipped_by_action += 1

            if what_if:
                print(f"[{action.lower()}] Will skip: {src}")
            continue

        if action in ("Move", "Copy"):
            # Run Protocol v1: Use TargetPath from mapping, never invent it
            target_path_str = (row.get("TargetPath") or "").strip()

            if not target_path_str:
                # No TargetPath provided - cannot execute
                print(f"[skip] No TargetPath in mapping for: {src}")
                skipped_by_action += 1
                continue

            dst = Path(target_path_str)

            # Validate TargetPath is absolute or make it relative to dest_root
            if not dst.is_absolute():
                dst = dest_root / dst

            operations.append((src, dst, action))

    print(f"Processed {row_count} mapping entries")
    print(f"  - {len(operations)} files to process")
    print(f"  - {skipped_residuals} residuals to leave in place")
    print(f"  - {skipped_by_action} files to skip by action")
    print(f"  - {suggested} files suggested (not executed)\n")

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

        # Collision handling: never overwrite, never silently skip
        final_dst, dup_index = _resolve_collision(dst)
        if dup_index > 0:
            collision_renames += 1
            print(f"[collision] target exists, renaming -> {final_dst.name}")
        if not what_if:
            journal.log_collision(src, dst, final_dst, dup_index, pass_id)
        # Print action
        if what_if:
            print(f"DRY: {action} {src}  ->  {final_dst}")
        else:
            print(f"{action.upper()}: {src}  ->  {final_dst}")

        if not what_if:
            final_dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                if action == "Copy":
                    shutil.copy2(str(src), str(final_dst))
                    copied += 1
                    journal.log_copy(src, final_dst, pass_id)
                else:  # Move
                    shutil.move(str(src), str(final_dst))
                    moved += 1
                    journal.log_move(src, final_dst, pass_id)

            except Exception as e:
                print(f"  ERROR: {e}")
                skipped_by_error += 1
                journal.log_error(src, final_dst, str(e), pass_id)
        else:
            # In dry run, count what would happen
            if action == "Copy":
                copied += 1
            else:
                moved += 1

    # Calculate totals
    skipped_action_total = skipped_by_action + suggested
    total_skipped = skipped_action_total + skipped_by_error
    total_files = moved + copied + total_skipped + skipped_residuals

    # Extract pass id (if present)
    pass_ids = [
        row.get("PassId")
        for row in mapping_rows
        if row.get("PassId") and str(row.get("PassId")).isdigit()
    ]
    pass_id = max((int(p) for p in pass_ids), default=None)

    elapsed_s = (datetime.now() - start_time).total_seconds()

    # ✅ Canonical summary (single source of truth)
    print(f"\n{'=' * 60}")
    print("Execution Summary:")
    print(f"  Moved:                    {moved}")
    print(f"  Copied:                   {copied}")
    print(f"  Skipped (action/suggest): {skipped_action_total}")
    print(f"  Skipped (errors):         {skipped_by_error}")
    print(f"  Skipped (total):          {total_skipped}")
    print(f"  Residuals left in place:  {skipped_residuals}")
    print(f"  Total files:              {total_files}")
    print(f"  Collision renames:        {collision_renames}")

    if pass_id is not None:
        print(f"  PassId:                   {pass_id}")

    print(f"  Elapsed (sec):            {elapsed_s:.1f}")
    print(f"\nDestination: {dest_root}")
    print(f"Mode: {'DRY' if what_if else 'LIVE'}")
    print(f"{'=' * 60}")
