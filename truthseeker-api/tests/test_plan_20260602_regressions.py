import asyncio
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_graph_ends_immediately_after_commander():
    source = Path("app/agents/graph.py").read_text(encoding="utf-8")

    assert 'graph.add_edge("commander", END)' in source
    assert 'graph.add_edge("commander", "challenger")' not in source


def test_legacy_paid_text_provider_code_and_docs_are_removed():
    repo_root = Path(__file__).resolve().parents[2]
    checked_paths = [
        repo_root / "truthseeker-api" / ".env.example",
        repo_root / "truthseeker-api" / "app" / "config.py",
        repo_root / "truthseeker-api" / "app" / "agents" / "tools" / "internal_text_aigc.py",
        repo_root / "truthseeker-api" / "app" / "agents" / "nodes" / "forensics.py",
        repo_root / "truthseeker-api" / "app" / "agents" / "nodes" / "osint.py",
        repo_root / "docs" / "APP_FLOW.md",
        repo_root / "docs" / "BACKEND_STRUCTURE.md",
        repo_root / "docs" / "TECH_STACK.md",
        repo_root / "task.md",
        repo_root / "lessons.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in checked_paths)

    legacy_name = "Sapl" + "ing"
    legacy_lower = "sap" + "ling"
    legacy_upper = "SAP" + "LING"
    legacy_tool = legacy_lower + "_ai_detector"

    assert legacy_name not in combined
    assert legacy_lower not in combined
    assert legacy_upper not in combined
    assert legacy_tool not in combined


@pytest.mark.asyncio
async def test_ai_text_detector_uses_internal_tool_without_external_http(monkeypatch):
    from app.agents.tools import internal_text_aigc

    async def fake_analyze_text(text):
        assert text == "请立即验证账号。否则将限制功能。"
        return {
            "is_ai_generated": True,
            "ai_probability": 0.76,
            "confidence": 0.81,
            "degraded": False,
            "manipulation_score": 0.64,
            "key_claims": ["要求验证账号"],
            "anomalies": ["句式模板化"],
            "structural_analysis": {"local_ai_score": 0.72},
            "social_engineering": {"score": 0.64, "indicators": ["设置功能受限压力"]},
            "extracted_urls": [],
        }

    monkeypatch.setattr(internal_text_aigc, "analyze_text", fake_analyze_text, raising=False)
    monkeypatch.setattr(internal_text_aigc.settings, "TEXT_AIGC_DETECTOR_ENABLED", True, raising=False)
    monkeypatch.setattr(internal_text_aigc.settings, "TEXT_AIGC_AI_THRESHOLD", 0.6, raising=False)

    result = await internal_text_aigc.detect_ai_generated_text("请立即验证账号。否则将限制功能。")

    assert result["status"] == "success"
    assert result["provider"] == "internal_text_detector"
    assert result["tool"] == "ai_text_detector"
    assert result["analysis_available"] is True
    assert result["external_analysis_available"] is False
    assert result["ai_probability"] == pytest.approx(0.76)
    assert result["is_ai_generated"] is True
    assert result["internal_text_analysis"]["structural_analysis"]["local_ai_score"] == pytest.approx(0.72)
    assert "http" not in result


@pytest.mark.asyncio
async def test_internal_ai_text_detector_handles_unicode_without_api_fallback(monkeypatch):
    from app.agents.tools import internal_text_aigc

    async def fake_analyze_text(_text):
        return {
            "is_ai_generated": True,
            "ai_probability": 0.68,
            "confidence": 0.79,
            "degraded": False,
            "key_claims": ["通知要求用户跳转链接"],
            "anomalies": ["客服口吻异常"],
        }

    monkeypatch.setattr(internal_text_aigc, "analyze_text", fake_analyze_text, raising=False)
    monkeypatch.setattr(internal_text_aigc.settings, "TEXT_AIGC_DETECTOR_ENABLED", True, raising=False)

    result = await internal_text_aigc.detect_ai_generated_text("客服通知：请立即验证账号。")

    assert result["status"] == "success"
    assert result["analysis_available"] is True
    assert result["external_analysis_available"] is False
    assert result["provider"] == "internal_text_detector"
    assert result["ai_probability"] == pytest.approx(0.68)
    assert "error" not in result


def test_internal_text_structure_exposes_multi_signal_aigc_features():
    from app.agents.tools.text_detection import analyze_text_structure

    result = analyze_text_structure(
        "请立即核验账号。请立即核验身份。请立即扫码进入。请立即完成复核。"
    )

    assert "local_ai_score" in result
    assert "burstiness_score" in result
    assert "repetition_score" in result
    assert "detection_signals" in result
    assert 0.0 <= result["local_ai_score"] <= 1.0
    assert any(signal["name"] == "repetitive_phrasing" for signal in result["detection_signals"])

@pytest.mark.asyncio
async def test_forensics_adds_internal_text_aigc_tool_result(monkeypatch):
    from app.agents.nodes import forensics as forensics_module

    async def fake_read_text_sample(_item):
        return {"text": "请立即验证账号，否则将限制功能。", "encoding": "utf-8", "charset": "utf-8"}

    async def fake_text_detector(text, target="text"):
        return {
            "tool": "ai_text_detector",
            "provider": "internal_text_detector",
            "target": target,
            "status": "success",
            "degraded": False,
            "ai_probability": 0.73,
            "summary": "内部文本检测: AI 生成概率 73.0%",
        }

    async def fake_forensics_interpret(*args, **kwargs):
        return "取证报告"

    async def fake_case_rag_search(*args, **kwargs):
        return {"tool": "case_rag_search", "status": "skipped", "matches": [], "summary": "跳过"}

    monkeypatch.setattr(forensics_module, "_read_text_sample", fake_read_text_sample)
    monkeypatch.setattr(forensics_module, "detect_ai_generated_text", fake_text_detector)
    monkeypatch.setattr(forensics_module, "forensics_interpret", fake_forensics_interpret)
    monkeypatch.setattr(forensics_module, "case_rag_search", fake_case_rag_search)
    monkeypatch.setattr(forensics_module, "record_audit_event", lambda *args, **kwargs: None)

    updates = await forensics_module.forensics_node({
        "task_id": "task-1",
        "input_type": "text",
        "case_prompt": "",
        "current_round": 1,
        "phase_rounds": {"forensics": 1, "osint": 1, "commander": 1},
        "evidence_files": [{"id": "file-1", "name": "notice.txt", "modality": "text"}],
        "input_files": {},
        "tool_results": {},
        "confidence_history": [],
    })

    tool_results = updates["forensics_result"]["tool_results"]
    assert any(item.get("tool") == "ai_text_detector" for item in tool_results)
    assert updates["forensics_result"]["text_aigc_detection"]["ai_probability"] == pytest.approx(0.73)


@pytest.mark.asyncio
async def test_forensics_exposes_aigc_fields_without_deepfake_report_aliases(monkeypatch):
    from app.agents.nodes import forensics as forensics_module

    async def fake_analyze_media(*args, **kwargs):
        return {
            "model": "sightengine_genai",
            "provider": "sightengine",
            "analysis_available": True,
            "is_ai_generated": True,
            "is_aigc": True,
            "aigc_probability": 0.91,
            "ai_generated_probability": 0.91,
            "confidence": 0.91,
        }

    async def fake_forensics_interpret(*args, **kwargs):
        return "AIGC 图像取证报告"

    async def fake_case_rag_search(*args, **kwargs):
        return {"tool": "case_rag_search", "status": "skipped", "matches": [], "summary": "跳过"}

    monkeypatch.setattr(forensics_module, "analyze_media", fake_analyze_media)
    monkeypatch.setattr(forensics_module, "forensics_interpret", fake_forensics_interpret)
    monkeypatch.setattr(forensics_module, "case_rag_search", fake_case_rag_search)
    monkeypatch.setattr(forensics_module, "scan_file_hash", lambda *args, **kwargs: asyncio.sleep(0, result={"status": "skipped"}))
    monkeypatch.setattr(forensics_module, "record_audit_event", lambda *args, **kwargs: None)

    updates = await forensics_module.forensics_node({
        "task_id": "task-1",
        "input_type": "image",
        "case_prompt": "",
        "current_round": 1,
        "phase_rounds": {"forensics": 1, "osint": 1, "commander": 1},
        "evidence_files": [{"id": "file-1", "name": "sample.jpg", "modality": "image", "file_url": "https://storage.example/sample.jpg"}],
        "input_files": {},
        "tool_results": {},
        "confidence_history": [],
    })

    result = updates["forensics_result"]
    assert result["is_aigc"] is True
    assert result["is_aigc_manipulated"] is True
    assert result["aigc_probability"] == pytest.approx(0.91)
    assert "deepfake_probability" not in result
    assert "is_deepfake" not in result
    assert "AIGC 风险" in updates["evidence_board"][0]["description"]


@pytest.mark.asyncio
async def test_osint_adds_internal_text_aigc_tool_result(monkeypatch):
    from app.agents.nodes import osint as osint_module

    async def fake_read_text_sample(_item):
        return {"text": "请立即验证账号，否则将限制功能。", "encoding": "utf-8", "charset": "utf-8"}

    async def fake_text_detector(text, target="text"):
        return {
            "tool": "ai_text_detector",
            "provider": "internal_text_detector",
            "target": target,
            "status": "success",
            "degraded": False,
            "ai_probability": 0.74,
            "summary": "内部文本检测: AI 生成概率 74.0%",
        }

    async def fake_analyze_text(_text):
        return {"ai_probability": 0.2, "manipulation_score": 0.1, "social_engineering": {"score": 0.1}, "key_claims": [], "anomalies": []}

    async def fake_case_rag_search(*args, **kwargs):
        return {"tool": "case_rag_search", "status": "skipped", "matches": [], "summary": "跳过"}

    async def fake_osint_interpret(*args, **kwargs):
        return "情报报告"

    async def fake_search_osint(*args, **kwargs):
        return {"status": "skipped", "results": [], "summary": "跳过"}

    monkeypatch.setattr(osint_module, "_read_text_sample", fake_read_text_sample)
    monkeypatch.setattr(osint_module, "detect_ai_generated_text", fake_text_detector)
    monkeypatch.setattr(osint_module, "analyze_text", fake_analyze_text)
    monkeypatch.setattr(osint_module, "search_osint", fake_search_osint)
    monkeypatch.setattr(osint_module, "case_rag_search", fake_case_rag_search)
    monkeypatch.setattr(osint_module, "osint_interpret", fake_osint_interpret)
    monkeypatch.setattr(osint_module, "record_audit_event", lambda *args, **kwargs: None)

    updates = await osint_module.osint_node({
        "task_id": "task-1",
        "input_type": "text",
        "case_prompt": "",
        "current_round": 1,
        "phase_rounds": {"forensics": 1, "osint": 1, "commander": 1},
        "evidence_files": [{"id": "file-1", "name": "notice.txt", "modality": "text"}],
        "input_files": {},
        "tool_results": {},
        "forensics_result": {},
        "confidence_history": [],
    })

    assert updates["osint_result"]["text_aigc_detection"]["ai_probability"] == pytest.approx(0.74)
    assert updates["osint_result"]["text_risk_score"] >= 0.37


class FakeQuery:
    def __init__(self, table_name, db):
        self.table_name = table_name
        self.db = db
        self.filters = {}
        self.payload = None
        self.operation = None
        self.limit_value = None
        self.order_by = None

    def select(self, _columns, count=None):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, key, desc=False):
        self.order_by = (key, desc)
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def execute(self):
        table = self.db.setdefault(self.table_name, [])
        rows = list(table)
        for key, value in self.filters.items():
            rows = [row for row in rows if row.get(key) == value]
        if self.operation == "delete":
            self.db[self.table_name] = [
                row for row in table
                if not all(row.get(key) == value for key, value in self.filters.items())
            ]
            return SimpleNamespace(data=rows)
        if self.order_by:
            key, desc = self.order_by
            rows = sorted(rows, key=lambda row: row.get(key) or "", reverse=desc)
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return SimpleNamespace(data=rows, count=len(rows))


