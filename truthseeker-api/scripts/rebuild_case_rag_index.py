"""Rebuild public case-library RAG chunks.

Usage:
  python scripts/rebuild_case_rag_index.py --include-builtin --include-public
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.case_rag import rebuild_case_rag_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild case-library RAG embeddings.")
    parser.add_argument("--include-builtin", action="store_true", help="Index built-in demo cases.")
    parser.add_argument("--include-public", action="store_true", help="Index published public case_library_entries.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    include_builtin = args.include_builtin or not args.include_public
    include_public = args.include_public
    result = await rebuild_case_rag_index(include_builtin=include_builtin, include_public=include_public)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
