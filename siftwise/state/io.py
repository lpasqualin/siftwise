from pathlib import Path
from typing import Dict, Any, List
import csv
import json


def ensure_sift_dir(dest_root: Path) -> Path:
    """
    Ensure <dest_root>/.sift exists and return that path.
    """
    sift_dir = dest_root / ".sift"
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
    core_fields = [
        "SourcePath",
        "NodeID",
        "Label",
        "Confidence",
        "Why",
        "IsResidual",
        "Action",
        "TargetPath",
        "ResidualReason",  # <- new, but always present
    ]

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

    core_fields = [
        "SourcePath",
        "NodeID",
        "Label",
        "Confidence",
        "Why",
        "IsResidual",
        "Action",
        "TargetPath",
        "ResidualReason",
    ]

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
