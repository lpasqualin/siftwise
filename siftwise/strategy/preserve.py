# siftwise/strategy/preserve.py
from pathlib import Path
from typing import List

def compute_preserve_mode(root: Path, file_paths: List[Path], user_mode: str = "smart") -> str:
    """
    Decide preserve mode for this run.

    user_mode:
      - "on"  -> always preserve original subfolders
      - "off" -> never preserve original subfolders
      - "smart" -> infer based on folder signal
    """
    user_mode = (user_mode or "smart").lower().strip()

    # If user explicitly chose on/off, trust it.
    if user_mode in ("on", "off"):
        return user_mode

    # SMART mode:
    if not file_paths:
        return "off"

    # Ensure all paths are Path objects
    file_paths = [Path(p) for p in file_paths]

    rel_parts = []
    for p in file_paths:
        try:
            rel = p.relative_to(root)
            rel_parts.append(rel.parts[:-1])  # folders only
        except Exception:
            # If a file isn't under root, ignore it
            continue

    if not rel_parts:
        return "off"

    depths = [len(parts) for parts in rel_parts]
    avg_depth = sum(depths) / len(depths)

    junk = {
        "downloads", "desktop", "misc", "stuff", "old",
        "backup", "temp", "tmp", "new folder", "newfolder"
    }

    meaningful = 0
    total = 0

    for parts in rel_parts:
        for folder in parts:
            total += 1
            t = folder.lower()
            if t and t not in junk and not t.isdigit():
                meaningful += 1

    density = meaningful / max(total, 1)

    # Decision thresholds (MVP)
    if avg_depth >= 2.0 and density >= 0.55:
        return "on"
    return "off"
