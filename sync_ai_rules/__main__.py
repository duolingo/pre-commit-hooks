#!/usr/bin/env python3
"""
Sync AI Rules - Plugin-based rule parser and documentation generator.
Scans source directories, parses rules, and generates documentation sections.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List

from sync_ai_rules.core.interfaces import RuleMetadata
from sync_ai_rules.core.plugin_manager import PluginManager
from sync_ai_rules.file_updater import update_documentation_file


def find_project_root() -> str:
    """Find project root by looking for .cursor/rules or .code_review directories."""
    current = Path.cwd()

    for path in [current] + list(current.parents):
        if (path / ".cursor" / "rules").exists() or (path / ".code_review").exists():
            return str(path)

    return str(current)


def get_category(file_path: str, source_dir: str) -> str:
    """Extract category from file path relative to source directory."""
    rel_path = os.path.relpath(file_path, source_dir)
    folder = os.path.dirname(rel_path)
    return folder if folder and folder != "." else "root"


def group_by_category(rules: List[RuleMetadata]) -> Dict[str, List[RuleMetadata]]:
    """Group rules by category."""
    groups: Dict[str, List[RuleMetadata]] = {}
    for rule in rules:
        groups.setdefault(rule.category, []).append(rule)
    return groups


def scan_and_parse(parser, source_dir: str, project_root: str) -> List[RuleMetadata]:
    """Scan directory and parse files with given parser."""
    rules = []

    if not os.path.exists(source_dir):
        return rules

    for root, _, files in os.walk(source_dir):
        # Skip generated/personal directories
        if "generated" in Path(root).parts or "personal" in Path(root).parts:
            continue

        for file in files:
            file_path = os.path.join(root, file)

            if not parser.can_parse(file_path):
                continue

            context = {
                "project_root": project_root,
                "relative_path": os.path.relpath(file_path, project_root),
                "category": get_category(file_path, source_dir),
            }

            rule = parser.parse(file_path, context)
            if rule:
                rules.append(rule)

    return rules


def main():
    """Main orchestration: load plugins → parse → generate → update files."""
    # Setup
    project_root = find_project_root()
    script_dir = os.path.dirname(os.path.abspath(__file__))

    plugin_manager = PluginManager()
    plugin_manager.load_plugins(script_dir)

    # Process each parser → generator pair
    results = {}

    for parser in plugin_manager.parsers.values():
        # Get source directories from parser
        source_dirs = parser.source_directories
        if not source_dirs:
            continue

        all_rules = []
        for rel_dir in source_dirs:
            source_dir = os.path.join(project_root, rel_dir)
            print(f"Scanning {rel_dir}...")
            rules = scan_and_parse(parser, source_dir, project_root)
            all_rules.extend(rules)

        if not all_rules:
            continue

        # Group rules by category
        grouped_rules = group_by_category(all_rules)

        print(f"  Found {len(all_rules)} rules in {len(grouped_rules)} categories")

        # Store for generator
        results[parser.name] = grouped_rules

    if not results:
        print("Error: No rules found in any source directory")
        sys.exit(1)

    # Generate and update documentation
    print("\nGenerating documentation...")

    # Get target files (all generators use same files)
    first_generator = next(iter(plugin_manager.generators.values()))
    output_files = [
        os.path.join(project_root, filename) for filename in first_generator.default_filenames
    ]

    # Generate content from each generator
    for parser_name, grouped_rules in results.items():
        # Get the generator for this parser
        generator_name = plugin_manager.parser_to_generator.get(parser_name)
        if not generator_name:
            continue

        generator = plugin_manager.generators.get(generator_name)
        if not generator:
            continue

        content = generator.generate(grouped_rules, {})

        # Update all target files
        for file_path in output_files:
            success, message = update_documentation_file(
                file_path, content, generator.get_section_markers()
            )
            status = "✓" if success else "✗"
            print(f"{status} {generator.name}: {message}")

    print("\n✓ Rules synchronization completed!")


if __name__ == "__main__":
    main()
