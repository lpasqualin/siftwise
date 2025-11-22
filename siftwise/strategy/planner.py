"""
Siftwise Strategy Layer - Planner v2.0 (Phase 2 Integration)

Implements:
- 7-Step Routing Algorithm (Spec A)
- Entity Extraction Pipeline (Spec C)
- Structure Preservation ON/OFF/SMART (Spec B v1)
- Multi-Pass Intelligence scaffolding (Spec D)

This file is a stable, spec-aligned planner for Siftwise v1.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Iterable, Tuple
import re
from datetime import datetime

from siftwise.schemas import FileResult, RoutingDecision
from siftwise.strategy.rules_engine import load_rules, apply_rules


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
    candidates = []

    # Priority 1: Immediate parent folder
    if source_path.parent.name:
        candidates.append({"text": source_path.parent.name, "source": "parent", "position": 0})

    # Priority 2: Filename
    candidates.append({"text": source_path.stem, "source": "filename", "position": 1})

    scored = []
    for cand in candidates:
        norm = normalize_segment(cand["text"])
        if not norm:
            continue
        if is_junk(norm):
            continue

        score = score_entity_candidate(norm, cand["source"], cand["position"])
        if score > 0:
            scored.append({"text": norm, "score": score})

    if not scored:
        return None, 0.0

    scored.sort(key=lambda x: x["score"], reverse=True)
    winner = scored[0]

    if winner["score"] < ENTITY_MIN_SCORE:
        return None, winner["score"] / ENTITY_MIN_SCORE

    canonical = canonicalize_entity(winner["text"])
    confidence = min(winner["score"] / 5.0, 1.0)
    return canonical, confidence


def normalize_segment(text: str) -> str:
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_junk(text: str) -> bool:
    if len(text) < 2:
        return True

    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if not tokens:
        return True

    if all(t in JUNK_WORDS for t in tokens):
        return True

    if text.lower() in GENERIC_CATEGORIES:
        return True

    if re.match(r"^(19|20)\d{2}$", text):
        return True

    return False


def score_entity_candidate(text: str, source: str, position: int) -> float:
    score = 0.0

    if source == "parent":
        score += 2.0
    elif source == "filename":
        score += 1.0

    if re.search(r"[a-z][A-Z]", text):
        score += 1.0

    if re.search(r"\b\d{3,5}\b.*[a-zA-Z]{3,}", text):
        score += 2.0

    if text and text[0].isupper():
        score += 0.8

    return max(score, 0.0)


def canonicalize_entity(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    text = text.strip(".-_")
    if text.islower():
        text = text.title()
    return text


# ============================================================================
# ROUTING ENGINE (Spec A - 7 Steps)
# ============================================================================

def route_file(
    result: FileResult,
    root: Optional[Path] = None,
    rules: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    7-Step Routing Algorithm with Rules Integration.
    Returns routing result with Domain, Kind, Entity, Year, etc.
    """
    path = result.path
    label = result.label
    confidence = result.confidence

    tokens, parent_tokens = extract_tokens(path, root)

    domain = choose_domain(label, tokens, parent_tokens)
    kind = choose_kind(label, tokens, path.suffix)

    entity, entity_conf = extract_entity(path, tokens, parent_tokens)
    if entity_conf < 0.75:
        entity = None

    year = extract_year(path)
    prefix = build_prefix(domain, kind, entity, year)

    # Determine action (strategy layer owns this)
    action, is_residual = determine_action(confidence, result.is_residual, label)

    # Apply rules if provided
    if rules:
        entities_list = [entity] if entity else []
        domain_override, action_override = apply_rules(
            result=result,
            current_label=domain or "Archive",
            current_action=action,
            entities=entities_list,
            rules=rules
        )
        if domain_override != (domain or "Archive"):
            domain = domain_override
        if action_override:
            action = action_override

    why = build_why(domain, kind, entity, year, label, tokens)

    if rules and domain_override:
        why += " [rules applied]"

    return {
        "source_path": str(path),
        "domain": domain,
        "kind": kind,
        "entity": entity,
        "year": year,
        "semantic_prefix": str(prefix) if prefix else "",
        "confidence": confidence,
        "action": action,
        "is_residual": is_residual,
        "why": why,
    }


