from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

class Journal:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, op, src, dest=None, pass_id=None, reason=""):
        ts = datetime.utcnow().isoformat()
        dest_str = str(dest) if dest else ""
        line = f"{ts} | {op} | {src} | {dest_str} | {pass_id} | {reason}\n"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line)

@dataclass
class JournalEvent:
    ts: str
    run_id: str
    event: str                # "Move" | "Copy" | "CollisionRename"
    src: str
    dst: str
    final_dst: str
    action: str               # same as event for now
    pass_id: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None


def get_journal_path(sift_dir: Path) -> Path:
    return sift_dir / "journal.jsonl"


def new_run_id() -> str:
    # stable-ish id for a run
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def append_event(sift_dir: Path, ev: JournalEvent) -> None:
    path = get_journal_path(sift_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(ev), ensure_ascii=False) + "\n")


def read_events(sift_dir: Path) -> list[Dict[str, Any]]:
    path = get_journal_path(sift_dir)
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out
