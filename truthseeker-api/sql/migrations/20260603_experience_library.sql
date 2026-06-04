-- Private personal experience library and per-user RAG chunks.

create extension if not exists vector;

create table if not exists public.experience_library_entries (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references public.profiles(id) on delete cascade,
  source_task_id uuid references public.tasks(id) on delete set null,
  source_session_id uuid references public.consultation_sessions(id) on delete set null,
  status text not null default 'active' check (status in ('active', 'archived')),
  target_agents text[] not null default '{}',
  title text not null,
  problem_pattern text not null,
  recommended_method text not null,
  evidence_to_check jsonb not null default '[]'::jsonb,
  when_to_escalate text not null default '',
  limitations text not null default '',
  content_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_experience_entries_user_hash
  on public.experience_library_entries(user_id, content_hash)
  where status = 'active';

create index if not exists idx_experience_entries_user_created
  on public.experience_library_entries(user_id, created_at desc);

create index if not exists idx_experience_entries_agents
  on public.experience_library_entries using gin(target_agents);

alter table public.experience_library_entries enable row level security;

create policy experience_entries_select_own on public.experience_library_entries
  for select to authenticated using (user_id = (select auth.uid()));

create policy experience_entries_insert_own on public.experience_library_entries
  for insert to authenticated with check (user_id = (select auth.uid()));

create policy experience_entries_update_own on public.experience_library_entries
  for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

create policy experience_entries_delete_own on public.experience_library_entries
  for delete to authenticated using (user_id = (select auth.uid()));

drop trigger if exists set_experience_library_entries_updated_at on public.experience_library_entries;
create trigger set_experience_library_entries_updated_at before update on public.experience_library_entries
  for each row execute function public.set_updated_at();

create table if not exists public.experience_library_rag_chunks (
  id uuid default gen_random_uuid() primary key,
  entry_id uuid references public.experience_library_entries(id) on delete cascade,
  user_id uuid references public.profiles(id) on delete cascade,
  target_agent text not null check (target_agent in ('forensics', 'osint', 'challenger')),
  chunk_id text not null unique,
  title text not null,
  chunk_text text not null,
  snippet text,
  embedding vector(1024) not null,
  embedding_model text not null,
  embedding_dimensions integer not null default 1024,
  content_hash text not null,
  indexed_at timestamptz not null default now()
);

create index if not exists idx_experience_rag_user_agent
  on public.experience_library_rag_chunks(user_id, target_agent);

create index if not exists idx_experience_rag_entry
  on public.experience_library_rag_chunks(entry_id);

create index if not exists idx_experience_rag_fts
  on public.experience_library_rag_chunks
  using gin (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(chunk_text, '')));

create index if not exists idx_experience_rag_embedding_hnsw
  on public.experience_library_rag_chunks
  using hnsw (embedding vector_cosine_ops);

alter table public.experience_library_rag_chunks enable row level security;

create policy experience_rag_select_own on public.experience_library_rag_chunks
  for select to authenticated using (user_id = (select auth.uid()));

create policy experience_rag_insert_own on public.experience_library_rag_chunks
  for insert to authenticated with check (user_id = (select auth.uid()));

create policy experience_rag_delete_own on public.experience_library_rag_chunks
  for delete to authenticated using (user_id = (select auth.uid()));

create or replace function public.match_experience_library_rag_chunks(
  query_embedding vector(1024),
  match_user_id uuid,
  match_agent text,
  match_count integer default 12
)
returns table (
  chunk_id text,
  entry_id uuid,
  user_id uuid,
  target_agent text,
  title text,
  chunk_text text,
  snippet text,
  similarity double precision
)
language sql
stable
as $$
  select
    c.chunk_id,
    c.entry_id,
    c.user_id,
    c.target_agent,
    c.title,
    c.chunk_text,
    c.snippet,
    1 - (c.embedding <=> query_embedding) as similarity
  from public.experience_library_rag_chunks c
  where c.user_id = match_user_id
    and c.target_agent = match_agent
  order by c.embedding <=> query_embedding
  limit greatest(match_count, 1)
$$;
