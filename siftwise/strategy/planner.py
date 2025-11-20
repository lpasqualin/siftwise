"""
Planner module for Siftwise strategy layer.

Main entry point for converting analyzer results into concrete execution plans.
Decides Action and TargetPath for each file based on confidence, rules, and entities.
"""

from pathlib import Path
from typing import Iterable, List, Dict, Any, Optional
from collections import defaultdict

# Import from sibling modules
from .entities import extract_entities_for_result
from .rules_engine import apply_rules, load_rules, get_builtin_rules

# Import analyzer confidence thresholds
# We'll duplicate them here to avoid circular imports
# These should match analyzer.py constants
HIGH = 0.85  # High confidence - definitely move
MED_HIGH = 0.75  # Medium-high - suggest review
MED = 0.65  # Medium - suggest review
MED_LOW = 0.50  # Medium-low - likely residual
LOW = 0.40  # Low - definitely residual
VERY_LOW = 0.30  # Very low - unknown/ambiguous


# Enhanced label to folder mapping
# Maps detector labels to destination folder paths
LABEL_FOLDER_MAP = {
    # Documents - text/office files
    "documents": "Documents",
    "spreadsheets": "Documents/Spreadsheets",
    "presentations": "Documents/Presentations",
    "pdfs": "Documents/PDFs",

    # Media - images, videos, audio
    "media": "Media",
    "images": "Media/Images",
    "videos": "Media/Videos",
    "audio": "Media/Audio",

    # Data - structured data files
    "data": "Data",
    "databases": "Data/Databases",

    # Archives - compressed files
    "archives": "Archives",

    # Code - scripts and source files
    "code": "Code",

    # Special categories
    "payroll": "Vendors/Payroll",
    "large_files": "LargeFiles",
    "empty_files": "EmptyFiles",
    "dated_files": "DatedFiles",

    # Fallback
    "uncategorized": "Uncategorized",
    "misc": "Misc",
    "": "Uncategorized",
}


def build_plan(
        results: Iterable,
        dest_root: Path,
        config: Optional[dict] = None,
) -> dict:
    """
    Main entry point for the strategy layer.

    Takes analyzer results and produces a complete execution plan including:
    - Action decisions (Move/Suggest/Skip) based on confidence + rules
    - TargetPath computation based on labels + structure preferences
    - Tree plan for visualization
    - Statistics for reporting

    Args:
        results: Iterable of Result objects from analyzer
        dest_root: Destination root directory for file organization
        config: Optional config dict with:
            - use_rules: bool (default False)
            - rules_path: Path to rules.yaml (optional)
            - preserve_structure: bool (default True)
            - scan_root: Path to original scan root (required for preserve_structure)
            - label_folder_map: dict to override default label mappings

    Returns:
        Dict with:
        - mapping_rows: List[dict] ready for Mapping.csv
        - tree_plan: Dict describing folder hierarchy for TreePlan.json
        - stats: Dict with counts and metrics
    """
    # Parse config
    config = config or {}
    use_rules = config.get('use_rules', False)
    rules_path = config.get('rules_path')
    preserve_structure = config.get('preserve_structure', True)
    label_folder_map = config.get('label_folder_map', LABEL_FOLDER_MAP)
    scan_root = config.get('scan_root')

    # Load rules if requested
    rules = None
    if use_rules:
        # Load user rules
        user_rules = load_rules(rules_path) if rules_path else {}
        # Merge with built-in rules
        builtin_rules = get_builtin_rules()

        # Combine rules (user rules take precedence)
        all_rules = builtin_rules.copy()
        if user_rules.get('rules'):
            all_rules['rules'] = builtin_rules.get('rules', []) + user_rules.get('rules', [])

        rules = all_rules if all_rules.get('rules') else None

    # Convert results to list if needed
    results_list = list(results)

    # Process each result
    mapping_rows = []
    tree_structure = defaultdict(list)  # folder -> [files]
    stats = {
        'total_files': len(results_list),
        'by_action': defaultdict(int),
        'by_label': defaultdict(int),
        'by_target_folder': defaultdict(int),
        'residual_count': 0,
        'rule_overrides': 0,
    }

    for result in results_list:
        # 1. Extract entities
        entities = extract_entities_for_result(result)

        # 2. Apply rules (may override label and/or action)
        current_label = result.label or ""
        current_action = getattr(result, 'action', None)

        final_label, action_override = apply_rules(
            result=result,
            current_label=current_label,
            current_action=current_action,
            entities=entities,
            rules=rules,
        )

        if action_override:
            stats['rule_overrides'] += 1

        # 3. Determine final action
        confidence = result.confidence

        if action_override:
            final_action = action_override
        else:
            # Use confidence-based policy
            final_action = _determine_action(confidence, final_label)

        # 3b. Derive residual flag from final_action
        # Anything that is not Move is considered residual
        is_residual = (final_action != "Move")

        # 4. Compute target path
        target_path = _compute_target_path(
            result=result,
            label=final_label,
            entities=entities,
            dest_root=dest_root,
            preserve_structure=preserve_structure,
            label_folder_map=label_folder_map,
            scan_root=scan_root,
        )

        # 5. Build mapping row
        row = {
            'SourcePath': str(result.path),
            'NodeID': _label_to_node_id(final_label),
            'Label': final_label or "",
            'Confidence': f"{confidence:.2f}",
            'Why': result.why,
            'IsResidual': "True" if is_residual else "False",
            'Action': final_action,
            'TargetPath': str(target_path),
        }

        # Add entities if present
        if entities:
            row['Entities'] = ', '.join(entities)

        # Add residual reason if analyzer set one
        residual_reason = getattr(result, 'residual_reason', '')
        if residual_reason:
            row['ResidualReason'] = residual_reason

        mapping_rows.append(row)

        # 6. Update stats
        stats['by_action'][final_action] += 1
        stats['by_label'][final_label or 'uncategorized'] += 1

        if is_residual:
            stats['residual_count'] += 1

        # Track by target folder (top-level only)
        top_level_folder = _get_top_level_folder(target_path, dest_root)
        stats['by_target_folder'][top_level_folder] += 1

        # Build tree structure
        tree_structure[top_level_folder].append(result.path.name)

    # 7. Build tree plan
    tree_plan = _build_tree_plan(tree_structure, dest_root, stats)

    # 8. Finalize stats
    stats['by_action'] = dict(stats['by_action'])
    stats['by_label'] = dict(stats['by_label'])
    stats['by_target_folder'] = dict(stats['by_target_folder'])
    stats['residual_percentage'] = (
        stats['residual_count'] / stats['total_files'] * 100
        if stats['total_files'] > 0 else 0
    )

    return {
        'mapping_rows': mapping_rows,
        'tree_plan': tree_plan,
        'stats': stats,
    }