class FakeStorageBucket:
    def __init__(self, files=None):
        self.files = files or {}
        self.signed_paths = []

    def create_signed_url(self, path, expires_in):
        self.signed_paths.append((path, expires_in))
        return {"signedURL": f"https://storage.example/sign/{path}?token=secret"}

    def download(self, path):
        return self.files[path]


class FakeStorage:
    def __init__(self, files=None):
        self.bucket = FakeStorageBucket(files)

    def from_(self, bucket_name):
        assert bucket_name == "media"
        return self.bucket


class FakeSupabase:
    def __init__(self, db, files=None):
        self.db = db
        self.storage = FakeStorage(files)

    def table(self, table_name):
        return FakeQuery(table_name, self.db)


@pytest.mark.asyncio
async def test_commander_confidence_is_weighted_sum_not_quality_multiplier(monkeypatch):
    from app.agents.nodes import commander as commander_module

    async def fake_ruling(*args, **kwargs):
        return "结构化置信度应以加权求和为准。"

    monkeypatch.setattr(commander_module, "commander_ruling", fake_ruling)
    monkeypatch.setattr(commander_module, "build_provenance_graph", lambda **kwargs: {"nodes": [], "edges": [], "citations": []})
    monkeypatch.setattr(commander_module, "record_audit_event", lambda *args, **kwargs: None)

    updates = await commander_module.commander_node({
        "task_id": "task-1",
        "current_round": 1,
        "forensics_result": {"confidence": 0.95, "aigc_probability": 0.01, "is_aigc": False, "degraded": False},
        "osint_result": {"confidence": 0.82, "threat_score": 0.95, "text_risk_score": 0.95, "degraded": False},
        "challenger_feedback": {"quality_score": 0.0, "confidence": 0.0, "issue_count": 4},
        "evidence_board": [],
        "expert_messages": [],
        "case_prompt": "",
        "evidence_files": [],
        "phase_residual_risks": [],
        "provenance_graph": {},
    })

    assert updates["final_verdict"]["confidence"] == pytest.approx(0.674)
    assert updates["final_verdict"]["confidence_overall"] == pytest.approx(0.674)
    assert updates["final_verdict"]["confidence_components"]["challenger"]["weighted"] == pytest.approx(0.0)
    assert updates["final_verdict"]["aigc_score"] == pytest.approx(0.2895)
    assert "deepfake_score" not in updates["final_verdict"]