def extract_tokens(path: Path, root: Optional[Path]) -> Tuple[List[str], List[str]]:
    filename_tokens = re.findall(r"[a-z0-9]+", path.stem.lower())

    parent_tokens: List[str] = []
    if root:
        try:
            rel = path.parent.relative_to(root)
            for part in rel.parts:
                parent_tokens.extend(re.findall(r"[a-z0-9]+", part.lower()))
        except ValueError:
            pass

    return filename_tokens, parent_tokens


def choose_domain(label: str, tokens: List[str], parent_tokens: List[str]) -> Optional[str]:
    scores = {d: 0.0 for d in DOMAINS}

    for prefix, dom in LABEL_TO_DOMAIN.items():
        if label.startswith(prefix):
            scores[dom] += 0.7

    for token in tokens + parent_tokens:
        if token in DOMAIN_HINTS:
            dom, boost = DOMAIN_HINTS[token]
            scores[dom] += boost

    best_dom, best_score = max(scores.items(), key=lambda x: x[1])
    return best_dom if best_score >= 0.4 else "Archive"


def choose_kind(label: str, tokens: List[str], extension: str) -> Optional[str]:
    scores = {k: 0.0 for k in KINDS}

    if label in LABEL_TO_KIND:
        scores[LABEL_TO_KIND[label]] += 0.8

    for token in tokens:
        if token in KIND_HINTS:
            knd, boost = KIND_HINTS[token]
            scores[knd] += boost

    ext = extension.lower()
    if ext in [".jpg", ".png", ".jpeg", ".gif", ".heic"]:
        scores["Photos"] += 0.7
    elif ext in [".mp4", ".mov", ".mkv", ".avi"]:
        scores["Videos"] += 0.7
    elif ext in [".mp3", ".wav", ".m4a", ".flac"]:
        scores["Audio"] += 0.7
    elif ext in [".pdf", ".docx", ".doc", ".txt", ".rtf"]:
        scores["Documents"] += 0.4

    best_kind, best_score = max(scores.items(), key=lambda x: x[1])
    return best_kind if best_score >= 0.3 else "Documents"


def extract_year(path: Path) -> Optional[int]:
    current_year = datetime.now().year
    pattern = re.compile(r"\b(19\d{2}|20\d{2})\b")

    matches = pattern.findall(path.stem)
    for match in reversed(matches):
        year = int(match)
        if 1990 <= year <= current_year + 1:
            return year

    matches = pattern.findall(str(path.parent))
    for match in reversed(matches):
        year = int(match)
        if 1990 <= year <= current_year + 1:
            return year

    return None


def build_prefix(domain: Optional[str], kind: Optional[str], entity: Optional[str], year: Optional[int]) -> Optional[Path]:
    segments: List[str] = []
    if domain:
        segments.append(domain)
    if kind:
        segments.append(kind)
    if entity:
        segments.append(entity)
    if year:
        segments.append(str(year))

    return Path(*segments) if segments else None


def determine_action(confidence: float, is_residual: bool, label: str = "") -> Tuple[str, bool]:
    """
    Determine action and residual status based on confidence.

    Strategy layer owns this logic - analyzer just classifies.

    IMPORTANT: The analyzer determines residual status. Strategy layer only
    decides the ACTION based on confidence. Don't re-mark non-residuals as residuals!
    """
    # Residuals always skip (analyzer marked them)
    if is_residual:
        return "Skip", True

    # Special handling for empty/large files
    if label in ["empty_files", "large_files"]:
        return "Suggest", False

    # Confidence-based actions for NON-residuals
    # Note: is_residual stays False even if we Skip due to low confidence
    if confidence >= 0.85:
        return "Move", False
    elif confidence >= 0.75:
        return "Suggest", False
    else:
        # Low confidence: Skip but DON'T mark as residual
        # The analyzer already decided this wasn't residual
        return "Skip", False

    # Special handling for empty/large files
    if label in ["empty_files", "large_files"]:
        return "Suggest", False

    # Confidence-based actions
    if confidence >= 0.85:
        return "Move", False
    elif confidence >= 0.75:
        return "Suggest", False
    else:
        return "Skip", True


def build_why(domain, kind, entity, year, label, tokens) -> str:
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
# STRUCTURE PRESERVATION (Spec B v1)
# ============================================================================

SMART_MIN_COHERENCE = 0.60
SMART_MIN_FILES = 2


