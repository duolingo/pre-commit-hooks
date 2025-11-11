#!/usr/bin/env python3
"""
This script uses a plugin architecture to parse rules and generate documentation.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List

from sync_ai_rules.core.plugin_manager import PluginManager
from sync_ai_rules.core.rule_metadata import RuleMetadata
from sync_ai_rules.file_updater import update_documentation_file


def find_project_root() -> str:
    """Return current working directory as project root."""
    return str(Path.cwd())


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
    """Main orchestration: load pipelines → parse → generate → update files."""
    # Setup
    project_root = find_project_root()
    script_dir = os.path.dirname(os.path.abspath(__file__))

    plugin_manager = PluginManager()
    plugin_manager.load_plugins(script_dir)

    if not plugin_manager.pipelines:
        print("Error: No pipelines configured")
        sys.exit(1)

    # Get target files (all generators use same files)
    first_generator = plugin_manager.pipelines[0].generator
    output_files = [
        os.path.join(project_root, filename) for filename in first_generator.default_filenames
    ]

    # Process each pipeline
    print()
    for pipeline in plugin_manager.pipelines:
        print(f"Processing pipeline: {pipeline.name}")

        # Scan and parse using pipeline's parser
        all_rules = []
        for rel_dir in pipeline.parser.source_directories:
            source_dir = os.path.join(project_root, rel_dir)
            print(f"  Scanning {rel_dir}...")
            rules = scan_and_parse(pipeline.parser, source_dir, project_root)
            all_rules.extend(rules)

        if not all_rules:
            print("  No rules found, skipping")
            continue

        # Group rules by category
        grouped_rules = group_by_category(all_rules)
        print(f"  Found {len(all_rules)} rules in {len(grouped_rules)} categories")

        # Generate content using pipeline's generator
        content = pipeline.generator.generate(grouped_rules, {})

        # Update all target files
        for file_path in output_files:
            success, message = update_documentation_file(
                file_path, content, pipeline.generator.get_section_markers()
            )
            status = "✓" if success else "✗"
            print(f"  {status} {message}")

    print("\n✓ Rules synchronization completed!")


if __name__ == "__main__":
    main()
