"""SSE 检测端点 - Layer 2: 四 Agent 完整事件流"""
import asyncio
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

HEARTBEAT_INTERVAL = 20  # 秒


class DetectRequest(BaseModel):
    """API 请求验证模型（非 LangGraph State）"""
    task_id: Optional[str] = None
    input_type: str = "video"
    file_url: Optional[str] = None
    file_urls: Optional[dict] = None
    user_id: Optional[str] = "anonymous"
    priority_focus: str = "balanced"
    max_rounds: int = 3


def _sse(data: dict) -> str:
    """构建 SSE data 行（D-2 修复：确保 JSON 内无原始换行）"""
    payload = json.dumps(data, ensure_ascii=True).replace("\n", "\\n")
    return f"data: {payload}\n\n"


async def _heartbeat_sender(queue: asyncio.Queue, stop: asyncio.Event) -> None:
    """D-3 修复：后台发送心跳 SSE 注释行"""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_INTERVAL)
        except asyncio.TimeoutError:
            await queue.put(":keepalive\n\n")


async def sse_event_generator(request: DetectRequest) -> AsyncGenerator[str, None]:
    """生成 Layer 2 四 Agent SSE 事件流"""
    task_id = request.task_id or str(uuid.uuid4())
    queue: asyncio.Queue[str] = asyncio.Queue()
    stop_heartbeat = asyncio.Event()

    # 初始化 State
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

    # 启动心跳任务
    hb_task = asyncio.create_task(_heartbeat_sender(queue, stop_heartbeat))

    # 发送开始事件
    await queue.put(_sse({
        "type": "start",
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "max_rounds": initial_state["max_rounds"],
    }))

    final_verdict_data = None

    # 主事件流（后台任务，向 queue 写入）
    async def run_graph():
        nonlocal final_verdict_data
        try:
            async for chunk in compiled_graph.astream(initial_state, stream_mode="updates"):
                for node_name, updates in chunk.items():
                    await queue.put(_sse({"type": "node_start", "node": node_name}))

                    for log_entry in updates.get("logs", []):
                        await queue.put(_sse({"type": "agent_log", "node": node_name, "log": log_entry}))

                    evidence_list = updates.get("evidence_board", [])
                    if evidence_list:
                        await queue.put(_sse({"type": "evidence_update", "evidence": evidence_list, "node": node_name}))

                    challenges = updates.get("challenges", [])
                    if challenges:
                        await queue.put(_sse({"type": "challenges_update", "challenges": challenges}))

                    if updates.get("forensics_result"):
                        await queue.put(_sse({"type": "forensics_result", "result": updates["forensics_result"]}))

                    if updates.get("osint_result"):
                        await queue.put(_sse({"type": "osint_result", "result": updates["osint_result"]}))

                    if updates.get("challenger_feedback"):
                        await queue.put(_sse({"type": "challenger_feedback", "feedback": updates["challenger_feedback"]}))

                    if updates.get("agent_weights"):
                        await queue.put(_sse({"type": "weights_update", "weights": updates["agent_weights"]}))

                    if "current_round" in updates:
                        await queue.put(_sse({"type": "round_update", "round": updates["current_round"]}))

                    if updates.get("final_verdict"):
                        final_verdict_data = updates["final_verdict"]
                        await queue.put(_sse({"type": "final_verdict", "verdict": updates["final_verdict"]}))

                    await queue.put(_sse({"type": "node_complete", "node": node_name}))
        except Exception as e:
            # D-4 修复：异常时发送 error 事件
            logger.error("SSE stream error for task %s: %s", task_id, e)
            await queue.put(_sse({
                "type": "error",
                "task_id": task_id,
                "message": "检测过程发生异常，请稍后重试",
            }))
        finally:
            stop_heartbeat.set()  # 停止心跳

    graph_task = asyncio.create_task(run_graph())

    # 消费 queue，产出 SSE 行
    try:
        while not graph_task.done() or not queue.empty():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield event
            except asyncio.TimeoutError:
                continue
    finally:
        stop_heartbeat.set()
        graph_task.cancel()
        hb_task.cancel()
        # 等待任务清理
        await asyncio.gather(graph_task, hb_task, return_exceptions=True)

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
    yield _sse({
        "type": "complete",
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


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
            # D-5 修复：移除 Access-Control-Allow-Origin，统一由 CORSMiddleware 处理
        },
    )
