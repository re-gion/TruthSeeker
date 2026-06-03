"""Delete stale public case-library RAG chunks.

Usage:
  python scripts/delete_public_case_rag_chunks.py --title-contains "案例3-图片-客服通知.jpg 等 2 个检材"
  python scripts/delete_public_case_rag_chunks.py --title-contains "案例3-图片-客服通知.jpg 等 2 个检材" --apply
  python scripts/delete_public_case_rag_chunks.py --case-id <case_id> --apply

The default mode is dry-run. Pass --apply to actually delete matched chunks.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.utils.supabase_client import supabase


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete stale public case-library RAG chunks.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case-id", help="Delete public chunks for this case_id.")
    group.add_argument("--title-contains", help="Delete public chunks whose title contains this text.")
    parser.add_argument("--apply", action="store_true", help="Actually delete matched chunks. Omit for dry-run.")
    return parser.parse_args()


def _query_matches(case_id: str | None, title_contains: str | None) -> list[dict]:
    query = (
        supabase.table("case_library_rag_chunks")
        .select("chunk_id,case_id,title,source_kind")
        .eq("source_kind", "public")
    )
    if case_id:
        query = query.eq("case_id", case_id)
    if title_contains:
        query = query.ilike("title", f"%{title_contains}%")
    return query.limit(500).execute().data or []


def _delete_matches(rows: list[dict]) -> int:
    deleted = 0
    for row in rows:
        chunk_id = row.get("chunk_id")
        if not chunk_id:
            continue
        supabase.table("case_library_rag_chunks").delete().eq("source_kind", "public").eq("chunk_id", chunk_id).execute()
        deleted += 1
    return deleted


def main() -> None:
    args = parse_args()
    rows = _query_matches(args.case_id, args.title_contains)
    deleted = _delete_matches(rows) if args.apply else 0
    print(json.dumps({
        "status": "deleted" if args.apply else "dry_run",
        "matched_chunks": len(rows),
        "deleted_chunks": deleted,
        "matches": rows[:50],
        "truncated": len(rows) > 50,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