@pytest.mark.asyncio
async def test_sightengine_image_provider_returns_normalized_aigc_result(monkeypatch):
    from app.agents.tools import deepfake_api

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "success", "type": {"ai_generated": 0.91}}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            return SimpleNamespace(content=b"fake-image", headers={"content-disposition": 'filename="sample.jpg"'})

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(deepfake_api.httpx, "AsyncClient", lambda *args, **kwargs: FakeClient())
    monkeypatch.setattr(deepfake_api.settings, "SIGHTENGINE_API_USER", "user", raising=False)
    monkeypatch.setattr(deepfake_api.settings, "SIGHTENGINE_API_SECRET", "secret", raising=False)

    result = await deepfake_api.analyze_with_sightengine("https://storage.example/sample.jpg")

    assert result["model"] == "sightengine_genai"
    assert result["is_ai_generated"] is True
    assert result["is_aigc"] is True
    assert result["aigc_probability"] == pytest.approx(0.91)
    assert result["ai_generated_probability"] == pytest.approx(0.91)
    assert result["analysis_available"] is True
    assert "deepfake_probability" not in result
    assert "is_deepfake" not in result


@pytest.mark.asyncio
async def test_whoisxml_domain_provenance_returns_whois_and_dns_history(monkeypatch):
    from app.agents.tools import domain_provenance

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            if "whoisserver" in url:
                return FakeResponse({"WhoisRecord": {"createdDate": "2026-06-01", "registrarName": "Example Registrar"}})
            if "ip-geolocation" in url:
                return FakeResponse({"ip": params["ipAddress"], "location": {"country": "BR"}})
            raise AssertionError(f"unexpected GET {url}")

        async def post(self, url, json=None):
            return FakeResponse({"records": [{"rrtype": "A", "value": "203.0.113.10", "firstSeen": "2026-06-01"}]})

    monkeypatch.setattr(domain_provenance.httpx, "AsyncClient", lambda *args, **kwargs: FakeClient())
    monkeypatch.setattr(domain_provenance.settings, "WHOISXML_API_KEY", "key", raising=False)
    monkeypatch.setattr(domain_provenance.settings, "DOMAIN_PROVENANCE_ENABLED", True, raising=False)

    result = await domain_provenance.analyze_domain_provenance("http://halifax.co.uk.account.security.update.moroba.com.br")

    assert result["status"] == "success"
    assert result["domain"] == "moroba.com.br"
    assert result["whois"]["created_date"] == "2026-06-01"
    assert result["dns_history"][0]["value"] == "203.0.113.10"


