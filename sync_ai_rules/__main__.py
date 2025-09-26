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


def main():
    """Main entry point."""
    # Find project root
    project_root = find_project_root()
    rules_dir = os.path.join(project_root, ".cursor", "rules")

    if not os.path.exists(rules_dir):
        print(f"Error: Rules directory not found: {rules_dir}")
        sys.exit(1)

    print(f"Syncing rules from: {rules_dir}")

    # Initialize plugin manager
    script_dir = os.path.dirname(os.path.abspath(__file__))
    plugin_manager = PluginManager()
    plugin_manager.load_plugins(script_dir)

    # Scan for rules using available parsers
    rules = []
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
                "relative_path": os.path.relpath(file_path, project_root),
                "category": get_category(file_path, rules_dir),
            }

            # Parse the rule
            rule = parser.parse(file_path, context)
            if rule:
                rules.append(rule)

    if not rules:
        print("No rules found to sync")
        return

    # Group rules by category
    grouped_rules = group_rules_by_category(rules)

    # Get markdown generator
    generator = plugin_manager.get_generator("markdown")
    if not generator:
        print("Error: Markdown generator not found")
        sys.exit(1)

    # Generate content
    content = generator.generate(grouped_rules, {})

    # Print summary
    total_rules = sum(len(rules) for rules in grouped_rules.values())
    print(f"\nFound {total_rules} rules in {len(grouped_rules)} categories")

    # Update output files using generator's default filenames
    output_files = [
        os.path.join(project_root, filename) for filename in generator.default_filenames
    ]

    for file_path in output_files:
        success, message = update_documentation_file(
            file_path, content, generator.get_section_markers()
        )

        if success:
            print(f"✓ {message}")
        else:
            print(f"✗ {message}")

    print("\n✓ Rules synchronization completed!")


if __name__ == "__main__":
    main()
