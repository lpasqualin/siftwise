"""
Siftwise Entity Extraction V1 - Dictionary-Led Pipeline

High-precision entity extraction for routing enhancement and metadata enrichment.
No ML/embeddings - pure rules and dictionaries for deterministic behavior.

Extracts:
- Organizations/Brands (Amazon, IRS, Chase, etc.)
- People/Clients (ClientA, Farah, etc.)
- Places/Trips (NYC, Orlando, etc.)
- Years/Dates (2024, Q1-2023, etc.)

Design principles:
1. High precision over recall (better to miss than false positive)
2. Aggressive noise filtering (no generic junk)
3. Deterministic normalization (same input → same output)
4. Safe fallbacks (never crash on bad input)
"""

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import re
from dataclasses import dataclass


# ============================================================================
# ENTITY DICTIONARIES (Built-in starter set)
# ============================================================================

# Organizations & Brands (financial, tech, services)
ORG_ENTITIES = {
    # Financial
    "amazon", "apple", "irs", "chase", "amex", "american express",
    "bank of america", "bofa", "citi", "citibank", "wells fargo",
    "paypal", "venmo", "zelle", "stripe", "square",
    
    # Tech & Services
    "google", "microsoft", "netflix", "spotify", "github", "gitlab",
    "notion", "slack", "zoom", "dropbox", "uber", "lyft", "airbnb",
    
    # Retail & Home
    "home depot", "homedepot", "lowes", "costco", "walmart", "target",
    "amazon", "ebay", "etsy",
    
    # Healthcare & Insurance
    "aetna", "cigna", "bcbs", "blue cross", "united healthcare",
    "kaiser", "anthem",
    
    # Utilities & Services  
    "comcast", "xfinity", "verizon", "att", "tmobile", "sprint",
    "geico", "state farm", "allstate", "progressive",
}

# People & Clients (starter set - user should extend)
PERSON_ENTITIES = {
    "farah", "leo", "client a", "client b", "clienta", "clientb",
    "project x", "projectx", "team alpha", "partner",
}

# Places & Trips
PLACE_ENTITIES = {
    "nyc", "new york", "new york city", "manhattan", "brooklyn", "queens",
    "orlando", "miami", "tampa", "jacksonville",
    "chicago", "boston", "philadelphia", "philly",
    "seattle", "portland", "san francisco", "sf", "bay area",
    "los angeles", "la", "san diego",
    "vegas", "las vegas", "reno",
    "denver", "austin", "houston", "dallas",
    "atlanta", "charlotte", "nashville",
    "quebec", "montreal", "toronto", "vancouver",
    "italy", "france", "spain", "uk", "england", "germany",
    "japan", "china", "mexico", "canada",
    "trip", "vacation", "travel",
}

# Acronyms that ARE valid entities (whitelist for < 3 char)
ACRONYM_WHITELIST = {
    "irs", "nyc", "la", "sf", "uk", "us", "eu",
    "hr", "it", "pr", "qa", "qa",
}


# ============================================================================
# NOISE FILTERS (Junk tokens to exclude)
# ============================================================================

JUNK_TOKENS = {
    # Generic file operations
    "copy", "copyof", "copy of", "duplicate", "backup", "export",
    "scan", "scanned", "screenshot", "capture",
    
    # Versions & status
    "final", "draft", "temp", "temporary", "new", "old",
    "v1", "v2", "v3", "version", "revised", "updated",
    
    # Generic descriptors
    "misc", "miscellaneous", "untitled", "document", "file",
    "folder", "archive", "data", "info", "stuff",
    
    # Locations (too generic)
    "desktop", "downloads", "documents", "pictures", "music",
    "videos", "my documents", "mydocuments",
    
    # Date fragments (handled separately)
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "mon", "tue", "wed", "thu", "fri",
    
    # Generic financial
    "receipt", "invoice", "statement", "bill", "payment",
    "transaction", "report", "summary", "total",
    
    # Image/media artifacts
    "img", "image", "photo", "pic", "video", "audio",
    "jpg", "png", "pdf", "doc", "docx", "xlsx",
}

# Suffixes to strip during normalization
JUNK_SUFFIXES = {
    "copy", "scan", "final", "draft", "v2", "v3",
    "receipt", "statement", "invoice", "report", "summary",
    "document", "doc", "file", "backup", "export",
}


# ============================================================================
# ENTITY RESULT DATACLASS
# ============================================================================

@dataclass
class EntityResult:
    """Result of entity extraction."""
    domain: str  # Not used in v1, reserved for future
    kind: str  # org | person | place | project | year | none
    entity: str  # Normalized entity string
    year: Optional[int]  # Extracted year if any
    confidence: float  # 0.0-1.0
    source: str  # Where entity was found: filename | parent | path


# ============================================================================
# NORMALIZATION FUNCTIONS
# ============================================================================

