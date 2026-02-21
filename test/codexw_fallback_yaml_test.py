#!/usr/bin/env python3
"""Targeted tests for codexw fallback YAML parser/writer behavior."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import pathlib
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CODEXW_PATH = REPO_ROOT / "codexw" / "__main__.py"


def load_codexw_module():
    loader = importlib.machinery.SourceFileLoader("codexw_module", str(CODEXW_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("failed to build import spec for codexw")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class CodexwFallbackYamlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codexw = load_codexw_module()

    def test_flow_list_parses_as_list(self):
        parsed = self.codexw._parse_simple_yaml(
            """
domains:
  default: [core]
  allowed: [core, testing]
""".strip()
        )

        self.assertEqual(parsed["domains"]["default"], ["core"])
        self.assertEqual(parsed["domains"]["allowed"], ["core", "testing"])

        normalized = self.codexw.normalize_profile(parsed)
        self.assertEqual(normalized["default_domains"], ["core"])
        self.assertEqual(normalized["allowed_domains"], ["core", "testing"])

    def test_inline_comments_do_not_override_values(self):
        parsed = self.codexw._parse_simple_yaml(
            """
review:
  strict_gate: false # advisory mode
  depth_hotspots: 1 # small changes only
domains:
  default: [core]
  allowed: [core]
""".strip()
        )

        self.assertFalse(parsed["review"]["strict_gate"])
        self.assertEqual(parsed["review"]["depth_hotspots"], 1)

        normalized = self.codexw.normalize_profile(parsed)
        self.assertFalse(normalized["strict_gate"])
        self.assertEqual(normalized["depth_hotspots"], 1)

    def test_no_space_comment_after_closed_flow_and_quoted_scalars(self):
        parsed = self.codexw._parse_simple_yaml(
            """
domains:
  default: [core]# comment
  allowed: [core, testing]# comment
repo:
  name: 'Repo Name'# comment
prompts:
  global: "line"# comment
meta:
  link: https://example.com/#fragment
""".strip()
        )

        self.assertEqual(parsed["domains"]["default"], ["core"])
        self.assertEqual(parsed["domains"]["allowed"], ["core", "testing"])
        self.assertEqual(parsed["repo"]["name"], "Repo Name")
        self.assertEqual(parsed["prompts"]["global"], "line")
        self.assertEqual(parsed["meta"]["link"], "https://example.com/#fragment")

        normalized = self.codexw.normalize_profile(parsed)
        self.assertEqual(normalized["default_domains"], ["core"])
        self.assertEqual(normalized["allowed_domains"], ["core", "testing"])
        self.assertEqual(normalized["repo_name"], "Repo Name")

    def test_list_item_with_colon_is_not_forced_to_inline_map(self):
        parsed = self.codexw._parse_simple_yaml(
            """
values:
  - https://example.com
""".strip()
        )
        self.assertEqual(parsed["values"], ["https://example.com"])

    def test_single_quote_escapes_in_flow_items(self):
        parsed = self.codexw._parse_simple_yaml(
            """
values:
  - ['it''s,ok', core]
""".strip()
        )
        self.assertEqual(parsed["values"], [["it's,ok", "core"]])

    def test_explicit_nulls_do_not_turn_into_empty_maps(self):
        parsed = self.codexw._parse_simple_yaml(
            """
review:
  default_base:
  output_root:
domains:
  default: [core]
  allowed: [core]
pipeline:
  core_passes:
    - id: core-breadth
      name: Core breadth
      instructions: |
        test
""".strip()
        )

        self.assertIsNone(parsed["review"]["default_base"])
        self.assertIsNone(parsed["review"]["output_root"])

        normalized = self.codexw.normalize_profile(parsed)
        self.assertEqual(normalized["default_base"], "main")
        self.assertEqual(normalized["output_root"], ".codex/review-runs")

    def test_dump_yaml_round_trips_with_fallback_parser(self):
        profile = {
            "version": 1,
            "repo": {"name": "Repo"},
            "review": {"default_base": "main", "strict_gate": True, "depth_hotspots": 2},
            "domains": {"default": ["core"], "allowed": ["core", "testing"]},
            "prompts": {
                "global": "Line 1\nLine 2",
                "by_domain": {"testing": "Focus on tests"},
            },
            "pipeline": {
                "include_policy_pass": True,
                "include_core_passes": True,
                "include_domain_passes": True,
                "include_depth_passes": True,
                "core_passes": [
                    {
                        "id": "core-breadth",
                        "name": "Core breadth",
                        "instructions": "Task:\n- cover all files",
                    }
                ],
            },
        }

        dumped = self.codexw._dump_yaml_text(profile)
        parsed = self.codexw._parse_simple_yaml(dumped)

        self.assertEqual(parsed["domains"]["allowed"], ["core", "testing"])
        self.assertEqual(parsed["review"]["depth_hotspots"], 2)
        self.assertEqual(parsed["prompts"]["global"], "Line 1\nLine 2")

    def test_default_domain_prompt_template_is_repo_agnostic(self):
        prompt = self.codexw.default_domain_prompt_template("custom-domain")
        self.assertIn("Domain focus: custom-domain", prompt)
        self.assertIn("domain-specific correctness and policy compliance", prompt)
        self.assertNotIn("FakeUsersRepository", prompt)
        self.assertNotIn("Duolingo", prompt)

    def test_bootstrap_profile_uses_generic_domain_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = pathlib.Path(tmp)
            rules_dir = repo_root / ".cursor" / "rules"
            rules_dir.mkdir(parents=True, exist_ok=True)
            (rules_dir / "testing-rule.mdc").write_text(
                """---
description: Testing conventions
domain: testing
---
Use testing standards.
""",
                encoding="utf-8",
            )

            profile = self.codexw.build_bootstrap_profile(repo_root)
            self.assertIn("testing", profile["domains"]["allowed"])
            self.assertEqual(
                profile["prompts"]["by_domain"]["testing"],
                self.codexw.default_domain_prompt_template("testing"),
            )

    def test_extract_rule_domains_does_not_keyword_infer_from_description(self):
        domains = self.codexw._extract_rule_domains(
            {"description": "check experiment treatment and dispatcher usage"},
            "rules/misc-rule.mdc",
        )
        self.assertEqual(domains, [])

    def test_infer_domains_from_rule_metadata_is_generic(self):
        inferred = self.codexw.infer_domains_from_rule_metadata(
            [
                {"domains": ["zeta"]},
                {"domains": ["alpha"]},
            ]
        )
        self.assertEqual(inferred, ["core", "alpha", "zeta"])


if __name__ == "__main__":
    unittest.main()
