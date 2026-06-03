from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.case_library import (
    build_case_fingerprint,
    build_case_library_entry,
    ensure_case_library_entry,
    _derive_media_category,
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


class CapturingLLM:
    def __init__(self, content):
        self.content = content
        self.prompt = ""

    async def ainvoke(self, prompt):
        self.prompt = prompt
        return SimpleNamespace(content=self.content)


class RaceInsertQuery(FakeQuery):
    def execute(self):
        if self.operation == "insert":
            table = self.db.setdefault(self.table_name, [])
            table.append(
                {
                    **self.payload,
                    "id": "case-race",
                    "status": "published",
                    "content_fingerprint": self.payload["content_fingerprint"],
                }
            )
            raise RuntimeError("duplicate key value violates unique constraint")
        return super().execute()


class RaceInsertSupabase(FakeSupabase):
    def table(self, table_name):
        return RaceInsertQuery(table_name, self.db)


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


def test_redact_public_markdown_removes_sensitive_values_and_key_evidence_section():
    markdown = """
# 鉴伪报告
上传者 test@example.com，手机号 13812345678，身份证 110101199901011234。
Storage: user-1/tmpabc.png?token=secret-token

## 关键证据
- {"type": "forensics", "source": "forensics_agent", "confidence": 0.95}
- {"type": "osint", "source": "osint_agent", "confidence": 0.82}

## 处置建议
- 冻结相关账号。
"""

    redacted = redact_public_markdown(markdown)

    assert "test@example.com" not in redacted
    assert "13812345678" not in redacted
    assert "110101199901011234" not in redacted
    assert "secret-token" not in redacted
    assert "关键证据" not in redacted
    assert "forensics_agent" not in redacted
    assert "处置建议" in redacted
    assert "冻结相关账号" in redacted


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
    assert "storage_path" not in entry["public_files"][0]
    assert "sha256" not in entry["public_files"][0]
    assert entry["public_files"][0]["name"] == "voice-of-boss.mp3"
    assert "13812345678" not in entry["report_markdown"]


def test_derive_media_category_accepts_canonical_text_image_input_type_without_files():
    assert _derive_media_category([], "text_image") == "image_text_mixed"


def test_build_markdown_from_report_row_tolerates_invalid_confidence():
    from app.services.case_library import build_markdown_from_report_row

    markdown = build_markdown_from_report_row({
        "verdict": "forged",
        "confidence_overall": "not-a-number",
        "summary": "存在伪造风险。",
        "verdict_payload": {},
    })

    assert "存在伪造风险" in markdown
    assert "综合置信度" not in markdown


def test_public_case_markdown_omits_key_evidence_section():
    from app.services.case_library import build_markdown_from_report_row, sanitize_case_for_response

    markdown = build_markdown_from_report_row({
        "verdict": "forged",
        "confidence_overall": 0.91,
        "summary": "最终裁决已说明证据链。",
        "key_evidence": [{"type": "forensics", "source": "forensics_agent", "confidence": 0.95}],
        "verdict_payload": {"key_evidence": [{"type": "osint", "source": "osint_agent", "confidence": 0.82}]},
    })

    assert "最终裁决已说明证据链" in markdown
    assert "关键证据" not in markdown
    assert "forensics_agent" not in markdown

    payload = sanitize_case_for_response({"id": "case-1", "report_markdown": "# 报告\n\n## 关键证据\n- 无意义字段\n\n## 摘要\n保留"}, include_report=True)

    assert "关键证据" not in payload["report_markdown"]
    assert "无意义字段" not in payload["report_markdown"]
    assert "摘要" in payload["report_markdown"]


@pytest.mark.asyncio
async def test_ensure_case_library_entry_is_idempotent_and_skips_duplicates():
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

    result = await ensure_case_library_entry(client, task, report, "# 报告")

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
                        "storage_path": "stale-public-path.png",
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
        ],
        "tasks": [
            {
                "id": "task-1",
                "metadata": {
                    "files": [
                        {
                            "id": "file-1",
                            "storage_path": "user-1/sample.png",
                        }
                    ]
                },
            }
        ],
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
    assert fake.storage.bucket.signed_paths == [("user-1/sample.png", 600)]


@pytest.mark.asyncio
async def test_generate_case_title_and_summary_fallback():
    """LLM 失败时应返回规则生成的 fallback 标题和摘要"""
    from app.services.case_library import generate_case_title_and_summary

    task = {
        "description": "测试案例提示词",
        "metadata": {"files": [{"name": "test.jpg", "modality": "image"}]},
    }
    report = {
        "verdict": "forged",
        "confidence_overall": 0.92,
        "verdict_payload": {},
    }

    # 传入 None 作为 llm，触发 fallback
    title, summary = await generate_case_title_and_summary(task, report, llm=None)

    assert isinstance(title, str) and len(title) > 0
    assert isinstance(summary, str) and len(summary) > 0
    assert "forged" in title.lower() or "伪造" in title or "确认" in title


@pytest.mark.asyncio
async def test_generate_case_title_and_summary_does_not_send_raw_file_name_to_llm():
    """LLM prompt 不应包含原始文件名，避免模型复述敏感语义"""
    from app.services.case_library import generate_case_title_and_summary

    llm = CapturingLLM('{"title":"公开案例标题","summary":"这是一个面向公众的案例摘要，用于说明检测结论。"}')
    task = {
        "description": "测试案例提示词",
        "metadata": {"files": [{"name": "张三公司内部通知.jpg", "modality": "image"}]},
    }
    report = {"verdict": "forged", "confidence_overall": 0.92, "verdict_payload": {}}

    await generate_case_title_and_summary(task, report, llm=llm)

    assert "张三公司内部通知.jpg" not in llm.prompt
    assert "张三公司" not in llm.prompt


@pytest.mark.asyncio
async def test_ensure_case_library_entry_treats_race_insert_as_duplicate():
    from app.services.case_library import ensure_case_library_entry

    db = {"case_library_entries": []}
    client = RaceInsertSupabase(db)
    task = {
        "id": "task-race",
        "description": "核验",
        "metadata": {"share_to_casebase": True, "files": [{"name": "a.txt", "modality": "text", "sha256": "race"}]},
    }
    report = {"verdict": "suspicious", "summary": "重复", "verdict_payload": {}}

    result = await ensure_case_library_entry(client, task, report, "# 报告")

    assert result["status"] == "duplicate"
    assert result["entry"]["id"] == "case-race"


@pytest.mark.asyncio
async def test_ensure_case_library_entry_async_skipped():
    """未勾选 share_to_casebase 时应返回 skipped"""
    from app.services.case_library import ensure_case_library_entry

    task = {"metadata": {}}  # 没有 share_to_casebase
    result = await ensure_case_library_entry(None, task, None)
    assert result["status"] == "skipped"
    assert result["reason"] == "not_requested"
