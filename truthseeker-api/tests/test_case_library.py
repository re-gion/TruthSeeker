from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.services.case_library import (
    build_case_fingerprint,
    build_case_library_entry,
    ensure_case_library_entry,
    redact_public_markdown,
)


class FakeQuery:
    def __init__(self, table_name, db):
        self.table_name = table_name
        self.db = db
        self.filters = {}
        self.payload = None
        self.operation = None
        self.order_by = None
        self.range_value = None
        self.limit_value = None

    def select(self, _columns, count=None):
        self.count_mode = count
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, key, desc=False):
        self.order_by = (key, desc)
        return self

    def range(self, start, end):
        self.range_value = (start, end)
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def execute(self):
        table = self.db.setdefault(self.table_name, [])
        if self.operation == "insert":
            row = {**self.payload, "id": self.payload.get("id") or f"{self.table_name}-{len(table) + 1}"}
            table.append(row)
            return SimpleNamespace(data=[row], count=None)

        rows = list(table)
        for key, value in self.filters.items():
            rows = [row for row in rows if row.get(key) == value]
        if self.order_by:
            key, desc = self.order_by
            rows = sorted(rows, key=lambda row: row.get(key) or "", reverse=desc)
        count = len(rows)
        if self.range_value:
            start, end = self.range_value
            rows = rows[start:end + 1]
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return SimpleNamespace(data=rows, count=count)


class FakeStorageBucket:
    def __init__(self):
        self.signed_paths = []

    def create_signed_url(self, path, expires_in):
        self.signed_paths.append((path, expires_in))
        return {"signedURL": f"https://storage.example/sign/{path}?token=secret"}


class FakeStorage:
    def __init__(self):
        self.bucket = FakeStorageBucket()

    def from_(self, bucket_name):
        assert bucket_name == "media"
        return self.bucket


class FakeSupabase:
    def __init__(self, db):
        self.db = db
        self.storage = FakeStorage()

    def table(self, table_name):
        return FakeQuery(table_name, self.db)


def test_build_case_fingerprint_is_stable_for_same_files_and_prompt():
    files_a = [
        {"name": "a.png", "sha256": "bbb", "storage_path": "u/a.png"},
        {"name": "b.txt", "sha256": "aaa", "storage_path": "u/b.txt"},
    ]
    files_b = [
        {"name": "b-copy.txt", "sha256": "aaa", "storage_path": "other/b.txt"},
        {"name": "a-copy.png", "sha256": "bbb", "storage_path": "other/a.png"},
    ]

    assert build_case_fingerprint(files_a, " 请 判断 是否伪造 ") == build_case_fingerprint(files_b, "请 判断 是否伪造")
    assert build_case_fingerprint(files_a, "另一个提示词") != build_case_fingerprint(files_a, "请 判断 是否伪造")


def test_redact_public_markdown_removes_sensitive_values_but_keeps_report_evidence():
    markdown = """
# 鉴伪报告
上传者 test@example.com，手机号 13812345678，身份证 110101199901011234。
Storage: user-1/tmpabc.png?token=secret-token
关键证据：口型不同步，压缩伪影异常。
"""

    redacted = redact_public_markdown(markdown)

    assert "test@example.com" not in redacted
    assert "13812345678" not in redacted
    assert "110101199901011234" not in redacted
    assert "secret-token" not in redacted
    assert "口型不同步" in redacted
    assert "压缩伪影异常" in redacted


def test_build_case_library_entry_derives_category_and_public_fields():
    task = {
        "id": "task-1",
        "user_id": "user-1",
        "title": "董事长语音诈骗 13812345678",
        "description": "核验是否合成",
        "metadata": {
            "share_to_casebase": True,
            "files": [
                {
                    "name": "voice-of-boss.mp3",
                    "mime_type": "audio/mpeg",
                    "size_bytes": 1024,
                    "modality": "audio",
                    "storage_path": "user-1/tmp.mp3",
                    "sha256": "abc123",
                }
            ],
        },
    }
    report = {
        "verdict": "forged",
        "confidence_overall": 0.91,
        "summary": "高度疑似音频克隆。",
        "verdict_payload": {"analysis_summary": "高度疑似音频克隆。", "recommendations": ["冻结转账"]},
    }

    entry = build_case_library_entry(task, report, "# 报告\n手机号 13812345678\n关键证据保留")

    assert entry["media_category"] == "audio_forgery"
    assert entry["title"] == "董事长语音诈骗 [手机号]"
    assert entry["summary"] == "高度疑似音频克隆。"
    assert entry["verdict"] == "forged"
    assert entry["confidence_overall"] == 0.91
    assert entry["content_fingerprint"]
    assert entry["public_files"][0]["storage_path"] == "user-1/tmp.mp3"
    assert entry["public_files"][0]["name"] == "voice-of-boss.mp3"
    assert "13812345678" not in entry["report_markdown"]


def test_ensure_case_library_entry_is_idempotent_and_skips_duplicates():
    db = {
        "case_library_entries": [
            {
                "id": "case-existing",
                "status": "published",
                "content_fingerprint": build_case_fingerprint([{"sha256": "abc"}], "核验"),
            }
        ]
    }
    client = FakeSupabase(db)
    task = {
        "id": "task-1",
        "user_id": "user-1",
        "title": "重复案例",
        "description": "核验",
        "metadata": {"share_to_casebase": True, "files": [{"name": "a.txt", "modality": "text", "storage_path": "u/a.txt", "sha256": "abc"}]},
    }
    report = {"verdict": "suspicious", "summary": "重复", "verdict_payload": {}}

    result = ensure_case_library_entry(client, task, report, "# 报告")

    assert result["status"] == "duplicate"
    assert result["entry"]["id"] == "case-existing"
    assert len(db["case_library_entries"]) == 1


def test_public_cases_api_lists_details_and_creates_preview_urls(monkeypatch):
    from app.api.v1 import cases as cases_module

    monkeypatch.setattr("app.middleware.auth._is_public", lambda path, method="GET": True)
    db = {
        "case_library_entries": [
            {
                "id": "case-1",
                "task_id": "task-1",
                "status": "published",
                "title": "公开案例",
                "media_category": "image_forgery",
                "summary": "存在局部篡改。",
                "verdict": "suspicious",
                "confidence_overall": 0.82,
                "difficulty": "Medium",
                "public_files": [
                    {
                        "id": "file-1",
                        "name": "sample.png",
                        "mime_type": "image/png",
                        "modality": "image",
                        "size_bytes": 2048,
                        "storage_path": "user-1/sample.png",
                    }
                ],
                "report_markdown": "# 报告\n存在局部篡改。",
                "published_at": "2026-05-28T00:00:00+00:00",
            },
            {
                "id": "case-private",
                "status": "draft",
                "title": "未公开",
                "media_category": "image_forgery",
            },
        ]
    }
    fake = FakeSupabase(db)
    monkeypatch.setattr(cases_module, "supabase", fake)

    client = TestClient(app)
    listing = client.get("/api/v1/cases?category=image_forgery&page=1&page_size=6")
    detail = client.get("/api/v1/cases/case-1")
    preview = client.post("/api/v1/cases/case-1/preview-url", json={"file_id": "file-1"})

    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == "case-1"
    assert detail.status_code == 200
    assert detail.json()["report_markdown"].startswith("# 报告")
    assert detail.json()["public_files"][0]["storage_path"] is None
    assert preview.status_code == 200
    assert preview.json()["signed_url"].startswith("https://storage.example/sign/user-1/sample.png")
