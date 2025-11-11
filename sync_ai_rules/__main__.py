#!/usr/bin/env python3
"""
This script uses a plugin architecture to parse rules and generate documentation.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List

from sync_ai_rules.core.interfaces import RuleMetadata
from sync_ai_rules.core.plugin_manager import PluginManager
from sync_ai_rules.file_updater import update_documentation_file


def find_project_root() -> str:
    """Find the project root by looking for key indicators."""
    current = Path.cwd()

    # Look for .cursor/rules directory
    for path in [current] + list(current.parents):
        if (path / ".cursor" / "rules").exists():
            return str(path)

    # Fallback to current directory
    return str(current)


def get_category(file_path: str, rules_dir: str) -> str:
    """Get category name from file path."""
    rel_path = os.path.relpath(file_path, rules_dir)
    folder = os.path.dirname(rel_path)

    if not folder or folder == ".":
        return "root"

    return folder


def group_rules_by_category(rules: List[RuleMetadata]) -> Dict[str, List[RuleMetadata]]:
    """Group rules by their category."""
    groups = {}

    for rule in rules:
        category = rule.category
        if category not in groups:
            groups[category] = []
        groups[category].append(rule)

    return groups


def scan_rules_directory(
    rules_dir: str, project_root: str, plugin_manager: PluginManager
) -> List[RuleMetadata]:
    """Scan a directory for rules and parse them."""
    rules = []

    if not os.path.exists(rules_dir):
        return rules

    for root, dirs, files in os.walk(rules_dir):
        # Skip generated and personal directories
        if "generated" in Path(root).parts or "personal" in Path(root).parts:
            continue

        for file in files:
            file_path = os.path.join(root, file)

            # Find appropriate parser
            parser = plugin_manager.get_parser_for_file(file_path)
            if not parser:
                continue

            # Create parsing context
            context = {
                "project_root": project_root,
                "relative_path": os.path.relpath(file_path, project_root),
                "category": get_category(file_path, rules_dir),
            }

            # Parse the rule
            rule = parser.parse(file_path, context)
            if rule:
                rules.append(rule)

    return rules


def main():
    """Main entry point."""
    # Find project root
    project_root = find_project_root()
    cursor_rules_dir = os.path.join(project_root, ".cursor", "rules")
    code_review_dir = os.path.join(project_root, ".code_review")

    if not os.path.exists(cursor_rules_dir) and not os.path.exists(code_review_dir):
        print("Error: Neither .cursor/rules nor .code_review directory found")
        sys.exit(1)

    # Initialize plugin manager
    script_dir = os.path.dirname(os.path.abspath(__file__))
    plugin_manager = PluginManager()
    plugin_manager.load_plugins(script_dir)

    # Scan development rules (.cursor/rules/)
    print(f"Scanning development rules from: {cursor_rules_dir}")
    dev_rules = scan_rules_directory(cursor_rules_dir, project_root, plugin_manager)
    grouped_dev_rules = group_rules_by_category(dev_rules)

    # Scan code review guidelines (.code_review/)
    print(f"Scanning code review guidelines from: {code_review_dir}")
    review_rules = scan_rules_directory(code_review_dir, project_root, plugin_manager)
    grouped_review_rules = group_rules_by_category(review_rules)

    # Print summary
    total_dev_rules = sum(len(rules) for rules in grouped_dev_rules.values())
    total_review_rules = sum(len(rules) for rules in grouped_review_rules.values())
    print(f"\nFound {total_dev_rules} development rules in {len(grouped_dev_rules)} categories")
    print(
        f"Found {total_review_rules} code review guidelines in {len(grouped_review_rules)} categories"
    )

    # Get generators
    dev_generator = plugin_manager.get_generator("development-rules")
    review_generator = plugin_manager.get_generator("code-review-guidelines")

    if not dev_generator or not review_generator:
        print("Error: Required generators not found")
        sys.exit(1)

    # Generate content for both sections
    dev_content = dev_generator.generate(grouped_dev_rules, {}) if dev_rules else None
    review_content = review_generator.generate(grouped_review_rules, {}) if review_rules else None

    # Update output files (both generators use same target files)
    output_files = [
        os.path.join(project_root, filename) for filename in dev_generator.default_filenames
    ]

    for file_path in output_files:
        # Update development rules section
        if dev_content:
            success, message = update_documentation_file(
                file_path, dev_content, dev_generator.get_section_markers()
            )
            if success:
                print(f"✓ Development rules: {message}")
            else:
                print(f"✗ Development rules: {message}")

        # Update code review guidelines section
        if review_content:
            success, message = update_documentation_file(
                file_path, review_content, review_generator.get_section_markers()
            )
            if success:
                print(f"✓ Code review guidelines: {message}")
            else:
                print(f"✗ Code review guidelines: {message}")

    print("\n✓ Rules synchronization completed!")


if __name__ == "__main__":
    main()
