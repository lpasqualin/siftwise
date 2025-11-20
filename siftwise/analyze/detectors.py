"""
Enhanced file detectors for Siftwise analyzer.
These detectors examine files and return classification signals.
Now includes context-aware and pattern-learning detectors.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any
import re


@dataclass
class Signal:
    """Classification signal from a detector"""
    label: str           # Suggested category/folder
    confidence: float    # 0.0 to 1.0
    method: str         # Detection method used
    why: str            # Human-readable explanation


class Detector:
    """Base class for file detectors"""
    
    def __init__(self):
        self.confidence_boost = 0.0  # Can be set for iteration-based boosting
    
    def score(self, path: Path) -> Optional[Signal]:
        """Analyze a file and return a classification signal, or None"""
        raise NotImplementedError
    
    def adjust_confidence(self, base_confidence: float) -> float:
        """Apply any confidence adjustments (e.g., iteration boosts)"""
        return min(base_confidence + self.confidence_boost, 0.95)


class ExtensionDetector(Detector):
    """Enhanced extension-based classification with more categories"""
    
    def __init__(self):
        super().__init__()
        self.extension_map = {
            # Documents
            "documents": {
                "extensions": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", 
                              ".tex", ".md", ".rst"],
                "confidence": 0.85
            },
            # Spreadsheets (separate from general documents)
            "spreadsheets": {
                "extensions": [".xlsx", ".xls", ".csv", ".tsv", ".ods"],
                "confidence": 0.85
            },
            # Code/Development
            "code": {
                "extensions": [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", 
                              ".h", ".jsx", ".ts", ".tsx", ".go", ".rs", ".rb",
                              ".php", ".swift", ".kt", ".scala", ".r", ".m", ".sh",
                              ".bat", ".ps1", ".yaml", ".yml", ".toml"],
                "confidence": 0.90
            },
            # Data files
            "data": {
                "extensions": [".json", ".xml", ".db", ".sql", ".parquet", 
                              ".feather", ".hdf", ".h5", ".mat", ".npy", ".pkl"],
                "confidence": 0.85
            },
            # Images
            "images": {
                "extensions": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", 
                              ".ico", ".tiff", ".webp", ".raw", ".psd", ".ai"],
                "confidence": 0.90
            },
            # Videos
            "videos": {
                "extensions": [".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv", 
                              ".webm", ".m4v", ".mpg", ".mpeg"],
                "confidence": 0.90
            },
            # Audio
            "audio": {
                "extensions": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", 
                              ".m4a", ".opus", ".aiff"],
                "confidence": 0.90
            },
            # Archives
            "archives": {
                "extensions": [".zip", ".tar", ".gz", ".rar", ".7z", ".bz2", 
                              ".xz", ".tar.gz", ".tar.bz2", ".tar.xz"],
                "confidence": 0.95
            },
            # Executables
            "executables": {
                "extensions": [".exe", ".msi", ".app", ".deb", ".rpm", ".dmg", 
                              ".pkg", ".appimage", ".snap"],
                "confidence": 0.85
            },
            # Config files
            "configs": {
                "extensions": [".ini", ".cfg", ".conf", ".config", ".env", 
                              ".properties", ".plist"],
                "confidence": 0.75
            },
            # Logs
            "logs": {
                "extensions": [".log", ".out", ".err"],
                "confidence": 0.70
            }
        }
    
    def score(self, path: Path) -> Optional[Signal]:
        ext = path.suffix.lower()
        
        # Handle compound extensions like .tar.gz
        if path.name.lower().endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
            return Signal(
                label="archives",
                confidence=self.adjust_confidence(0.95),
                method="extension",
                why="matched archive extension"
            )
        
        if not ext:
            return None
        
        for label, config in self.extension_map.items():
            if ext in config["extensions"]:
                return Signal(
                    label=label,
                    confidence=self.adjust_confidence(config["confidence"]),
                    method="extension",
                    why=f"matched {ext} extension"
                )
        
        # Unknown extension - very low confidence
        return Signal(
            label="misc",
            confidence=self.adjust_confidence(0.25),
            method="extension",
            why=f"unknown extension {ext}"
        )


class KeywordDetector(Detector):
    """Enhanced keyword detection with more categories and patterns"""
    
    def __init__(self):
        super().__init__()
        self.keyword_patterns = {
            "finance": {
                "keywords": ["invoice", "receipt", "tax", "1099", "w2", "w-2", "paystub", 
                           "statement", "bill", "expense", "budget", "financial",
                           "payment", "transaction"],
                "confidence": 0.75
            },
            "contracts": {
                "keywords": ["contract", "agreement", "nda", "msa", "sow", "terms",
                           "legal", "amendment", "addendum"],
                "confidence": 0.80
            },
            "presentations": {
                "keywords": ["slides", "presentation", "deck", "pitch", "keynote",
                           "powerpoint", "ppt"],
                "confidence": 0.70
            },
            "reports": {
                "keywords": ["report", "analysis", "summary", "review", "assessment",
                           "evaluation", "study", "findings"],
                "confidence": 0.65
            },
            "resumes": {
                "keywords": ["resume", "cv", "curriculum", "vitae", "portfolio"],
                "confidence": 0.85
            },
            "personal": {
                "keywords": ["personal", "private", "confidential", "diary", "journal"],
                "confidence": 0.60
            },
            "projects": {
                "keywords": ["project", "proposal", "plan", "roadmap", "milestone",
                           "deliverable", "scope"],
                "confidence": 0.65
            },
            "marketing": {
                "keywords": ["marketing", "campaign", "advertising", "promotion",
                           "brochure", "flyer", "newsletter"],
                "confidence": 0.70
            },
            "medical": {
                "keywords": ["medical", "health", "prescription", "diagnosis", 
                           "treatment", "patient", "clinical"],
                "confidence": 0.75
            },
            "education": {
                "keywords": ["course", "syllabus", "lecture", "homework", "assignment",
                           "exam", "quiz", "study", "notes"],
                "confidence": 0.70
            }
        }
    
    def score(self, path: Path) -> Optional[Signal]:
        filename_lower = path.name.lower()
        stem_lower = path.stem.lower()
        
        # Check both filename and stem for better matching
        best_match = None
        best_confidence = 0
        
        for label, config in self.keyword_patterns.items():
            for keyword in config["keywords"]:
                # Check for word boundaries to avoid partial matches
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, filename_lower) or re.search(pattern, stem_lower):
                    confidence = config["confidence"]
                    
                    # Boost confidence for exact stem matches
                    if keyword == stem_lower:
                        confidence = min(confidence + 0.1, 0.95)
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = (label, keyword)
        
        if best_match:
            label, keyword = best_match
            return Signal(
                label=label,
                confidence=self.adjust_confidence(best_confidence),
                method="keyword",
                why=f"contains '{keyword}' in filename"
            )
        
        return None


class DatePatternDetector(Detector):
    """Enhanced date detection with better categorization"""
    
    def __init__(self):
        super().__init__()
        # More comprehensive date patterns
        self.date_patterns = [
            (r'\d{4}[-_]\d{2}[-_]\d{2}', "YYYY-MM-DD", 0.50),
            (r'\d{2}[-_]\d{2}[-_]\d{4}', "MM-DD-YYYY", 0.50),
            (r'\d{8}', "YYYYMMDD", 0.45),
            (r'\d{6}', "YYMMDD", 0.40),
            (r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[-_]?\d{4}', "month-year", 0.45),
            (r'\d{4}[-_](jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', "year-month", 0.45),
            (r'(q1|q2|q3|q4)[-_]?\d{4}', "quarter-year", 0.55),
            (r'\d{4}[-_](q1|q2|q3|q4)', "year-quarter", 0.55),
        ]
    
    def score(self, path: Path) -> Optional[Signal]:
        filename_lower = path.name.lower()
        
        for pattern, description, confidence in self.date_patterns:
            if re.search(pattern, filename_lower):
                # Check for financial keywords to boost confidence
                if any(term in filename_lower for term in ['report', 'statement', 'invoice']):
                    confidence = min(confidence + 0.15, 0.85)
                    label = "finance"
                else:
                    label = "dated_files"
                
                return Signal(
                    label=label,
                    confidence=self.adjust_confidence(confidence),
                    method="date_pattern",
                    why=f"contains date in {description}"
                )
        
        return None


class SizeBasedDetector(Detector):
    """Enhanced size-based detection with better thresholds"""
    
    def score(self, path: Path) -> Optional[Signal]:
        try:
            size_bytes = path.stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            
            if size_bytes == 0:  # Empty file
                return Signal(
                    label="empty_files",
                    confidence=self.adjust_confidence(0.95),
                    method="size",
                    why="empty file (0 bytes)"
                )
            elif size_bytes < 100:  # Less than 100 bytes
                return Signal(
                    label="empty_files",
                    confidence=self.adjust_confidence(0.30),
                    method="size",
                    why=f"nearly empty ({size_bytes} bytes)"
                )
            elif size_mb > 500:  # Greater than 500MB
                return Signal(
                    label="large_files",
                    confidence=self.adjust_confidence(0.80),
                    method="size",
                    why=f"very large file ({size_mb:.1f}MB)"
                )
            elif size_mb > 100:  # Greater than 100MB
                return Signal(
                    label="large_files",
                    confidence=self.adjust_confidence(0.60),
                    method="size",
                    why=f"large file ({size_mb:.1f}MB)"
                )
        except Exception:
            pass
        
        return None


class ContextualDetector(Detector):
    """
    Detector that uses successful classifications as context for pattern matching.
    This detector learns from what has already been classified successfully.
    """
    
    def __init__(self, successful_classifications: Dict[str, Dict[str, Any]]):
        super().__init__()
        self.patterns = successful_classifications
        self.build_fuzzy_patterns()
    
    def build_fuzzy_patterns(self):
        """Build fuzzy matching patterns from successful classifications"""
        self.fuzzy_patterns = {}
        
        for filename, info in self.patterns.items():
            # Extract meaningful parts of the filename
            parts = re.findall(r'[a-zA-Z]+|\d+', filename)
            
            for part in parts:
                if len(part) >= 3:  # Only meaningful parts
                    part_lower = part.lower()
                    if part_lower not in self.fuzzy_patterns:
                        self.fuzzy_patterns[part_lower] = {}
                    
                    label = info["label"]
                    if label not in self.fuzzy_patterns[part_lower]:
                        self.fuzzy_patterns[part_lower][label] = 0
                    self.fuzzy_patterns[part_lower][label] += 1
    
    def score(self, path: Path) -> Optional[Signal]:
        filename_lower = path.name.lower()
        
        # Direct match
        if filename_lower in self.patterns:
            info = self.patterns[filename_lower]
            return Signal(
                label=info["label"],
                confidence=self.adjust_confidence(min(info["confidence"] * 0.9, 0.85)),
                method="contextual",
                why=f"matches previously classified '{filename_lower}'"
            )
        
        # Stem match (without extension)
        stem_lower = path.stem.lower()
        if stem_lower in self.patterns:
            info = self.patterns[stem_lower]
            return Signal(
                label=info["label"],
                confidence=self.adjust_confidence(min(info["confidence"] * 0.8, 0.75)),
                method="contextual",
                why=f"similar to previously classified '{stem_lower}'"
            )
        
        # Fuzzy pattern matching
        parts = re.findall(r'[a-zA-Z]+|\d+', filename_lower)
        label_scores = {}
        
        for part in parts:
            if len(part) >= 3 and part in self.fuzzy_patterns:
                for label, count in self.fuzzy_patterns[part].items():
                    if label not in label_scores:
                        label_scores[label] = 0
                    label_scores[label] += count
        
        if label_scores:
            best_label = max(label_scores.items(), key=lambda x: x[1])
            if best_label[1] >= 2:  # At least 2 pattern matches
                return Signal(
                    label=best_label[0],
                    confidence=self.adjust_confidence(min(0.55 + best_label[1] * 0.05, 0.75)),
                    method="contextual",
                    why=f"pattern similarity to {best_label[1]} classified files"
                )
        
        return None


class SiblingPatternDetector(Detector):
    """
    Detector that uses naming patterns extracted from successfully classified files.
    This helps identify files that follow organizational naming conventions.
    """
    
    def __init__(self, naming_patterns: Dict[str, str]):
        super().__init__()
        self.patterns = naming_patterns
    
    def score(self, path: Path) -> Optional[Signal]:
        filename_lower = path.name.lower()
        
        best_match = None
        best_pattern_length = 0
        
        for pattern, label in self.patterns.items():
            if pattern in filename_lower:
                # Longer patterns are more specific and get higher confidence
                if len(pattern) > best_pattern_length:
                    best_pattern_length = len(pattern)
                    best_match = (pattern, label)
        
        if best_match:
            pattern, label = best_match
            # Confidence based on pattern length and specificity
            base_confidence = min(0.50 + len(pattern) * 0.02, 0.80)
            
            return Signal(
                label=label,
                confidence=self.adjust_confidence(base_confidence),
                method="sibling_pattern",
                why=f"matches naming pattern '{pattern}'"
            )
        
        return None


def get_default_detectors() -> List[Detector]:
    """
    Return the default stack of detectors used by the analyzer.
    Order matters - earlier detectors take precedence when confidence is equal.
    """
    return [
        ExtensionDetector(),
        KeywordDetector(),
        DatePatternDetector(),
        SizeBasedDetector(),
    ]
