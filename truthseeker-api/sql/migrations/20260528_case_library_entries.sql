-- Public case library: stores redacted public report cards and private Storage references.

create table if not exists public.case_library_entries (
  id uuid default gen_random_uuid() primary key,
  task_id uuid references public.tasks(id) on delete set null,
  user_id uuid references public.profiles(id) on delete set null,
  status text not null default 'published'
    check (status in ('published', 'draft', 'hidden')),
  title text not null,
  media_category text not null
    check (media_category in ('text_generation', 'image_forgery', 'image_text_mixed', 'audio_forgery', 'video_forgery')),
  summary text,
  verdict text check (verdict in ('authentic', 'suspicious', 'forged', 'inconclusive')),
  confidence_overall float check (confidence_overall is null or (confidence_overall >= 0 and confidence_overall <= 1)),
  difficulty text check (difficulty in ('Low', 'Medium', 'High')),
  public_files jsonb not null default '[]'::jsonb,
  report_markdown text not null default '',
  content_fingerprint text not null,
  published_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_case_library_entries_fingerprint
  on public.case_library_entries(content_fingerprint)
  where status = 'published';

create index if not exists idx_case_library_entries_category_published
  on public.case_library_entries(media_category, published_at desc)
  where status = 'published';

create index if not exists idx_case_library_entries_task_id
  on public.case_library_entries(task_id);

alter table public.case_library_entries enable row level security;

create policy case_library_entries_public_select on public.case_library_entries
  for select to public using (status = 'published');

create policy case_library_entries_insert_authenticated on public.case_library_entries
  for insert to authenticated with check (true);

create policy case_library_entries_update_authenticated on public.case_library_entries
  for update to authenticated using (true);

drop trigger if exists set_case_library_entries_updated_at on public.case_library_entries;
create trigger set_case_library_entries_updated_at before update on public.case_library_entries
  for each row execute function public.set_updated_at();

alter table public.tasks drop constraint if exists tasks_input_type_check;
alter table public.tasks add constraint tasks_input_type_check
  check (input_type in ('video', 'audio', 'image', 'text', 'mixed'));
