from pathlib import Path
from typing import Dict, Any, List
import csv
import json
from siftwise.schemas import MAPPING_CSV_FIELDS, RoutingDecision


def ensure_sift_dir(dest_root: Path, archive_existing: bool = False):
    sift_dir = dest_root / ".sift"

    if sift_dir.exists() and archive_existing:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = dest_root / f".sift_archive_{timestamp}"
        sift_dir.rename(archive_path)

    sift_dir.mkdir(parents=True, exist_ok=True)
    return sift_dir

def write_treeplan(sift_dir: Path, plan: Dict[str, Any], override_path: str | None = None) -> Path:
    """
    Write TreePlan.json to the .sift directory.

    `plan` must be a dict representing the full tree structure, e.g.:

    {
      "root": {
        "id": "n_root",
        "name": "",
        "children": [
          {"id": "n_documents", "name": "documents", "children": []},
          ...
        ]
      }
    }
    """
    path = Path(override_path) if override_path else sift_dir / "TreePlan.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)

    return path


def write_mapping(sift_dir: Path, rows: List[Dict[str, Any]]) -> Path:
    """
    Write Mapping.csv into the sift dir.

    We normalize columns so that:
      - All "core" columns are always present (in a stable order)
      - Any extra keys from rows are added to the header
      - Rows are backfilled with "" for missing columns
    """
    path = sift_dir / "Mapping.csv"

    # Core schema we care about (order matters for readability)
    core_fields = MAPPING_CSV_FIELDS

    if not rows:
        fieldnames = core_fields
    else:
        # Union of all keys across rows
        all_keys = set()
        for row in rows:
            all_keys.update(row.keys())

        # Start with core fields in fixed order, then append any unknowns
        fieldnames = core_fields + [
            k for k in all_keys
            if k not in core_fields
        ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            # Normalize row: only header keys, fill missing with ""
            normalized = {name: row.get(name, "") for name in fieldnames}
            writer.writerow(normalized)

    print(f"[sift] wrote Mapping.csv -> {path}")
    return path


def write_preview(sift_dir: Path, counts: Dict[str, Any]) -> Path:
    """
    Write a simple preview counts JSON (e.g., per-label counts, residual stats).
    """
    path = sift_dir / "PreviewCounts.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(counts, f, indent=2)
    print(f"[sift] wrote PreviewCounts.json -> {path}")
    return path


def write_residual_summary(sift_dir: Path, summary: Dict[str, Any]) -> Path:
    """
    Write a residual summary JSON used by refine-residuals.
    """
    path = sift_dir / "ResidualSummary.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[sift] wrote ResidualSummary.json -> {path}")
    return path


def get_sift_dir(dest_root: Path) -> Path:
    """
    Return <dest_root>/.sift, and complain loudly if it doesn't exist.
    """
    sift_dir = dest_root / ".sift"
    if not sift_dir.exists():
        raise FileNotFoundError(
            f"Siftwise state dir not found at {sift_dir}. "
            f"Run 'sift draft-structure --root ... --dest-root \"{dest_root}\"' first."
        )
    return sift_dir


import json
from pathlib import Path
from typing import Dict, Any

def load_treeplan(sift_dir: Path, override_path: str | None = None) -> Dict[str, Any]:
    path = Path(override_path) if override_path else sift_dir / "TreePlan.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_mapping(sift_dir: Path, override_path: str | None = None) -> List[Dict[str, str]]:
    """
    Load Mapping.csv (or a custom mapping path) from the sift dir.
    """
    path = Path(override_path) if override_path else (sift_dir / "Mapping.csv")

    rows: List[Dict[str, str]] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def read_treeplan(sift_dir: Path, override_path: str | None = None) -> Dict[str, Any]:
    """
    Backwards-compatible wrapper around load_treeplan.
    """
    return load_treeplan(sift_dir, override_path)


def read_mapping(sift_dir: Path, override_path: str | None = None) -> List[Dict[str, str]]:
    """
    Backwards-compatible wrapper around load_mapping.
    """
    return load_mapping(sift_dir, override_path)


