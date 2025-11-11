#!/usr/bin/env python3
"""
Plugin manager for loading parsers and generators from explicit configuration.
"""

import importlib.util
from pathlib import Path
from typing import Dict, Optional

import yaml

from .interfaces import InputParser, OutputGenerator


class PluginManager:
    """Loads and manages parser and generator plugins from configuration."""

    def __init__(self):
        self.parsers: Dict[str, InputParser] = {}
        self.generators: Dict[str, OutputGenerator] = {}
        self.parser_to_generator: Dict[str, str] = {}  # Maps parser name to generator name

    def load_plugins(self, base_path: str):
        """Load all plugins from plugins.yaml configuration file."""
        config_path = Path(base_path) / "plugins.yaml"

        if not config_path.exists():
            print(f"✗ Plugin configuration not found: {config_path}")
            return

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)

            # Load parsers
            for parser_config in config.get("parsers", []):
                self._load_parser(base_path, parser_config)
                # Store parser -> generator mapping
                if "generator" in parser_config:
                    self.parser_to_generator[parser_config["name"]] = parser_config["generator"]

            # Load generators
            for generator_config in config.get("generators", []):
                self._load_generator(base_path, generator_config)

        except Exception as e:
            print(f"✗ Failed to load plugin configuration: {e}")

    def _load_parser(self, base_path: str, config: dict):
        """Load a specific parser from configuration."""
        try:
            module_path = Path(base_path) / "parsers" / f"{config['module']}.py"
            spec = importlib.util.spec_from_file_location(
                f"parsers.{config['module']}", module_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get the specified class
            parser_class = getattr(module, config["class"])
            parser = parser_class()
            self.parsers[parser.name] = parser
            print(f"✓ Loaded parser: {parser.name} ({config['description']})")

        except Exception as e:
            print(f"✗ Failed to load parser {config['name']}: {e}")

    def _load_generator(self, base_path: str, config: dict):
        """Load a specific generator from configuration."""
        try:
            module_path = Path(base_path) / "generators" / f"{config['module']}.py"
            spec = importlib.util.spec_from_file_location(
                f"generators.{config['module']}", module_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get the specified class
            generator_class = getattr(module, config["class"])
            generator = generator_class()
            self.generators[generator.name] = generator
            print(f"✓ Loaded generator: {generator.name} ({config['description']})")

        except Exception as e:
            print(f"✗ Failed to load generator {config['name']}: {e}")

    def get_parser_for_file(self, file_path: str) -> Optional[InputParser]:
        """Get appropriate parser for a file."""
        for parser in self.parsers.values():
            if parser.can_parse(file_path):
                return parser
        return None

    def get_generator(self, name: str) -> Optional[OutputGenerator]:
        """Get generator by name."""
        return self.generators.get(name)
