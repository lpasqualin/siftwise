import csv, shutil
from pathlib import Path

def undo(log_csv: Path):
    # Replays the log in reverse: Move/Copy -> delete dest (if exists) and try to move back
    rows = list(csv.DictReader(log_csv.open(encoding='utf-8')))
    for r in reversed(rows):
        action = r.get('Action','')
        src = Path(r.get('SourcePath',''))
        dest = Path(r.get('DestPath',''))
        if action in ('Move','Copy'):
            try:
                if dest.exists():
                    # Try to move back to original path if possible; else just delete copy
                    if action == 'Move':
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(dest), str(src))
                    else:
                        dest.unlink(missing_ok=True)
            except Exception:
                pass
