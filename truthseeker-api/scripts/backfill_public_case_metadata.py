"""Backfill media_category/title/summary of published public case entries.

历史公开案例可能带着错误的媒体类别（音频+文本被误标为图文混合）和缺少案情依据的
标题/摘要。本脚本用修复后的 `case_library` 逻辑重新推导类别、重新生成标题摘要，
并同步刷新案例 RAG chunks。

Usage:
  python scripts/backfill_public_case_metadata.py --task-id <task_id>          # dry-run
  python scripts/backfill_public_case_metadata.py --task-id <task_id> --apply  # 实际写库
  python scripts/backfill_public_case_metadata.py --all --apply
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.case_library import (  # noqa: E402
    _derive_media_category,
    _task_files,
    generate_case_title_and_summary,
)
from app.services.case_rag import index_case_record  # noqa: E402
from app.utils.supabase_client import supabase  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill public case metadata.")
    parser.add_argument("--task-id", action="append", default=[], help="Task id to backfill (repeatable).")
    parser.add_argument("--all", action="store_true", help="Backfill every published entry.")
    parser.add_argument("--apply", action="store_true", help="Write changes; default is dry-run.")
    return parser.parse_args()


def _fetch_entries(task_ids: list[str], fetch_all: bool) -> list[dict]:
    query = supabase.table("case_library_entries").select("*").eq("status", "published")
    resp = query.execute()
    rows = resp.data or []
    if fetch_all:
        return rows
    wanted = set(task_ids)
    return [row for row in rows if row.get("task_id") in wanted]


def _fetch_row(table: str, key: str, value: str) -> dict | None:
    resp = supabase.table(table).select("*").eq(key, value).execute()
    return resp.data[0] if resp.data else None


async def backfill_entry(entry: dict, llm, *, apply: bool) -> dict:
    task_id = entry.get("task_id")
    task = _fetch_row("tasks", "id", task_id)
    report = _fetch_row("reports", "task_id", task_id)
    if not task or not report:
        return {"task_id": task_id, "status": "skipped", "reason": "missing task or report"}

    old_category = entry.get("media_category")
    new_category = _derive_media_category(_task_files(task), task.get("input_type"))
    new_title, new_summary = await generate_case_title_and_summary(task, report, llm, client=supabase)

    changes = {
        "task_id": task_id,
        "entry_id": entry.get("id"),
        "category": {"old": old_category, "new": new_category},
        "title": {"old": entry.get("title"), "new": new_title},
        "summary": {"old": entry.get("summary"), "new": new_summary},
    }
    if not apply:
        changes["status"] = "dry_run"
        return changes

    payload = {
        "media_category": new_category,
        "title": new_title,
        "summary": new_summary,
    }
    supabase.table("case_library_entries").update(payload).eq("id", entry.get("id")).execute()
    updated_entry = {**entry, **payload}
    rag_result = await index_case_record(supabase, updated_entry, source_kind="public")
    changes["status"] = "applied"
    changes["rag"] = rag_result
    return changes


async def main() -> None:
    args = parse_args()
    if not args.task_id and not args.all:
        print("请指定 --task-id <id>（可重复）或 --all")
        raise SystemExit(2)

    try:
        from app.agents.tools.llm_client import get_llm

        llm = get_llm()
    except Exception as exc:
        print(f"[warn] LLM 不可用，标题/摘要将使用确定性兜底: {exc}")
        llm = None

    entries = _fetch_entries(args.task_id, args.all)
    if not entries:
        print("未找到匹配的已发布公开案例。")
        return
    results = []
    for entry in entries:
        try:
            results.append(await backfill_entry(entry, llm, apply=args.apply))
        except Exception as exc:
            results.append({"task_id": entry.get("task_id"), "status": "error", "error": f"{type(exc).__name__}: {exc}"})
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