def read_preview(sift_dir: Path, override_path: str | None = None) -> Dict[str, Any]:
    """
    Read PreviewCounts.json (or a custom preview path) from the sift dir.
    Safe if file is missing: returns {}.
    """
    path = Path(override_path) if override_path else (sift_dir / "PreviewCounts.json")
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def update_mapping(
    sift_dir: Path,
    rows: List[Dict[str, Any]],
    override_path: str | None = None,
) -> Path:
    """
    Update Mapping.csv in the sift dir by replacing it with the given rows.

    Uses the same normalization as write_mapping so we don't get DictWriter
    errors when new fields (e.g., ResidualReason) are added.
    """
    path = Path(override_path) if override_path else (sift_dir / "Mapping.csv")

    # Use centralized schema from schemas.py
    core_fields = MAPPING_CSV_FIELDS

    if not rows:
        fieldnames = core_fields
    else:
        all_keys = set()
        for row in rows:
            all_keys.update(row.keys())

        fieldnames = core_fields + [
            k for k in all_keys
            if k not in core_fields
        ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            normalized = {name: row.get(name, "") for name in fieldnames}
            writer.writerow(normalized)

    print(f"[sift] updated Mapping.csv -> {path}")
    return path


"""
Extensions to io.py for Entity Extraction V1

Add these functions to your existing siftwise/state/io.py file.
They handle Entities.csv export and reading.
"""

from pathlib import Path
from typing import Dict, Any, List
import csv


def write_entities_csv(sift_dir: Path, entities_data: Dict[str, Dict[str, Any]]) -> Path:
    """
    Write Entities.csv to the .sift directory.

    Args:
        sift_dir: Path to .sift directory
        entities_data: Dict mapping entity_name → {kind, count, example_paths}

    Returns:
        Path to written Entities.csv

    Format:
        Entity,Kind,Count,ExamplePaths
        Amazon,org,14,"/path/a,/path/b,/path/c"
        NYC,place,4,"/path/x,/path/y"
    """
    path = sift_dir / "Entities.csv"

    fieldnames = ["Entity", "Kind", "Count", "ExamplePaths"]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Sort by count descending, then alphabetically
        sorted_entities = sorted(
            entities_data.items(),
            key=lambda x: (-x[1]["count"], x[0])
        )

        for entity_name, data in sorted_entities:
            example_paths_str = ",".join(data.get("example_paths", [])[:5])  # Max 5 examples

            writer.writerow({
                "Entity": entity_name,
                "Kind": data["kind"],
                "Count": data["count"],
                "ExamplePaths": example_paths_str,
            })

    print(f"[sift] wrote Entities.csv -> {path} ({len(entities_data)} entities)")
    return path


def read_entities_csv(sift_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Read Entities.csv from the .sift directory.

    Returns:
        Dict mapping entity_name → {kind, count, example_paths}
    """
    path = sift_dir / "Entities.csv"

    if not path.exists():
        return {}

    entities_data: Dict[str, Dict[str, Any]] = {}

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entity = row["Entity"]
            entities_data[entity] = {
                "kind": row["Kind"],
                "count": int(row["Count"]),
                "example_paths": row["ExamplePaths"].split(",") if row["ExamplePaths"] else [],
            }

    return entities_data


def aggregate_entities_from_mapping(mapping_rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate entity counts from Mapping.csv rows.

    Extracts Entity and Year columns and counts occurrences.

    Args:
        mapping_rows: List of mapping row dicts

    Returns:
        Dict mapping entity_name → {kind, count, example_paths}
    """
    entity_counts: Dict[str, Dict[str, Any]] = {}

    for row in mapping_rows:
        # Extract entity from row
        entity = row.get("Entity", "").strip()

        if not entity:
            continue

        # Determine kind from context (org/person/place/year)
        # In v1, we'll use simple heuristics since kind isn't in Mapping.csv yet
        kind = "unknown"

        # Try to infer kind from entity characteristics
        if entity.isupper() and len(entity) <= 4:
            kind = "org"  # Likely acronym
        elif any(char.isdigit() for char in entity):
            kind = "project"  # Contains numbers, likely project code
        elif entity.istitle():
            kind = "person"  # TitleCase, likely person/place

        # Initialize or update count
        if entity not in entity_counts:
            entity_counts[entity] = {
                "kind": kind,
                "count": 0,
                "example_paths": [],
            }

        entity_counts[entity]["count"] += 1

        # Add example path (max 5)
        if len(entity_counts[entity]["example_paths"]) < 5:
            source_path = row.get("SourcePath", "")
            if source_path and source_path not in entity_counts[entity]["example_paths"]:
                entity_counts[entity]["example_paths"].append(source_path)

    return entity_counts
