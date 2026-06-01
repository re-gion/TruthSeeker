-- Public case RAG: pgvector-backed chunks for published and builtin cases.

create extension if not exists vector;

create table if not exists public.case_library_rag_chunks (
  id uuid default gen_random_uuid() primary key,
  source_kind text not null check (source_kind in ('public', 'builtin')),
  case_id text not null,
  chunk_id text not null unique,
  chunk_index integer not null check (chunk_index >= 0),
  title text not null,
  media_category text not null
    check (media_category in ('text_generation', 'image_forgery', 'image_text_mixed', 'audio_forgery', 'video_forgery')),
  verdict text check (verdict in ('authentic', 'suspicious', 'forged', 'inconclusive')),
  difficulty text check (difficulty in ('Low', 'Medium', 'High', 'Critical')),
  chunk_text text not null,
  snippet text,
  embedding vector(1024) not null,
  embedding_model text not null,
  embedding_dimensions integer not null default 1024,
  content_hash text not null,
  published_at timestamptz,
  indexed_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_case_library_rag_chunks_case
  on public.case_library_rag_chunks(source_kind, case_id, chunk_index);

create index if not exists idx_case_library_rag_chunks_category
  on public.case_library_rag_chunks(media_category);

create unique index if not exists idx_case_library_rag_chunks_source_hash
  on public.case_library_rag_chunks(source_kind, case_id, chunk_index, content_hash);

create index if not exists idx_case_library_rag_chunks_fts
  on public.case_library_rag_chunks
  using gin (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(chunk_text, '')));

create index if not exists idx_case_library_rag_chunks_embedding_hnsw
  on public.case_library_rag_chunks
  using hnsw (embedding vector_cosine_ops);

alter table public.case_library_rag_chunks enable row level security;

create policy case_library_rag_chunks_service_all on public.case_library_rag_chunks
  for all to authenticated using (true) with check (true);

create or replace function public.match_case_library_rag_chunks(
  query_embedding vector(1024),
  match_count integer default 12,
  filter_category text default null
)
returns table (
  chunk_id text,
  case_id text,
  source_kind text,
  title text,
  media_category text,
  verdict text,
  difficulty text,
  chunk_text text,
  snippet text,
  similarity double precision
)
language sql
stable
as $$
  select
    c.chunk_id,
    c.case_id,
    c.source_kind,
    c.title,
    c.media_category,
    c.verdict,
    c.difficulty,
    c.chunk_text,
    c.snippet,
    1 - (c.embedding <=> query_embedding) as similarity
  from public.case_library_rag_chunks c
  where filter_category is null or c.media_category = filter_category
  order by c.embedding <=> query_embedding
  limit greatest(match_count, 1)
$$;
