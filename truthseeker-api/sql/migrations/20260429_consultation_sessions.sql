-- Add structured human-in-the-loop consultation sessions and message metadata.

alter table if exists public.tasks
  drop constraint if exists tasks_status_check;

alter table if exists public.tasks
  add constraint tasks_status_check
  check (status in ('pending', 'preprocessing', 'analyzing', 'deliberating', 'waiting_consultation', 'waiting_consultation_approval', 'completed', 'failed'));

create table if not exists public.consultation_sessions (
  id uuid default gen_random_uuid() primary key,
  task_id uuid references public.tasks(id) on delete cascade not null,
  status text not null default 'requested'
    check (status in ('requested', 'waiting_user_approval', 'active', 'summary_pending', 'summary_confirmed', 'skipped', 'cancelled')),
  reason text,
  triggered_by_agent text,
  trigger_phase text,
  trigger_round integer,
  repeat_index integer not null default 1,
  context_payload jsonb default '{}'::jsonb,
  summary_payload jsonb default '{}'::jsonb,
  created_by text,
  approved_by uuid references public.profiles(id) on delete set null,
  approved_at timestamptz,
  closed_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table if exists public.consultation_invites
  add column if not exists session_id uuid references public.consultation_sessions(id) on delete set null;

alter table if exists public.consultation_messages
  add column if not exists session_id uuid references public.consultation_sessions(id) on delete set null,
  add column if not exists message_type text default 'expert_opinion',
  add column if not exists anchor_agent text,
  add column if not exists anchor_phase text,
  add column if not exists confidence double precision,
  add column if not exists suggested_action text,
  add column if not exists metadata jsonb default '{}'::jsonb;

create index if not exists idx_consultation_sessions_task_created
  on public.consultation_sessions(task_id, created_at desc);

create index if not exists idx_consultation_sessions_task_status
  on public.consultation_sessions(task_id, status);

create index if not exists idx_consultation_invites_session_id
  on public.consultation_invites(session_id);

create index if not exists idx_consultation_messages_session_created
  on public.consultation_messages(session_id, created_at);

alter table public.consultation_sessions enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_trigger
    where tgname = 'set_consultation_sessions_updated_at'
      and tgrelid = 'public.consultation_sessions'::regclass
  ) then
    create trigger set_consultation_sessions_updated_at before update on public.consultation_sessions
      for each row execute function public.set_updated_at();
  end if;
end $$;

drop policy if exists consultation_sessions_select_task_owner on public.consultation_sessions;
create policy consultation_sessions_select_task_owner on public.consultation_sessions
  for select
  using (exists (select 1 from public.tasks where tasks.id = consultation_sessions.task_id and tasks.user_id = (select auth.uid())));

drop policy if exists consultation_sessions_insert_task_owner on public.consultation_sessions;
create policy consultation_sessions_insert_task_owner on public.consultation_sessions
  for insert
  with check (exists (select 1 from public.tasks where tasks.id = consultation_sessions.task_id and tasks.user_id = (select auth.uid())));

drop policy if exists consultation_sessions_update_task_owner on public.consultation_sessions;
create policy consultation_sessions_update_task_owner on public.consultation_sessions
  for update
  using (exists (select 1 from public.tasks where tasks.id = consultation_sessions.task_id and tasks.user_id = (select auth.uid())));
