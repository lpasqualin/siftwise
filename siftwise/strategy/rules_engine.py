"""
Rules engine for Siftwise.

Provides a flexible system for applying user-defined rules that can override
analyzer decisions. V1 is simple but extensible to support YAML/JSON rules.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import re


def load_rules(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load rules from a YAML/JSON configuration file.

    V1: Returns empty dict if no config or file doesn't exist.
    Future: Parse YAML with rules like:
        - pattern: "*/ADP/*"
          label: "payroll"
          action: "Move"
          target_folder: "Vendors/ADP"
        - extension: ".kdbx"
          action: "Skip"
          reason: "Password database - do not move"

    Args:
        config_path: Path to rules.yaml or rules.json (optional)

    Returns:
        Dict with rules configuration, or empty dict if no rules
    """
    if config_path is None:
        return {}

    if not config_path.exists():
        return {}

    # V1: Just return empty dict
    # Future: Parse YAML/JSON and return structured rules
    try:
        import yaml
        with config_path.open('r', encoding='utf-8') as f:
            rules = yaml.safe_load(f)
            return rules if rules else {}
    except ImportError:
        # YAML not available, try JSON
        try:
            import json
            with config_path.open('r', encoding='utf-8') as f:
                rules = json.load(f)
                return rules if rules else {}
        except Exception:
            return {}
    except Exception:
        return {}


def apply_rules(
        result,
        current_label: str,
        current_action: Optional[str],
        entities: List[str],
        rules: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Optional[str]]:
    """
    Apply rules to potentially override label and/or action.

    Args:
        result: Analyzer Result object (has path, confidence, etc.)
        current_label: Label assigned by analyzer
        current_action: Action assigned by analyzer/planner
        entities: List of extracted entities
        rules: Rules dict from load_rules()

    Returns:
        Tuple of (final_label, action_override)
        - final_label: Either current_label or overridden label
        - action_override: None if no override, or new action string
    """
    if not rules or not rules.get('rules'):
        # No rules to apply
        return current_label, None

    path = result.path
    path_str = str(path)

    # Apply rules in order (first match wins, or use priority field)
    rule_list = rules.get('rules', [])

    for rule in rule_list:
        if _rule_matches(rule, path, path_str, current_label, entities):
            # Apply the rule
            new_label = rule.get('label', current_label)
            new_action = rule.get('action')  # None if not specified

            # Optionally log why rule was applied
            if hasattr(result, 'why') and rule.get('reason'):
                # Could modify result.why here if we want
                pass

            return new_label, new_action

    # No rules matched
    return current_label, None


def _rule_matches(
        rule: Dict[str, Any],
        path: Path,
        path_str: str,
        current_label: str,
        entities: List[str],
) -> bool:
    """
    Check if a rule matches the given file.

    Rules can specify multiple conditions:
    - pattern: glob or regex pattern for path
    - extension: file extension (e.g., ".kdbx")
    - label: only apply if current label matches
    - entity: only apply if specific entity is present
    - min_confidence: only apply if confidence >= threshold
    """
    # Check extension match
    if 'extension' in rule:
        required_ext = rule['extension']
        if not required_ext.startswith('.'):
            required_ext = '.' + required_ext
        if path.suffix.lower() != required_ext.lower():
            return False

    # Check pattern match (glob-style)
    if 'pattern' in rule:
        pattern = rule['pattern']
        # Convert glob to regex for matching
        if '*' in pattern or '?' in pattern:
            # Simple glob: convert to regex
            regex_pattern = pattern.replace('/', r'\/')
            regex_pattern = regex_pattern.replace('.', r'\.')
            regex_pattern = regex_pattern.replace('*', '.*')
            regex_pattern = regex_pattern.replace('?', '.')
            if not re.search(regex_pattern, path_str, re.IGNORECASE):
                return False
        else:
            # Exact substring match
            if pattern.lower() not in path_str.lower():
                return False

    # Check regex match (more powerful than pattern)
    if 'regex' in rule:
        regex = rule['regex']
        if not re.search(regex, path_str):
            return False

    # Check label match
    if 'if_label' in rule:
        if current_label != rule['if_label']:
            return False

    # Check entity match
    if 'entity' in rule:
        if rule['entity'] not in entities:
            return False

    # Check entity pattern (any entity matches pattern)
    if 'entity_pattern' in rule:
        pattern = rule['entity_pattern']
        if not any(re.search(pattern, entity, re.IGNORECASE) for entity in entities):
            return False

    # All conditions passed
    return True


def create_rule_from_search(
        pattern: str,
        target_label: str,
        target_folder: Optional[str] = None,
        action: str = "Move",
) -> Dict[str, Any]:
    """
    Helper to create a rule dict from search results.

    Useful for the future "search + make rule" feature.

    Args:
        pattern: Search pattern that matched files
        target_label: Label to assign to matching files
        target_folder: Optional specific folder path
        action: Action to take (Move, Suggest, Skip, etc.)

    Returns:
        Dict representing a rule that can be added to rules config
    """
    rule = {
        'pattern': pattern,
        'label': target_label,
        'action': action,
    }

    if target_folder:
        rule['target_folder'] = target_folder

    return rule


def validate_rules(rules: Dict[str, Any]) -> List[str]:
    """
    Validate rules configuration and return list of warnings/errors.

    Args:
        rules: Rules dict from load_rules()

    Returns:
        List of warning/error messages (empty if all valid)
    """
    issues = []

    if not isinstance(rules, dict):
        issues.append("Rules must be a dictionary")
        return issues

    rule_list = rules.get('rules', [])
    if not isinstance(rule_list, list):
        issues.append("'rules' must be a list")
        return issues

    for i, rule in enumerate(rule_list):
        if not isinstance(rule, dict):
            issues.append(f"Rule #{i + 1}: must be a dictionary")
            continue

        # Check for at least one matching condition
        has_condition = any(
            key in rule
            for key in ['pattern', 'regex', 'extension', 'entity', 'entity_pattern']
        )
        if not has_condition:
            issues.append(
                f"Rule #{i + 1}: must have at least one condition "
                "(pattern, regex, extension, entity, entity_pattern)"
            )

        # Check for valid action if specified
        if 'action' in rule:
            valid_actions = {'Move', 'Suggest', 'Skip', 'Copy', 'Delete'}
            if rule['action'] not in valid_actions:
                issues.append(
                    f"Rule #{i + 1}: invalid action '{rule['action']}'. "
                    f"Must be one of: {', '.join(valid_actions)}"
                )

    return issues


def get_builtin_rules() -> Dict[str, Any]:
    """
    Return a set of sensible built-in rules.

    These are always applied unless explicitly disabled.
    """
    return {
        'rules': [
            # Password databases should never be moved automatically
            {
                'extension': '.kdbx',
                'action': 'Skip',
                'reason': 'Password database - manual review required',
            },
            {
                'extension': '.keychain',
                'action': 'Skip',
                'reason': 'Keychain file - manual review required',
            },
            # System files
            {
                'pattern': '*/.DS_Store',
                'action': 'Skip',
                'reason': 'macOS system file',
            },
            {
                'pattern': '*/Thumbs.db',
                'action': 'Skip',
                'reason': 'Windows system file',
            },
            {
                'pattern': '*/desktop.ini',
                'action': 'Skip',
                'reason': 'Windows system file',
            },
        ]
    }