@pytest.mark.asyncio
async def test_whoisxml_dns_history_422_preserves_whois_and_marks_partial(monkeypatch):
    from app.agents.tools import domain_provenance

    post_bodies = []

    class FakeResponse:
        def __init__(self, payload, status_code=200, url="https://example.invalid"):
            self.payload = payload
            self.status_code = status_code
            self.request = httpx.Request("POST", url)
            self.response = httpx.Response(status_code, request=self.request, json=payload)

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("unprocessable", request=self.request, response=self.response)

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            if "whoisserver" in url:
                return FakeResponse({
                    "WhoisRecord": {
                        "createdDate": "2026-06-01",
                        "registrarName": "Example Registrar",
                        "ips": ["203.0.113.10"],
                        "registryData": {
                            "createdDate": "2026-05-31",
                            "registrarName": "Registry Registrar",
                        },
                    }
                }, url=url)
            if "ip-geolocation" in url:
                return FakeResponse({
                    "ip": params["ipAddress"],
                    "location": {"country": "BR", "city": "Sao Paulo"},
                    "isp": "Example ISP",
                    "as": {"asn": 64512, "name": "EXAMPLE-AS"},
                }, url=url)
            raise AssertionError(f"unexpected GET {url}")

        async def post(self, url, json=None):
            post_bodies.append(json)
            return FakeResponse({"error": "bad request"}, status_code=422, url=url)

    monkeypatch.setattr(domain_provenance.httpx, "AsyncClient", lambda *args, **kwargs: FakeClient())
    monkeypatch.setattr(domain_provenance.settings, "WHOISXML_API_KEY", "key", raising=False)
    monkeypatch.setattr(domain_provenance.settings, "DOMAIN_PROVENANCE_ENABLED", True, raising=False)

    result = await domain_provenance.analyze_domain_provenance("http://halifax.co.uk.account.security.update.moroba.com.br")

    assert result["status"] == "partial"
    assert result["domain"] == "moroba.com.br"
    assert result["whois"]["created_date"] == "2026-06-01"
    assert result["dns_history"] == []
    assert result["ip_geolocation"][0]["country"] == "BR"
    assert post_bodies[0]["searchType"] == "forward"
    assert post_bodies[0]["recordType"] == "a"
    assert post_bodies[0]["domainName"] == "moroba.com.br"


