"""
Entity extraction module for Siftwise.

Provides hooks for extracting meaningful entities (addresses, companies, 
projects, etc.) from file paths and metadata. V1 is intentionally minimal 
but designed for easy extension.
"""

from pathlib import Path
from typing import List
import re


def extract_entities_for_result(result) -> List[str]:
    """
    Extract entities from a Result object.

    V1 implementation: Extract simple patterns from filename and path components.
    Future versions can plug in:
    - Address detection (e.g., "1350 Wadsworth")
    - Company names (e.g., "ADP", "Acme Corp")
    - Account numbers
    - Project codes

    Args:
        result: Analyzer Result object with path, label, confidence, etc.

    Returns:
        List of entity strings found in the file path/name
    """
    entities = []

    # Extract from path components
    path = result.path

    # 1. Extract potential addresses (simple pattern: numbers + street name)
    address_entities = _extract_address_patterns(path)
    entities.extend(address_entities)

    # 2. Extract potential company/vendor names (uppercase sequences)
    company_entities = _extract_company_patterns(path)
    entities.extend(company_entities)

    # 3. Extract year patterns (useful for dated files)
    year_entities = _extract_year_patterns(path)
    entities.extend(year_entities)

    # Return unique entities, preserving order
    seen = set()
    unique_entities = []
    for entity in entities:
        if entity not in seen:
            seen.add(entity)
            unique_entities.append(entity)

    return unique_entities


def _extract_address_patterns(path: Path) -> List[str]:
    """
    Extract potential address patterns from path.

    Examples:
    - "1350 Wadsworth" 
    - "123 Main St"
    - "456-Oak-Ave"
    """
    entities = []

    # Pattern: 3-5 digits followed by a word (street name)
    address_pattern = r'\b(\d{3,5}\s+[A-Z][a-z]+(?:\s+(?:St|Ave|Rd|Dr|Ln|Way|Blvd|Ct))?)\b'

    # Check all path parts
    path_str = str(path)
    matches = re.findall(address_pattern, path_str)
    entities.extend(matches)

    # Also check for dash-separated addresses: "1350-Wadsworth"
    dash_pattern = r'\b(\d{3,5}[-_][A-Z][a-z]+)\b'
    matches = re.findall(dash_pattern, path_str)
    entities.extend([m.replace('-', ' ').replace('_', ' ') for m in matches])

    return entities


def _extract_company_patterns(path: Path) -> List[str]:
    """
    Extract potential company/vendor names from path.

    Examples:
    - "ADP" (all caps, 2-5 letters)
    - "QuickBooks"
    - "Microsoft"
    """
    entities = []

    # Pattern 1: All-caps acronyms (2-5 letters)
    # Common for companies like ADP, IBM, AWS, etc.
    for part in path.parts:
        acronyms = re.findall(r'\b([A-Z]{2,5})\b', part)
        # Filter out common false positives
        filtered = [
            a for a in acronyms
            if a not in {'PDF', 'DOC', 'XLS', 'PNG', 'JPG', 'CSV', 'TXT', 'ZIP'}
        ]
        entities.extend(filtered)

    # Pattern 2: CamelCase names (potential company names)
    for part in path.parts:
        camel_case = re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', part)
        entities.extend(camel_case)

    return entities


def _extract_year_patterns(path: Path) -> List[str]:
    """
    Extract year patterns that might be useful for organization.

    Examples:
    - "2024"
    - "FY2023"
    """
    entities = []

    path_str = str(path)

    # Pattern: 4-digit years (1990-2099)
    years = re.findall(r'\b(19\d{2}|20\d{2})\b', path_str)
    entities.extend(years)

    # Pattern: Fiscal year markers
    fy_years = re.findall(r'\b(FY\s*\d{2,4})\b', path_str, re.IGNORECASE)
    entities.extend([fy.upper().replace(' ', '') for fy in fy_years])

    return entities


def extract_entities_from_paths(paths: List[Path]) -> dict[str, List[Path]]:
    """
    Batch entity extraction: map entities to the paths that contain them.

    Useful for discovering common entities across a file collection.

    Args:
        paths: List of Path objects to analyze

    Returns:
        Dict mapping entity strings to lists of paths containing that entity
    """
    entity_map: dict[str, List[Path]] = {}

    for path in paths:
        # Create a minimal result-like object for extraction
        class _TempResult:
            def __init__(self, p):
                self.path = p

        entities = extract_entities_for_result(_TempResult(path))

        for entity in entities:
            if entity not in entity_map:
                entity_map[entity] = []
            entity_map[entity].append(path)

    return entity_map


def suggest_entity_folders(entity_map: dict[str, List[Path]], min_frequency: int = 3) -> List[str]:
    """
    Suggest which entities are common enough to warrant their own folders.

    Args:
        entity_map: Output from extract_entities_from_paths()
        min_frequency: Minimum number of files to suggest a folder

    Returns:
        List of entity names that appear frequently enough
    """
    suggestions = []

    for entity, paths in entity_map.items():
        if len(paths) >= min_frequency:
            suggestions.append(entity)

    # Sort by frequency (most common first)
    suggestions.sort(key=lambda e: len(entity_map[e]), reverse=True)

    return suggestions