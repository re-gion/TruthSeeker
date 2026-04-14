"""SSE 检测端点 - Layer 2: 四 Agent 完整事件流"""
import json
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
from app.agents.graph import compiled_graph
from app.agents.state import TruthSeekerState
from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)

router = APIRouter()


class DetectRequest(BaseModel):
    task_id: Optional[str] = None
    input_type: str = "video"
    file_url: Optional[str] = None
    file_urls: Optional[dict] = None
    user_id: Optional[str] = "anonymous"
    priority_focus: str = "balanced"
    max_rounds: int = 3


async def sse_event_generator(request: DetectRequest) -> AsyncGenerator[str, None]:
    """生成 Layer 2 四 Agent SSE 事件流"""
    task_id = request.task_id or str(uuid.uuid4())

    # 初始化 State（Layer 2 扩展版）
    initial_state: TruthSeekerState = {
        "task_id": task_id,
        "user_id": request.user_id or "anonymous",
        "input_files": request.file_urls or {"primary": request.file_url or "mock://default"},
        "input_type": request.input_type,
        "priority_focus": request.priority_focus,
        "current_round": 1,
        "max_rounds": min(request.max_rounds, 5),
        "convergence_threshold": 0.05,
        "forensics_result": None,
        "osint_result": None,
        "challenger_feedback": None,
        "final_verdict": None,
        "agent_weights": {},
        "previous_weights": {},
        "evidence_board": [],
        "confidence_history": [],
        "challenges": [],
        "logs": [],
        "is_converged": False,
        "termination_reason": None,
    }

    # 发送开始事件
    yield f"data: {json.dumps({'type': 'start', 'task_id': task_id, 'timestamp': datetime.now(timezone.utc).isoformat(), 'max_rounds': initial_state['max_rounds']})}\\n\\n"

    final_verdict_data = None  # 追踪最终裁决，用于更新任务状态

    # 流式执行 LangGraph
    async for chunk in compiled_graph.astream(initial_state, stream_mode="updates"):
        for node_name, updates in chunk.items():
            # 节点开始
            yield f"data: {json.dumps({'type': 'node_start', 'node': node_name})}\\n\\n"

            # Agent 日志（逐条发送）
            for log_entry in updates.get("logs", []):
                yield f"data: {json.dumps({'type': 'agent_log', 'node': node_name, 'log': log_entry})}\\n\\n"

            # 证据更新
            evidence_list = updates.get("evidence_board", [])
            if evidence_list:
                yield f"data: {json.dumps({'type': 'evidence_update', 'evidence': evidence_list, 'node': node_name})}\\n\\n"

            # 质询记录
            challenges = updates.get("challenges", [])
            if challenges:
                yield f"data: {json.dumps({'type': 'challenges_update', 'challenges': challenges})}\\n\\n"

            # 法医结果
            if updates.get("forensics_result"):
                yield f"data: {json.dumps({'type': 'forensics_result', 'result': updates['forensics_result']})}\\n\\n"

            # OSINT 结果
            if updates.get("osint_result"):
                yield f"data: {json.dumps({'type': 'osint_result', 'result': updates['osint_result']})}\\n\\n"

            # 质询官反馈
            if updates.get("challenger_feedback"):
                yield f"data: {json.dumps({'type': 'challenger_feedback', 'feedback': updates['challenger_feedback']})}\\n\\n"

            # 权重更新
            if updates.get("agent_weights"):
                yield f"data: {json.dumps({'type': 'weights_update', 'weights': updates['agent_weights']})}\\n\\n"

            # 轮次更新
            if "current_round" in updates:
                yield f"data: {json.dumps({'type': 'round_update', 'round': updates['current_round']})}\\n\\n"

            # 最终裁决
            if updates.get("final_verdict"):
                final_verdict_data = updates["final_verdict"]
                yield f"data: {json.dumps({'type': 'final_verdict', 'verdict': updates['final_verdict']})}\\n\\n"

            # 节点完成
            yield f"data: {json.dumps({'type': 'node_complete', 'node': node_name})}\\n\\n"

    # 更新任务状态到 Supabase
    if final_verdict_data:
        try:
            supabase.table("tasks").update({
                "status": "completed",
                "result": final_verdict_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", task_id).execute()
        except Exception as e:
            logger.warning("Failed to update task status: %s", e)

    # 完成
    yield f"data: {json.dumps({'type': 'complete', 'task_id': task_id, 'timestamp': datetime.now(timezone.utc).isoformat()})}\\n\\n"


@router.post("/stream")
async def detect_stream(request: DetectRequest):
    """SSE 流式检测端点（Layer 2 四 Agent）"""
    return StreamingResponse(
        sse_event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
