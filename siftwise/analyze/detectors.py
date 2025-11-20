"""
Enhanced file type detection for Siftwise.

Provides stronger detection through:
- Extension-based classification with normalization
- Keyword pattern matching in filenames
- Directory context hints
- Size-based special handling

All detectors are explicit rule-based - no ML/embeddings.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List


@dataclass
class Signal:
    """Detection signal from a detector"""
    label: str
    confidence: float
    method: str
    why: str


class Detector:
    """Base class for file detectors"""
    def score(self, path: Path) -> Optional[Signal]:
        """Return a Signal if this detector matches the file, else None"""
        raise NotImplementedError


# Extension normalization - convert aliases to canonical forms
EXTENSION_ALIASES = {
    '.jpeg': '.jpg',
    '.jpe': '.jpg',
    '.tif': '.tiff',
    '.htm': '.html',
    '.mpg': '.mpeg',
}


# Extension to (label, confidence) mappings
EXTENSION_LABELS = {
    # Documents - text/office files
    '.pdf': ('documents', 0.95),
    '.doc': ('documents', 0.95),
    '.docx': ('documents', 0.95),
    '.txt': ('documents', 0.90),
    '.rtf': ('documents', 0.90),
    '.odt': ('documents', 0.90),
    '.pages': ('documents', 0.90),
    '.md': ('documents', 0.85),
    '.log': ('documents', 0.75),

    # Spreadsheets - structured data with formulas
    '.xls': ('spreadsheets', 0.95),
    '.xlsx': ('spreadsheets', 0.95),
    '.ods': ('spreadsheets', 0.90),
    '.numbers': ('spreadsheets', 0.90),
    '.xlsm': ('spreadsheets', 0.95),

    # Presentations
    '.ppt': ('presentations', 0.95),
    '.pptx': ('presentations', 0.95),
    '.key': ('presentations', 0.90),
    '.odp': ('presentations', 0.90),

    # Data - structured data files
    '.csv': ('data', 0.90),
    '.json': ('data', 0.95),
    '.xml': ('data', 0.90),
    '.parquet': ('data', 0.95),
    '.db': ('data', 0.90),
    '.sqlite': ('data', 0.90),
    '.sqlite3': ('data', 0.90),
    '.sql': ('data', 0.85),
    '.yaml': ('data', 0.85),
    '.yml': ('data', 0.85),
    '.toml': ('data', 0.85),
    '.ini': ('data', 0.80),
    '.conf': ('data', 0.75),

    # Archives - compressed/bundled files
    '.zip': ('archives', 0.95),
    '.rar': ('archives', 0.95),
    '.7z': ('archives', 0.95),
    '.tar': ('archives', 0.95),
    '.gz': ('archives', 0.95),
    '.bz2': ('archives', 0.95),
    '.xz': ('archives', 0.90),
    '.dmg': ('archives', 0.85),
    '.iso': ('archives', 0.90),

    # Images
    '.jpg': ('images', 0.95),
    '.png': ('images', 0.95),
    '.gif': ('images', 0.95),
    '.bmp': ('images', 0.90),
    '.svg': ('images', 0.90),
    '.webp': ('images', 0.90),
    '.ico': ('images', 0.85),
    '.tiff': ('images', 0.90),
    '.psd': ('images', 0.85),
    '.ai': ('images', 0.85),
    '.eps': ('images', 0.80),
    '.raw': ('images', 0.85),
    '.cr2': ('images', 0.85),
    '.nef': ('images', 0.85),

    # Videos
    '.mp4': ('videos', 0.95),
    '.mov': ('videos', 0.95),
    '.avi': ('videos', 0.95),
    '.mkv': ('videos', 0.95),
    '.wmv': ('videos', 0.90),
    '.flv': ('videos', 0.90),
    '.webm': ('videos', 0.90),
    '.m4v': ('videos', 0.90),
    '.mpeg': ('videos', 0.90),

    # Audio
    '.mp3': ('audio', 0.95),
    '.wav': ('audio', 0.95),
    '.flac': ('audio', 0.95),
    '.aac': ('audio', 0.90),
    '.ogg': ('audio', 0.90),
    '.m4a': ('audio', 0.90),
    '.wma': ('audio', 0.85),
    '.opus': ('audio', 0.85),
    '.aiff': ('audio', 0.85),

    # Code/Scripts
    '.py': ('code', 0.95),
    '.js': ('code', 0.95),
    '.html': ('code', 0.90),
    '.css': ('code', 0.90),
    '.java': ('code', 0.95),
    '.cpp': ('code', 0.95),
    '.c': ('code', 0.95),
    '.h': ('code', 0.90),
    '.hpp': ('code', 0.90),
    '.sh': ('code', 0.90),
    '.bat': ('code', 0.90),
    '.ps1': ('code', 0.90),
    '.rb': ('code', 0.95),
    '.php': ('code', 0.95),
    '.go': ('code', 0.95),
    '.rs': ('code', 0.95),
    '.swift': ('code', 0.95),
    '.kt': ('code', 0.95),
    '.ts': ('code', 0.95),
    '.jsx': ('code', 0.90),
    '.tsx': ('code', 0.90),
    '.vue': ('code', 0.90),
    '.r': ('code', 0.90),
    '.scala': ('code', 0.95),
    '.pl': ('code', 0.90),
    '.lua': ('code', 0.90),
}


class ExtensionDetector(Detector):
    """
    Primary detector - classifies files by extension.

    Handles:
    - Extension normalization (e.g., .jpeg → .jpg)
    - Double extensions (e.g., .tar.gz)
    - High confidence for known extensions
    """

    def score(self, path: Path) -> Optional[Signal]:
        if not path.is_file():
            return None

        # Get extension and normalize
        ext = path.suffix.lower()
        original_ext = ext
        ext = EXTENSION_ALIASES.get(ext, ext)

        # Handle double extensions like .tar.gz
        if ext == '.gz' and path.stem.endswith('.tar'):
            ext = '.tar.gz'

        # Look up in mappings
        if ext in EXTENSION_LABELS:
            label, confidence = EXTENSION_LABELS[ext]

            # Build explanation
            why = f"Extension '{original_ext}' matches {label}"
            if original_ext != ext:
                why = f"Extension '{original_ext}' (normalized to '{ext}') matches {label}"

            return Signal(
                label=label,
                confidence=confidence,
                method="extension",
                why=why
            )

        return None


# Keyword patterns for filename analysis: keyword -> (label, confidence, description)
KEYWORD_PATTERNS = {
    # Financial documents
    'invoice': ('documents', 0.80, 'financial document'),
    'receipt': ('documents', 0.80, 'financial document'),
    'statement': ('documents', 0.75, 'financial statement'),
    'tax': ('documents', 0.80, 'tax document'),
    'payroll': ('payroll', 0.85, 'payroll document'),

    # Legal documents
    'contract': ('documents', 0.85, 'legal document'),
    'agreement': ('documents', 0.85, 'legal document'),
    'lease': ('documents', 0.85, 'legal document'),

    # Personal documents
    'resume': ('documents', 0.90, 'personal document'),
    'cv': ('documents', 0.90, 'personal document'),

    # Business documents
    'report': ('documents', 0.75, 'business document'),
    'proposal': ('documents', 0.80, 'business document'),
    'presentation': ('presentations', 0.75, 'presentation'),
    'slide': ('presentations', 0.70, 'presentation'),

    # Media descriptors
    'screenshot': ('images', 0.85, 'screen capture'),
    'photo': ('images', 0.80, 'photograph'),
    'picture': ('images', 0.80, 'image'),
    'scan': ('documents', 0.75, 'scanned document'),

    # Archives and backups
    'backup': ('archives', 0.70, 'backup file'),
    'archive': ('archives', 0.75, 'archived content'),

    # Data
    'export': ('data', 0.70, 'data export'),
    'database': ('data', 0.80, 'database file'),
    'dump': ('data', 0.75, 'data dump'),
}


class KeywordDetector(Detector):
    """
    Secondary detector - looks for meaningful keywords in filenames.

    Helps classify files when extension alone is ambiguous.
    Confidence is lower than extension-based detection.
    """

    def score(self, path: Path) -> Optional[Signal]:
        if not path.is_file():
            return None

        filename_lower = path.stem.lower()

        # Check for keyword matches
        for keyword, (label, base_confidence, description) in KEYWORD_PATTERNS.items():
            if keyword in filename_lower:
                # Boost confidence slightly if keyword is at the start
                position = filename_lower.find(keyword)
                position_ratio = position / max(len(filename_lower), 1)

                confidence_boost = 0.05 if position_ratio < 0.3 else 0.0
                final_confidence = min(base_confidence + confidence_boost, 0.95)

                return Signal(
                    label=label,
                    confidence=final_confidence,
                    method="keyword",
                    why=f"Filename contains '{keyword}' ({description})"
                )

        return None


class DirectoryContextDetector(Detector):
    """
    Tertiary detector - uses parent directory names as hints.

    Provides contextual clues when files are already somewhat organized.
    Lower confidence than extension or keyword detection.
    """

    DIRECTORY_HINTS = {
        # Document folders
        'documents': ('documents', 0.60),
        'docs': ('documents', 0.60),
        'papers': ('documents', 0.55),

        # Media folders
        'photos': ('images', 0.65),
        'pictures': ('images', 0.65),
        'images': ('images', 0.65),
        'screenshots': ('images', 0.70),
        'videos': ('videos', 0.65),
        'movies': ('videos', 0.60),
        'music': ('audio', 0.65),
        'audio': ('audio', 0.65),
        'recordings': ('audio', 0.60),

        # Archives
        'archives': ('archives', 0.60),
        'backup': ('archives', 0.55),
        'backups': ('archives', 0.55),

        # Code
        'code': ('code', 0.60),
        'projects': ('code', 0.50),
        'src': ('code', 0.55),
        'source': ('code', 0.55),
        'scripts': ('code', 0.60),

        # Data
        'data': ('data', 0.60),
        'database': ('data', 0.60),
        'exports': ('data', 0.55),

        # Low confidence hints
        'downloads': ('misc', 0.35),  # Downloads are usually mixed
    }

    def score(self, path: Path) -> Optional[Signal]:
        if not path.is_file():
            return None

        # Check parent directory names (closest parent gets priority)
        for parent in path.parents:
            parent_name = parent.name.lower()

            if parent_name in self.DIRECTORY_HINTS:
                label, confidence = self.DIRECTORY_HINTS[parent_name]
                return Signal(
                    label=label,
                    confidence=confidence,
                    method="directory_context",
                    why=f"Located in '{parent.name}/' folder"
                )

        return None


class SizeDetector(Detector):
    """
    Special-case detector for unusual file sizes.

    Handles:
    - Empty files (0 bytes) - always flagged
    - Very large files (>1GB) - may need special handling
    """

    def score(self, path: Path) -> Optional[Signal]:
        if not path.is_file():
            return None

        try:
            size = path.stat().st_size
        except (OSError, PermissionError):
            return None

        # Empty files - high confidence
        if size == 0:
            return Signal(
                label="empty_files",
                confidence=1.0,
                method="size",
                why="Empty file (0 bytes)"
            )

        # Very large files (>1GB) - may need special handling
        if size > 1_000_000_000:
            gb_size = size / 1_000_000_000
            return Signal(
                label="large_files",
                confidence=0.85,
                method="size",
                why=f"Large file ({gb_size:.1f} GB)"
            )

        return None


class DatePatternDetector(Detector):
    """
    Detects files with date-based naming patterns.

    Helps identify files organized by date.
    Lower confidence - often combined with other signals.
    """

    def score(self, path: Path) -> Optional[Signal]:
        if not path.is_file():
            return None

        filename = path.stem.lower()

        # Common date patterns in filenames
        date_patterns = [
            r'\d{4}[-_]\d{2}[-_]\d{2}',  # YYYY-MM-DD
            r'\d{8}',  # YYYYMMDD
            r'\d{2}[-_]\d{2}[-_]\d{4}',  # MM-DD-YYYY
        ]

        import re
        for pattern in date_patterns:
            if re.search(pattern, filename):
                return Signal(
                    label="dated_files",
                    confidence=0.55,
                    method="date_pattern",
                    why="Filename contains date pattern"
                )

        return None


def get_default_detectors() -> List[Detector]:
    """
    Return the default set of detectors in priority order.

    Order matters:
    1. Extension - highest confidence, most reliable
    2. Keyword - medium confidence, context-dependent
    3. Directory - lower confidence, environmental hint
    4. Size - special cases only
    5. Date - lowest confidence, often ambiguous
    """
    return [
        ExtensionDetector(),
        KeywordDetector(),
        DirectoryContextDetector(),
        SizeDetector(),
        DatePatternDetector(),
    ]
