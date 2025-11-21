"""
Journaling system for Siftwise operations.

Logs all file operations (moves, copies, collisions, errors) to journal.log
for undo/audit trail.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


class Journal:
    """
    Append-only journal for file operations.

    Journal format (CSV):
    - Timestamp: ISO 8601 datetime
    - Operation: Move | Copy | Collision | Skip | Error
    - SourcePath: Original file path
    - DestPath: Destination path (or final path after collision)
    - Status: OK | Error | Renamed
    - Details: Additional info (collision index, error message, etc.)
    - PassId: Which pass/iteration this was
    """

    def __init__(self, journal_path: Path):
        self.path = journal_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Create with header if doesn't exist
        if not self.path.exists():
            self._write_header()

    def _write_header(self):
        with self.path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'Timestamp', 'Operation', 'SourcePath', 'DestPath',
                'Status', 'Details', 'PassId'
            ])
            writer.writeheader()

    def log(
            self,
            operation: str,
            source_path: Path,
            dest_path: Optional[Path] = None,
            status: str = 'OK',
            details: str = '',
            pass_id: Optional[int] = None,
    ):
        """Log a single operation."""
        with self.path.open('a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'Timestamp', 'Operation', 'SourcePath', 'DestPath',
                'Status', 'Details', 'PassId'
            ])

            writer.writerow({
                'Timestamp': datetime.now().isoformat(),
                'Operation': operation,
                'SourcePath': str(source_path),
                'DestPath': str(dest_path) if dest_path else '',
                'Status': status,
                'Details': details,
                'PassId': str(pass_id) if pass_id else '',
            })

    def log_move(self, source: Path, dest: Path, pass_id: Optional[int] = None):
        """Log a successful move operation."""
        self.log('Move', source, dest, 'OK', '', pass_id)

    def log_copy(self, source: Path, dest: Path, pass_id: Optional[int] = None):
        """Log a successful copy operation."""
        self.log('Copy', source, dest, 'OK', '', pass_id)

    def log_collision(
            self,
            source: Path,
            original_dest: Path,
            renamed_dest: Path,
            dup_index: int,
            pass_id: Optional[int] = None,
    ):
        """Log a collision rename."""
        details = f'Collision: {original_dest.name} → {renamed_dest.name} (dup_index={dup_index})'
        self.log('Collision', source, renamed_dest, 'Renamed', details, pass_id)

    def log_skip(self, source: Path, reason: str, pass_id: Optional[int] = None):
        """Log a skipped file."""
        self.log('Skip', source, None, 'Skipped', reason, pass_id)

    def log_error(
            self,
            source: Path,
            dest: Optional[Path],
            error_msg: str,
            pass_id: Optional[int] = None,
    ):
        """Log an error."""
        self.log('Error', source, dest, 'Error', error_msg, pass_id)


def get_journal(dest_root: Path) -> Journal:
    """Get or create journal for a destination root."""
    journal_path = dest_root / '.sift' / 'journal.log'
    return Journal(journal_path)