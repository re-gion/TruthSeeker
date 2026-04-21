-- TruthSeeker baseline schema and RLS policies.
-- This file must run before later incremental migrations in a fresh Supabase project.

create extension if not exists pgcrypto;

create table if not exists public.tasks (
  id uuid default gen_random_uuid() primary key,
  title text not null default 'Untitled Task',
  status text not null default 'pending',
  input_type text not null default 'video',
  description text,
  user_id text,
  metadata jsonb not null default '{}'::jsonb,
  storage_paths jsonb not null default '{}'::jsonb,
  priority_focus text not null default 'balanced',
  result jsonb,
  verdict jsonb,
  response_ms integer,
  duration_ms integer,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.analysis_states (
  id uuid default gen_random_uuid() primary key,
  task_id uuid references public.tasks(id) on delete cascade not null,
  round_number int default 1,
  forensics_score float,
  osint_score float,
  convergence_delta float,
  evidence_board jsonb default '{}'::jsonb,
  result_snapshot jsonb default '{}'::jsonb,
  current_agent text,
  is_converged boolean default false,
  termination_reason text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.agent_logs (
  id uuid default gen_random_uuid() primary key,
  task_id uuid references public.tasks(id) on delete cascade not null,
  round_number int not null,
  agent_name text not null,
  log_type text,
  content text not null,
  metadata jsonb default '{}'::jsonb,
  timestamp timestamptz default now()
);

create table if not exists public.reports (
  id uuid default gen_random_uuid() primary key,
  task_id uuid references public.tasks(id) on delete cascade not null unique,
  verdict text,
  confidence_overall float,
  summary text,
  key_evidence jsonb default '[]'::jsonb,
  recommendations jsonb default '[]'::jsonb,
  verdict_payload jsonb default '{}'::jsonb,
  share_token text unique,
  report_hash text,
  generated_at timestamptz default now()
);

create table if not exists public.consultation_invites (
  id uuid default gen_random_uuid() primary key,
  task_id uuid references public.tasks(id) on delete cascade not null,
  token text not null unique,
  status text default 'pending',
  expires_at timestamptz,
  created_at timestamptz default now()
);

create table if not exists public.consultation_messages (
  id uuid default gen_random_uuid() primary key,
  task_id uuid references public.tasks(id) on delete cascade not null,
  role text not null default 'expert',
  message text not null,
  expert_name text,
  created_at timestamptz default now()
);

create table if not exists public.audit_logs (
  id uuid default gen_random_uuid() primary key,
  action text not null,
  task_id uuid references public.tasks(id) on delete set null,
  user_id text,
  actor_role text default 'user',
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create index if not exists idx_tasks_user_created on public.tasks(user_id, created_at desc);
create index if not exists idx_tasks_status_created on public.tasks(status, created_at desc);
create index if not exists idx_analysis_states_task_round on public.analysis_states(task_id, round_number);
create index if not exists idx_agent_logs_task_round on public.agent_logs(task_id, round_number);
create index if not exists idx_reports_share_token on public.reports(share_token);
create index if not exists idx_reports_report_hash on public.reports(report_hash);
create index if not exists idx_consultation_invites_token on public.consultation_invites(token);
create index if not exists idx_consultation_messages_task_created on public.consultation_messages(task_id, created_at);
create index if not exists idx_audit_logs_task_created on public.audit_logs(task_id, created_at desc);
create index if not exists idx_audit_logs_action_created on public.audit_logs(action, created_at desc);

alter table public.tasks enable row level security;
alter table public.analysis_states enable row level security;
alter table public.agent_logs enable row level security;
alter table public.reports enable row level security;
alter table public.consultation_invites enable row level security;
alter table public.consultation_messages enable row level security;
alter table public.audit_logs enable row level security;

drop policy if exists tasks_select_own on public.tasks;
create policy tasks_select_own on public.tasks
  for select to authenticated
  using (user_id is null or user_id = auth.uid()::text);

drop policy if exists tasks_insert_own on public.tasks;
create policy tasks_insert_own on public.tasks
  for insert to authenticated
  with check (user_id is null or user_id = auth.uid()::text);

drop policy if exists tasks_update_own on public.tasks;
create policy tasks_update_own on public.tasks
  for update to authenticated
  using (user_id is null or user_id = auth.uid()::text)
  with check (user_id is null or user_id = auth.uid()::text);

drop policy if exists tasks_delete_own on public.tasks;
create policy tasks_delete_own on public.tasks
  for delete to authenticated
  using (user_id is null or user_id = auth.uid()::text);

drop policy if exists analysis_states_select_task_owner on public.analysis_states;
create policy analysis_states_select_task_owner on public.analysis_states
  for select to authenticated
  using (exists (
    select 1 from public.tasks
    where tasks.id = analysis_states.task_id
      and (tasks.user_id is null or tasks.user_id = auth.uid()::text)
  ));

drop policy if exists agent_logs_select_task_owner on public.agent_logs;
create policy agent_logs_select_task_owner on public.agent_logs
  for select to authenticated
  using (exists (
    select 1 from public.tasks
    where tasks.id = agent_logs.task_id
      and (tasks.user_id is null or tasks.user_id = auth.uid()::text)
  ));

drop policy if exists reports_select_task_owner on public.reports;
create policy reports_select_task_owner on public.reports
  for select to authenticated
  using (exists (
    select 1 from public.tasks
    where tasks.id = reports.task_id
      and (tasks.user_id is null or tasks.user_id = auth.uid()::text)
  ));

drop policy if exists consultation_invites_select_task_owner on public.consultation_invites;
create policy consultation_invites_select_task_owner on public.consultation_invites
  for select to authenticated
  using (exists (
    select 1 from public.tasks
    where tasks.id = consultation_invites.task_id
      and (tasks.user_id is null or tasks.user_id = auth.uid()::text)
  ));

drop policy if exists consultation_messages_select_task_owner on public.consultation_messages;
create policy consultation_messages_select_task_owner on public.consultation_messages
  for select to authenticated
  using (exists (
    select 1 from public.tasks
    where tasks.id = consultation_messages.task_id
      and (tasks.user_id is null or tasks.user_id = auth.uid()::text)
  ));

drop policy if exists audit_logs_select_task_owner on public.audit_logs;
create policy audit_logs_select_task_owner on public.audit_logs
  for select to authenticated
  using (
    task_id is null
    or exists (
      select 1 from public.tasks
      where tasks.id = audit_logs.task_id
        and (tasks.user_id is null or tasks.user_id = auth.uid()::text)
    )
  );