def normalize_token(text: str) -> str:
    """
    Normalize a token for matching.
    
    Steps:
    1. Lowercase
    2. Strip whitespace
    3. Collapse separators to spaces
    4. Remove multiple spaces
    
    Examples:
        "Client_A" → "client a"
        "NEW-YORK-CITY" → "new york city"
        "Chase__Bank" → "chase bank"
    """
    if not text:
        return ""
    
    # Lowercase and strip
    text = text.lower().strip()
    
    # Replace separators with spaces
    for sep in ['_', '-', '.', '/']:
        text = text.replace(sep, ' ')
    
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def canonicalize_entity(text: str) -> str:
    """
    Canonicalize entity for output.
    
    Examples:
        "client a" → "ClientA"
        "new york city" → "NewYorkCity"
        "irs" → "IRS"
        "chase" → "Chase"
    """
    if not text:
        return ""
    
    # Remove junk suffixes
    normalized = normalize_token(text)
    tokens = normalized.split()
    
    # Strip junk suffixes
    filtered_tokens = []
    for token in tokens:
        if token not in JUNK_SUFFIXES:
            filtered_tokens.append(token)
    
    if not filtered_tokens:
        return ""
    
    # Rejoin and apply casing
    cleaned = ' '.join(filtered_tokens)
    
    # Special case: all-caps acronyms
    if len(cleaned) <= 4 and cleaned.upper() in ACRONYM_WHITELIST:
        return cleaned.upper()
    
    # TitleCase with no spaces
    words = cleaned.split()
    canonical = ''.join(word.capitalize() for word in words)
    
    return canonical


def strip_year_suffix(text: str) -> str:
    """
    Remove trailing year patterns from text.
    
    Examples:
        "trip_nyc_2024" → "trip_nyc"
        "Client-A-2023" → "Client-A"
    """
    # Remove patterns like _2024, -2024, 2024
    text = re.sub(r'[_\-\s]*(19|20)\d{2}$', '', text)
    text = re.sub(r'[_\-\s]*Q[1-4][_\-\s]*(19|20)\d{2}$', '', text, flags=re.IGNORECASE)
    
    return text.strip('_- ')


# ============================================================================
# ENTITY MATCHING FUNCTIONS
# ============================================================================

def extract_year(path: Path) -> Optional[int]:
    """
    Extract year from path using regex.
    
    Patterns supported:
    - 2024, 2023, etc. (1990-2099)
    - Q1-2023, Q4_2024
    - 2024-01, 2024_03
    
    Returns the most recent valid year found.
    """
    from datetime import datetime
    current_year = datetime.now().year
    
    # Build full path string
    path_str = str(path)
    
    # Pattern 1: Standalone 4-digit years
    years = re.findall(r'\b(19\d{2}|20\d{2})\b', path_str)
    valid_years = [int(y) for y in years if 1990 <= int(y) <= current_year + 1]
    
    # Pattern 2: Quarter formats (Q1-2023, Q4_2024)
    quarter_matches = re.findall(r'Q[1-4][_\-\s]*(19\d{2}|20\d{2})', path_str, re.IGNORECASE)
    valid_years.extend([int(y) for y in quarter_matches if 1990 <= int(y) <= current_year + 1])
    
    # Pattern 3: Month formats (2024-01, 2024_03)
    month_matches = re.findall(r'(19\d{2}|20\d{2})[_\-](0[1-9]|1[0-2])', path_str)
    valid_years.extend([int(y[0]) for y in month_matches if 1990 <= int(y[0]) <= current_year + 1])
    
    # Return most recent year
    return max(valid_years) if valid_years else None


def match_entity_in_token(token: str, entity_set: Set[str]) -> Optional[str]:
    """
    Match a token against an entity set.
    
    Handles:
    - Exact matches
    - Multi-word entities ("new york city")
    - Partial matches for long tokens
    
    Returns the matched entity (normalized) or None.
    """
    normalized = normalize_token(token)
    
    # Exact match
    if normalized in entity_set:
        return normalized
    
    # Check if token contains a multi-word entity
    for entity in entity_set:
        if ' ' in entity and entity in normalized:
            return entity
    
    # Check if any single-word entity is in token
    words = normalized.split()
    for word in words:
        if len(word) >= 3 and word in entity_set:
            return word
    
    return None


def is_junk_token(token: str) -> bool:
    """
    Check if token is junk and should be filtered.
    
    Rules:
    - < 3 chars unless in whitelist
    - In JUNK_TOKENS set
    - Pure numbers (unless year)
    - Only special chars
    """
    if not token:
        return True
    
    normalized = normalize_token(token)
    
    # Too short unless whitelisted
    if len(normalized) < 3 and normalized not in ACRONYM_WHITELIST:
        return True
    
    # In junk set
    if normalized in JUNK_TOKENS:
        return True
    
    # Pure numbers (years handled separately)
    if normalized.isdigit():
        return True
    
    # Only special chars
    if not re.search(r'[a-z0-9]', normalized):
        return True
    
    return False


