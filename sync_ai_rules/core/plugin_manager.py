#!/usr/bin/env python3
"""
Plugin manager for loading parser-generator pipelines from configuration.
"""

import importlib.util
from pathlib import Path
from typing import List

import yaml

from .interfaces import InputParser, OutputGenerator, Pipeline


class PluginManager:
    """Loads and manages parser-generator pipelines from configuration."""

    def __init__(self):
        self.pipelines: List[Pipeline] = []

    def load_plugins(self, base_path: str):
        """Load all pipelines from plugins.yaml configuration file."""
        config_path = Path(base_path) / "plugins.yaml"

        if not config_path.exists():
            print(f"✗ Plugin configuration not found: {config_path}")
            return

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)

            # Load pipelines
            for pipeline_config in config.get("pipelines", []):
                pipeline = self._load_pipeline(base_path, pipeline_config)
                if pipeline:
                    self.pipelines.append(pipeline)
                    print(f"✓ Loaded pipeline: {pipeline.name} - {pipeline.description}")

        except Exception as e:
            print(f"✗ Failed to load plugin configuration: {e}")

    def _load_pipeline(self, base_path: str, config: dict) -> Pipeline:
        """Load a single parser-generator pipeline."""
        try:
            # Load parser
            parser_config = config["parser"]
            parser = self._load_parser(base_path, parser_config)

            # Load generator
            generator_config = config["generator"]
            generator = self._load_generator(base_path, generator_config)

            # Create pipeline
            return Pipeline(
                name=config["name"],
                description=config["description"],
                parser=parser,
                generator=generator,
            )

        except Exception as e:
            print(f"✗ Failed to load pipeline {config.get('name', 'unknown')}: {e}")
            return None

    def _load_parser(self, base_path: str, config: dict) -> InputParser:
        """Load a parser from configuration."""
        module_path = Path(base_path) / "parsers" / f"{config['module']}.py"
        spec = importlib.util.spec_from_file_location(f"parsers.{config['module']}", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        parser_class = getattr(module, config["class"])
        return parser_class()

    def _load_generator(self, base_path: str, config: dict) -> OutputGenerator:
        """Load a generator from configuration."""
        module_path = Path(base_path) / "generators" / f"{config['module']}.py"
        spec = importlib.util.spec_from_file_location(f"generators.{config['module']}", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        generator_class = getattr(module, config["class"])
        return generator_class()
