from dataclasses import dataclass
from siftwise.schemas import FileResult
from pathlib import Path
from typing import List, Iterable, Optional, Set
from .detectors import Signal, Detector, get_default_detectors

# Confidence thresholds - more nuanced levels
HIGH = 0.85      # High confidence - definitely move
MED_HIGH = 0.75  # Medium-high - probably move
MED = 0.65       # Medium - suggest review
MED_LOW = 0.50   # Medium-low - likely residual
LOW = 0.40       # Low - definitely residual
VERY_LOW = 0.30  # Very low - unknown/ambiguous


def determine_residual(label: str, confidence: float, method: str, path: Path) -> tuple[bool, str]:
    """
    Enhanced residual determination with multiple criteria and explanations.
    
    Returns: (is_residual, reason)
    """
    reasons = []
    
    # 1. No label or generic labels
    if not label or label.lower() in ["uncategorized", "unknown", "misc", ""]:
        if label == "misc":
            reasons.append("generic/miscellaneous classification")
        else:
            reasons.append("no clear category")
    
    # 2. Very low confidence (below LOW threshold)
    if confidence < LOW:
        reasons.append(f"confidence {confidence:.2f} below threshold {LOW}")
    
    # 3. Medium-low confidence for certain generic categories
    elif confidence < MED_LOW and label in ["misc", "dated_files", "empty_files"]:
        reasons.append(f"weak classification as '{label}'")
    
    # 4. Files that only matched by weak methods
    elif method in ["size", "date_pattern"] and confidence < MED:
        reasons.append(f"only matched by {method} heuristic")
    
    # 5. Ambiguous file patterns
    filename = path.name.lower()
    ambiguous_patterns = [
        "temp", "tmp", "copy", "backup", "old", "new", 
        "test", "sample", "example", "untitled", "document"
    ]
    if any(pattern in filename for pattern in ambiguous_patterns) and confidence < MED_HIGH:
        reasons.append("ambiguous filename pattern")
    
    # 6. Files with conflicting signals (would need multi-detector analysis)
    # This is a placeholder for future multi-signal conflict detection
    if label == "dated_files" and confidence < MED:
        reasons.append("date-only classification needs context")
    
    # Determine if residual based on accumulated reasons
    is_residual = len(reasons) > 0
    reason = "; ".join(reasons) if reasons else ""
    
    return is_residual, reason

def pick_label(signals: List[Signal]) -> Signal:
    """
    Enhanced label selection considering signal quality and conflicts.
    """
    if not signals:
        # Return a "no match" signal
        return Signal(
            label="",
            confidence=0.0,
            method="none",
            why="no detector matched"
        )
    
    # Filter out very weak signals
    strong_signals = [s for s in signals if s.confidence >= VERY_LOW]
    if not strong_signals:
        strong_signals = signals  # Fall back to all signals if none are strong
    
    # Check for conflicts (multiple high-confidence different labels)
    high_conf_labels = set()
    for s in strong_signals:
        if s.confidence >= MED_HIGH:
            high_conf_labels.add(s.label)
    
    # If multiple high-confidence labels, reduce confidence
    confidence_penalty = 0.0
    if len(high_conf_labels) > 1:
        confidence_penalty = 0.15  # Reduce confidence due to ambiguity
    
    # Sort by confidence and explanation quality
    def signal_score(s: Signal) -> tuple:
        explanation_quality = len(s.why) / 100  # Normalize to 0-1
        method_priority = {
            "extension": 1.0,
            "keyword": 0.9,
            "content": 0.85,
            "date_pattern": 0.5,
            "size": 0.3,
        }.get(s.method, 0.5)
        
        adjusted_confidence = s.confidence - confidence_penalty
        return (adjusted_confidence * method_priority, explanation_quality)
    
    strong_signals.sort(key=signal_score, reverse=True)
    best = strong_signals[0]
    
    # Apply confidence penalty to the returned signal if there were conflicts
    if confidence_penalty > 0:
        best = Signal(
            label=best.label,
            confidence=max(best.confidence - confidence_penalty, VERY_LOW),
            method=best.method,
            why=best.why + " (multiple classifications detected)"
        )
    
    return best