def _determine_action(confidence: float, label: str) -> str:
    """
    Determine action based on confidence thresholds.

    Policy:
    - >= HIGH (0.85): Move
    - >= MED_HIGH (0.75): Move
    - >= MED (0.65): Suggest
    - < MED: Skip

    Special cases:
    - empty_files, large_files: Suggest even at high confidence
    """
    # Special handling for certain labels
    if label in ["empty_files", "large_files"] and confidence < HIGH:
        return "Suggest"

    # Standard confidence-based policy
    if confidence >= HIGH:  # 0.85
        return "Move"
    elif confidence >= MED_HIGH:  # 0.75
        return "Move"
    elif confidence >= MED:  # 0.65
        return "Suggest"
    else:
        return "Skip"


def _compute_target_path(
        result,
        label: str,
        entities: List[str],
        dest_root: Path,
        preserve_structure: bool,
        label_folder_map: Dict[str, str],
        scan_root: Optional[Path] = None,
) -> Path:
    """
    Compute the target path for a file with proper structure preservation.

    Logic:
    1. Map label to top-level folder using label_folder_map
       Example: "documents" → "Documents"

    2. If preserve_structure=True and scan_root is set:
       Preserve the relative path from scan_root inside the target bucket
       Example:
         Source: /Incoming/Car/Insurance/Policy.pdf
         Label: documents
         Scan root: /Incoming
         Result: /Sorted/Documents/Car/Insurance/Policy.pdf

    3. If preserve_structure=False or scan_root is None:
       Flatten files directly under the target bucket
       Example:
         Source: /Incoming/Car/Insurance/Policy.pdf
         Label: documents
         Result: /Sorted/Documents/Policy.pdf

    4. (Future) Entity-based organization could add another level

    Args:
        result: Analyzer Result object with .path
        label: Detected label (e.g., "documents", "images")
        entities: Extracted entities (future use)
        dest_root: Destination root directory
        preserve_structure: Whether to maintain relative paths
        label_folder_map: Mapping from labels to folder paths
        scan_root: Original scan root (required for preserve_structure)

    Returns:
        Full target path including filename
    """
    # 1. Get top-level folder from label
    top_folder = label_folder_map.get(label, label_folder_map.get("", "Uncategorized"))

    # Start with dest_root / top_folder
    target = dest_root / top_folder

    # 2. Preserve relative structure if requested
    if preserve_structure and scan_root is not None:
        try:
            # Get relative path from scan_root
            rel = result.path.relative_to(scan_root)
            rel_parent = rel.parent

            # If there are intermediate directories, preserve them
            # Example: Car/Insurance from Incoming/Car/Insurance/Policy.pdf
            if str(rel_parent) not in (".", ""):
                target = target / rel_parent
        except ValueError:
            # result.path is not under scan_root
            # This can happen if file is outside the original scan directory
            # Just flatten under top_folder
            pass

    # 3. Add filename at the very end
    target = target / result.path.name

    return target