@pytest.mark.asyncio
async def test_whoisxml_dns_history_uses_post_and_enriches_ip_geolocation(monkeypatch):
    from app.agents.tools import domain_provenance

    post_bodies = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            if "whoisserver" in url:
                return FakeResponse({"WhoisRecord": {"createdDate": "2026-06-01", "registrarName": "Example Registrar"}})
            if "ip-geolocation" in url:
                return FakeResponse({
                    "ip": params["ipAddress"],
                    "location": {"country": "BR", "city": "Sao Paulo"},
                    "isp": "Example ISP",
                    "as": {"asn": 64512, "name": "EXAMPLE-AS"},
                })
            raise AssertionError(f"unexpected GET {url}")

        async def post(self, url, json=None):
            post_bodies.append(json)
            return FakeResponse({"result": {"records": [{"date": "2026-06-01", "ips": [{"ip": "203.0.113.10"}]}]}})

    monkeypatch.setattr(domain_provenance.httpx, "AsyncClient", lambda *args, **kwargs: FakeClient())
    monkeypatch.setattr(domain_provenance.settings, "WHOISXML_API_KEY", "key", raising=False)
    monkeypatch.setattr(domain_provenance.settings, "DOMAIN_PROVENANCE_ENABLED", True, raising=False)

    result = await domain_provenance.analyze_domain_provenance("moroba.com.br")

    assert result["status"] == "success"
    assert result["dns_history"][0]["value"] == "203.0.113.10"
    assert result["ip_geolocation"][0]["asn"] == 64512
    assert post_bodies == [{
        "apiKey": "key",
        "searchType": "forward",
        "recordType": "a",
        "domainName": "moroba.com.br",
        "outputFormat": "JSON",
        "limit": 20,
    }]