# ============================================================================
# MAIN EXTRACTION FUNCTION
# ============================================================================

def extract_entities_for_result(result) -> EntityResult:
    """
    Extract entities from an analyzer Result object.
    
    Multi-stage pipeline:
    1. Tokenize filename and parent path
    2. Extract year (separate pipeline)
    3. Match against entity dictionaries (org, person, place)
    4. Apply noise filtering
    5. Normalize and canonicalize
    6. Return EntityResult with confidence
    
    Args:
        result: Analyzer Result object with .path, .label, .confidence
        
    Returns:
        EntityResult with entity, kind, year, confidence, source
    """
    path = result.path if hasattr(result, 'path') else Path(str(result))
    
    # Extract year first (independent pipeline)
    year = extract_year(path)
    
    # Tokenize filename and parent
    filename_tokens = tokenize_path_component(path.stem)
    parent_tokens = tokenize_path_component(path.parent.name) if path.parent.name != '.' else []
    
    # Remove year patterns from tokens for cleaner entity matching
    filename_no_year = strip_year_suffix(path.stem)
    parent_no_year = strip_year_suffix(path.parent.name) if path.parent.name != '.' else ""
    
    filename_tokens_clean = tokenize_path_component(filename_no_year)
    parent_tokens_clean = tokenize_path_component(parent_no_year)
    
    # Try to match entities (priority: parent → filename)
    candidates: List[Tuple[str, str, str, float]] = []  # (entity, kind, source, score)
    
    # Check parent folder first (higher priority)
    for token in parent_tokens_clean:
        if is_junk_token(token):
            continue
        
        # Try each dictionary
        if entity := match_entity_in_token(token, ORG_ENTITIES):
            candidates.append((entity, "org", "parent", 2.0))
        
        if entity := match_entity_in_token(token, PERSON_ENTITIES):
            candidates.append((entity, "person", "parent", 2.0))
        
        if entity := match_entity_in_token(token, PLACE_ENTITIES):
            candidates.append((entity, "place", "parent", 1.8))
    
    # Check filename (lower priority)
    for token in filename_tokens_clean:
        if is_junk_token(token):
            continue
        
        if entity := match_entity_in_token(token, ORG_ENTITIES):
            candidates.append((entity, "org", "filename", 1.5))
        
        if entity := match_entity_in_token(token, PERSON_ENTITIES):
            candidates.append((entity, "person", "filename", 1.5))
        
        if entity := match_entity_in_token(token, PLACE_ENTITIES):
            candidates.append((entity, "place", "filename", 1.3))
    
    # No entities found
    if not candidates:
        return EntityResult(
            domain="",
            kind="none",
            entity="",
            year=year,
            confidence=0.0,
            source="none",
        )
    
    # Sort by score and pick best
    candidates.sort(key=lambda x: x[3], reverse=True)
    best_entity, best_kind, best_source, best_score = candidates[0]
    
    # Canonicalize entity
    canonical_entity = canonicalize_entity(best_entity)
    
    # Calculate confidence (0.0-1.0)
    confidence = min(best_score / 3.0, 1.0)  # Normalize to 0-1 range
    
    return EntityResult(
        domain="",  # Reserved for future use
        kind=best_kind,
        entity=canonical_entity,
        year=year,
        confidence=confidence,
        source=best_source,
    )


def tokenize_path_component(component: str) -> List[str]:
    """
    Tokenize a path component (filename or folder name).
    
    Splits on: spaces, underscores, dashes, dots
    Returns lowercase tokens.
    """
    if not component:
        return []
    
    # Split on separators
    tokens = re.split(r'[_\-\.\s]+', component)
    
    # Clean and filter
    cleaned = []
    for token in tokens:
        token = token.strip()
        if token and len(token) > 0:
            cleaned.append(token.lower())
    
    return cleaned


# ============================================================================
# BATCH PROCESSING
# ============================================================================

def extract_entities_from_results(results) -> List[EntityResult]:
    """
    Batch process multiple results.
    
    Args:
        results: Iterable of Result objects
        
    Returns:
        List of EntityResult objects
    """
    return [extract_entities_for_result(r) for r in results]


def aggregate_entity_counts(entity_results: List[EntityResult]) -> Dict[str, Dict[str, any]]:
    """
    Aggregate entity counts for Entities.csv export.
    
    Returns:
        Dict mapping entity_name → {kind, count, example_paths}
    """
    aggregated: Dict[str, Dict[str, any]] = {}
    
    for er in entity_results:
        if not er.entity or er.kind == "none":
            continue
        
        if er.entity not in aggregated:
            aggregated[er.entity] = {
                "kind": er.kind,
                "count": 0,
                "example_paths": [],
            }
        
        aggregated[er.entity]["count"] += 1
        
        # Keep up to 5 example paths
        if len(aggregated[er.entity]["example_paths"]) < 5:
            # Get source path if available
            # Note: We'd need to pass result.path here, but for now skip
            pass
    
    return aggregated
