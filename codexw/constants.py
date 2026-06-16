"""Constants and default configurations for codexw.

This module contains all magic numbers, default pass specifications, and
sentinel values used throughout the codexw package. Centralizing these
makes the codebase easier to understand and maintain.
"""

from __future__ import annotations

# Sentinel string that Codex outputs when no actionable findings exist.
# Used for pass success/failure detection.
NO_FINDINGS_SENTINEL = "No actionable findings."

# Default global prompt injected into all review passes.
# Provides baseline review guidance without repo-specific context.
DEFAULT_GLOBAL_PROMPT = (
    "Use repository standards for lifecycle, state, architecture boundaries, and "
    "production-safety. Prioritize behavior-changing issues and policy violations "
    "over style-only comments."
)

# Policy pass instructions template.
# The policy pass enforces all discovered rule files and outputs coverage.
DEFAULT_POLICY_PASS_INSTRUCTIONS = (
    "Task:\n"
    "- Enforce every standard file listed above.\n"
    "- Output a 'Rule Coverage' section with one line per rule file:\n"
    "  <rule file> :: Covered | NotApplicable :: short reason\n"
    "- Then output actionable findings using the required schema.\n"
    f"- If no actionable findings exist, include exactly this line: {NO_FINDINGS_SENTINEL}"
)

# Core passes run for the "core" domain. Each pass focuses on a different
# risk class to improve recall and reduce blind spots.
#
# Rationale for 4 passes:
# 1. core-breadth: Ensures every changed file is touched at least once.
#    Catches obvious issues across the entire diff surface.
# 2. core-regressions: Focuses on behavioral changes, crashes, and security.
#    These are the highest-impact bugs that escape code review.
# 3. core-architecture: Focuses on structural issues - boundaries, concurrency,
#    lifecycle. Harder to spot but cause long-term maintenance pain.
# 4. core-tests: Focuses on test coverage gaps. Missing tests allow future
#    regressions to slip through.
DEFAULT_CORE_PASS_SPECS: list[dict[str, str]] = [
    {
        "id": "core-breadth",
        "name": "Core 1: breadth coverage across all changed files",
        "instructions": (
            "Task:\n"
            "- Perform full-breadth review across every changed file listed above.\n"
            "- Output a 'Breadth Coverage' section with one line per changed file:\n"
            "  <file path> :: Reviewed | NotApplicable :: short reason\n"
            "- Then output actionable findings using the required schema.\n"
            f"- If no actionable findings exist, include exactly this line: {NO_FINDINGS_SENTINEL}"
        ),
    },
    {
        "id": "core-regressions",
        "name": "Core 2: regressions/security/crash scan",
        "instructions": (
            "Focus areas:\n"
            "- behavioral regressions\n"
            "- crash/nullability risks\n"
            "- state corruption and data-loss risks\n"
            "- security and privacy issues"
        ),
    },
    {
        "id": "core-architecture",
        "name": "Core 3: architecture/concurrency scan",
        "instructions": (
            "Focus areas:\n"
            "- architecture boundaries and dependency misuse\n"
            "- lifecycle and concurrency/threading issues\n"
            "- error-handling/fallback correctness\n"
            "- protocol/contract boundary failures"
        ),
    },
    {
        "id": "core-tests",
        "name": "Core 4: test-coverage scan",
        "instructions": (
            "Focus areas:\n"
            "- missing tests required to protect the change\n"
            "- high-risk edge cases without coverage\n"
            "- regressions likely to escape without tests"
        ),
    },
]

# Depth pass instructions template.
# {hotspot} is replaced with the actual file path at runtime.
DEFAULT_DEPTH_PASS_INSTRUCTIONS = (
    "Task:\n"
    "- Perform depth-first review of hotspot file: {hotspot}\n"
    "- Traverse directly related changed call paths\n"
    "- Prioritize subtle behavioral, concurrency, state, and boundary-condition failures\n"
    "- Output only actionable findings with required schema\n"
    f"- If no actionable findings exist, include exactly this line: {NO_FINDINGS_SENTINEL}"
)

# Default review configuration values.
DEFAULT_BASE_BRANCH = "main"
DEFAULT_DEPTH_HOTSPOTS = 3
DEFAULT_OUTPUT_ROOT = ".codex/review-runs"
DEFAULT_STRICT_GATE = True

# Default rule patterns to search for when no profile exists.
DEFAULT_RULE_PATTERNS = ("AGENTS.md", ".cursor/rules/**/*.mdc")

# Model fallback and compatibility handling constants.
# These are used by pass execution retry logic.
REASONING_EFFORT_ORDER = ("xhigh", "high", "medium", "low", "minimal")
DEFAULT_MODEL_FALLBACK_WINDOW = 5
PREVIOUS_MAJOR_MINOR_CANDIDATES = (2, 1)
REASONING_PARAM_HINTS = {"model_reasoning_effort", "reasoning.effort", "reasoning_effort"}
MODEL_UNAVAILABLE_CODE_HINTS = {
    "model_not_found",
    "unknown_model",
    "model_unavailable",
    "unsupported_model",
    "model_not_supported",
}
COMPAT_CODE_HINTS = {
    "unsupported_option_combination",
    "unsupported_argument_combination",
}