def _label_to_node_id(label: str) -> str:
    """
    Convert a label to a node ID for tree structure.

    Consistent with draft_structure.py's _slug function.
    Creates URL/ID-safe identifiers.
    """
    if not label:
        return "n_uncategorized"

    # Create id-safe slug: lowercase, alnum only
    slug = "".join(
        ch.lower() if ch.isalnum() else "_"
        for ch in label
    ).strip("_") or "misc"

    return f"n_{slug}"


def _get_top_level_folder(target_path: Path, dest_root: Path) -> str:
    """
    Extract the top-level folder name from a target path.

    E.g., /dest/Documents/Spreadsheets/file.xlsx → "Documents"
    """
    try:
        relative = target_path.relative_to(dest_root)
        return relative.parts[0] if relative.parts else "Uncategorized"
    except ValueError:
        return "Uncategorized"


def _build_tree_plan(
        tree_structure: Dict[str, List[str]],
        dest_root: Path,
        stats: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a tree plan structure for TreePlan.json.

    Format:
    {
        "root": str(dest_root),
        "root_id": "n_root",
        "nodes": [
            {"id": "n_root", "name": "Sorted", "parent": None},
            {"id": "n_documents", "name": "Documents", "parent": "n_root"},
            ...
        ]
    }
    """
    nodes = [
        {"id": "n_root", "name": dest_root.name or "Sorted", "parent": None}
    ]

    # Add a node for each top-level folder
    for folder_name in sorted(tree_structure.keys()):
        node_id = _label_to_node_id(folder_name)

        # Avoid duplicate IDs
        if node_id not in [n["id"] for n in nodes]:
            nodes.append({
                "id": node_id,
                "name": folder_name,
                "parent": "n_root",
            })

    return {
        "root": str(dest_root),
        "root_id": "n_root",
        "nodes": nodes,
    }


def replan_residuals(
        mapping_rows: List[Dict[str, str]],
        updated_results: List,
        dest_root: Path,
        config: Optional[dict] = None,
) -> dict:
    """
    Re-plan only the residual files with updated analyzer results.

    Used by refine-residuals command to update the plan without
    disrupting non-residual files.

    Args:
        mapping_rows: Current mapping rows (all files)
        updated_results: New Result objects for residual files
        dest_root: Destination root
        config: Optional config (same as build_plan)

    Returns:
        Dict with updated mapping_rows and stats
    """
    # Build a map of source path to updated result
    updated_map = {str(r.path): r for r in updated_results}

    # Update only the rows that have updated results
    new_rows = []
    stats = {
        'total_updated': 0,
        'reclassified': 0,
        'still_residual': 0,
    }

    for row in mapping_rows:
        source_path = row.get('SourcePath', '')

        if source_path in updated_map:
            # This file was re-analyzed
            result = updated_map[source_path]

            # Use build_plan logic for this single result
            mini_plan = build_plan([result], dest_root, config)
            updated_row = mini_plan['mapping_rows'][0]

            new_rows.append(updated_row)
            stats['total_updated'] += 1

            # Track if still residual
            if updated_row.get('IsResidual', '').lower() == 'true':
                stats['still_residual'] += 1
            else:
                stats['reclassified'] += 1
        else:
            # Keep original row unchanged
            new_rows.append(row)

    return {
        'mapping_rows': new_rows,
        'stats': stats,
    }


def get_plan_summary(plan: dict) -> str:
    """
    Generate a human-readable summary of a plan.

    Useful for CLI output.
    """
    stats = plan.get('stats', {})

    lines = [
        f"Plan Summary:",
        f"  Total files: {stats.get('total_files', 0)}",
        f"  Actions:",
    ]

    for action, count in sorted(stats.get('by_action', {}).items()):
        lines.append(f"    {action}: {count}")

    lines.append(f"  Residual files: {stats.get('residual_count', 0)} "
                 f"({stats.get('residual_percentage', 0):.1f}%)")

    if stats.get('rule_overrides', 0) > 0:
        lines.append(f"  Rule overrides: {stats.get('rule_overrides', 0)}")

    return '\n'.join(lines)