@pytest.mark.asyncio
async def test_virustotal_queued_url_scan_uses_existing_url_report(monkeypatch):
    from app.agents.tools import threat_intel

    requested_urls = []

    class FakeResponse:
        def __init__(self, payload, status_code=200):
            self.payload = payload
            self.status_code = status_code

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, headers=None, data=None):
            requested_urls.append(("POST", url))
            return FakeResponse({"data": {"id": "analysis-1"}})

        async def get(self, url, headers=None):
            requested_urls.append(("GET", url))
            if "/analyses/" in url:
                return FakeResponse({"data": {"attributes": {"status": "queued", "stats": {}}}})
            if "/urls/" in url:
                return FakeResponse({
                    "data": {
                        "attributes": {
                            "last_analysis_stats": {
                                "malicious": 8,
                                "suspicious": 0,
                                "harmless": 84,
                                "undetected": 0,
                            }
                        }
                    }
                })
            raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(threat_intel.httpx, "AsyncClient", lambda *args, **kwargs: FakeClient())
    monkeypatch.setattr(threat_intel.asyncio, "sleep", lambda *_args, **_kwargs: asyncio.sleep(0))
    monkeypatch.setattr(threat_intel, "VT_URL_POLL_ATTEMPTS", 1)

    result = await threat_intel._virustotal_scan(
        "http://halifax.co.uk.account.security.update.moroba.com.br",
        "vt-key",
    )

    assert result["status"] == "success"
    assert result["virustotal"]["scan_available"] is True
    assert result["virustotal"]["malicious"] == 8
    assert result["virustotal"]["source"] == "existing_url_report"
    assert any("/api/v3/urls/" in url for method, url in requested_urls if method == "GET")


def test_text_case_preview_returns_utf8_text(monkeypatch):
    from app.api.v1 import cases as cases_module

    monkeypatch.setattr("app.middleware.auth._is_public", lambda path, method="GET": True)
    db = {
        "case_library_entries": [{
            "id": "case-1",
            "task_id": "task-1",
            "status": "published",
            "user_id": "user-1",
            "public_files": [{"id": "file-1", "mime_type": "text/plain", "modality": "text", "name": "notice.txt"}],
        }],
        "tasks": [{"id": "task-1", "metadata": {"files": [{"id": "file-1", "storage_path": "user-1/notice.txt"}]}}],
    }
    fake = FakeSupabase(db, files={"user-1/notice.txt": "中文客服通知".encode("gb18030")})
    monkeypatch.setattr(cases_module, "supabase", fake)

    client = TestClient(app)
    resp = client.post("/api/v1/cases/case-1/preview-url", json={"file_id": "file-1"})

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["preview_kind"] == "text"
    assert payload["text"] == "中文客服通知"
    assert payload["charset"] == "utf-8"
    assert payload["text_url"] == "/api/v1/cases/case-1/files/file-1/text"

    text_resp = client.get("/api/v1/cases/case-1/files/file-1/text")

    assert text_resp.status_code == 200
    assert "charset=utf-8" in text_resp.headers["content-type"].lower()
    assert text_resp.text == "中文客服通知"


