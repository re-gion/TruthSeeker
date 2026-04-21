from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class FakeQuery:
    def __init__(self, table_name, db):
        self.table_name = table_name
        self.db = db
        self.filters = {}
        self.sort = None
        self.limit_value = None

    def select(self, _columns):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, key, desc=False):
        self.sort = (key, desc)
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        rows = list(self.db.get(self.table_name, []))

        for key, value in self.filters.items():
            rows = [row for row in rows if row.get(key) == value]

        if self.sort:
            sort_key, desc = self.sort
            rows = sorted(rows, key=lambda row: row.get(sort_key) or "", reverse=desc)

        if self.limit_value is not None:
            rows = rows[: self.limit_value]

        return SimpleNamespace(data=rows)


class FakeSupabase:
    def __init__(self, db):
        self.db = db

    def table(self, table_name):
        return FakeQuery(table_name, self.db)


def build_dashboard_db():
    from datetime import datetime, timezone, timedelta
    from zoneinfo import ZoneInfo
    now = datetime.now(timezone.utc)
    today_str = now.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
    yesterday = now - timedelta(days=1)
    yesterday_str = yesterday.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
    return {
        "tasks": [
            {
                "id": "task-1",
                "status": "completed",
                "input_type": "video",
                "result": {"verdict": "forged", "threat_type": "政务短视频换脸"},
                "response_ms": 180,
                "started_at": f"{today_str}T08:00:00.000Z",
                "completed_at": f"{today_str}T08:00:00.180Z",
                "created_at": f"{today_str}T07:55:00.000Z",
                "user_id": "user-1",
            },
            {
                "id": "task-2",
                "status": "completed",
                "input_type": "audio",
                "result": "{\"verdict\":\"authentic\",\"threat_type\":\"语音冒充\"}",
                "started_at": f"{yesterday_str}T08:00:00.000Z",
                "completed_at": f"{yesterday_str}T08:00:00.120Z",
                "created_at": f"{yesterday_str}T07:55:00.000Z",
                "token": "task-secret",
            },
            {
                "id": "task-3",
                "status": "analyzing",
                "input_type": "text",
                "created_at": f"{today_str}T10:00:00.000Z",
            },
        ],
        "reports": [
            {
                "id": "report-1",
                "task_id": "task-1",
                "verdict": "forged",
                "generated_at": f"{today_str}T08:01:00.000Z",
                "key_evidence": [
                    {"type": "visual", "source": "frame_forensics"},
                    {"type": "visual", "source": "face_swap_trace"},
                    {"type": "osint", "source": "reverse_search"},
                ],
                "verdict_payload": {
                    "verdict": "forged",
                    "analysis_summary": "高风险伪造",
                    "raw_result": {"should_not": "leak"},
                },
            },
            {
                "id": "report-2",
                "task_id": "task-2",
                "verdict": "authentic",
                "generated_at": f"{yesterday_str}T08:01:00.000Z",
                "key_evidence": [
                    {"type": "audio", "source": "voiceprint"},
                    {"type": "text", "source": "metadata"},
                ],
                "verdict_payload": {
                    "verdict": "authentic",
                    "analysis_summary": "未发现明显伪造",
                    "user_email": "hidden@example.com",
                },
            },
        ],
        "consultation_invites": [
            {
                "id": "invite-1",
                "task_id": "task-1",
                "status": "accepted",
                "created_at": f"{today_str}T08:05:00.000Z",
                "expires_at": "2999-01-01T00:00:00+00:00",
                "token": "invite-secret",
                "invitee_email": "expert@example.com",
            },
            {
                "id": "invite-2",
                "task_id": "task-1",
                "status": "pending",
                "created_at": f"{today_str}T08:06:00.000Z",
                "expires_at": "2999-01-01T00:00:00+00:00",
            },
        ],
    }


class DashboardApiTests(TestCase):
    def test_dashboard_overview_returns_public_aggregated_snapshot(self):
        from app.api.v1 import dashboard as dashboard_module

        with patch.object(dashboard_module, "supabase", FakeSupabase(build_dashboard_db())):
            client = TestClient(app)
            response = client.get("/api/v1/dashboard/overview")

        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(
            set(body.keys()),
            {
                "generated_at",
                "kpis",
                "trend_series",
                "threat_mix",
                "status_breakdown",
                "evidence_mix",
                "flow_sankey",
                "capability_metrics",
                "data_warnings",
            },
        )
        self.assertEqual(body["data_warnings"], [])
        self.assertEqual(
            body["kpis"],
            {
                "total_tasks": 3,
                "high_risk_tasks": 1,
                "average_response_ms": 150,
                "completed_today": 1,
            },
        )
        self.assertEqual(
            [item["label"] for item in body["evidence_mix"]],
            ["视觉证据", "开源情报", "音频证据", "文本证据"],
        )
        self.assertTrue(body["flow_sankey"]["nodes"])
        self.assertTrue(body["flow_sankey"]["links"])

        serialized = str(body)
        self.assertNotIn("task-secret", serialized)
        self.assertNotIn("invite-secret", serialized)
        self.assertNotIn("hidden@example.com", serialized)
        self.assertNotIn("raw_result", serialized)

    def test_dashboard_overview_returns_empty_evidence_views_when_reports_missing(self):
        from app.api.v1 import dashboard as dashboard_module

        db = build_dashboard_db()
        db["reports"] = []

        with patch.object(dashboard_module, "supabase", FakeSupabase(db)):
            client = TestClient(app)
            response = client.get("/api/v1/dashboard/overview")

        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["evidence_mix"], [])
        self.assertEqual(body["flow_sankey"], {"nodes": [], "links": []})
        self.assertEqual(body["capability_metrics"][0]["value"], 0)
