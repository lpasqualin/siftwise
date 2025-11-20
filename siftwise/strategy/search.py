"""
Search module for Siftwise.

Provides basic search capabilities over mapping data and file results.
Foundation for future "Smart Search + Rule Capture" features.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import re


def search_mapping(
        mapping_rows: List[Dict[str, str]],
        query: str,
        limit: int = 100,
        fields: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    """
    Basic substring search over Mapping.csv data.

    Searches across SourcePath, Label, Why, and other fields.

    Args:
        mapping_rows: List of mapping row dicts from Mapping.csv
        query: Search query (substring or simple pattern)
        limit: Maximum number of results to return
        fields: Optional list of fields to search in (default: all text fields)

    Returns:
        List of matching rows (up to limit)
    """
    if not query or not query.strip():
        return []

    query_lower = query.lower()

    # Default fields to search
    if fields is None:
        fields = ['SourcePath', 'Label', 'Why', 'Action']
        # Include Entities if present
        if mapping_rows and 'Entities' in mapping_rows[0]:
            fields.append('Entities')

    matches = []

    for row in mapping_rows:
        # Check if query matches any field
        for field in fields:
            value = row.get(field, '')
            if query_lower in value.lower():
                matches.append(row)
                break  # Don't add same row multiple times

        if len(matches) >= limit:
            break

    return matches


def search_by_pattern(
        mapping_rows: List[Dict[str, str]],
        pattern: str,
        field: str = 'SourcePath',
        limit: int = 100,
) -> List[Dict[str, str]]:
    """
    Search using a glob-style or regex pattern.

    More powerful than simple substring search.

    Args:
        mapping_rows: List of mapping row dicts
        pattern: Glob pattern (e.g., "*.pdf") or regex
        field: Field to search in (default: SourcePath)
        limit: Maximum results

    Returns:
        List of matching rows
    """
    matches = []

    # Determine if pattern is glob or regex
    is_glob = any(c in pattern for c in ['*', '?'])

    if is_glob:
        # Convert glob to regex
        regex_pattern = pattern.replace('.', r'\.')
        regex_pattern = regex_pattern.replace('*', '.*')
        regex_pattern = regex_pattern.replace('?', '.')
        regex_pattern = f'^{regex_pattern}$'
    else:
        # Use as-is (assume it's a regex)
        regex_pattern = pattern

    try:
        compiled = re.compile(regex_pattern, re.IGNORECASE)
    except re.error:
        # Invalid pattern, fall back to substring
        return search_mapping(mapping_rows, pattern, limit, [field])

    for row in mapping_rows:
        value = row.get(field, '')
        if compiled.search(value):
            matches.append(row)

            if len(matches) >= limit:
                break

    return matches


def search_residuals(
        mapping_rows: List[Dict[str, str]],
        query: Optional[str] = None,
        limit: int = 100,
) -> List[Dict[str, str]]:
    """
    Search only residual files (IsResidual=True).

    Useful for focused refinement efforts.

    Args:
        mapping_rows: List of mapping row dicts
        query: Optional search query within residuals
        limit: Maximum results

    Returns:
        List of residual rows matching query (or all residuals if no query)
    """
    # Filter to residuals first
    residuals = [
        row for row in mapping_rows
        if row.get('IsResidual', '').lower() == 'true'
    ]

    if not query:
        return residuals[:limit]

    # Apply search query to residuals
    return search_mapping(residuals, query, limit)


def search_by_confidence(
        mapping_rows: List[Dict[str, str]],
        min_confidence: Optional[float] = None,
        max_confidence: Optional[float] = None,
        limit: int = 100,
) -> List[Dict[str, str]]:
    """
    Search by confidence range.

    Useful for finding files that need review or refinement.

    Args:
        mapping_rows: List of mapping row dicts
        min_confidence: Minimum confidence threshold (inclusive)
        max_confidence: Maximum confidence threshold (inclusive)
        limit: Maximum results

    Returns:
        List of rows within confidence range
    """
    matches = []

    for row in mapping_rows:
        try:
            conf = float(row.get('Confidence', '0'))
        except (ValueError, TypeError):
            continue

        if min_confidence is not None and conf < min_confidence:
            continue

        if max_confidence is not None and conf > max_confidence:
            continue

        matches.append(row)

        if len(matches) >= limit:
            break

    return matches


def group_by_entity(
        mapping_rows: List[Dict[str, str]],
) -> Dict[str, List[Dict[str, str]]]:
    """
    Group mapping rows by extracted entities.

    Useful for discovering entity-based organization opportunities.

    Args:
        mapping_rows: List of mapping row dicts with 'Entities' field

    Returns:
        Dict mapping entity names to lists of rows containing that entity
    """
    entity_groups: Dict[str, List[Dict[str, str]]] = {}

    for row in mapping_rows:
        entities_str = row.get('Entities', '')
        if not entities_str:
            continue

        # Parse entities (assume comma-separated)
        entities = [e.strip() for e in entities_str.split(',') if e.strip()]

        for entity in entities:
            if entity not in entity_groups:
                entity_groups[entity] = []
            entity_groups[entity].append(row)

    return entity_groups


def search_and_suggest_rule(
        mapping_rows: List[Dict[str, str]],
        pattern: str,
        target_label: str,
) -> Dict[str, Any]:
    """
    Search for files matching a pattern and suggest a rule.

    Foundation for "Smart Search + Rule Capture" feature.

    Args:
        mapping_rows: List of mapping row dicts
        pattern: Pattern to search for
        target_label: Proposed label for matching files

    Returns:
        Dict with:
        - matches: List of matching rows
        - suggested_rule: Dict representing the rule
        - impact: Stats about what the rule would affect
    """
    # Find matches
    matches = search_by_pattern(mapping_rows, pattern)

    # Analyze impact
    current_labels = {}
    residual_count = 0

    for row in matches:
        label = row.get('Label', 'uncategorized')
        current_labels[label] = current_labels.get(label, 0) + 1

        if row.get('IsResidual', '').lower() == 'true':
            residual_count += 1

    # Suggest rule
    suggested_rule = {
        'pattern': pattern,
        'label': target_label,
        'action': 'Move',
    }

    return {
        'matches': matches,
        'suggested_rule': suggested_rule,
        'impact': {
            'total_files': len(matches),
            'residual_files': residual_count,
            'current_labels': current_labels,
        }
    }


def get_search_stats(
        mapping_rows: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Get statistics useful for search and analysis.

    Args:
        mapping_rows: List of mapping row dicts

    Returns:
        Dict with various stats
    """
    total = len(mapping_rows)

    # Count by label
    by_label = {}
    # Count by action
    by_action = {}
    # Count residuals
    residual_count = 0
    # Confidence distribution
    confidences = []

    for row in mapping_rows:
        label = row.get('Label', 'uncategorized')
        by_label[label] = by_label.get(label, 0) + 1

        action = row.get('Action', 'Skip')
        by_action[action] = by_action.get(action, 0) + 1

        if row.get('IsResidual', '').lower() == 'true':
            residual_count += 1

        try:
            conf = float(row.get('Confidence', '0'))
            confidences.append(conf)
        except (ValueError, TypeError):
            pass

    # Calculate confidence stats
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        'total_files': total,
        'by_label': by_label,
        'by_action': by_action,
        'residual_count': residual_count,
        'residual_percentage': (residual_count / total * 100) if total > 0 else 0,
        'avg_confidence': avg_confidence,
        'unique_labels': len(by_label),
    }