"""
Siftwise Strategy Layer - Planner v2.0 (Phase 2 Integration)

This module implements the complete Phase 2 integration:
- 7-Step Routing Algorithm (Spec A)
- Entity Extraction Pipeline (Spec C)
- Structure Preservation (Spec B)
- Multi-Pass Intelligence (Spec D)

Replaces the old planner.py with spec-compliant routing logic.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Iterable, Tuple
from dataclasses import dataclass
import re
from datetime import datetime


# ============================================================================
# CANONICAL DIMENSIONS (Spec A)
# ============================================================================

DOMAINS = [
    "Personal", "Business", "Work", "Finance", "Projects",
    "Health", "Legal", "Family", "Creative", "Learning",
    "Travel", "Home", "Media", "Software", "Archive"
]

KINDS = [
    "Photos", "Videos", "Audio", "Documents", "Notes", "Records",
    "Receipts", "Invoices", "Statements", "Contracts", "IDs",
    "Reports", "Summaries", "Plans", "Taxes", "Insurance",
    "Assets", "Certificates", "Applications", "Forms",
    "Screenshots", "Exports", "Backups", "Installers"
]

# Domain scoring hints
DOMAIN_HINTS = {
    "invoice": ("Finance", 0.8), "bank": ("Finance", 0.7),
    "statement": ("Finance", 0.7), "receipt": ("Finance", 0.6),
    "tax": ("Finance", 0.8), "payment": ("Finance", 0.6),
    "contract": ("Legal", 0.8), "agreement": ("Legal", 0.8),
    "medical": ("Health", 0.8), "health": ("Health", 0.8),
    "travel": ("Travel", 0.8), "flight": ("Travel", 0.7),
}

# Kind scoring hints
KIND_HINTS = {
    "invoice": ("Invoices", 0.9), "receipt": ("Receipts", 0.9),
    "statement": ("Statements", 0.9), "contract": ("Contracts", 0.9),
    "photo": ("Photos", 0.8), "video": ("Videos", 0.8),
}

# Label mappings
LABEL_TO_DOMAIN = {
    "finance": "Finance", "legal": "Legal", "health": "Health",
    "photo": "Personal", "video": "Media", "audio": "Media",
}

LABEL_TO_KIND = {
    "finance.invoice": "Invoices", "finance.receipt": "Receipts",
    "finance.statement": "Statements", "legal.contract": "Contracts",
    "photo": "Photos", "video": "Videos", "audio": "Audio",
}


# ============================================================================
# ENTITY EXTRACTION (Spec C)
# ============================================================================

JUNK_WORDS = {
    "copy", "copyof", "final", "new", "scan", "export", "backup",
    "old", "misc", "temp", "documents", "docs", "files", "folder",
    "downloads", "desktop", "archive"
}

GENERIC_CATEGORIES = {
    "invoices", "receipts", "statements", "contracts",
    "photos", "videos", "documents", "reports"
}

ENTITY_MIN_SCORE = 2.0


def extract_entity(source_path: Path, tokens: List[str], parent_tokens: List[str]) -> Tuple[Optional[str], float]:
    """
    Entity Extraction Pipeline (5 steps from Spec C).

    Returns: (entity_string | None, confidence)
    """
    # Step 0: Build candidate pool
    candidates = []

    # Priority 1: Immediate parent folder
    if source_path.parent.name:
        candidates.append({
            'text': source_path.parent.name,
            'source': 'parent',
            'position': 0
        })

    # Priority 2: Filename
    candidates.append({
        'text': source_path.stem,
        'source': 'filename',
        'position': 1
    })

    # Process candidates
    scored = []
    for cand in candidates:
        # Step 1: Normalize
        norm = normalize_segment(cand['text'])
        if not norm:
            continue

        # Step 2: Hard junk filter
        if is_junk(norm):
            continue

        # Step 3: Score
        score = score_entity_candidate(norm, cand['source'], cand['position'])
        if score > 0:
            scored.append({'text': norm, 'score': score})

    # Step 4: Choose winner
    if not scored:
        return None, 0.0

    scored.sort(key=lambda x: x['score'], reverse=True)
    winner = scored[0]

    if winner['score'] < ENTITY_MIN_SCORE:
        return None, winner['score'] / ENTITY_MIN_SCORE

    # Step 5: Canonicalize
    canonical = canonicalize_entity(winner['text'])
    confidence = min(winner['score'] / 5.0, 1.0)

    return canonical, confidence


def normalize_segment(text: str) -> str:
    """Step 1: Normalize segment."""
    text = text.replace('_', ' ').replace('-', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def is_junk(text: str) -> bool:
    """Step 2: Hard junk filter."""
    if len(text) < 2:
        return True

    tokens = re.findall(r'[a-z0-9]+', text.lower())
    if not tokens:
        return True

    if all(t in JUNK_WORDS for t in tokens):
        return True

    if text.lower() in GENERIC_CATEGORIES:
        return True

    if re.match(r'^(19|20)\d{2}$', text):  # Pure year
        return True

    return False


def score_entity_candidate(text: str, source: str, position: int) -> float:
    """Step 3: Score candidate."""
    score = 0.0

    # Base score from position
    if source == 'parent':
        score += 2.0
    elif source == 'filename':
        score += 1.0

    # Boost for CamelCase/TitleCase
    if re.search(r'[a-z][A-Z]', text):
        score += 1.0

    # Boost for address-like (numbers + words)
    if re.search(r'\b\d{3,5}\b.*[a-zA-Z]{3,}', text):
        score += 2.0

    # Boost for capitalized words
    if text and text[0].isupper():
        score += 0.8

    return max(score, 0.0)


def canonicalize_entity(text: str) -> str:
    """Step 5: Canonicalize entity string."""
    text = re.sub(r'\s+', ' ', text.strip())
    text = text.strip('.-_')

    if text.islower():
        text = text.title()

    return text


# ============================================================================
# ROUTING ENGINE (Spec A - 7 Steps)
# ============================================================================

def route_file(result, root: Optional[Path] = None) -> Dict[str, Any]:
    """
    7-Step Routing Algorithm.

    Returns routing result with Domain, Kind, Entity, Year, etc.
    """
    # Extract path and basic info
    path = result.path if hasattr(result, 'path') else Path(str(result))
    label = result.label if hasattr(result, 'label') else ""
    confidence = result.confidence if hasattr(result, 'confidence') else 0.0

    # Step 0: Collect signals
    tokens, parent_tokens = extract_tokens(path, root)

    # Step 1: Choose Domain
    domain = choose_domain(label, tokens, parent_tokens)

    # Step 2: Choose Kind
    kind = choose_kind(label, tokens, path.suffix)

    # Step 3: Extract Entity
    entity, entity_conf = extract_entity(path, tokens, parent_tokens)
    if entity_conf < 0.75:
        entity = None

    # Step 4: Extract Year
    year = extract_year(path)

    # Step 5: Build semantic prefix
    prefix = build_prefix(domain, kind, entity, year)

    # Step 6: Determine action and residual status
    action, is_residual = determine_action(confidence)

    # Step 7: Build why string
    why = build_why(domain, kind, entity, year, label, tokens)

    return {
        'source_path': str(path),
        'domain': domain,
        'kind': kind,
        'entity': entity,
        'year': year,
        'semantic_prefix': str(prefix) if prefix else "",
        'confidence': confidence,
        'action': action,
        'is_residual': is_residual,
        'why': why,
    }


def extract_tokens(path: Path, root: Optional[Path]) -> Tuple[List[str], List[str]]:
    """Extract filename and parent tokens."""
    filename_tokens = re.findall(r'[a-z0-9]+', path.stem.lower())

    parent_tokens = []
    if root:
        try:
            rel = path.parent.relative_to(root)
            for part in rel.parts:
                parent_tokens.extend(re.findall(r'[a-z0-9]+', part.lower()))
        except ValueError:
            pass

    return filename_tokens, parent_tokens


def choose_domain(label: str, tokens: List[str], parent_tokens: List[str]) -> Optional[str]:
    """Step 1: Choose domain."""
    scores = {d: 0.0 for d in DOMAINS}

    # Score from label
    for prefix, domain in LABEL_TO_DOMAIN.items():
        if label.startswith(prefix):
            scores[domain] += 0.7

    # Score from tokens
    for token in tokens + parent_tokens:
        if token in DOMAIN_HINTS:
            domain, boost = DOMAIN_HINTS[token]
            scores[domain] += boost

    best = max(scores.items(), key=lambda x: x[1])
    return best[0] if best[1] >= 0.4 else "Archive"


def choose_kind(label: str, tokens: List[str], extension: str) -> Optional[str]:
    """Step 2: Choose kind."""
    scores = {k: 0.0 for k in KINDS}

    # Score from label
    if label in LABEL_TO_KIND:
        scores[LABEL_TO_KIND[label]] += 0.8

    # Score from tokens
    for token in tokens:
        if token in KIND_HINTS:
            kind, boost = KIND_HINTS[token]
            scores[kind] += boost

    # Score from extension
    ext = extension.lower()
    if ext in [".jpg", ".png"]:
        scores["Photos"] += 0.7
    elif ext in [".mp4", ".mov"]:
        scores["Videos"] += 0.7
    elif ext in [".pdf", ".docx"]:
        scores["Documents"] += 0.4

    best = max(scores.items(), key=lambda x: x[1])
    return best[0] if best[1] >= 0.3 else "Documents"


def extract_year(path: Path) -> Optional[int]:
    """Step 4: Extract year."""
    current_year = datetime.now().year
    pattern = re.compile(r'\b(19\d{2}|20\d{2})\b')

    # Try filename first
    matches = pattern.findall(path.stem)
    for match in reversed(matches):
        year = int(match)
        if 1990 <= year <= current_year + 1:
            return year

    # Try parent path
    matches = pattern.findall(str(path.parent))
    for match in reversed(matches):
        year = int(match)
        if 1990 <= year <= current_year + 1:
            return year

    return None


def build_prefix(domain: Optional[str], kind: Optional[str],
                 entity: Optional[str], year: Optional[int]) -> Optional[Path]:
    """Step 5: Build semantic prefix."""
    segments = []
    if domain:
        segments.append(domain)
    if kind:
        segments.append(kind)
    if entity:
        segments.append(entity)
    if year:
        segments.append(str(year))

    return Path(*segments) if segments else None


def determine_action(confidence: float) -> Tuple[str, bool]:
    """Step 6: Determine action and residual status."""
    if confidence >= 0.85:
        return "Move", False
    elif confidence >= 0.75:
        return "Suggest", True
    elif confidence >= 0.60:
        return "Skip", True
    else:
        return "Skip", False


def build_why(domain, kind, entity, year, label, tokens) -> str:
    """Step 7: Build explanation string."""
    parts = []
    if domain:
        parts.append(f"Domain={domain}")
    if kind:
        parts.append(f"Kind={kind}")
    if entity:
        parts.append(f"Entity={entity}")
    if year:
        parts.append(f"Year={year}")
    return ", ".join(parts) if parts else "No clear classification"


# ============================================================================
# STRUCTURE PRESERVATION (Spec B)
# ============================================================================

def build_target_path(routed: Dict, source_path: Path, scan_root: Optional[Path],
                      preserve_structure: bool) -> str:
    """
    Apply structure preservation logic.

    - ON (preserve=True): prefix / relative_subpath / filename
    - OFF (preserve=False): prefix / filename
    """
    prefix_str = routed['semantic_prefix']
    prefix = Path(prefix_str) if prefix_str else Path("Unrouted")
    filename = source_path.name

    if preserve_structure and scan_root:
        try:
            relative_subpath = source_path.parent.relative_to(scan_root)
            if relative_subpath == Path("."):
                target = prefix / filename
            else:
                target = prefix / relative_subpath / filename
        except (ValueError, AttributeError):
            target = prefix / filename
    else:
        target = prefix / filename

    return str(target)


# ============================================================================
# MAIN PLANNER FUNCTIONS
# ============================================================================

def build_plan(results: Iterable, dest_root: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point: Build complete execution plan.

    Implements full Phase 2 integration.
    """
    preserve_structure = config.get('preserve_structure', True)
    scan_root = config.get('scan_root')
    pass_id = config.get('pass_id', 1)

    mapping_rows = []
    nodes = set()

    for result in results:
        # Route file
        routed = route_file(result, scan_root)

        # Build target path
        source_path = Path(routed['source_path'])
        target_path = build_target_path(routed, source_path, scan_root, preserve_structure)

        # Create mapping row
        row = {
            'SourcePath': routed['source_path'],
            'Domain': routed['domain'] or "",
            'Kind': routed['kind'] or "",
            'Entity': routed['entity'] or "",
            'Year': str(routed['year']) if routed['year'] else "",
            'TargetPath': target_path,
            'Confidence': f"{routed['confidence']:.2f}",
            'Action': routed['action'],
            'IsResidual': str(routed['is_residual']),
            'Why': routed['why'],
            'PassId': str(pass_id),
            'PreviousPassId': "",
            'PreviousAction': "",
            'PreviousConfidence': "",
            'PreviousTargetPath': "",
        }

        mapping_rows.append(row)

        # Track nodes
        if routed['domain']:
            nodes.add(routed['domain'])

    # Build tree plan
    tree_plan = {
        'root': str(dest_root),
        'root_id': 'n_root',
        'nodes': [{'id': 'n_root', 'name': dest_root.name, 'parent': None}]
    }

    # Calculate stats
    stats = {
        'total_files': len(mapping_rows),
        'move_count': sum(1 for r in mapping_rows if r['Action'] == 'Move'),
        'suggest_count': sum(1 for r in mapping_rows if r['Action'] == 'Suggest'),
        'skip_count': sum(1 for r in mapping_rows if r['Action'] == 'Skip'),
        'residual_count': sum(1 for r in mapping_rows if r['IsResidual'] == 'True'),
        'residual_percentage': 0.0,
    }

    if stats['total_files'] > 0:
        stats['residual_percentage'] = (stats['residual_count'] / stats['total_files']) * 100

    return {
        'tree_plan': tree_plan,
        'mapping_rows': mapping_rows,
        'stats': stats
    }


