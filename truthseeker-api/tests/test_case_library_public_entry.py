import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import case_library


class FakeQuery:
    def __init__(self, table_name, db):
        self.table_name = table_name
        self.db = db
        self.filters = {}
        self._insert_payload = None

    def select(self, _columns):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, _key, desc=False):
        return self

    def limit(self, _count):
        return self

    def insert(self, payload):
        self._insert_payload = payload
        return self

    def execute(self):
        if self._insert_payload is not None:
            rows = self.db.setdefault(self.table_name, [])
            rows.append(self._insert_payload)
            return SimpleNamespace(data=[self._insert_payload])
        rows = list(self.db.setdefault(self.table_name, []))
        for key, value in self.filters.items():
            rows = [row for row in rows if row.get(key) == value]
        return SimpleNamespace(data=rows)


class FakeSupabase:
    def __init__(self, db):
        self.db = db

    def table(self, table_name):
        return FakeQuery(table_name, self.db)


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    async def ainvoke(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(content=json.dumps(self.payload, ensure_ascii=False))


def _task(files, *, input_type="text_audio", share=True):
    return {
        "id": "task-1",
        "user_id": "user-1",
        "input_type": input_type,
        "description": "请判断该内容是否可能用于诈骗或身份冒充场景。重点检查伪造领导、亲友口吻。",
        "metadata": {
            "share_to_casebase": share,
            "case_prompt": "请判断该内容是否可能用于诈骗或身份冒充场景。重点检查伪造领导、亲友口吻。",
            "files": files,
        },
    }


def _report():
    return {
        "task_id": "task-1",
        "verdict": "suspicious",
        "confidence_overall": 0.929,
        "summary": "### 最终裁决结论\n可疑",
        "key_evidence": [{"type": "forensics", "source": "forensics_agent", "confidence": 0.95}],
        "verdict_payload": {"verdict": "suspicious", "confidence_overall": 0.929},
    }


@pytest.mark.parametrize(
    ("modalities", "expected"),
    [
        ({"audio", "text"}, "audio_forgery"),
        ({"video", "text"}, "video_forgery"),
        ({"image", "text"}, "image_text_mixed"),
        ({"image"}, "image_forgery"),
        ({"text"}, "text_generation"),
        ({"audio"}, "audio_forgery"),
        ({"video"}, "video_forgery"),
        ({"audio", "video"}, "video_forgery"),
        ({"image", "audio", "text"}, "audio_forgery"),
    ],
)
def test_derive_media_category_by_modality(modalities, expected):
    files = [{"modality": item, "name": f"f{i}"} for i, item in enumerate(sorted(modalities))]
    assert case_library._derive_media_category(files) == expected


@pytest.mark.parametrize(
    ("input_type", "expected"),
    [
        ("text_audio", "audio_forgery"),
        ("text_video", "video_forgery"),
        ("text_image", "image_text_mixed"),
        ("image", "image_forgery"),
        ("audio", "audio_forgery"),
        ("text", "text_generation"),
        ("mixed", "image_text_mixed"),
    ],
)
def test_derive_media_category_from_input_type_fallback(input_type, expected):
    assert case_library._derive_media_category([], input_type) == expected


def test_evidence_context_reads_agent_snapshots():
    db = {
        "analysis_states": [
            {
                "task_id": "task-1",
                "created_at": "2026-08-15T10:00:00+00:00",
                "result_snapshot": {
                    "forensics": {
                        "llm_analysis": "文本内容为【农业银行安全提醒】钓鱼短信。",
                        "audio_transcripts": [{"text": "农业银行安全提醒语音内容"}],
                    }
                },
            },
            {
                "task_id": "task-1",
                "created_at": "2026-08-15T10:05:00+00:00",
                "result_snapshot": {
                    "osint": {"llm_analysis": "域名注册于免费托管平台，无官方关联。"}
                },
            },
        ]
    }
    context = case_library._collect_evidence_context(FakeSupabase(db), "task-1")
    assert "农业银行" in context["forensics_analysis"]
    assert context["audio_transcripts"] == ["农业银行安全提醒语音内容"]
    assert "免费托管平台" in context["osint_analysis"]


def test_evidence_context_empty_without_client_or_states():
    assert case_library._collect_evidence_context(None, "task-1") == {}
    assert case_library._collect_evidence_context(FakeSupabase({}), "task-1") == {}


async def test_audio_text_entry_uses_audio_category_and_grounded_prompt():
    files = [
        {"id": "t.txt", "name": "案例7-文本-短信.txt", "modality": "text", "sha256": "a", "size_bytes": 10},
        {"id": "a.mp3", "name": "案例7-音频-客服.mp3", "modality": "audio", "sha256": "b", "size_bytes": 20},
    ]
    db = {
        "case_library_entries": [],
        "analysis_states": [
            {
                "task_id": "task-1",
                "created_at": "2026-08-15T10:00:00+00:00",
                "result_snapshot": {
                    "forensics": {"llm_analysis": "文本内容为【农业银行安全提醒】钓鱼短信，音频为AI合成。"}
                },
            }
        ],
    }
    llm = FakeLLM({"title": "冒充农业银行安全提醒的合成语音案例", "summary": "本案为AI合成音频，置信度92.9%。"})
    result = await case_library.ensure_case_library_entry(
        FakeSupabase(db), _task(files), _report(), llm=llm
    )
    assert result["status"] == "created"
    entry = result["entry"]
    assert entry["media_category"] == "audio_forgery"
    assert entry["title"] == "冒充农业银行安全提醒的合成语音案例"

    prompt = llm.prompts[0]
    # 案情事实必须进入 LLM 输入
    assert "农业银行" in prompt
    assert "案例7-音频-客服.mp3" in prompt
    # 严格约束：检测诉求不是案情、禁止编造
    assert "检测诉求" in prompt
    assert "禁止编造" in prompt


async def test_fallback_title_does_not_borrow_case_prompt_words():
    files = [{"id": "a.mp3", "name": "语音.mp3", "modality": "audio", "sha256": "b", "size_bytes": 20}]
    title, summary = case_library._fallback_title_and_summary(
        "suspicious", "audio_forgery", 0.929, "High",
        case_prompt="请判断该内容是否可能用于诈骗或身份冒充场景",
    )
    assert "诈骗" not in title
    assert "身份冒充" not in title
    assert "音频伪造" in title
    assert "可疑" in summary or "高度可疑" in summary


async def test_generated_text_strips_urls():
    files = [{"id": "t.txt", "name": "短信.txt", "modality": "text", "sha256": "a", "size_bytes": 10}]
    db = {"case_library_entries": [], "analysis_states": []}
    llm = FakeLLM({
        "title": "钓鱼短信案例 http://evil.example.com/x",
        "summary": "详见 https://phish.example.com 链接，置信度92.9%。",
    })
    result = await case_library.ensure_case_library_entry(
        FakeSupabase(db), _task(files, input_type="text"), _report(), llm=llm
    )
    entry = result["entry"]
    assert "http" not in entry["title"]
    assert "http" not in entry["summary"]


async def test_generated_text_strips_bare_domain_adjacent_to_chinese():
    # \b 在 Unicode 下中文与数字/字母之间不构成边界，需显式环视才能清掉裸域名
    cleaned = case_library._clean_generated_public_text(
        "短信导向000webhostapp.com免费域名钓鱼链接，路径拼写混杂chase.Bank品牌。",
        max_chars=360,
    )
    assert "000webhostapp" not in cleaned
    assert "chase.Bank" not in cleaned
    # 不应误伤普通数字/中文
    assert "免费域名" in cleaned


def test_clean_generated_text_removes_empty_quote_pairs():
    cleaned = case_library._clean_generated_public_text(
        '链接路径拼写"chase.Bank"与宣称主体矛盾。',
        max_chars=360,
    )
    assert '""' not in cleaned
    assert "与宣称主体矛盾" in cleaned


async def test_llm_failure_falls_back_to_honest_summary():
    files = [{"id": "a.mp3", "name": "语音.mp3", "modality": "audio", "sha256": "b", "size_bytes": 20}]
    db = {"case_library_entries": [], "analysis_states": []}

    class BrokenLLM:
        async def ainvoke(self, _prompt):
            raise RuntimeError("boom")

    result = await case_library.ensure_case_library_entry(
        FakeSupabase(db), _task(files), _report(), llm=BrokenLLM()
    )
    entry = result["entry"]
    assert entry["media_category"] == "audio_forgery"
    assert "音频伪造" in entry["title"]
    assert "92.9%" in entry["summary"]


@pytest.mark.parametrize(
    ("verdict", "media_category", "expected_title"),
    [
        ("authentic", "image_forgery", "图像检材真实性核验案例"),
        ("authentic", "audio_forgery", "音频检材真实性核验案例"),
        ("inconclusive", "image_text_mixed", "图文检材研判案例"),
    ],
)
def test_fallback_title_for_authentic_and_inconclusive(verdict, media_category, expected_title):
    title, summary = case_library._fallback_title_and_summary(
        verdict, media_category, 0.924, "High"
    )
    assert title == expected_title
    # 真实/无法判定案例的标题不应出现"伪造""疑似"等与结论矛盾的词
    assert "伪造" not in title
    assert "疑似" not in title
    assert "内容真实" in summary or "无法判定" in summary