def test_delete_case_also_deletes_public_rag_chunks(monkeypatch):
    from app.api.v1 import cases as cases_module

    db = {
        "case_library_entries": [{"id": "case-1", "user_id": "user-1", "status": "published"}],
        "case_library_rag_chunks": [
            {"case_id": "case-1", "source_kind": "public", "chunk_id": "old"},
            {"case_id": "case-1", "source_kind": "builtin", "chunk_id": "builtin"},
        ],
    }
    monkeypatch.setattr(cases_module, "supabase", FakeSupabase(db))
    request = SimpleNamespace(state=SimpleNamespace(user_id="user-1"))

    asyncio.run(cases_module.delete_case("case-1", request))

    assert db["case_library_entries"] == []
    assert db["case_library_rag_chunks"] == [{"case_id": "case-1", "source_kind": "builtin", "chunk_id": "builtin"}]


@pytest.mark.asyncio
async def test_audit_log_markdown_contains_complete_log_not_report_truncation(monkeypatch):
    from app.services import report_generator

    monkeypatch.setattr(report_generator, "_fetch_task_data", lambda _task_id: {
        "task": {"id": "task-1", "title": "任务"},
        "report": None,
        "analysis_states": [],
        "agent_logs": [
            {"timestamp": f"2026-06-02T00:{index:02d}:00+00:00", "agent": "forensics", "type": "action", "content": f"log-{index}"}
            for index in range(60)
        ],
        "audit_logs": [],
        "consultation_sessions": [],
        "consultation_messages": [],
    })

    markdown = await report_generator.generate_audit_log_markdown("task-1")

    assert "log-0" in markdown
    assert "log-59" in markdown
    assert "及其他" not in markdown