def compute_folder_coherence(mapping_rows: List[Dict[str, Any]], scan_root: Optional[Path]) -> Dict[Path, float]:
    if not scan_root:
        return {}

    folder_counts: Dict[Path, Dict[Tuple[str, str], int]] = {}
    folder_totals: Dict[Path, int] = {}

    for row in mapping_rows:
        src_str = row.get("SourcePath") or row.get("source_path")
        if not src_str:
            continue
        src = Path(src_str)

        try:
            rel_folder = src.parent.relative_to(scan_root)
        except ValueError:
            continue

        dom = row.get("Domain") or row.get("domain") or "Archive"
        kind = row.get("Kind") or row.get("kind") or "Documents"
        key = (dom, kind)

        folder_counts.setdefault(rel_folder, {})
        folder_counts[rel_folder][key] = folder_counts[rel_folder].get(key, 0) + 1
        folder_totals[rel_folder] = folder_totals.get(rel_folder, 0) + 1

    coherence: Dict[Path, float] = {}
    for folder, counts in folder_counts.items():
        total = folder_totals.get(folder, 0)
        if total <= SMART_MIN_FILES:
            coherence[folder] = 1.0
        else:
            coherence[folder] = max(counts.values()) / total

    return coherence


def build_target_path(
    routed: Dict[str, Any],
    source_path: Path,
    scan_root: Optional[Path],
    preserve_structure: Optional[bool] = None,
    preserve_mode: Optional[str] = None,
    folder_coherence: Optional[Dict[Path, float]] = None,
) -> str:
    prefix_str = routed.get("semantic_prefix") or ""
    prefix = Path(prefix_str) if prefix_str else Path("Unrouted")
    filename = source_path.name

    # Back-compat resolution
    if preserve_mode is None:
        if preserve_structure is None:
            preserve_mode = "ON"
        else:
            preserve_mode = "ON" if preserve_structure else "OFF"

    preserve_mode = str(preserve_mode).upper().strip()

    if not scan_root:
        preserve_mode = "OFF"

    if preserve_mode == "OFF":
        return str(prefix / filename)

    try:
        relative_subpath = source_path.parent.relative_to(scan_root)
    except Exception:
        relative_subpath = None

    rel_part = None if (not relative_subpath or relative_subpath == Path(".")) else relative_subpath

    if preserve_mode == "SMART":
        if rel_part is None or folder_coherence is None:
            return str(prefix / filename)
        coherence = folder_coherence.get(rel_part, 0.0)
        return str(prefix / rel_part / filename) if coherence >= SMART_MIN_COHERENCE else str(prefix / filename)

    # ON
    if rel_part is None:
        return str(prefix / filename)
    return str(prefix / rel_part / filename)


# ============================================================================
# MAIN PLANNER FUNCTIONS
# ============================================================================

