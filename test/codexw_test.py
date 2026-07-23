#!/usr/bin/env python3
"""Targeted regression tests for codexw."""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from unittest import mock

# Add codexw to path
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from codexw.yaml_fallback import parse_simple_yaml, dump_yaml_text
from codexw.cli import build_parser
from codexw.git import collect_numstat, detect_default_base, resolve_base_ref
from codexw.profile import (
    normalize_profile,
    default_domain_prompt_template,
    build_bootstrap_profile,
    infer_domains_from_rule_metadata,
)
from codexw.reporting import write_combined_report
from codexw.passes import (
    ModelFallbackState,
    PassSpec,
    RetryStrategy,
    build_model_fallback_chain,
    extract_configured_effort_from_output,
    extract_supported_effort_from_output,
    run_review_pass_with_compat,
)
from codexw.utils import CodexwError


class CodexwTests(unittest.TestCase):
    _SKIP_PRE_COMMIT_INTEGRATION_ENV = "CODEXW_SKIP_PRECOMMIT_INTEGRATION"

    @staticmethod
    def _resolve_pre_commit_cmd() -> list[str]:
        binary = shutil.which("pre-commit")
        if binary:
            return [binary]

        probe = subprocess.run(
            [sys.executable, "-m", "pre_commit", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if probe.returncode == 0:
            return [sys.executable, "-m", "pre_commit"]

        raise AssertionError(
            "pre-commit is required for integration coverage. "
            "Install pre-commit or make the pre_commit module available."
        )

    @staticmethod
    def _snapshot_working_tree_to_git_repo(target_repo_root: pathlib.Path) -> str:
        tracked = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        ).stdout.decode("utf-8", errors="replace")
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        ).stdout.decode("utf-8", errors="replace")

        paths = {
            p
            for p in (tracked + untracked).split("\x00")
            if p and not p.endswith("/")
        }

        target_repo_root.mkdir(parents=True, exist_ok=True)
        for rel in sorted(paths):
            src = REPO_ROOT / rel
            if not src.is_file():
                continue
            dst = target_repo_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        subprocess.run(
            ["git", "init"],
            cwd=target_repo_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        subprocess.run(["git", "add", "."], cwd=target_repo_root, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=codexw-test",
                "-c",
                "user.email=codexw-test@example.com",
                "commit",
                "-m",
                "snapshot",
            ],
            cwd=target_repo_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=target_repo_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()

    def test_flow_list_parses_as_list(self):
        parsed = parse_simple_yaml(
            """
domains:
  default: [core]
  allowed: [core, testing]
""".strip()
        )

        self.assertEqual(parsed["domains"]["default"], ["core"])
        self.assertEqual(parsed["domains"]["allowed"], ["core", "testing"])

        normalized = normalize_profile(parsed)
        self.assertEqual(normalized["default_domains"], ["core"])
        self.assertEqual(normalized["allowed_domains"], ["core", "testing"])

    def test_inline_comments_do_not_override_values(self):
        parsed = parse_simple_yaml(
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

        normalized = normalize_profile(parsed)
        self.assertFalse(normalized["strict_gate"])
        self.assertEqual(normalized["depth_hotspots"], 1)

    def test_no_space_comment_after_closed_flow_and_quoted_scalars(self):
        parsed = parse_simple_yaml(
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

        normalized = normalize_profile(parsed)
        self.assertEqual(normalized["default_domains"], ["core"])
        self.assertEqual(normalized["allowed_domains"], ["core", "testing"])
        self.assertEqual(normalized["repo_name"], "Repo Name")

    def test_list_item_with_colon_is_not_forced_to_inline_map(self):
        parsed = parse_simple_yaml(
            """
values:
  - https://example.com
""".strip()
        )
        self.assertEqual(parsed["values"], ["https://example.com"])

    def test_malformed_mapping_indentation_raises(self):
        malformed = """
rules:
  include:
    - AGENTS.md
     - .cursor/rules/**/*.mdc
""".strip()
        with self.assertRaises(ValueError):
            parse_simple_yaml(malformed)

    def test_malformed_nested_mapping_indentation_raises(self):
        malformed = """
review:
  strict_gate: true
    depth_hotspots: 3
""".strip()
        with self.assertRaises(ValueError):
            parse_simple_yaml(malformed)

    def test_single_quote_escapes_in_flow_items(self):
        parsed = parse_simple_yaml(
            """
values:
  - ['it''s,ok', core]
""".strip()
        )
        self.assertEqual(parsed["values"], [["it's,ok", "core"]])

    def test_explicit_nulls_do_not_turn_into_empty_maps(self):
        parsed = parse_simple_yaml(
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

        normalized = normalize_profile(parsed)
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

        dumped = dump_yaml_text(profile)
        parsed = parse_simple_yaml(dumped)

        self.assertEqual(parsed["domains"]["allowed"], ["core", "testing"])
        self.assertEqual(parsed["review"]["depth_hotspots"], 2)
        self.assertEqual(parsed["prompts"]["global"], "Line 1\nLine 2")

    def test_default_domain_prompt_template_is_repo_agnostic(self):
        prompt = default_domain_prompt_template("custom-domain")
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

            profile = build_bootstrap_profile(repo_root)
            self.assertIn("testing", profile["domains"]["allowed"])
            self.assertEqual(
                profile["prompts"]["by_domain"]["testing"],
                default_domain_prompt_template("testing"),
            )

    def test_bootstrap_profile_ignores_malformed_rule_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = pathlib.Path(tmp)
            rules_dir = repo_root / ".cursor" / "rules"
            rules_dir.mkdir(parents=True, exist_ok=True)
            (rules_dir / "broken-rule.mdc").write_text(
                """---
domain:
  - testing
    - broken
---
Body
""",
                encoding="utf-8",
            )
            profile = build_bootstrap_profile(repo_root)
            self.assertIn("core", profile["domains"]["allowed"])

    def test_infer_domains_from_rule_metadata_is_generic(self):
        inferred = infer_domains_from_rule_metadata(
            [
                {"domains": ["zeta"]},
                {"domains": ["alpha"]},
            ]
        )
        self.assertEqual(inferred, ["core", "alpha", "zeta"])

    def test_script_entrypoint_runs_from_external_cwd(self):
        script_path = REPO_ROOT / "codexw" / "__main__.py"
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [str(script_path), "review", "--help"],
                cwd=tmp,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("usage: codexw review", proc.stdout)

    def test_module_entrypoint_runs_from_repo_root(self):
        proc = subprocess.run(
            [sys.executable, "-m", "codexw", "review", "--help"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("usage: codexw review", proc.stdout)

    def test_cli_rejects_conflicting_gate_flags(self):
        parser = build_parser()
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(
                    ["review", "--fail-on-findings", "--no-fail-on-findings"]
                )

    def test_uncommitted_numstat_includes_untracked_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = pathlib.Path(tmp)
            subprocess.run(
                ["git", "init"],
                cwd=repo_root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            (repo_root / "tracked.txt").write_text("seed\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=repo_root, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=codexw-test",
                    "-c",
                    "user.email=codexw-test@example.com",
                    "commit",
                    "-m",
                    "seed",
                ],
                cwd=repo_root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            (repo_root / "new_untracked.py").write_text(
                "line1\nline2\nline3\n",
                encoding="utf-8",
            )

            rows = collect_numstat(repo_root, mode="uncommitted", base="main", commit="")
            by_path = {path: delta for delta, path in rows}
            self.assertIn("new_untracked.py", by_path)
            self.assertEqual(by_path["new_untracked.py"], 3)

    def test_detect_default_base_returns_remote_qualified_ref_when_local_missing(self):
        def fake_ref_exists(_repo_root, ref):
            return ref == "refs/remotes/origin/main"

        with mock.patch("codexw.git.git_ref_exists", side_effect=fake_ref_exists):
            self.assertEqual(detect_default_base(REPO_ROOT), "origin/main")

    def test_resolve_base_ref_prefers_local_branch_over_remote(self):
        def fake_ref_exists(_repo_root, ref):
            return ref in {"refs/heads/main", "refs/remotes/origin/main"}

        with mock.patch("codexw.git.git_ref_exists", side_effect=fake_ref_exists):
            self.assertEqual(resolve_base_ref(REPO_ROOT, "main"), "main")

    def test_resolve_base_ref_maps_to_origin_when_only_remote_exists(self):
        def fake_ref_exists(_repo_root, ref):
            return ref == "refs/remotes/origin/main"

        with mock.patch("codexw.git.git_ref_exists", side_effect=fake_ref_exists):
            self.assertEqual(resolve_base_ref(REPO_ROOT, "main"), "origin/main")

    def test_combined_report_appends_only_executed_pass_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = pathlib.Path(tmp)
            output_root = repo_root / "out"
            output_root.mkdir(parents=True, exist_ok=True)
            profile_path = repo_root / "local-review-profile.yaml"
            profile_path.write_text("version: 1\n", encoding="utf-8")

            current_pass = output_root / "pass-1-current.md"
            stale_pass = output_root / "pass-2-stale.md"
            pass_status = output_root / "pass-status.md"
            combined = output_root / "combined-report.md"
            findings_json = output_root / "findings.json"

            current_pass.write_text("Current pass output\n", encoding="utf-8")
            stale_pass.write_text("Stale pass output\n", encoding="utf-8")
            pass_status.write_text("- [PASS] status\n", encoding="utf-8")

            write_combined_report(
                path=combined,
                profile={"repo_name": "Repo"},
                profile_path=profile_path,
                repo_root=repo_root,
                target_desc="base branch: main",
                selected_domains=["core"],
                rule_files=[],
                changed_files=["a.py"],
                modules=[(1, "a.py")],
                hotspots=[],
                depth_hotspots=0,
                pass_count=1,
                summary_lines=["- [PASS] current"],
                raw_findings=[],
                findings_json_path=findings_json,
                executed_pass_files=[current_pass],
            )

            report = combined.read_text(encoding="utf-8")
            self.assertIn("## pass-1-current", report)
            self.assertNotIn("## pass-2-stale", report)
            self.assertNotIn("## pass-status", report)

    def test_pre_commit_hook_runs_codexw_alias_with_print_effective_profile(self):
        skip_flag = os.environ.get(self._SKIP_PRE_COMMIT_INTEGRATION_ENV, "").strip().lower()
        if skip_flag in {"1", "true", "yes", "on"}:
            self.skipTest(
                "Skipping pre-commit integration test because "
                f"{self._SKIP_PRE_COMMIT_INTEGRATION_ENV}={skip_flag!r}"
            )

        pre_commit_cmd = self._resolve_pre_commit_cmd()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = pathlib.Path(tmp)
            hook_repo_root = tmp_root / "hook-repo"
            consumer_root = tmp_root / "consumer-repo"

            repo_rev = self._snapshot_working_tree_to_git_repo(hook_repo_root)
            consumer_root.mkdir(parents=True, exist_ok=True)

            subprocess.run(
                ["git", "init"],
                cwd=consumer_root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            (consumer_root / "sample.txt").write_text("sample\n", encoding="utf-8")
            subprocess.run(["git", "add", "sample.txt"], cwd=consumer_root, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=codexw-test",
                    "-c",
                    "user.email=codexw-test@example.com",
                    "commit",
                    "-m",
                    "seed",
                ],
                cwd=consumer_root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            (consumer_root / ".pre-commit-config.yaml").write_text(
                (
                    "repos:\n"
                    f"  - repo: {hook_repo_root}\n"
                    f"    rev: {repo_rev}\n"
                    "    hooks:\n"
                    "      - id: codexw\n"
                    "        args:\n"
                    "          - --print-effective-profile\n"
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    *pre_commit_cmd,
                    "run",
                    "codexw",
                    "--all-files",
                    "--hook-stage",
                    "manual",
                ],
                cwd=consumer_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if proc.returncode != 0:
                self.fail(
                    "pre-commit codexw hook failed.\n"
                    f"stdout:\n{proc.stdout}\n"
                    f"stderr:\n{proc.stderr}"
                )

            self.assertIn("Codexw (alias)", proc.stdout)
            self.assertIn('"effective_profile"', proc.stdout)
            self.assertTrue((consumer_root / "local-review-profile.yaml").is_file())

    def test_recursive_model_fallback_chain(self):
        chain = build_model_fallback_chain("gpt-5.3-codex")
        self.assertEqual(
            chain,
            [
                "gpt-5.3-codex",
                "gpt-5.2-codex",
                "gpt-5.1-codex",
                "gpt-5-codex",
                "gpt-4.2-codex",
            ],
        )
        self.assertEqual(len(chain), len(set(chain)))

    def test_pass_retry_falls_back_model_then_effort(self):
        pass_spec = PassSpec(
            id="pass-1-policy-sweep",
            name="Policy pass",
            prompt="Run policy review",
        )
        model_state = ModelFallbackState()

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = pathlib.Path(tmp)
            out_file = repo_root / "pass.md"
            calls: list[list[str]] = []
            responses = [
                (
                    1,
                    "error: model_not_found: The model `gpt-5.3-codex` "
                    "does not exist or you do not have access to it.",
                ),
                (
                    1,
                    "error: model_reasoning_effort 'xhigh' is not supported for this model. "
                    "Supported values: high, medium, low.",
                ),
                (0, "No actionable findings."),
            ]

            def fake_run(cmd, cwd, write_to, stream_output):
                _ = cwd, stream_output
                calls.append(cmd)
                exit_code, text = responses[len(calls) - 1]
                write_to.write_text(text, encoding="utf-8")
                return exit_code

            with mock.patch("codexw.passes.run_captured", side_effect=fake_run):
                run_review_pass_with_compat(
                    repo_root=repo_root,
                    out_file=out_file,
                    target_args=["--uncommitted"],
                    target_desc="uncommitted changes",
                    pass_spec=pass_spec,
                    model_state=model_state,
                )

        self.assertEqual(len(calls), 3)
        self.assertNotIn('model="', " ".join(calls[0]))
        self.assertIn('model="gpt-5.2-codex"', " ".join(calls[1]))
        self.assertIn('model="gpt-5.2-codex"', " ".join(calls[2]))
        self.assertIn('model_reasoning_effort="high"', " ".join(calls[2]))
        self.assertEqual(model_state.selected_model, "gpt-5.2-codex")
        self.assertEqual(model_state.selected_effort, "high")

    def test_pass_retry_reuses_resolved_model_and_effort(self):
        pass_spec = PassSpec(
            id="pass-2-core-breadth",
            name="Core breadth",
            prompt="Run core pass",
        )
        model_state = ModelFallbackState(
            preferred_model="gpt-5.3-codex",
            selected_model="gpt-5.2-codex",
            selected_effort="high",
        )

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = pathlib.Path(tmp)
            out_file = repo_root / "pass.md"
            calls: list[list[str]] = []

            def fake_run(cmd, cwd, write_to, stream_output):
                _ = cwd, stream_output
                calls.append(cmd)
                write_to.write_text("No actionable findings.", encoding="utf-8")
                return 0

            with mock.patch("codexw.passes.run_captured", side_effect=fake_run):
                run_review_pass_with_compat(
                    repo_root=repo_root,
                    out_file=out_file,
                    target_args=["--base", "main"],
                    target_desc="base branch: main",
                    pass_spec=pass_spec,
                    model_state=model_state,
                )

        self.assertEqual(len(calls), 1)
        joined = " ".join(calls[0])
        self.assertIn('model="gpt-5.2-codex"', joined)
        self.assertIn('model_reasoning_effort="high"', joined)

    def test_pass_retry_uses_recent_five_model_window(self):
        pass_spec = PassSpec(
            id="pass-3-policy-sweep",
            name="Policy pass recent chain",
            prompt="Run policy review",
        )
        model_state = ModelFallbackState(preferred_model="gpt-9.9-codex")

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = pathlib.Path(tmp)
            out_file = repo_root / "pass.md"
            calls: list[list[str]] = []

            fallback_chain = build_model_fallback_chain("gpt-9.9-codex")
            final_model = fallback_chain[-1]

            def fake_run(cmd, cwd, write_to, stream_output):
                _ = cwd, stream_output
                calls.append(cmd)
                joined = " ".join(cmd)
                if f'model="{final_model}"' in joined:
                    write_to.write_text("No actionable findings.", encoding="utf-8")
                    return 0

                current_model = None
                for model in fallback_chain:
                    if f'model="{model}"' in joined:
                        current_model = model
                        break
                if current_model is None:
                    current_model = fallback_chain[0]

                write_to.write_text(
                    "error: model_not_found: The model "
                    f"`{current_model}` does not exist or you do not have access to it.",
                    encoding="utf-8",
                )
                return 1

            with mock.patch("codexw.passes.run_captured", side_effect=fake_run):
                run_review_pass_with_compat(
                    repo_root=repo_root,
                    out_file=out_file,
                    target_args=["--uncommitted"],
                    target_desc="uncommitted changes",
                    pass_spec=pass_spec,
                    model_state=model_state,
                )

        # Recency policy limits fallback to latest five candidate models.
        self.assertEqual(len(calls), 5)
        self.assertIn(f'model="{final_model}"', " ".join(calls[-1]))
        self.assertEqual(model_state.selected_model, final_model)

    def test_pass_retry_does_not_slide_beyond_recent_five_window(self):
        pass_spec = PassSpec(
            id="pass-4-policy-sweep",
            name="Policy pass fixed window",
            prompt="Run policy review",
        )
        model_state = ModelFallbackState(preferred_model="gpt-9.9-codex")

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = pathlib.Path(tmp)
            out_file = repo_root / "pass.md"
            calls: list[list[str]] = []
            expected_chain = build_model_fallback_chain("gpt-9.9-codex")

            def fake_run(cmd, cwd, write_to, stream_output):
                _ = cwd, stream_output
                calls.append(cmd)
                joined = " ".join(cmd)

                current_model = expected_chain[0]
                for model in expected_chain:
                    if f'model="{model}"' in joined:
                        current_model = model
                        break

                write_to.write_text(
                    "error: model_not_found: The model "
                    f"`{current_model}` does not exist or you do not have access to it.",
                    encoding="utf-8",
                )
                return 1

            with mock.patch("codexw.passes.run_captured", side_effect=fake_run):
                with self.assertRaises(CodexwError):
                    run_review_pass_with_compat(
                        repo_root=repo_root,
                        out_file=out_file,
                        target_args=["--uncommitted"],
                        target_desc="uncommitted changes",
                        pass_spec=pass_spec,
                        model_state=model_state,
                    )

        self.assertEqual(len(calls), len(expected_chain))
        for idx, model in enumerate(expected_chain):
            self.assertIn(f'model="{model}"', " ".join(calls[idx]))
        self.assertIsNone(model_state.selected_model)

    def test_previous_major_includes_dot_two_variant(self):
        chain = build_model_fallback_chain("gpt-4.2-codex")
        self.assertEqual(
            chain,
            [
                "gpt-4.2-codex",
                "gpt-4.1-codex",
                "gpt-4-codex",
                "gpt-3.2-codex",
                "gpt-3.1-codex",
            ],
        )

    def test_reasoning_effort_unsupported_detects_reasoning_dot_effort_param(self):
        output = """
ERROR: {
  "error": {
    "message": "Unsupported value: 'xhigh' is not supported with the 'gpt-5-codex' model. Supported values are: 'low', 'medium', and 'high'.",
    "type": "invalid_request_error",
    "param": "reasoning.effort",
    "code": "unsupported_value"
  }
}
""".strip()
        self.assertTrue(RetryStrategy.reasoning_effort_unsupported(output))
        self.assertEqual(extract_supported_effort_from_output(output), "high")

    def test_extract_configured_effort_from_reasoning_effort_banner(self):
        output = """
model: gpt-5-codex
reasoning effort: xhigh
""".strip()
        self.assertEqual(extract_configured_effort_from_output(output), "xhigh")

    def test_model_unavailable_detects_chatgpt_model_not_supported_message(self):
        output = (
            "ERROR: {\"detail\":\"The 'gpt-0-codex' model is not supported when using Codex "
            "with a ChatGPT account.\"}"
        )
        self.assertTrue(RetryStrategy.model_unavailable(output))

    def test_model_unavailable_does_not_trigger_on_reasoning_effort_error(self):
        output = """
ERROR: {
  "error": {
    "message": "Unsupported value: 'xhigh' is not supported with the 'gpt-5-codex' model.",
    "param": "reasoning.effort",
    "code": "unsupported_value"
  }
}
""".strip()
        self.assertFalse(RetryStrategy.model_unavailable(output))


if __name__ == "__main__":
    unittest.main()
