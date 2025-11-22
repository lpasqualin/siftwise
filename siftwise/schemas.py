"""
Siftwise Data Schemas - Single Source of Truth

All data structures used across layers are defined here.
This prevents duplication and ensures consistency.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List


# ============================================================================
# ANALYZER OUTPUT (Analysis Layer → Strategy Layer)
# ============================================================================

@dataclass
class FileResult:
    """
    Output from the analysis layer.

    Contains ONLY classification information - no decisions about actions
    or target paths. Those are the strategy layer's job.

    Used by: analyzer.py → planner.py
    """
    path: Path  # Source file path
    label: str  # Classification label (e.g., "documents", "images")
    confidence: float  # Confidence score (0.0 to 1.0)
    method: str  # Detection method (e.g., "extension", "keyword")
    why: str  # Explanation of classification
    is_residual: bool  # True if file couldn't be confidently classified
    residual_reason: str  # Why it was marked as residual (empty if not residual)


# ============================================================================
# STRATEGY OUTPUT (Strategy Layer → State/Execution)
# ============================================================================

@dataclass
class RoutingDecision:
    """
    Routing decision from strategy layer.

    Contains domain/kind/entity routing plus action decisions.
    This is what gets written to Mapping.csv.

    Used by: planner.py → io.py → executor.py
    """
    # Source
    source_path: str

    # Routing dimensions (Spec A)
    domain: Optional[str]  # e.g., "Finance", "Personal"
    kind: Optional[str]  # e.g., "Invoices", "Photos"
    entity: Optional[str]  # e.g., "AcmeCorp", "VacationTrip"
    year: Optional[int]  # e.g., 2024

    # Target & action
    target_path: str  # Full target path (may include preserved structure)
    confidence: float  # Confidence after any boosting
    action: str  # Move | Suggest | Skip

    # Metadata
    is_residual: bool  # True if still residual after planning
    why: str  # Explanation (includes routing + rules)

    # Pass tracking
    pass_id: int  # Current pass number (1, 2, 3...)

    # History (for refinement passes)
    previous_pass_id: str = ""
    previous_action: str = ""
    previous_confidence: str = ""
    previous_target_path: str = ""

    def to_csv_row(self) -> dict:
        """Convert to CSV row dict for Mapping.csv."""
        return {
            "SourcePath": self.source_path,
            "Domain": self.domain or "",
            "Kind": self.kind or "",
            "Entity": self.entity or "",
            "Year": str(self.year) if self.year else "",
            "TargetPath": self.target_path,
            "Confidence": f"{self.confidence:.4f}",
            "Action": self.action,
            "IsResidual": str(self.is_residual),
            "Why": self.why,
            "PassId": str(self.pass_id),
            "PreviousPassId": self.previous_pass_id,
            "PreviousAction": self.previous_action,
            "PreviousConfidence": self.previous_confidence,
            "PreviousTargetPath": self.previous_target_path,
        }

    @classmethod
    def from_csv_row(cls, row: dict) -> 'RoutingDecision':
        """Create from CSV row dict."""
        return cls(
            source_path=row.get("SourcePath", ""),
            domain=row.get("Domain") or None,
            kind=row.get("Kind") or None,
            entity=row.get("Entity") or None,
            year=int(row["Year"]) if row.get("Year") and row["Year"].isdigit() else None,
            target_path=row.get("TargetPath", ""),
            confidence=float(row.get("Confidence", 0.0)),
            action=row.get("Action", "Skip"),
            is_residual=row.get("IsResidual", "False").lower() in ("true", "1", "yes"),
            why=row.get("Why", ""),
            pass_id=int(row["PassId"]) if row.get("PassId", "").isdigit() else 1,
            previous_pass_id=row.get("PreviousPassId", ""),
            previous_action=row.get("PreviousAction", ""),
            previous_confidence=row.get("PreviousConfidence", ""),
            previous_target_path=row.get("PreviousTargetPath", ""),
        )


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class PlanConfig:
    """
    Configuration for planning operations.

    Used by: draft_structure, refine_residuals → planner.py
    """
    use_rules: bool = False
    scan_root: Optional[Path] = None
    preserve_structure_mode: str = "SMART"  # OFF | ON | SMART
    pass_id: int = 1
    rules_path: Optional[Path] = None


# ============================================================================
# CONSTANTS
# ============================================================================

# CSV field order for Mapping.csv (ensures consistent column ordering)
MAPPING_CSV_FIELDS = [
    "SourcePath",
    "Domain",
    "Kind",
    "Entity",
    "Year",
    "TargetPath",
    "Confidence",
    "Action",
    "IsResidual",
    "Why",
    "PassId",
    "PreviousPassId",
    "PreviousAction",
    "PreviousConfidence",
    "PreviousTargetPath",
]

# Valid actions
VALID_ACTIONS = {"Move", "Suggest", "Skip", "Copy"}

# Action priorities (for conflict resolution)
ACTION_PRIORITY = {
    "Move": 3,
    "Suggest": 2,
    "Skip": 1,
    "Copy": 3,
}