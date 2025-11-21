"""
Siftwise strategy layer - intelligent file organization planning.

This package sits between analyze and execute, providing:
- Confidence-based action decisions
- Rule-based overrides
- Entity extraction and grouping
- Target path computation
- Search and discovery tools

Main entry point: planner.build_plan()
"""

from .planner import (
    build_plan,
    replan_residuals,
    get_plan_summary,
)

from .entities import (
    extract_entities_for_result,
    extract_entities_from_paths,
    suggest_entity_folders,
)

from .rules_engine import (
    load_rules,
    apply_rules,
    get_builtin_rules,
    validate_rules,
    create_rule_from_search,
)

from .preserve import compute_preserve_mode

from .search import (
    search_mapping,
    search_by_pattern,
    search_residuals,
    search_by_confidence,
    group_by_entity,
    search_and_suggest_rule,
    get_search_stats,
)

__all__ = [
    # Main planner
    'build_plan',
    'replan_residuals',
    'get_plan_summary',

    # Entity extraction
    'extract_entities_for_result',
    'extract_entities_from_paths',
    'suggest_entity_folders',

    # Rules engine
    'load_rules',
    'apply_rules',
    'get_builtin_rules',
    'validate_rules',
    'create_rule_from_search',

    # Search
    'search_mapping',
    'search_by_pattern',
    'search_residuals',
    'search_by_confidence',
    'group_by_entity',
    'search_and_suggest_rule',
    'get_search_stats',
]