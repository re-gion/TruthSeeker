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
    def test_challenger_convergence_has_confidence_and_five_round_guard(self):
        source = read_source("app/agents/edges/conditions.py")

        self.assertIn("evaluate_phase_convergence", source)
        self.assertIn("confidence", source)
        self.assertIn("force_max_rounds", source)

    def test_report_timeline_groups_challenger_by_phase_round(self):
        source = read_source("app/services/report_generator.py")

        self.assertIn("Challenger ↔", source)
        self.assertIn("_build_challenger_timeline_sections", source)
        self.assertIn("## 六、质询时间线", source)
        self.assertNotIn("证据时间线（按轮次）", source)
        self.assertNotIn("证据时间线（按质询阶段）", source)

    def test_llm_agent_outputs_require_markdown_sections(self):
        source = read_source("app/agents/tools/llm_client.py")

        self.assertIn("### 自主检材观察", source)
        self.assertIn("### 外部检测结果解读", source)
        self.assertIn("### 自主情报推理", source)
        self.assertIn("### 来源可信度与图谱质量", source)
        self.assertIn("### 质询对象与本轮置信度", source)
        self.assertIn("### 收敛依据", source)
        self.assertIn("challenger_model_review", source)
        self.assertNotIn("不要使用 Markdown", source)

    def test_challenger_feedback_exposes_confidence_and_model_recommendation(self):
        source = read_source("app/agents/nodes/challenger.py")

        self.assertIn('"confidence": confidence', source)
        self.assertIn('"satisfaction": confidence', source)
        self.assertIn('"model_requires_more_evidence"', source)
        self.assertIn('"model_target_agent"', source)
        self.assertIn("phase_round < 2", source)

    def test_report_sections_and_markdown_fields_are_readable(self):
        source = read_source("app/services/report_generator.py")

        self.assertIn("## 五、Challenger 逻辑质询", source)
        self.assertIn("## 六、质询时间线", source)
        self.assertIn("## 七、全程审计日志", source)
        self.assertIn("## 八、建议与说明", source)
        self.assertIn("_build_full_audit_log_sections", source)
        self.assertIn("_render_markdown_field", source)
        self.assertIn("llm_cross_validation", source)

    def test_history_and_stream_interfaces_include_audit_logs(self):
        consultation = read_source("app/api/v1/consultation.py")
        detect = read_source("app/api/v1/detect.py")

        self.assertIn("audit_logs", consultation)
        self.assertIn('action="detect_start"', detect)
        self.assertIn("audit_timeline_event", detect)


class KimiProviderSourceTests(unittest.TestCase):
    def test_config_supports_official_and_coding_plan_without_model_fallback(self):
        config = read_source("app/config.py")
        llm_client = read_source("app/agents/tools/llm_client.py")
        env_example = read_source(".env.example")

        self.assertIn("KIMI_PROVIDER", config)
        self.assertIn("KIMI_CODING_API_KEY", config)
        self.assertIn("KIMI_CODING_BASE_URL", config)
        self.assertIn("resolve_kimi_runtime", config)
        self.assertIn("resolve_kimi_runtime", llm_client)
        self.assertIn("KIMI_PROVIDER=official", env_example)
        self.assertIn("KIMI_CODING_BASE_URL=https://api.kimi.com/coding/v1", env_example)
        self.assertNotIn("KIMI_FALLBACK_MODEL", config)
        self.assertNotIn("KIMI_FALLBACK_MODEL", llm_client)
        self.assertNotIn("KIMI_FALLBACK_MODEL", env_example)
        self.assertNotIn("moonshot-v1-128k", config)
        self.assertNotIn("moonshot-v1-128k", llm_client)
        self.assertNotIn("moonshot-v1-128k", env_example)

    def test_developer_docs_describe_all_agents_internal_reasoning_first(self):
        claude = (PROJECT_ROOT.parent / "CLAUDE.md").read_text(encoding="utf-8")
        tech_stack = (PROJECT_ROOT.parent / "docs/TECH_STACK.md").read_text(encoding="utf-8")
        app_flow = (PROJECT_ROOT.parent / "docs/APP_FLOW.md").read_text(encoding="utf-8")

        self.assertNotIn("验证 Forensics Agent 对图片的自主分析 + OSINT Agent 对文本内容的读取能力", claude)
        self.assertIn("四个 Agent 都应先基于 Kimi 2.6 对可访问样本和上下文自主推理", claude)
        self.assertIn("四个 Agent 共享 Kimi 2.6 原生多模态推理基座", tech_stack)
        self.assertIn("自主推理先行", app_flow)


if __name__ == "__main__":
    unittest.main()
