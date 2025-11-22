# siftwise/commands/promote_suggested.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pandas as pd


@dataclass
class PromoteResult:
    before_suggest: int
    after_suggest: int
    promoted: int
    mapping_path: Path


def promote_suggested(dest_root: str | Path) -> PromoteResult:
    dest_root = Path(dest_root)
    sift_dir = dest_root / ".sift"
    mapping_path = sift_dir / "Mapping.csv"

    if not mapping_path.exists():
        raise FileNotFoundError(f"Mapping.csv not found at: {mapping_path}")

    df = pd.read_csv(mapping_path)

    if "Action" not in df.columns:
        raise ValueError("Mapping.csv missing required column: Action")

    before = int((df["Action"] == "Suggest").sum())

    if before > 0:
        df.loc[df["Action"] == "Suggest", "Action"] = "Move"
        df.to_csv(mapping_path, index=False)

    after = int((df["Action"] == "Suggest").sum())
    promoted = before - after

    return PromoteResult(
        before_suggest=before,
        after_suggest=after,
        promoted=promoted,
        mapping_path=mapping_path,
    )
