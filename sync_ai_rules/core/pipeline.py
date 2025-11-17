#!/usr/bin/env python3

from dataclasses import dataclass


@dataclass
class Pipeline:
    """Represents a parser-generator pipeline."""

    name: str
    description: str
    parser: "InputParser"
    generator: "OutputGenerator"
