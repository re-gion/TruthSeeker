import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app


class FakeQuery:
    def __init__(self, table_name, db):
        self.table_name = table_name
        self.db = db
        self.filters = {}
        self.payload = None
        self.operation = None
        self.limit_value = None

    def select(self, _columns, count=None):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, key, desc=False):
        return self

    def range(self, start, end):
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def upsert(self, payload, on_conflict=None):
        self.operation = "upsert"
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def execute(self):
        table = self.db.setdefault(self.table_name, [])
        if self.operation == "insert":
            row = {**self.payload, "id": self.payload.get("id") or f"{self.table_name}-{len(table) + 1}"}
            table.append(row)
            return SimpleNamespace(data=[row], count=None)
        if self.operation == "upsert":
            rows = self.payload if isinstance(self.payload, list) else [self.payload]
            for row in rows:
                table.append({**row, "id": row.get("id") or f"{self.table_name}-{len(table) + 1}"})
            return SimpleNamespace(data=rows, count=None)
        if self.operation == "delete":
            self.db[self.table_name] = []
            return SimpleNamespace(data=[], count=None)
        rows = list(table)
        for key, value in self.filters.items():
            rows = [row for row in rows if row.get(key) == value]
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return SimpleNamespace(data=rows, count=len(rows))


class FakeRpc:
    def __init__(self, name, params, db):
        self.name = name
        self.params = params
        self.db = db

    def execute(self):
        if self.name == "match_case_library_rag_chunks":
            return SimpleNamespace(data=list(self.db.get("vector_matches", [])))
        return SimpleNamespace(data=[])


class FakeSupabase:
    def __init__(self, db):
        self.db = db

    def table(self, table_name):
        return FakeQuery(table_name, self.db)

    def rpc(self, name, params):
        return FakeRpc(name, params, self.db)


def test_chunk_markdown_is_stable_and_keeps_headings():
    from app.services.case_rag import build_chunk_hash, chunk_markdown

    markdown = "# 案例\n\n## 关键证据\n" + ("口型不同步。压缩伪影异常。\n\n" * 80)
    chunks = chunk_markdown(markdown, max_chars=300, overlap_chars=40)

    assert len(chunks) > 1
    assert chunks[0]["chunk_index"] == 0
    assert any("关键证据" in item["text"] for item in chunks)
    assert build_chunk_hash("builtin", "case-audio-scam", chunks[0]["text"]) == build_chunk_hash(
        "builtin", "case-audio-scam", chunks[0]["text"]
    )


def test_hybrid_merge_prefers_combined_vector_and_keyword_score():
    from app.services.case_rag import merge_hybrid_results

    merged = merge_hybrid_results(
        vector_rows=[
            {"chunk_id": "a", "similarity": 0.8, "title": "A"},
            {"chunk_id": "b", "similarity": 0.9, "title": "B"},
        ],
        keyword_rows=[
            {"chunk_id": "a", "keyword_score": 0.9, "title": "A"},
            {"chunk_id": "b", "keyword_score": 0.1, "title": "B"},
        ],
        limit=2,
    )

    assert [item["chunk_id"] for item in merged] == ["a", "b"]
    assert merged[0]["score"] > merged[1]["score"]


def test_case_rag_search_degrades_when_embedding_unavailable(monkeypatch):
    from app.services import case_rag

    async def fail_embed(_text):
        return {"status": "failed", "error": "missing embedding key", "embedding": None}

    monkeypatch.setattr(case_rag, "embed_text", fail_embed)

    result = asyncio.run(case_rag.case_rag_search(FakeSupabase({}), query="核验伪造视频", agent="osint"))

    assert result["status"] == "degraded"
    assert result["degraded"] is True
    assert "missing embedding key" in result["summary"]


def test_case_rag_search_merges_vector_and_keyword_hits(monkeypatch):
    from app.services import case_rag

    db = {
        "vector_matches": [
            {"chunk_id": "chunk-a", "case_id": "builtin-audio-scam", "title": "董事长语音诈骗", "similarity": 0.82},
        ],
        "case_library_rag_chunks": [
            {"chunk_id": "chunk-a", "case_id": "builtin-audio-scam", "title": "董事长语音诈骗", "keyword_score": 0.6},
        ],
    }

    async def fake_embed(_text):
        return {"status": "success", "embedding": [0.01] * 1024, "model": "test-embedding"}

    monkeypatch.setattr(case_rag, "embed_text", fake_embed)

    result = asyncio.run(case_rag.case_rag_search(FakeSupabase(db), query="高管语音转账诈骗", agent="forensics", top_k=3))

    assert result["status"] == "success"
    assert result["matches"][0]["case_id"] == "builtin-audio-scam"
    assert result["tool"] == "case_rag_search"


def test_builtin_case_detail_is_served_by_cases_api(monkeypatch):
    from app.api.v1 import cases as cases_module

    monkeypatch.setattr("app.middleware.auth._is_public", lambda path, method="GET": True)
    monkeypatch.setattr(cases_module, "supabase", FakeSupabase({"case_library_entries": []}))

    client = TestClient(app)
    resp = client.get("/api/v1/cases/builtin-audio-scam")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["id"] == "builtin-audio-scam"
    assert payload["source_kind"] == "builtin"
    assert payload["report_markdown"].startswith("# 董事长语音诈骗")
