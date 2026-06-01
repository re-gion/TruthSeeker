"""Built-in public case records used by the case library and RAG corpus."""
from __future__ import annotations

from typing import Any


BUILTIN_CASES: list[dict[str, Any]] = [
    {
        "id": "builtin-audio-scam",
        "source_kind": "builtin",
        "task_id": None,
        "title": "董事长语音诈骗",
        "media_category": "audio_forgery",
        "summary": "通过少量样本克隆高管声音，诱导财务人员发起转账的典型音频恶意 AIGC 案例。",
        "verdict": "forged",
        "confidence_overall": 0.9,
        "difficulty": "High",
        "public_files": [
            {
                "id": "builtin-audio-sample",
                "name": "董事长语音诈骗演示样本",
                "mime_type": "audio/mpeg",
                "modality": "audio",
                "size_bytes": None,
                "storage_path": None,
            }
        ],
        "published_at": "2026-06-01T00:00:00+08:00",
        "report_markdown": """# 董事长语音诈骗

## 案例概述

攻击者通过公开演讲、短视频或会议录音采集目标高管声音样本，使用语音克隆模型生成紧急转账指令，并配合即时通讯话术制造时间压力。

## 典型证据点

- 语音节奏与自然呼吸间隔不匹配，句尾能量衰减过于平滑。
- 背景噪声连续性异常，关键转账指令片段和寒暄片段噪声纹理不一致。
- 文本话术出现“马上”“保密”“不走常规审批”等社工诱导信号。
- 转账账户、域名、电话或聊天账号与历史业务链路不一致。

## 可借鉴研判方法

1. 电子取证侧优先检查声纹一致性、频谱断点、压缩链路和重采样痕迹。
2. 情报溯源侧核验收款账户、通信账号、域名和历史诈骗基础设施关联。
3. Challenger 应质询“声音像本人”与“交易链路可信”之间的逻辑跳跃。

## 处置建议

- 暂停转账并通过独立可信通道复核高管本人意图。
- 保留原始音频、聊天截图、转账账户和通信元数据。
- 将相似话术和 IOC 纳入后续监测，但不能把历史类案当作当前样本事实。
""",
    },
    {
        "id": "builtin-video-faceswap",
        "source_kind": "builtin",
        "task_id": None,
        "title": "Politician AI 伪造视频",
        "media_category": "video_forgery",
        "summary": "使用目标人物人脸替换和口型驱动技术生成虚假政治发言的视频伪造案例。",
        "verdict": "forged",
        "confidence_overall": 0.88,
        "difficulty": "Critical",
        "public_files": [
            {
                "id": "builtin-video-sample",
                "name": "政治人物伪造视频演示样本",
                "mime_type": "video/mp4",
                "modality": "video",
                "size_bytes": None,
                "storage_path": None,
            }
        ],
        "published_at": "2026-06-01T00:00:00+08:00",
        "report_markdown": """# Politician AI 伪造视频

## 案例概述

该类攻击通常以热点事件为诱饵，合成公众人物发表敏感言论的视频，再通过短视频平台和社交账号扩散。

## 典型证据点

- 面部边缘在快速转头、遮挡或强光区域出现局部漂移。
- 嘴唇开合与音素边界存在细微错位，牙齿区域纹理稳定性不足。
- 眼部高光、皮肤纹理和压缩伪影在面部区域与背景区域不一致。
- 原始发布账号、首发时间和二次搬运链路存在异常聚集。

## 可借鉴研判方法

1. 电子取证侧关注帧级伪影、口型同步、压缩链路和人脸区域一致性。
2. 情报溯源侧追踪首发账号、转发网络、相似标题和外部报道反证。
3. 报告应区分“视频画面疑似合成”和“言论事实真实性”两个问题。

## 处置建议

- 对外传播前保守标记为高风险，等待权威来源复核。
- 保存首发 URL、发布时间、账号标识和关键帧 hash。
- 不应仅凭历史政治伪造类案直接断定当前视频伪造。
""",
    },
    {
        "id": "builtin-mixed-phishing",
        "source_kind": "builtin",
        "task_id": None,
        "title": "钓鱼链接+伪造截图",
        "media_category": "image_text_mixed",
        "summary": "结合生成式聊天截图、仿冒页面链接和诱导话术的图文混合社工攻击案例。",
        "verdict": "suspicious",
        "confidence_overall": 0.84,
        "difficulty": "Medium",
        "public_files": [
            {
                "id": "builtin-mixed-image",
                "name": "伪造聊天截图演示样本",
                "mime_type": "image/png",
                "modality": "image",
                "size_bytes": None,
                "storage_path": None,
            }
        ],
        "published_at": "2026-06-01T00:00:00+08:00",
        "report_markdown": """# 钓鱼链接+伪造截图

## 案例概述

攻击者生成客服、同事或平台通知截图，搭配短链、仿冒域名或二维码，引导用户提交账号、验证码或资金信息。

## 典型证据点

- 截图字体、控件间距、状态栏时间和系统 UI 样式不一致。
- URL 域名与官方域名相似但存在字符替换、额外前缀或异常顶级域。
- 文本强调限时处理、账户冻结、内部审批等紧迫情境。
- 同一短链或落地域名在公开情报中关联多个钓鱼样本。

## 可借鉴研判方法

1. 电子取证侧检查截图合成痕迹、OCR 文本一致性和图像元数据。
2. OSINT 侧优先展开 URL、域名、证书、Whois、DNS 和公开搜索结果。
3. Challenger 应检查“截图可信”和“链接可信”是否被错误合并。

## 处置建议

- 禁止访问可疑链接，先在隔离环境中做 URL 情报核验。
- 将域名、短链、二维码内容和截图 OCR 结果纳入证据链。
- 类案可提示常见社工模式，但不能替代当前 URL 的实时威胁情报。
""",
    },
    {
        "id": "builtin-text-news",
        "source_kind": "builtin",
        "task_id": None,
        "title": "AI 生成新闻",
        "media_category": "text_generation",
        "summary": "利用大语言模型批量生成虚假舆情新闻并诱导扩散的文本恶意 AIGC 案例。",
        "verdict": "suspicious",
        "confidence_overall": 0.78,
        "difficulty": "Medium",
        "public_files": [
            {
                "id": "builtin-text-sample",
                "name": "AI 生成新闻演示文本",
                "mime_type": "text/plain",
                "modality": "text",
                "size_bytes": None,
                "storage_path": None,
            }
        ],
        "published_at": "2026-06-01T00:00:00+08:00",
        "report_markdown": """# AI 生成新闻

## 案例概述

攻击者围绕公共事件批量生成看似完整的新闻稿，混合真实地名、机构名和虚构引述，制造舆论误导。

## 典型证据点

- 叙述完整但缺少可核验的一手来源、记者署名或原始公告链接。
- 多段文字存在模板化连接词、空泛归因和过度均匀的段落结构。
- 关键事实在权威媒体、政府公告或公开数据库中无法交叉验证。
- 标题和正文之间存在情绪煽动强于事实支撑的倾向。

## 可借鉴研判方法

1. 文本检测侧分析写作风格、事实声明、引用来源和社工诱导风险。
2. OSINT 侧对核心实体、时间、地点、数字和引述做独立检索。
3. 报告应把“疑似 AI 生成”和“事实虚假”分开说明。

## 处置建议

- 标记为待核验内容，避免在未确认前二次传播。
- 保留原始文本、来源 URL、发布时间和账号信息。
- 使用类案提醒常见写作模式，但事实判定必须依赖当前文本和外部来源。
""",
    },
]


def list_builtin_cases(category: str = "all") -> list[dict[str, Any]]:
    if category == "all":
        return [dict(item) for item in BUILTIN_CASES]
    return [dict(item) for item in BUILTIN_CASES if item.get("media_category") == category]


def get_builtin_case(case_id: str) -> dict[str, Any] | None:
    for item in BUILTIN_CASES:
        if item["id"] == case_id:
            return dict(item)
    return None
