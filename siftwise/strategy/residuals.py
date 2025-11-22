"""
Residual Loop v1: Confidence Boosting and Promotion Logic

This module provides deterministic confidence boosting for residual files
based on history from previous passes, plus promotion logic to upgrade
residuals to SUGGEST or MOVE actions.

Key features:
- History-based confidence boosts (prefix match, entity match, action continuity)
- Deterministic promotion thresholds (HIGH >= 0.85 → MOVE, MED_HIGH >= 0.75 → SUGGEST)
- No randomness, no time-dependent behavior
- Preserves plan determinism across passes
"""

from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass


# Threshold constants (locked per brief)
HIGH_THRESHOLD = 0.85      # High confidence → MOVE, IsResidual=False
MED_HIGH_THRESHOLD = 0.75  # Medium-high → SUGGEST, IsResidual=True
CONFIDENCE_CAP = 0.99      # Maximum allowed confidence after boosting

def safe_float(v, default=0.0) -> float:
    """
    CSV values may be '', None, or non-numeric. Treat those as default.
    """
    try:
        if v is None:
            return default
        s = str(v).strip()
        if s == "":
            return default
        return float(s)
    except Exception:
        return default

@dataclass
class BoostResult:
    """Result of confidence boosting operation."""
    original_confidence: float
    boosted_confidence: float
    boost_applied: float
    boost_reasons: List[str]
    action: str  # MOVE | SUGGEST | Skip
    is_residual: bool


def extract_prefix(target_path: str) -> str:
    """
    Extract the top-level folder prefix from a target path.
    
    Examples:
        '/dest/documents/2024/file.txt' → 'documents'
        '/dest/photos' → 'photos'
        '/dest' → ''
    
    Args:
        target_path: Full target path string
        
    Returns:
        Top-level folder name, or empty string if none
    """
    if not target_path:
        return ""
    
    path = Path(target_path)
    parts = path.parts
    
    # Find the first part that's not root-like
    for i, part in enumerate(parts):
        if part not in ('/', '.', '..') and not part.endswith(':'):
            # Check if this might be dest_root by looking ahead
            # If there's another part after this, this is likely dest_root
            if i + 1 < len(parts):
                return parts[i + 1]
            else:
                return part
    
    return ""


def normalize_entity(entity: str) -> str:
    """
    Normalize an entity string for comparison.
    
    Handles case, whitespace, and common separators.
    
    Args:
        entity: Raw entity string
        
    Returns:
        Normalized entity for matching
    """
    if not entity:
        return ""
    
    # Convert to lowercase and strip
    normalized = entity.lower().strip()
    
    # Replace common separators with spaces
    for sep in ['-', '_', '.']:
        normalized = normalized.replace(sep, ' ')
    
    # Collapse multiple spaces
    normalized = ' '.join(normalized.split())
    
    return normalized


def extract_entities_from_path(path: Path) -> List[str]:
    """
    Extract potential entities from a file path using Entity Extraction V1.

    This is used for entity matching in confidence boosting.
    Falls back to simple extraction if entities module not available.

    Args:
        path: Path object to extract from

    Returns:
        List of normalized entity strings
    """
    try:
        from siftwise.analyze.entities import extract_entities_for_result, normalize_token

        # Create a minimal result-like object for extraction
        class _TempResult:
            def __init__(self, p):
                self.path = p
                self.label = ""
                self.confidence = 0.0

        # Extract entities using real entity extraction
        entity_result = extract_entities_for_result(_TempResult(path))

        # Return entities found
        entities = []
        if entity_result.entity:
            entities.append(normalize_token(entity_result.entity))

        # Also return year if found
        if entity_result.year:
            entities.append(str(entity_result.year))

        return entities

    except ImportError:
        # Fallback: simple extraction from filename (original placeholder logic)
        filename = path.stem.lower()
        import re

        # Extract potential year patterns
        years = re.findall(r'\b(19\d{2}|20\d{2})\b', filename)

        # Extract capitalized words (potential entities)
        entities = re.findall(r'\b[A-Z][a-z]+\b', path.stem)

        return [e.lower() for e in entities] + years


# ============================================================================
# NOTES
# ============================================================================