def replan_residuals(mapping_rows: List[Dict], updated_results: Iterable,
                     dest_root: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Refinement pass for residuals (Multi-Pass Intelligence).
    """
    preserve_structure = config.get('preserve_structure', True)
    scan_root = config.get('scan_root')
    pass_id = config.get('pass_id', 2)

    original_by_path = {row['SourcePath']: row for row in mapping_rows}
    updated_mapping = []
    reclassified = 0
    still_residual = 0

    for result in updated_results:
        source_path = str(result.path if hasattr(result, 'path') else result)
        original = original_by_path.get(source_path)

        if not original or original.get('IsResidual') != 'True':
            if original:
                updated_mapping.append(original)
            continue

        # Re-route
        routed = route_file(result, scan_root)
        target_path = build_target_path(routed, Path(source_path), scan_root, preserve_structure)

        # Track changes
        if routed['is_residual']:
            still_residual += 1
        else:
            reclassified += 1

        # Build row with history
        row = {
            'SourcePath': routed['source_path'],
            'Domain': routed['domain'] or "",
            'Kind': routed['kind'] or "",
            'Entity': routed['entity'] or "",
            'Year': str(routed['year']) if routed['year'] else "",
            'TargetPath': target_path,
            'Confidence': f"{routed['confidence']:.2f}",
            'Action': routed['action'],
            'IsResidual': str(routed['is_residual']),
            'Why': routed['why'],
            'PassId': str(pass_id),
            'PreviousPassId': original.get('PassId', '1'),
            'PreviousAction': original.get('Action', ''),
            'PreviousConfidence': original.get('Confidence', ''),
            'PreviousTargetPath': original.get('TargetPath', ''),
        }

        updated_mapping.append(row)

    # Add non-residuals back
    for row in mapping_rows:
        if row.get('IsResidual') != 'True':
            if not any(r['SourcePath'] == row['SourcePath'] for r in updated_mapping):
                updated_mapping.append(row)

    stats = {
        'total_files': len(updated_mapping),
        'residual_count': sum(1 for r in updated_mapping if r['IsResidual'] == 'True'),
        'reclassified': reclassified,
        'still_residual': still_residual,
    }

    return {
        'mapping_rows': updated_mapping,
        'stats': stats
    }


def get_plan_summary(plan: Dict[str, Any]) -> str:
    """Generate human-readable summary."""
    stats = plan['stats']
    lines = [
        f"Total files: {stats['total_files']}",
        f"  Move: {stats.get('move_count', 0)}",
        f"  Suggest: {stats.get('suggest_count', 0)}",
        f"  Skip: {stats.get('skip_count', 0)}",
        f"  Residuals: {stats['residual_count']} ({stats.get('residual_percentage', 0):.1f}%)",
    ]
    return "\n".join(lines)
