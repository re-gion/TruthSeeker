import unittest


class EvidenceFileContractTests(unittest.TestCase):
    def test_normalize_uploaded_files_preserves_modalities_and_rejects_prompt_only(self):
        from app.services.evidence_files import (
            MAX_EVIDENCE_FILES,
            normalize_uploaded_files,
            require_evidence_files,
        )

        raw_files = [
            {
                "name": "clip.mp4",
                "mime_type": "video/mp4",
                "size_bytes": 1024,
                "storage_path": "user/clip.mp4",
            },
            {
                "name": "source.txt",
                "mime_type": "text/plain",
                "size_bytes": 128,
                "storage_path": "user/source.txt",
            },
        ]

        files = normalize_uploaded_files(raw_files)

        self.assertEqual(MAX_EVIDENCE_FILES, 5)
        self.assertEqual([item["modality"] for item in files], ["video", "text"])
        self.assertEqual(files[0]["id"], "file-1")
        self.assertEqual(files[1]["id"], "file-2")
        self.assertTrue(require_evidence_files(files))
        self.assertFalse(require_evidence_files([]))

    def test_build_agent_file_views_routes_text_only_to_osint(self):
        from app.services.evidence_files import build_agent_file_views, normalize_uploaded_files

        files = normalize_uploaded_files(
            [
                {
                    "name": "voice.wav",
                    "mime_type": "audio/wav",
                    "size_bytes": 2048,
                    "storage_path": "case/voice.wav",
                    "file_url": "https://signed/voice.wav",
                },
                {
                    "name": "indicators.txt",
                    "mime_type": "text/plain",
                    "size_bytes": 256,
                    "storage_path": "case/indicators.txt",
                    "file_url": "https://signed/indicators.txt",
                },
            ]
        )

        views = build_agent_file_views(files)

        self.assertEqual([item["modality"] for item in views["forensics"]], ["audio"])
        self.assertEqual([item["modality"] for item in views["osint"]], ["text", "audio"])
        self.assertEqual(views["primary_forensics"]["file_url"], "https://signed/voice.wav")
        self.assertEqual(views["primary_osint"]["file_url"], "https://signed/indicators.txt")


class ReportIntegrityTests(unittest.TestCase):
    def test_report_hash_is_stable_and_sensitive_fields_are_excluded(self):
        from app.services.report_integrity import build_report_hash

        base = {
            "task_id": "task-1",
            "verdict": "forged",
            "confidence_overall": 0.91,
            "summary": "综合判断为伪造",
            "key_evidence": [{"type": "visual", "source": "forensics", "confidence": 0.87}],
            "recommendations": ["立即下架"],
            "verdict_payload": {"verdict": "forged", "token": "secret", "raw_result": {"x": 1}},
        }
        reordered = {
            "recommendations": ["立即下架"],
            "summary": "综合判断为伪造",
            "confidence_overall": 0.91,
            "verdict": "forged",
            "task_id": "task-1",
            "verdict_payload": {"raw_result": {"x": 1}, "token": "changed", "verdict": "forged"},
            "key_evidence": [{"confidence": 0.87, "source": "forensics", "type": "visual"}],
        }

        self.assertEqual(build_report_hash(base), build_report_hash(reordered))
        self.assertRegex(build_report_hash(base), r"^[a-f0-9]{64}$")

    def test_build_report_row_includes_report_hash(self):
        from app.services.analysis_persistence import build_report_row

        row = build_report_row(
            "task-1",
            {
                "verdict": "suspicious",
                "confidence": 0.72,
                "key_evidence": [{"type": "text", "source": "osint", "confidence": 0.7}],
                "recommendations": ["人工复核"],
                "llm_ruling": "证据存在冲突",
            },
            generated_at="2026-04-20T00:00:00+00:00",
        )

        self.assertIn("report_hash", row)
        self.assertRegex(row["report_hash"], r"^[a-f0-9]{64}$")


class AuditLogContractTests(unittest.TestCase):
    def test_build_audit_log_row_redacts_sensitive_payload(self):
        from app.services.audit_log import build_audit_log_row

        row = build_audit_log_row(
            action="share_created",
            task_id="task-1",
            user_id="user-1",
            metadata={
                "share_token": "secret-token",
                "file_url": "https://signed-url",
                "safe": "kept",
            },
        )

        self.assertEqual(row["action"], "share_created")
        self.assertEqual(row["task_id"], "task-1")
        self.assertEqual(row["user_id"], "user-1")
        self.assertEqual(row["metadata"]["share_token"], "[REDACTED]")
        self.assertEqual(row["metadata"]["file_url"], "[REDACTED]")
        self.assertEqual(row["metadata"]["safe"], "kept")


class AuthPublicRouteTests(unittest.TestCase):
    def test_write_side_routes_are_not_public_when_auth_middleware_is_enabled(self):
        from app.middleware.auth import _is_public

        self.assertFalse(_is_public("/api/v1/upload/", "POST"))
        self.assertFalse(_is_public("/api/v1/tasks", "POST"))
        self.assertFalse(_is_public("/api/v1/detect/stream", "POST"))
        self.assertFalse(_is_public("/api/v1/report/task-1/md", "GET"))
        self.assertFalse(_is_public("/api/v1/share/task-1", "POST"))
        self.assertTrue(_is_public("/api/v1/share/share-token", "GET"))
        self.assertTrue(_is_public("/api/v1/consultation/invite/invite-token", "GET"))
        self.assertTrue(_is_public("/api/v1/consultation/task-1/messages", "GET"))
        self.assertTrue(_is_public("/api/v1/consultation/task-1/unread", "GET"))


if __name__ == "__main__":
    unittest.main()