# 1. This change makes entity matching in boost logic much more accurate
# 2. Falls back gracefully if entities.py not available yet
# 3. No other changes needed to residuals.py
# 4. Boost logic now benefits from dictionary-based entity extraction


def calculate_confidence_boost(
    new_routed: Dict[str, Any],
    old_row: Dict[str, str],
    source_path: Path,
) -> BoostResult:
    """
    Calculate confidence boost for a residual file being re-routed.
    
    Applies deterministic boosts based on history matching:
    - Prefix match: +0.05 (target folder consistency)
    - Entity match: +0.05 (semantic continuity)  
    - Action continuity: +0.03 (if SUGGEST and confidence increased)
    - Conflict penalty: 0 boost if both prefix AND entity changed
    
    Args:
        new_routed: New routing result dict with keys:
            - Label, Confidence, TargetPath, etc.
        old_row: Previous mapping row dict with keys:
            - PreviousTargetPath, PreviousConfidence, PreviousAction, etc.
        source_path: Path object for the file being analyzed
        
    Returns:
        BoostResult with confidence adjustment and reasoning
    """
    original_conf = float(new_routed.get('Confidence', 0.0))
    boost = 0.0
    reasons = []
    
    # Extract comparison values
    new_prefix = extract_prefix(new_routed.get('TargetPath', ''))
    old_prefix = extract_prefix(old_row.get('PreviousTargetPath', ''))

    # PreviousConfidence may be empty on first refinement pass.
    # Fall back to current Confidence if needed.
    old_conf = safe_float(
        old_row.get('PreviousConfidence') or old_row.get('Confidence'),
        default=0.0
    )
    old_action = old_row.get('PreviousAction', '') or old_row.get('Action', '')

    # Extract entities for matching
    new_label = new_routed.get('Label', '')
    old_label = old_row.get('Label', '')  # Label might have changed
    
    # Check for entity matches (simple label comparison for MVP)
    # In future, could use full entity extraction
    new_entities = set(extract_entities_from_path(source_path))
    # We don't have old entities stored, so approximate with label
    old_entities = set([normalize_entity(old_label)]) if old_label else set()
    
    entity_overlap = bool(new_entities & old_entities)
    
    # Detect conflicts: both prefix AND entity changed
    prefix_changed = (new_prefix != old_prefix) if (new_prefix and old_prefix) else False
    entity_changed = not entity_overlap if old_entities else False
    
    has_conflict = prefix_changed and entity_changed
    
    if has_conflict:
        # Conflict detected: no boost
        reasons.append("prefix and entity both changed (conflict)")
        boost = 0.0
    else:
        # Apply boosts
        
        # 1. Prefix match boost
        if new_prefix and old_prefix and new_prefix == old_prefix:
            boost += 0.05
            reasons.append(f"target prefix matches previous ({new_prefix})")
        
        # 2. Entity match boost  
        if entity_overlap:
            boost += 0.05
            reasons.append("entity matches previous classification")
        
        # 3. Action continuity boost
        if old_action == 'SUGGEST' and original_conf > old_conf:
            boost += 0.03
            reasons.append("confidence increased from previous SUGGEST")
    
    # Apply boost and cap
    boosted_conf = min(original_conf + boost, CONFIDENCE_CAP)
    
    # Determine action and residual status
    action, is_residual = determine_action_from_confidence(boosted_conf)
    
    return BoostResult(
        original_confidence=original_conf,
        boosted_confidence=boosted_conf,
        boost_applied=boost,
        boost_reasons=reasons,
        action=action,
        is_residual=is_residual,
    )


def determine_action_from_confidence(confidence: float) -> tuple[str, bool]:
    """
    Determine Action and IsResidual from confidence using locked thresholds.
    
    Thresholds (from brief):
    - HIGH >= 0.85 → MOVE, IsResidual=False
    - MED_HIGH 0.75-0.85 → SUGGEST, IsResidual=True  
    - else → keep residual (Skip, IsResidual=True)
    
    Args:
        confidence: Confidence score (0.0-1.0)
        
    Returns:
        Tuple of (action, is_residual)
    """
    if confidence >= HIGH_THRESHOLD:
        return ("MOVE", False)
    elif confidence >= MED_HIGH_THRESHOLD:
        return ("SUGGEST", False)  # <-- THIS is the fix
    else:
        return ("RESIDUAL", True)  # (or "SKIP" if you want, see note)


