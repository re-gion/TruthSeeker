"""LangGraph State 定义 — 必须使用 TypedDict（LangGraph v1.0+ 规范）"""
from typing import TypedDict, Annotated, Optional
from operator import add


class EvidenceItem(TypedDict):
    type: str       # 'visual' | 'audio' | 'text' | 'osint'
    source: str     # 哪个 Agent/Tool 产生
    description: str
    confidence: float
    metadata: dict


class AgentLog(TypedDict):
    agent: str
    round: int
    type: str       # 'thinking' | 'action' | 'finding' | 'challenge' | 'conclusion'
    content: str
    timestamp: str


class TruthSeekerState(TypedDict):
    # 任务基础信息
    task_id: str
    user_id: str
    input_files: dict           # {modality: storage_path}
    input_type: str             # 'video' | 'audio' | 'image' | 'text'
    priority_focus: str         # 'visual' | 'audio' | 'text' | 'balanced'

    # 辩论状态
    current_round: int
    max_rounds: int             # 默认5
    convergence_threshold: float  # 默认0.05

    # 各 Agent 评估结果
    forensics_result: Optional[dict]
    osint_result: Optional[dict]
    challenger_feedback: Optional[dict]

    # 最终结果
    final_verdict: Optional[dict]

    # Agent 权重
    agent_weights: dict
    previous_weights: dict

    # 证据板（累积所有发现）
    evidence_board: Annotated[list[EvidenceItem], add]

    # 置信度历史（用于收敛判断）
    confidence_history: list[dict]  # [{round:1, scores: {...}}, ...]

    # 质询记录
    challenges: Annotated[list[dict], add]

    # 日志流（用于 SSE）
    logs: Annotated[list[AgentLog], add]

    # 终止条件
    is_converged: bool
    termination_reason: Optional[str]

    # --- Phase 1+ 新增字段 ---

    # 降级状态追踪
    degradation_status: dict    # {"reality_defender": "ok"|"degraded"|"failed", ...}

    # 专家会诊消息
    expert_messages: list[dict]  # [{role, content, timestamp}, ...]

    # 时间轴关键事件（仅记录重要节点，非全量 log）
    timeline_events: Annotated[list[dict], add]  # [{round, agent, event_type, summary}, ...]
