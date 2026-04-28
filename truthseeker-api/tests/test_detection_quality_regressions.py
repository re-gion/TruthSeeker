"""Regression tests for detection-quality issues found in generated reports.

These tests intentionally avoid importing app modules so they can run even when
the local Windows Python environment has asyncio/socket provider issues.
"""
from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_source(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


class ExternalToolFallbackSourceTests(unittest.TestCase):
    def test_reality_defender_fallback_does_not_emit_face_frame_gan_normal_claims(self):
        source = read_source("app/agents/tools/deepfake_api.py")

        self.assertNotIn("面部特征自然", source)
        self.assertNotIn("帧间一致性正常", source)
        self.assertNotIn("无 GAN 伪影检测", source)
        self.assertIn("analysis_available", source)

    def test_virustotal_fallback_distinguishes_no_key_from_call_failure(self):
        source = read_source("app/agents/tools/threat_intel.py")

        self.assertIn("fallback_reason", source)
        self.assertIn("api_key_configured", source)
        self.assertIn("submit_http_", source)
        self.assertIn("result_http_", source)


class OsintAndReportSourceTests(unittest.TestCase):
    def test_exa_queries_filter_internal_diagnostics_and_prioritize_hosts(self):
        source = read_source("app/agents/tools/osint_search.py")

        self.assertIn("_is_internal_diagnostic", source)
        self.assertIn("reputation phishing fraud", source)
        self.assertIn("maxCharacters", source)
        self.assertIn("MAX_RESULT_SUMMARY_CHARS", source)

    def test_markdown_report_uses_bounded_renderers_for_noisy_fields(self):
        source = read_source("app/services/report_generator.py")

        self.assertIn("_render_tool_results", source)
        self.assertIn("_render_search_results", source)
        self.assertIn("_render_provenance_graph_summary", source)
        self.assertIn("MAX_REPORT_FIELD_CHARS", source)


class ChallengerTimelineSourceTests(unittest.TestCase):
    def test_challenger_convergence_has_satisfaction_and_five_round_guard(self):
        source = read_source("app/agents/edges/conditions.py")

        self.assertIn("evaluate_phase_convergence", source)
        self.assertIn("satisfaction", source)
        self.assertIn("force_max_rounds", source)

    def test_report_timeline_groups_challenger_by_phase_round(self):
        source = read_source("app/services/report_generator.py")

        self.assertIn("Challenger ↔", source)
        self.assertIn("_build_challenger_timeline_sections", source)
        self.assertNotIn("证据时间线（按轮次）", source)


if __name__ == "__main__":
    unittest.main()