def apply_residual_refinement(
        old_mapping_row: Dict[str, str],
        new_analysis_result,
        pass_id: int,
) -> Dict[str, Any]:
    """
    Apply confidence boosting and promotion to a single residual row.

    This is the main entrypoint for refining a residual file.

    Args:
        old_mapping_row: Previous mapping CSV row (dict)
        new_analysis_result: New analyzer FileResult object
        pass_id: Current pass number (2, 3, etc.)

    Returns:
        Updated mapping row dict with:
        - Boosted confidence
        - Updated Action/IsResidual
        - Previous* history columns populated
    """
    # NOTE: FileResult doesn't have target_path - that's calculated by strategy layer
    # We just work with the classification data here

    # Build new routed dict from analysis result (minimal - no target_path yet)
    new_routed = {
        'Label': new_analysis_result.label,
        'Confidence': new_analysis_result.confidence,
        'TargetPath': old_mapping_row.get('TargetPath', ''),  # Preserve old target for now
        'Why': new_analysis_result.why,
        'Method': new_analysis_result.method,
    }

    # Calculate boost
    boost_result = calculate_confidence_boost(
        new_routed=new_routed,
        old_row=old_mapping_row,
        source_path=new_analysis_result.path,
    )

    # Build updated row with history chaining
    updated_row = {
        'SourcePath': str(new_analysis_result.path),
        'NodeID': old_mapping_row.get('NodeID', ''),  # Preserve NodeID
        'Label': new_analysis_result.label,
        'Confidence': f"{boost_result.boosted_confidence:.4f}",
        'Why': new_analysis_result.why,
        'Action': boost_result.action,
        'TargetPath': old_mapping_row.get('TargetPath', ''),  # Keep old target for now
        'IsResidual': str(boost_result.is_residual),
        'ResidualReason': new_analysis_result.residual_reason if boost_result.is_residual else '',
        'PassId': str(pass_id),

        # History chaining (from old row's current values)
        'PreviousPassId': old_mapping_row.get('PassId', ''),
        'PreviousAction': old_mapping_row.get('Action', ''),
        'PreviousConfidence': old_mapping_row.get('Confidence', ''),
        'PreviousTargetPath': old_mapping_row.get('TargetPath', ''),
    }

    # Add boost info to Why if boost was applied
    if boost_result.boost_applied > 0:
        boost_info = f" [+{boost_result.boost_applied:.2f} boost: {', '.join(boost_result.boost_reasons)}]"
        updated_row['Why'] = updated_row['Why'] + boost_info

    return updated_row


def build_refinement_stats(
    original_residuals: List[Dict[str, str]],
    updated_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build statistics for refine-residuals summary output.
    
    Calculates promotion counts and residual rate.
    
    Args:
        original_residuals: List of original residual rows
        updated_rows: List of updated rows after refinement
        
    Returns:
        Stats dict with counts and rates
    """
    def _is_true(v: str) -> bool:
        return str(v).strip().lower() in ("true", "1", "yes", "y")
    
    residuals_in = len(original_residuals)
    
    # Count by action/residual status
    reclassified_to_move = 0
    reclassified_to_suggest = 0
    still_residual = 0
    
    for row in updated_rows:
        action = row.get('Action', '')
        is_residual = _is_true(row.get('IsResidual', 'True'))
        
        if action == 'Move' and not is_residual:
            reclassified_to_move += 1
        elif action == 'Suggest' and is_residual:
            reclassified_to_suggest += 1
        elif is_residual:
            still_residual += 1
    
    total_reclassified = reclassified_to_move + reclassified_to_suggest
    
    residual_rate_after = (still_residual / residuals_in * 100) if residuals_in > 0 else 0
    
    return {
        'residuals_in': residuals_in,
        'reclassified_to_move': reclassified_to_move,
        'reclassified_to_suggest': reclassified_to_suggest,
        'still_residual': still_residual,
        'reclassified': total_reclassified,
        'residual_rate_after': residual_rate_after,
    }
