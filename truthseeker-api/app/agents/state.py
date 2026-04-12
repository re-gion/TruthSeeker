"""LangGraph State Definition - MUST use TypedDict, NOT Pydantic BaseModel"""
from typing import TypedDict, Annotated, List, Optional
from operator import add


class EvidenceItem(TypedDict):
    type: str        # 'visual' | 'audio' | 'text' | 'osint'
    source: str      # 产生的 Agent/Tool
    description: str
    confidence: float
    metadata: dict


class AgentLog(TypedDict):
    agent: str       # 'forensics' | 'osint' | 'challenger' | 'commander'
    round: int
    type: str        # 'thinking' | 'action' | 'finding' | 'challenge' | 'conclusion'
    content: str
    timestamp: str


class TruthSeekerState(TypedDict):
    # 任务基础信息
    task_id: str
    user_id: str
    input_files: dict          # {modality: storage_path or url}
    input_type: str            # 'video' | 'audio' | 'image' | 'text'
    priority_focus: str        # 'visual' | 'audio' | 'text' | 'balanced'

    # 辩论状态
    current_round: int
    max_rounds: int            # 默认 5
    convergence_threshold: float  # 默认 0.05

    # 各 Agent 评估结果
    forensics_result: Optional[dict]
    osint_result: Optional[dict]
    challenger_feedback: Optional[dict]
    final_verdict: Optional[dict]

    # 权重（用于收敛判断）
    agent_weights: dict        # {'forensics': 0.8, 'osint': 0.6, ...}
    previous_weights: dict     # 上一轮的权重

    # 证据板（累积所有发现）
    evidence_board: Annotated[List[EvidenceItem], add]

    # 置信度历史（用于收敛判断）
    confidence_history: List[dict]  # [{round:1, scores: {...}}, ...]

    # 质询记录（累积）
    challenges: Annotated[List[dict], add]

    # 日志流（用于 SSE 推送）
    logs: Annotated[List[AgentLog], add]

    # 终止条件
    is_converged: bool
    termination_reason: Optional[str]