def build_plan(results: Iterable[FileResult], dest_root: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build complete plan: TreePlan + Mapping rows + stats.
    """
    preserve_structure = config.get("preserve_structure", None)
    preserve_mode = config.get("preserve_structure_mode", None)
    scan_root = config.get("scan_root")
    pass_id = config.get("pass_id", 1)

    # Load rules if enabled
    rules = None
    if config.get("use_rules") and config.get("rules_path"):
        rules = load_rules(config["rules_path"])
        if rules:
            print(f"[sift][strategy] Loaded {len(rules.get('rules', []))} rules")

    mapping_rows: List[Dict[str, Any]] = []

    for result in results:
        routed = route_file(result, scan_root, rules)
        source_path = Path(routed["source_path"])

        target_path = build_target_path(
            routed,
            source_path,
            scan_root,
            preserve_structure=preserve_structure,
            preserve_mode=preserve_mode,
            folder_coherence=None,
        )

        # Create RoutingDecision object
        decision = RoutingDecision(
            source_path=routed["source_path"],
            domain=routed["domain"],
            kind=routed["kind"],
            entity=routed["entity"],
            year=routed["year"],
            target_path=target_path,
            confidence=routed["confidence"],
            action=routed["action"],
            is_residual=routed["is_residual"],
            why=routed["why"],
            pass_id=pass_id,
        )

        # Convert to CSV row dict
        row = decision.to_csv_row()
        mapping_rows.append(row)

    # SMART recompute (coherence needs full mapping)
    if (preserve_mode or "").upper() == "SMART":
        folder_coherence = compute_folder_coherence(mapping_rows, scan_root)
        for row in mapping_rows:
            sp = Path(row["SourcePath"])
            routed_stub = {
                "semantic_prefix": str(
                    build_prefix(
                        row.get("Domain") or None,
                        row.get("Kind") or None,
                        row.get("Entity") or None,
                        int(row["Year"]) if row.get("Year") else None,
                    )
                )
            }
            row["TargetPath"] = build_target_path(
                routed_stub,
                sp,
                scan_root,
                preserve_structure=preserve_structure,
                preserve_mode="SMART",
                folder_coherence=folder_coherence,
            )

    # Very minimal TreePlan
    tree_plan = {
        "root": str(dest_root),
        "root_id": "n_root",
        "nodes": [{"id": "n_root", "name": dest_root.name, "parent": None}],
    }

    stats = {
        "total_files": len(mapping_rows),
        "move_count": sum(1 for r in mapping_rows if r["Action"] == "Move"),
        "suggest_count": sum(1 for r in mapping_rows if r["Action"] == "Suggest"),
        "skip_count": sum(1 for r in mapping_rows if r["Action"] == "Skip"),
        "residual_count": sum(1 for r in mapping_rows if str(r["IsResidual"]) == "True"),
        "residual_percentage": 0.0,
    }
    if stats["total_files"] > 0:
        stats["residual_percentage"] = (stats["residual_count"] / stats["total_files"]) * 100.0

    return {"tree_plan": tree_plan, "mapping_rows": mapping_rows, "stats": stats}


def replan_residuals(
    mapping_rows: List[Dict[str, Any]],
    updated_results: Iterable[FileResult],
    dest_root: Path,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Residual-only refinement pass.
    """
    preserve_structure = config.get("preserve_structure", None)
    preserve_mode = config.get("preserve_structure_mode", None)
    scan_root = config.get("scan_root")
    pass_id = config.get("pass_id", 2)

    # Load rules if enabled
    rules = None
    if config.get("use_rules") and config.get("rules_path"):
        rules = load_rules(config["rules_path"])
        if rules:
            print(f"[sift][strategy] Loaded {len(rules.get('rules', []))} rules")

    def _is_true(v: Any) -> bool:
        return str(v).strip().lower() in ("true", "1", "yes", "y")

    original_by_path = {row["SourcePath"]: row for row in mapping_rows if row.get("SourcePath")}
    updated_mapping: List[Dict[str, Any]] = []

    reclassified = 0
    still_residual = 0

    folder_coherence = None
    if (preserve_mode or "").upper() == "SMART":
        folder_coherence = compute_folder_coherence(mapping_rows, scan_root)

    for result in updated_results:
        source_path = str(result.path)
        original = original_by_path.get(source_path)

        if not original or not _is_true(original.get("IsResidual")):
            continue

        routed = route_file(result, scan_root, rules)

        target_path = build_target_path(
            routed,
            Path(source_path),
            scan_root,
            preserve_structure=preserve_structure,
            preserve_mode=preserve_mode,
            folder_coherence=folder_coherence,
        )

        if routed["is_residual"]:
            still_residual += 1
        else:
            reclassified += 1

        # Create RoutingDecision object
        decision = RoutingDecision(
            source_path=routed["source_path"],
            domain=routed["domain"],
            kind=routed["kind"],
            entity=routed["entity"],
            year=routed["year"],
            target_path=target_path,
            confidence=routed["confidence"],
            action=routed["action"],
            is_residual=routed["is_residual"],
            why=routed["why"],
            pass_id=pass_id,
            previous_pass_id=original.get("PassId", ""),
            previous_action=original.get("Action", ""),
            previous_confidence=original.get("Confidence", ""),
            previous_target_path=original.get("TargetPath", ""),
        )

        # Convert to CSV row dict
        row = decision.to_csv_row()
        updated_mapping.append(row)

    # Add back all non-residual rows unchanged
    for row in mapping_rows:
        if not _is_true(row.get("IsResidual")):
            updated_mapping.append(row)

    stats = {
        "total_files": len(updated_mapping),
        "residual_count": sum(1 for r in updated_mapping if _is_true(r.get("IsResidual"))),
        "reclassified": reclassified,
        "still_residual": still_residual,
    }

    return {"mapping_rows": updated_mapping, "stats": stats}


def get_plan_summary(plan: Dict[str, Any]) -> str:
    stats = plan["stats"]
    lines = [
        f"Total files: {stats.get('total_files', 0)}",
        f"  Move: {stats.get('move_count', 0)}",
        f"  Suggest: {stats.get('suggest_count', 0)}",
        f"  Skip: {stats.get('skip_count', 0)}",
        f"  Residuals: {stats.get('residual_count', 0)} ({stats.get('residual_percentage', 0.0):.1f}%)",
    ]
    return "\n".join(lines)