-- Canonical human collaboration tables.
-- Legacy consultation_* tables are kept for read compatibility; new writes should use collaboration_*.

alter table if exists public.tasks
  drop constraint if exists tasks_status_check;

alter table if exists public.tasks
  add constraint tasks_status_check
  check (status in (
    'pending',
    'preprocessing',
    'analyzing',
    'deliberating',
    'waiting_collaboration',
    'waiting_collaboration_approval',
    'waiting_consultation',
    'waiting_consultation_approval',
    'completed',
    'failed'
  ));

create table if not exists public.collaboration_sessions (
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

create table if not exists public.collaboration_invites (
  id uuid default gen_random_uuid() primary key,
  task_id uuid references public.tasks(id) on delete cascade not null,
  token text not null unique,
  session_id uuid references public.collaboration_sessions(id) on delete set null,
  status text not null default 'pending',
  expires_at timestamptz not null,
  created_at timestamptz default now()
);

create table if not exists public.collaboration_messages (
  id uuid default gen_random_uuid() primary key,
  task_id uuid references public.tasks(id) on delete cascade not null,
  session_id uuid references public.collaboration_sessions(id) on delete set null,
  role text not null default 'expert',
  message text not null,
  expert_name text,
  message_type text default 'expert_opinion',
  anchor_agent text,
  anchor_phase text,
  confidence double precision,
  suggested_action text,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

do $$
begin
  if to_regclass('public.consultation_sessions') is not null then
    execute $copy_sessions$
      insert into public.collaboration_sessions (
        id,
        task_id,
        status,
        reason,
        triggered_by_agent,
        trigger_phase,
        trigger_round,
        repeat_index,
        context_payload,
        summary_payload,
        created_by,
        approved_by,
        approved_at,
        closed_at,
        created_at,
        updated_at
      )
      select
        id,
        task_id,
        status,
        reason,
        triggered_by_agent,
        trigger_phase,
        trigger_round,
        repeat_index,
        context_payload,
        summary_payload,
        created_by,
        approved_by,
        approved_at,
        closed_at,
        created_at,
        updated_at
      from public.consultation_sessions
      on conflict (id) do nothing
    $copy_sessions$;
  end if;
end $$;

do $$
begin
  if to_regclass('public.consultation_invites') is not null then
    execute $copy_invites$
      insert into public.collaboration_invites (
        id,
        task_id,
        token,
        session_id,
        status,
        expires_at,
        created_at
      )
      select
        ci.id,
        ci.task_id,
        ci.token,
        case
          when cs.id is not null then ci.session_id
          else null
        end,
        ci.status,
        ci.expires_at,
        ci.created_at
      from public.consultation_invites ci
      left join public.collaboration_sessions cs on cs.id = ci.session_id
      on conflict (id) do nothing
    $copy_invites$;
  end if;
end $$;

do $$
begin
  if to_regclass('public.consultation_messages') is not null then
    execute $copy_messages$
      insert into public.collaboration_messages (
        id,
        task_id,
        session_id,
        role,
        message,
        expert_name,
        message_type,
        anchor_agent,
        anchor_phase,
        confidence,
        suggested_action,
        metadata,
        created_at
      )
      select
        cm.id,
        cm.task_id,
        case
          when cs.id is not null then cm.session_id
          else null
        end,
        cm.role,
        cm.message,
        cm.expert_name,
        coalesce(cm.message_type, 'expert_opinion'),
        cm.anchor_agent,
        cm.anchor_phase,
        cm.confidence,
        cm.suggested_action,
        coalesce(cm.metadata, '{}'::jsonb),
        cm.created_at
      from public.consultation_messages cm
      left join public.collaboration_sessions cs on cs.id = cm.session_id
      on conflict (id) do nothing
    $copy_messages$;
  end if;
end $$;

alter table if exists public.experience_library_entries
  add column if not exists source_collaboration_session_id uuid references public.collaboration_sessions(id) on delete set null;

do $$
begin
  if to_regclass('public.experience_library_entries') is not null
    and exists (
      select 1
      from information_schema.columns
      where table_schema = 'public'
        and table_name = 'experience_library_entries'
        and column_name = 'source_session_id'
    )
  then
    execute $backfill_experience_sessions$
      update public.experience_library_entries e
      set source_collaboration_session_id = e.source_session_id
      from public.collaboration_sessions s
      where e.source_collaboration_session_id is null
        and e.source_session_id = s.id
    $backfill_experience_sessions$;
  end if;
end $$;

create index if not exists idx_collaboration_sessions_task_created
  on public.collaboration_sessions(task_id, created_at desc);

create index if not exists idx_collaboration_sessions_task_status
  on public.collaboration_sessions(task_id, status);

create index if not exists idx_collaboration_invites_task_created
  on public.collaboration_invites(task_id, created_at desc);

create index if not exists idx_collaboration_invites_session_id
  on public.collaboration_invites(session_id);

create index if not exists idx_collaboration_messages_task_created
  on public.collaboration_messages(task_id, created_at);

create index if not exists idx_collaboration_messages_session_created
  on public.collaboration_messages(session_id, created_at);

alter table public.collaboration_sessions enable row level security;
alter table public.collaboration_invites enable row level security;
alter table public.collaboration_messages enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_trigger
    where tgname = 'set_collaboration_sessions_updated_at'
      and tgrelid = 'public.collaboration_sessions'::regclass
  ) then
    create trigger set_collaboration_sessions_updated_at before update on public.collaboration_sessions
      for each row execute function public.set_updated_at();
  end if;
end $$;

drop policy if exists collaboration_sessions_select_task_owner on public.collaboration_sessions;
create policy collaboration_sessions_select_task_owner on public.collaboration_sessions
  for select
  using (exists (select 1 from public.tasks where tasks.id = collaboration_sessions.task_id and tasks.user_id = (select auth.uid())));

drop policy if exists collaboration_sessions_insert_task_owner on public.collaboration_sessions;
create policy collaboration_sessions_insert_task_owner on public.collaboration_sessions
  for insert
  with check (exists (select 1 from public.tasks where tasks.id = collaboration_sessions.task_id and tasks.user_id = (select auth.uid())));

drop policy if exists collaboration_sessions_update_task_owner on public.collaboration_sessions;
create policy collaboration_sessions_update_task_owner on public.collaboration_sessions
  for update
  using (exists (select 1 from public.tasks where tasks.id = collaboration_sessions.task_id and tasks.user_id = (select auth.uid())));

drop policy if exists collaboration_invites_select_task_owner on public.collaboration_invites;
create policy collaboration_invites_select_task_owner on public.collaboration_invites
  for select
  using (exists (select 1 from public.tasks where tasks.id = collaboration_invites.task_id and tasks.user_id = (select auth.uid())));

drop policy if exists collaboration_invites_insert_task_owner on public.collaboration_invites;
create policy collaboration_invites_insert_task_owner on public.collaboration_invites
  for insert
  with check (exists (select 1 from public.tasks where tasks.id = collaboration_invites.task_id and tasks.user_id = (select auth.uid())));

drop policy if exists collaboration_invites_update_task_owner on public.collaboration_invites;
create policy collaboration_invites_update_task_owner on public.collaboration_invites
  for update
  using (exists (select 1 from public.tasks where tasks.id = collaboration_invites.task_id and tasks.user_id = (select auth.uid())));

drop policy if exists collaboration_messages_select_task_or_invite on public.collaboration_messages;
create policy collaboration_messages_select_task_or_invite on public.collaboration_messages
  for select
  using (exists (select 1 from public.tasks where tasks.id = collaboration_messages.task_id and tasks.user_id = (select auth.uid())));

drop policy if exists collaboration_messages_insert_task_owner on public.collaboration_messages;
create policy collaboration_messages_insert_task_owner on public.collaboration_messages
  for insert
  with check (exists (select 1 from public.tasks where tasks.id = collaboration_messages.task_id and tasks.user_id = (select auth.uid())));

do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    begin
      alter publication supabase_realtime add table public.collaboration_sessions;
    exception
      when duplicate_object then null;
      when undefined_table then null;
    end;

    begin
      alter publication supabase_realtime add table public.collaboration_messages;
    exception
      when duplicate_object then null;
      when undefined_table then null;
    end;
  end if;
end $$;
