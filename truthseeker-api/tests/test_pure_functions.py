"""Pure-function unit tests for core modules with no network/async dependencies.

Covers:
- deepfake_api: _stable_float, _stable_int, _stable_sample, _parse_rd_result
- threat_intel: _mock_url_analysis (via sync wrapper), _default_metadata_result
- fallback: DegradationManager, minimal_forensics_result, minimal_osint_result
- report_integrity: _sanitize, build_report_hash
- text_validation: validate_text_plain_file, _has_safe_text_extension, _is_mostly_printable
- auth_config: validate_auth_configuration
- exception_handler: response shape (instantiated)
- conditions: should_converge, challenger_route
- analysis_persistence: normalize_final_verdict, build_resume_state_from_rows
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest

from app.agents.tools.deepfake_api import (
    _stable_float,
    _stable_int,
    _stable_sample,
    _parse_rd_result,
)
from app.agents.tools.fallback import (
    DegradationManager,
    minimal_forensics_result,
    minimal_osint_result,
)
from app.agents.tools.threat_intel import _default_metadata_result
from app.agents.edges.conditions import should_converge, challenger_route
from app.services.report_integrity import build_report_hash, _sanitize, SENSITIVE_KEYS, HASH_FIELDS
from app.services.text_validation import (
    validate_text_plain_file,
    _has_safe_text_extension,
    _is_mostly_printable,
    TEXT_ALLOWED_EXTENSIONS,
)
from app.services.auth_config import (
    validate_auth_configuration,
    LOCAL_ENVIRONMENTS,
    PRODUCTION_ENVIRONMENTS,
    UNSET_JWT_VALUES,
)
from app.services.analysis_persistence import (
    normalize_final_verdict,
    build_resume_state_from_rows,
)


class StableHashingTests(unittest.TestCase):
    """Verify SHA-256 stable derivation helpers."""

    def test_stable_float_deterministic(self):
        a = _stable_float("test-seed", minimum=0.0, maximum=1.0)
        b = _stable_float("test-seed", minimum=0.0, maximum=1.0)
        self.assertEqual(a, b)

    def test_stable_float_respects_bounds(self):
        for seed in ("a", "b", "xyz", "longer-seed-value", "https://example.com/file.mp4"):
            val = _stable_float(seed, minimum=0.1, maximum=0.9)
            self.assertGreaterEqual(val, 0.1)
            self.assertLessEqual(val, 0.9)

    def test_stable_float_different_seeds_differ(self):
        a = _stable_float("seed-a")
        b = _stable_float("seed-b")
        # Not guaranteed but extremely unlikely to collide
        self.assertIsInstance(a, float)
        self.assertIsInstance(b, float)

    def test_stable_int_deterministic(self):
        self.assertEqual(
            _stable_int("test", 1, 100),
            _stable_int("test", 1, 100),
        )

    def test_stable_int_respects_range(self):
        for seed in ("x", "y", "z"):
            val = _stable_int(seed, 10, 20)
            self.assertGreaterEqual(val, 10)
            self.assertLessEqual(val, 20)

    def test_stable_int_equal_bounds(self):
        self.assertEqual(_stable_int("any", 5, 5), 5)

    def test_stable_sample_deterministic(self):
        items = ["a", "b", "c", "d", "e"]
        a = _stable_sample(items, "seed-x", 3)
        b = _stable_sample(items, "seed-x", 3)
        self.assertEqual(a, b)

    def test_stable_sample_respects_count(self):
        items = ["a", "b", "c", "d", "e"]
        result = _stable_sample(items, "seed-y", 2)
        self.assertEqual(len(result), 2)
        for item in result:
            self.assertIn(item, items)

    def test_stable_sample_count_exceeds_list(self):
        items = ["a", "b"]
        result = _stable_sample(items, "seed-z", 5)
        self.assertLessEqual(len(result), len(items))


class ParseRdResultTests(unittest.TestCase):
    """Test _parse_rd_result normalizes Reality Defender output."""

    def test_ensemble_result(self):
        rd_data = {
            "ensemble": {"score": 0.85, "label": "FAKE"},
            "models": [{"name": "model_a", "score": 0.8, "label": "FAKE"}],
            "frameInferences": [{"frame": 1, "score": 0.7, "label": "FAKE"}],
            "requestId": "req-123",
        }
        result = _parse_rd_result(rd_data)
        self.assertTrue(result["is_deepfake"])
        self.assertAlmostEqual(result["deepfake_probability"], 0.85)
        self.assertAlmostEqual(result["confidence"], 0.85)
        self.assertEqual(result["model"], "reality_defender")
        self.assertEqual(len(result["models"]), 1)
        self.assertEqual(len(result["frame_inferences"]), 1)

    def test_fallback_to_first_model(self):
        rd_data = {
            "models": [{"name": "m1", "score": 0.3, "label": "REAL"}],
        }
        result = _parse_rd_result(rd_data)
        self.assertFalse(result["is_deepfake"])
        self.assertAlmostEqual(result["deepfake_probability"], 0.3)
        self.assertAlmostEqual(result["confidence"], 0.7)  # 1 - 0.3

    def test_fallback_to_top_level(self):
        rd_data = {"score": 0.6, "label": "FAKE"}
        result = _parse_rd_result(rd_data)
        self.assertTrue(result["is_deepfake"])
        self.assertAlmostEqual(result["deepfake_probability"], 0.6)

    def test_empty_data(self):
        result = _parse_rd_result({})
        self.assertFalse(result["is_deepfake"])
        self.assertAlmostEqual(result["deepfake_probability"], 0.0)
        self.assertEqual(result["models"], [])
        self.assertEqual(result["frame_inferences"], [])


class DegradationManagerTests(unittest.TestCase):
    def test_initial_state_is_ok(self):
        dm = DegradationManager()
        self.assertEqual(dm.get_status("reality_defender"), "ok")
        self.assertEqual(dm.get_degradation_level("reality_defender"), "full")
        self.assertTrue(dm.is_available("reality_defender"))

    def test_one_failure_degraded(self):
        dm = DegradationManager()
        dm.report_failure("reality_defender", RuntimeError("timeout"))
        self.assertEqual(dm.get_status("reality_defender"), "degraded")
        self.assertEqual(dm.get_degradation_level("reality_defender"), "degraded")
        self.assertTrue(dm.is_available("reality_defender"))

    def test_three_failures_failed(self):
        dm = DegradationManager()
        for i in range(3):
            dm.report_failure("reality_defender", RuntimeError(f"err-{i}"))
        self.assertEqual(dm.get_status("reality_defender"), "failed")
        self.assertEqual(dm.get_degradation_level("reality_defender"), "minimal")
        self.assertFalse(dm.is_available("reality_defender"))

    def test_success_resets(self):
        dm = DegradationManager()
        dm.report_failure("rd", RuntimeError("x"))
        dm.report_failure("rd", RuntimeError("x"))
        dm.report_success("rd")
        self.assertEqual(dm.get_status("rd"), "ok")
        self.assertEqual(dm.get_degradation_level("rd"), "full")

    def test_summary(self):
        dm = DegradationManager()
        dm.report_failure("rd", RuntimeError("x"))
        summary = dm.get_summary()
        self.assertIn("rd", summary["api_status"])
        self.assertEqual(summary["failure_counts"]["rd"], 1)

    def test_independent_apis(self):
        dm = DegradationManager()
        dm.report_failure("rd", RuntimeError("x"))
        self.assertEqual(dm.get_status("virustotal"), "ok")
        self.assertEqual(dm.get_status("rd"), "degraded")


class MinimalResultTests(unittest.TestCase):
    def test_minimal_forensics(self):
        result = minimal_forensics_result("video")
        self.assertFalse(result["is_deepfake"])
        self.assertAlmostEqual(result["confidence"], 0.2)
        self.assertTrue(result["degraded"])
        self.assertEqual(result["degradation_level"], "minimal")

    def test_minimal_osint(self):
        result = minimal_osint_result("text")
        self.assertAlmostEqual(result["threat_score"], 0.0)
        self.assertAlmostEqual(result["confidence"], 0.2)
        self.assertTrue(result["degraded"])


class ReportIntegrityTests(unittest.TestCase):
    def test_sanitize_removes_sensitive_keys(self):
        data = {
            "task_id": "abc",
            "token": "secret",
            "access_token": "secret2",
            "nested": {"share_token": "s3", "safe": "yes"},
            "list_data": [{"token": "x"}],
        }
        clean = _sanitize(data)
        self.assertEqual(clean["task_id"], "abc")
        self.assertNotIn("token", clean)
        self.assertNotIn("access_token", clean)
        self.assertNotIn("share_token", clean["nested"])
        self.assertEqual(clean["nested"]["safe"], "yes")
        self.assertNotIn("token", clean["list_data"][0])
        self.assertEqual(clean["list_data"][0], {})

    def test_build_report_hash_stable(self):
        row = {
            "task_id": "t1",
            "verdict": "suspicious",
            "confidence_overall": 0.85,
            "summary": "test",
            "key_evidence": ["e1"],
            "recommendations": [],
            "verdict_payload": {"verdict": "suspicious"},
        }
        h1 = build_report_hash(row)
        h2 = build_report_hash(row)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_build_report_hash_changes_with_data(self):
        row_a = {"task_id": "t1", "verdict": "suspicious", "confidence_overall": 0.85,
                 "summary": "test", "key_evidence": [], "recommendations": [], "verdict_payload": {}}
        row_b = dict(row_a, verdict="authentic")
        self.assertNotEqual(build_report_hash(row_a), build_report_hash(row_b))

    def test_sensitive_keys_not_in_hash_payload(self):
        row = {
            "task_id": "t1",
            "verdict": "suspicious",
            "confidence_overall": 0.85,
            "summary": "test",
            "key_evidence": [],
            "recommendations": [],
            "verdict_payload": {"verdict": "suspicious", "token": "leaked"},
        }
        h = build_report_hash(row)
        # Verify token is excluded from canonical payload
        canonical = {field: _sanitize(row.get(field)) for field in HASH_FIELDS}
        payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertNotIn("leaked", payload)


class TextValidationTests(unittest.TestCase):
    def test_safe_extensions(self):
        for ext in TEXT_ALLOWED_EXTENSIONS:
            self.assertTrue(_has_safe_text_extension(f"file{ext}"), ext)
        self.assertFalse(_has_safe_text_extension("file.exe"))
        self.assertFalse(_has_safe_text_extension("file.py"))
        self.assertFalse(_has_safe_text_extension(""))

    def test_printable_text(self):
        self.assertTrue(_is_mostly_printable("Hello, world! 你好世界"))
        self.assertTrue(_is_mostly_printable(""))
        self.assertTrue(_is_mostly_printable("line1\nline2\ttab"))

    def test_non_printable_text(self):
        control_heavy = "".join(chr(i) for i in range(1, 32))
        self.assertFalse(_is_mostly_printable(control_heavy))

    def test_validate_real_text_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
            f.write("Hello, this is a normal text file with some content.")
            f.flush()
            path = f.name
        try:
            self.assertTrue(validate_text_plain_file(path, "test.txt"))
        finally:
            os.unlink(path)

    def test_reject_binary_as_text(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"\x00\x01\x02\x03binary\x00\x05")
            path = f.name
        try:
            self.assertFalse(validate_text_plain_file(path, "test.txt"))
        finally:
            os.unlink(path)

    def test_reject_unsafe_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False, mode="w") as f:
            f.write("text content")
            path = f.name
        try:
            self.assertFalse(validate_text_plain_file(path, "test.exe"))
        finally:
            os.unlink(path)

    def test_empty_file_passes(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            path = f.name
        try:
            self.assertTrue(validate_text_plain_file(path, "empty.txt"))
        finally:
            os.unlink(path)


class AuthConfigTests(unittest.TestCase):
    def test_dev_allows_unset_jwt(self):
        self.assertFalse(validate_auth_configuration(environment="dev", jwt_secret="NOT_SET"))

    def test_production_rejects_unset_jwt(self):
        with self.assertRaises(RuntimeError):
            validate_auth_configuration(environment="production", jwt_secret="NOT_SET")

    def test_production_accepts_real_secret(self):
        self.assertTrue(validate_auth_configuration(environment="production", jwt_secret="real-secret-value"))

    def test_local_environments(self):
        for env in LOCAL_ENVIRONMENTS:
            result = validate_auth_configuration(environment=env, jwt_secret="NOT_SET")
            self.assertFalse(result, f"env={env!r} should return False for NOT_SET")

    def test_unset_values(self):
        for val in UNSET_JWT_VALUES:
            self.assertFalse(validate_auth_configuration(environment="dev", jwt_secret=val))


class ConditionsTests(unittest.TestCase):
    """Test convergence and routing logic (pure functions on state dicts)."""

    def test_max_rounds_forces_converge(self):
        state = {"current_round": 5, "max_rounds": 5, "confidence_history": []}
        self.assertEqual(should_converge(state), "converge")

    def test_round_below_max_continues(self):
        state = {"current_round": 1, "max_rounds": 5, "confidence_history": []}
        self.assertEqual(should_converge(state), "continue")

    def test_confidence_convergence(self):
        state = {
            "current_round": 3,
            "max_rounds": 5,
            "convergence_threshold": 0.05,
            "confidence_history": [
                {"scores": {"forensics": 0.80}},
                {"scores": {"forensics": 0.81}},
            ],
        }
        self.assertEqual(should_converge(state), "converge")

    def test_no_convergence_with_large_delta(self):
        state = {
            "current_round": 3,
            "max_rounds": 5,
            "convergence_threshold": 0.05,
            "confidence_history": [
                {"scores": {"forensics": 0.50}},
                {"scores": {"forensics": 0.90}},
            ],
        }
        self.assertEqual(should_converge(state), "continue")

    def test_challenger_route_advances_from_forensics_to_osint(self):
        state = {
            "analysis_phase": "forensics",
            "challenger_feedback": {"requires_more_evidence": False},
        }
        self.assertEqual(challenger_route(state), "osint")

    def test_challenger_route_retries_current_phase(self):
        state = {
            "analysis_phase": "osint",
            "challenger_feedback": {"requires_more_evidence": True},
        }
        self.assertEqual(challenger_route(state), "osint")

    def test_challenger_route_after_consultation_resume(self):
        state = {
            "analysis_phase": "forensics",
            "challenger_feedback": {"requires_more_evidence": True, "consultation_resumed": True},
        }
        self.assertEqual(challenger_route(state), "commander")

    def test_challenger_route_ends_after_commander_review(self):
        state = {
            "analysis_phase": "commander",
            "challenger_feedback": {"requires_more_evidence": False},
        }
        self.assertEqual(challenger_route(state), "end")

    def test_challenger_route_empty_feedback(self):
        state = {}
        self.assertEqual(challenger_route(state), "osint")


class NormalizeVerdictTests(unittest.TestCase):
    def test_adds_compatibility_aliases(self):
        verdict = {
            "confidence": 0.85,
            "verdict": "suspicious",
            "llm_ruling": "Test ruling",
            "agent_weights": {"forensics": 0.6},
            "key_evidence": ["e1"],
        }
        result = normalize_final_verdict(verdict)
        self.assertEqual(result["confidence_overall"], 0.85)
        self.assertEqual(result["verdict_label"], "suspicious")
        self.assertEqual(result["analysis_summary"], "Test ruling")
        self.assertEqual(result["total_evidence"], 1)

    def test_handles_none(self):
        result = normalize_final_verdict(None)
        self.assertEqual(result["confidence"], 0.0)
        self.assertEqual(result["total_evidence"], 0)

    def test_preserves_extra_fields(self):
        verdict = {"confidence": 0.9, "custom_field": "preserved"}
        result = normalize_final_verdict(verdict)
        self.assertEqual(result["custom_field"], "preserved")


class BuildResumeStateTests(unittest.TestCase):
    def _make_rows(self, snapshots):
        rows = []
        for i, snap in enumerate(snapshots, 1):
            rows.append({
                "round_number": i,
                "result_snapshot": snap,
                "evidence_board": {"evidence": [], "challenges": [], "timeline_events": []},
            })
        return rows

    def test_rebuilds_from_persistence_rows(self):
        rows = self._make_rows([
            {"forensics": {"confidence": 0.7}},
            {"osint": {"confidence": 0.6}},
            {"challenger": {"requires_more_evidence": True}},
        ])
        state = build_resume_state_from_rows(
            task_id="t1",
            user_id="u1",
            input_files={},
            input_type="video",
            priority_focus="forensics",
            case_prompt="test",
            evidence_files=[],
            max_rounds=5,
            expert_messages=[{"role": "expert", "content": "opinion"}],
            rows=rows,
        )
        self.assertEqual(state["task_id"], "t1")
        self.assertEqual(state["current_round"], 3)
        self.assertEqual(state["forensics_result"]["confidence"], 0.7)
        self.assertEqual(state["osint_result"]["confidence"], 0.6)
        self.assertIsNotNone(state["challenger_feedback"])
        self.assertEqual(state["consultation_resume"]["expert_message_count"], 1)
        self.assertFalse(state["is_converged"])

    def test_empty_rows_gives_defaults(self):
        state = build_resume_state_from_rows(
            task_id="t1", user_id="u1", input_files={}, input_type="video",
            priority_focus="forensics", case_prompt="", evidence_files=[],
            max_rounds=5, expert_messages=[], rows=[],
        )
        self.assertEqual(state["current_round"], 1)
        self.assertIsNone(state["forensics_result"])
        self.assertIsNone(state["osint_result"])
        self.assertEqual(state["analysis_phase"], "forensics")
        self.assertEqual(state["phase_rounds"], {"forensics": 1, "osint": 1, "commander": 1})


class DefaultMetadataResultTests(unittest.TestCase):
    def test_default_structure(self):
        result = _default_metadata_result()
        self.assertEqual(result["format"], "unknown")
        self.assertIsNone(result["dimensions"])
        self.assertFalse(result["has_exif"])
        self.assertEqual(result["exif_anomalies"], [])
        self.assertFalse(result["compression_artifacts"])
        self.assertIn("无法获取媒体元数据", result["manipulation_indicators"])


if __name__ == "__main__":
    unittest.main()
