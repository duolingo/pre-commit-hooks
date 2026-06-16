"""Codexw: Profile-aware Codex PR-grade review wrapper.

Public API:
    - CodexwError: Base exception type
    - PassSpec: Data class for review pass specification
    - build_bootstrap_profile: Build initial profile from repo signals
    - default_domain_prompt_template: Generic per-domain prompt template
    - normalize_profile: Normalize raw profile dict
    - load_profile: Load profile from file
    - write_profile: Write profile to file
"""

from .passes import PassSpec
from .profile import (
    build_bootstrap_profile,
    default_domain_prompt_template,
    load_profile,
    normalize_profile,
    write_profile,
)
from .utils import CodexwError

__all__ = [
    "CodexwError",
    "PassSpec",
    "build_bootstrap_profile",
    "default_domain_prompt_template",
    "load_profile",
    "normalize_profile",
    "write_profile",
]