@pytest.mark.asyncio
async def test_challenger_first_round_high_confidence_can_pass(monkeypatch):
    from app.agents.nodes import challenger as challenger_module

    async def fake_model_review(*args, **kwargs):
        return {
            "confidence": 0.85,
            "requires_more_evidence": False,
            "target_agent": "forensics",
            "issues": [],
            "residual_risks": [],
            "markdown": "### 质询对象与本轮置信度\n- 本轮置信度: 85.0%",
        }

    monkeypatch.setattr(challenger_module, "challenger_model_review", fake_model_review)
    monkeypatch.setattr(challenger_module, "_fetch_consultation_sessions", lambda _task_id: [])
    monkeypatch.setattr(challenger_module, "record_audit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(challenger_module, "supabase", FakeSupabase({"consultation_messages": []}))

    updates = await challenger_module.challenger_node({
        "task_id": "task-1",
        "analysis_phase": "forensics",
        "current_round": 1,
        "max_rounds": 5,
        "convergence_threshold": 0.08,
        "phase_rounds": {"forensics": 1, "osint": 1, "commander": 1},
        "phase_quality_history": {"forensics": [], "osint": [], "commander": []},
        "consultation_sessions": [],
        "consultation_trigger_history": [],
        "expert_messages": [],
        "evidence_files": [],
        "case_prompt": "",
        "forensics_result": {"confidence": 0.86, "tool_summary": {"total": 2, "failed": 0, "degraded": 0}},
        "osint_result": {},
        "final_verdict": {},
        "challenges": [],
    })

    assert updates["challenger_feedback"]["requires_more_evidence"] is False
    assert updates["challenger_feedback"]["next_phase"] == "osint"
    assert updates["phase_rounds"]["forensics"] == 1


@pytest.mark.asyncio
async def test_challenger_confidence_not_zero_when_strong_evidence_has_external_gap(monkeypatch):
    from app.agents.nodes import challenger as challenger_module

    async def fake_model_review(*args, **kwargs):
        return {
            "confidence": 0.0,
            "requires_more_evidence": True,
            "target_agent": "osint",
            "issues": [{
                "type": "osint_tool_degraded",
                "severity": "high",
                "agent": "osint",
                "description": "WhoisXML 降级导致注册信息缺口",
            }],
            "residual_risks": [],
            "markdown": "### 质询对象与本轮置信度\n- 本轮置信度: 0.0%",
        }

    monkeypatch.setattr(challenger_module, "challenger_model_review", fake_model_review)
    monkeypatch.setattr(challenger_module, "_fetch_consultation_sessions", lambda _task_id: [])
    monkeypatch.setattr(challenger_module, "record_audit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(challenger_module, "supabase", FakeSupabase({"consultation_messages": []}))

    updates = await challenger_module.challenger_node({
        "task_id": "task-1",
        "analysis_phase": "osint",
        "current_round": 2,
        "max_rounds": 5,
        "convergence_threshold": 0.08,
        "phase_rounds": {"forensics": 1, "osint": 1, "commander": 1},
        "phase_quality_history": {"forensics": [], "osint": [], "commander": []},
        "consultation_sessions": [],
        "consultation_trigger_history": [],
        "expert_messages": [],
        "evidence_files": [],
        "case_prompt": "",
        "forensics_result": {
            "confidence": 0.92,
            "aigc_probability": 0.98,
            "is_aigc": True,
            "tool_summary": {"total": 3, "failed": 0, "degraded": 0},
        },
        "osint_result": {
            "confidence": 0.82,
            "threat_score": 0.95,
            "text_risk_score": 0.75,
            "social_engineering_score": 0.68,
            "virustotal_summary": [{"virustotal": {"malicious": 8, "total": 92}}],
            "domain_provenance_summary": [{"status": "partial", "degraded": True}],
            "provenance_graph": {
                "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
                "citations": [{"id": "vt"}],
                "quality": {"completeness": 0.72, "citation_coverage": 0.4, "model_inferred_ratio": 0.3},
            },
            "tool_summary": {"total": 4, "failed": 0, "degraded": 1},
        },
        "final_verdict": {},
        "challenges": [],
    })

    assert updates["challenger_feedback"]["confidence"] >= 0.45


@pytest.mark.asyncio
async def test_forensics_reinforcement_context_contains_challenger_and_consultation_feedback(monkeypatch):
    from app.agents.nodes import forensics as forensics_module

    captured = {}

    async def fake_forensics_interpret(raw_api_result, *args, **kwargs):
        captured["raw_api_result"] = raw_api_result
        return "补强后的取证报告"

    async def fake_case_rag_search(*args, **kwargs):
        return {"tool": "case_rag_search", "status": "skipped", "matches": [], "summary": "跳过"}

    monkeypatch.setattr(forensics_module, "forensics_interpret", fake_forensics_interpret)
    monkeypatch.setattr(forensics_module, "case_rag_search", fake_case_rag_search)
    monkeypatch.setattr(forensics_module, "record_audit_event", lambda *args, **kwargs: None)

    await forensics_module.forensics_node({
        "task_id": "task-1",
        "input_type": "text",
        "case_prompt": "",
        "current_round": 2,
        "phase_rounds": {"forensics": 2, "osint": 1, "commander": 1},
        "evidence_files": [],
        "input_files": {},
        "tool_results": {},
        "forensics_result": {"llm_analysis": "上一轮报告"},
        "confidence_history": [],
        "challenger_feedback": {
            "target_agent": "forensics",
            "issues_found": [{"description": "需要补充图片深度取证"}],
            "llm_cross_validation": "Challenger 指出图片证据不足",
            "residual_risks": [{"reason": "仍缺少原图 EXIF"}],
        },
        "confirmed_consultation_summary": {"confirmed_summary": "专家建议优先复核原始截图来源。"},
    })

    context = captured["raw_api_result"]["reinforcement_context"]
    assert context["target_agent"] == "forensics"
    assert "需要补充图片深度取证" in context["challenger_issues"][0]["description"]
    assert "专家建议" in context["consultation_summary"]
    assert "上一轮报告" in context["previous_analysis"]
