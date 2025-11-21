from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Tuple
from datetime import datetime
import shutil

from .journaling import read_events, get_journal_path
from .executor import _resolve_collision  # we added this in core closeout


def undo_last_run(dest_root: Path, sift_dir: Path, what_if: bool = False) -> Dict[str, Any]:
    """
    Undo ONLY the most recent run in journal.jsonl.
    Strategy:
      1) read all events
      2) find last run_id
      3) reverse events for that run in reverse order
    """
    events = read_events(sift_dir)
    if not events:
        print("[undo] No journal found. Nothing to undo.")
        return {"undone": 0, "skipped": 0, "run_id": None}

    last_run_id = events[-1].get("run_id")
    last_run_events = [e for e in events if e.get("run_id") == last_run_id]

    undone = 0
    skipped = 0

    print(f"[undo] Undoing run_id={last_run_id} ({len(last_run_events)} events)")

    for e in reversed(last_run_events):
        ev_type = e.get("event")
        src = Path(e["src"])
        final_dst = Path(e["final_dst"])

        # For a Move: reverse by moving final_dst back to src
        if ev_type == "Move":
            if not final_dst.exists():
                print(f"[undo-skip] missing moved file: {final_dst}")
                skipped += 1
                continue

            back_dst, dup_index = _resolve_collision(src)
            if dup_index > 0:
                print(f"[undo-collision] source exists, restoring as {back_dst.name}")

            if what_if:
                print(f"DRY: UNDO Move {final_dst} -> {back_dst}")
            else:
                back_dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(final_dst), str(back_dst))
            undone += 1

        # For a Copy: undo by deleting the copy (safe delete)
        elif ev_type == "Copy":
            if not final_dst.exists():
                print(f"[undo-skip] missing copied file: {final_dst}")
                skipped += 1
                continue

            if what_if:
                print(f"DRY: UNDO Copy (delete) {final_dst}")
            else:
                final_dst.unlink()
            undone += 1

        # CollisionRename is informational; no direct undo op needed
        else:
            continue

    summary = {
        "run_id": last_run_id,
        "events": len(last_run_events),
        "undone": undone,
        "skipped": skipped,
        "mode": "DRY" if what_if else "LIVE",
        "ts": datetime.now().isoformat(timespec="seconds"),
    }

    # Optional small receipt
    try:
        from siftwise.state.io import write_residual_summary  # reuse a writer if you want
        # but don't force it if you don't want the artifact
        write_residual_summary(sift_dir, summary)  # writes UndoSummary.json (name is fine for MVP)
    except Exception:
        pass

    print(f"[undo] complete: undone={undone}, skipped={skipped}")
    return summary