def analyze_paths(
    paths: Iterable[Path],
    root_out: Path,
    detectors: Optional[List[Detector]] = None,
    refinement_iteration: int = 1,
) -> List[FileResult]:
    """
    Enhanced analyzer with smarter residual detection and iteration awareness.
    
    Args:
        paths: Files to analyze
        root_out: Output root directory
        detectors: Custom detectors (uses defaults if None)
        refinement_iteration: Which iteration this is (1=initial, 2+=refinement)
    """
    if detectors is None:
        detectors = get_default_detectors()
    
    # Track statistics for adaptive thresholds
    all_confidences: List[float] = []
    label_counts: dict[str, int] = {}
    
    # First pass: collect all signals
    path_signals: dict[Path, List[Signal]] = {}
    for p in paths:
        if not p.is_file():
            continue
        
        sigs: List[Signal] = []
        for d in detectors:
            s = d.score(p)
            if s:
                sigs.append(s)
        
        path_signals[p] = sigs
        
        # Collect statistics
        if sigs:
            best = pick_label(sigs)
            all_confidences.append(best.confidence)
            label_counts[best.label] = label_counts.get(best.label, 0) + 1
    
    # Calculate adaptive thresholds based on distribution
    avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.5
    
    # Identify rare categories (might need special handling)
    total_files = len(path_signals)
    rare_labels = {
        label for label, count in label_counts.items() 
        if count < max(3, total_files * 0.02)  # Less than 2% or 3 files
    }
    
    # Second pass: generate results with context awareness
    results: List[Result] = []
    
    for p, sigs in path_signals.items():
        if not sigs:
            # No detector matched - definitely residual
            results.append(
                FileResult(
                    path=p,
                    label="",
                    confidence=0.0,
                    method="none",
                    why="no detector matched",
                    is_residual=True,
                    residual_reason="no matching detector",
                )
            )
            continue
        
        best = pick_label(sigs)
        
        # Adjust confidence for rare labels (they might be mis-classifications)
        if best.label in rare_labels and best.confidence < HIGH:
            best = Signal(
                label=best.label,
                confidence=best.confidence * 0.8,  # Reduce confidence
                method=best.method,
                why=best.why + " (rare category)"
            )
        
        # Enhanced residual determination
        is_residual, residual_reason = determine_residual(
            best.label, best.confidence, best.method, p
        )
        
        # On refinement iterations, be more aggressive about classification
        if refinement_iteration > 1 and not is_residual:
            # Boost confidence slightly on refinement passes
            if best.confidence >= MED_LOW:
                best = Signal(
                    label=best.label,
                    confidence=min(best.confidence * 1.1, 0.95),
                    method=best.method,
                    why=best.why + f" (iteration {refinement_iteration})"
                )

        # Create FileResult with classification only (no action decisions)
        results.append(
            FileResult(
                path=p,
                label=best.label,
                confidence=best.confidence,
                method=best.method,
                why=best.why,
                is_residual=is_residual,
                residual_reason=residual_reason,
            )
        )
    
    return results


def get_residual_stats(results: List[FileResult]) -> dict:
    """
    Enhanced statistics about residual files for reporting.
    """
    total_files = len(results)
    residual_files = [r for r in results if r.is_residual]
    residual_count = len(residual_files)
    
    # Group residuals by reason
    residual_reasons: dict[str, int] = {}
    for r in residual_files:
        # Parse reasons (they're semicolon-separated)
        reasons = r.residual_reason.split("; ") if r.residual_reason else ["unknown"]
        for reason in reasons:
            key = reason.split(" ")[0] if reason else "unknown"  # First word as key
            residual_reasons[key] = residual_reasons.get(key, 0) + 1
    
    # Group residuals by original label attempt
    residual_labels: dict[str, int] = {}
    for r in residual_files:
        label = r.label or "none"
        residual_labels[label] = residual_labels.get(label, 0) + 1
    
    # Calculate confidence distributions
    residual_confidences = [r.confidence for r in residual_files]
    non_residual = [r for r in results if not r.is_residual]
    non_residual_confidences = [r.confidence for r in non_residual]
    
    # Percentile calculations
    def percentile(values: List[float], p: float) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = int(len(sorted_vals) * p)
        return sorted_vals[min(idx, len(sorted_vals)-1)]
    
    return {
        "total_files": total_files,
        "residual_count": residual_count,
        "residual_percentage": (residual_count / max(total_files, 1)) * 100,
        "residual_reasons": residual_reasons,
        "residual_labels": residual_labels,
        "residual_avg_confidence": sum(residual_confidences) / max(len(residual_confidences), 1),
        "residual_median_confidence": percentile(residual_confidences, 0.5),
        "non_residual_avg_confidence": sum(non_residual_confidences) / max(len(non_residual_confidences), 1),
        "non_residual_median_confidence": percentile(non_residual_confidences, 0.5),
        "confidence_gap": (
            (sum(non_residual_confidences) / max(len(non_residual_confidences), 1)) -
            (sum(residual_confidences) / max(len(residual_confidences), 1))
        ) if residual_confidences and non_residual_confidences else 0.0,
    }


def suggest_refinement_strategy(stats: dict) -> List[str]:
    """
    Suggest strategies for improving residual classification based on statistics.
    """
    suggestions = []
    
    if stats["residual_percentage"] > 20:
        suggestions.append("High residual rate - consider adding domain-specific detectors")
    
    reasons = stats.get("residual_reasons", {})
    if reasons.get("no", 0) > stats["residual_count"] * 0.3:
        suggestions.append("Many files have no category - add more extension mappings")
    
    if reasons.get("confidence", 0) > stats["residual_count"] * 0.3:
        suggestions.append("Low confidence is common - consider keyword or content analysis")
    
    if reasons.get("ambiguous", 0) > stats["residual_count"] * 0.2:
        suggestions.append("Ambiguous filenames detected - implement naming convention rules")
    
    if stats.get("confidence_gap", 0) < 0.3:
        suggestions.append("Small confidence gap - detectors may need tuning")
    
    return suggestions
