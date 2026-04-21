-- TruthSeeker baseline schema and RLS policies.
-- This file must run before later incremental migrations in a fresh Supabase project.
-- Updated 2026-04-21: aligned with live Supabase schema (uuid user_id, CHECK constraints, result_snapshot).

create extension if not exists pgcrypto;

-- profiles: mirrors Supabase auth.users
create table if not exists public.profiles (
  id uuid references auth.users(id) on delete cascade primary key,
  username text unique,
  role text default 'user' check (role in ('user', 'admin')),
  avatar_url text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- tasks: core detection task tracking
create table if not exists public.tasks (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references public.profiles(id),
  title text not null default 'Untitled Task',
  description text,
  input_type text not null default 'video'
    check (input_type in ('video', 'audio', 'image', 'text', 'mixed')),
  priority_focus text not null default 'balanced'
    check (priority_focus in ('visual', 'audio', 'text', 'balanced')),
  storage_paths jsonb not null default '{}'::jsonb,
  status text not null default 'pending'
    check (status in ('pending', 'preprocessing', 'analyzing', 'deliberating', 'waiting_consultation', 'completed', 'failed')),
  progress integer default 0 check (progress >= 0 and progress <= 100),
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  expires_at timestamptz default (now() + interval '7 days'),
  deleted_at timestamptz,
  result jsonb,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- analysis_states: per-round agent debate snapshots
create table if not exists public.analysis_states (
  id uuid default gen_random_uuid() primary key,
  task_id uuid references public.tasks(id) on delete cascade not null,
  round_number int default 1,
  forensics_score float check (forensics_score is null or (forensics_score >= 0 and forensics_score <= 1)),
  osint_score float check (osint_score is null or (osint_score >= 0 and osint_score <= 1)),
  convergence_delta float,
  evidence_board jsonb default '{}'::jsonb,
  result_snapshot jsonb not null default '{}'::jsonb,
  current_agent text,
  is_converged boolean default false,
  termination_reason text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- agent_logs: per-agent thinking/action/finding logs
create table if not exists public.agent_logs (
  id uuid default gen_random_uuid() primary key,
  task_id uuid references public.tasks(id) on delete cascade not null,
  round_number int not null default 1,
  agent_name text not null,
  log_type text check (log_type in ('thinking', 'action', 'finding', 'challenge', 'conclusion')),
  content text not null,
  metadata jsonb default '{}'::jsonb,
  timestamp timestamptz default now()
);

-- reports: final verdict and share tokens
create table if not exists public.reports (
  id uuid default gen_random_uuid() primary key,
  task_id uuid references public.tasks(id) on delete cascade not null unique,
  verdict text check (verdict in ('authentic', 'suspicious', 'forged', 'inconclusive')),
  confidence_overall float,
  summary text,
  key_evidence jsonb default '[]'::jsonb,
  recommendations jsonb default '[]'::jsonb,
  verdict_payload jsonb default '{}'::jsonb,
  share_token text unique,
  report_hash text,
  generated_at timestamptz default now()
);

-- consultation_invites: expert invitation tokens
create table if not exists public.consultation_invites (
  id uuid default gen_random_uuid() primary key,
  task_id uuid references public.tasks(id) on delete cascade not null,
  token text not null unique,
  status text default 'pending',
  expires_at timestamptz,
  created_at timestamptz default now()
);

-- consultation_messages: expert chat messages
create table if not exists public.consultation_messages (
  id uuid default gen_random_uuid() primary key,
  task_id uuid references public.tasks(id) on delete cascade not null,
  role text not null default 'expert',
  message text not null,
  expert_name text,
  created_at timestamptz default now()
);

-- audit_logs: security and action audit trail
create table if not exists public.audit_logs (
  id uuid default gen_random_uuid() primary key,
  action text not null,
  task_id uuid references public.tasks(id) on delete set null,
  user_id text,
  actor_role text default 'user',
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

-- system_stats: dashboard aggregate stats
create table if not exists public.system_stats (
  id serial primary key,
  date date unique default current_date,
  total_tasks integer default 0,
  completed_tasks integer default 0,
  avg_processing_time interval,
  threat_type_distribution jsonb default '{}'::jsonb,
  updated_at timestamptz default now()
);

-- Indexes
create index if not exists idx_tasks_user_created on public.tasks(user_id, created_at desc);
create index if not exists idx_tasks_status_created on public.tasks(status, created_at desc);
create index if not exists idx_analysis_states_task_round on public.analysis_states(task_id, round_number);
create index if not exists idx_agent_logs_task_round on public.agent_logs(task_id, round_number);
create index if not exists idx_reports_share_token on public.reports(share_token);
create index if not exists idx_reports_report_hash on public.reports(report_hash);
create index if not exists idx_consultation_invites_token on public.consultation_invites(token);
create index if not exists idx_consultation_invites_task_id on public.consultation_invites(task_id);
create index if not exists idx_consultation_messages_task_created on public.consultation_messages(task_id, created_at);
create index if not exists idx_audit_logs_task_created on public.audit_logs(task_id, created_at desc);
create index if not exists idx_audit_logs_action_created on public.audit_logs(action, created_at desc);

-- Enable RLS on all tables
alter table public.profiles enable row level security;
alter table public.tasks enable row level security;
alter table public.analysis_states enable row level security;
alter table public.agent_logs enable row level security;
alter table public.reports enable row level security;
alter table public.consultation_invites enable row level security;
alter table public.consultation_messages enable row level security;
alter table public.audit_logs enable row level security;
alter table public.system_stats enable row level security;

-- Helper functions (search_path set for security)
create or replace function public.set_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin new.updated_at = now(); return new; end;
$$;

create or replace function public.handle_new_user()
returns trigger language plpgsql set search_path = '' as $$
begin
  insert into public.profiles (id, username, role) values (
    new.id,
    coalesce(new.raw_user_meta_data->>'username', new.email),
    coalesce(new.raw_user_meta_data->>'role', 'user')
  );
  return new;
end;
$$;

-- profiles RLS (using (select auth.uid()) for initplan optimization)
create policy "Users can view own profile" on public.profiles
  for select to authenticated using ((select auth.uid()) = id);
create policy "Users can update own profile" on public.profiles
  for update to authenticated using ((select auth.uid()) = id);

-- tasks RLS
create policy users_own_tasks_select on public.tasks
  for select to authenticated using ((select auth.uid()) = user_id);
create policy users_own_tasks_insert on public.tasks
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy users_own_tasks_update on public.tasks
  for update to authenticated using ((select auth.uid()) = user_id);
create policy anon_tasks_insert on public.tasks
  for insert to public with check (user_id is null);

-- analysis_states RLS
create policy "Analysis states viewable by task owner" on public.analysis_states
  for select to authenticated
  using (exists (select 1 from public.tasks where tasks.id = analysis_states.task_id and tasks.user_id = (select auth.uid())));
create policy "Analysis states insertable by service" on public.analysis_states
  for insert to authenticated
  with check (exists (select 1 from public.tasks where tasks.id = analysis_states.task_id and tasks.user_id = (select auth.uid())));

-- agent_logs RLS
create policy "Agent logs viewable by task owner" on public.agent_logs
  for select to authenticated
  using (exists (select 1 from public.tasks where tasks.id = agent_logs.task_id and tasks.user_id = (select auth.uid())));
create policy "Agent logs insertable by service" on public.agent_logs
  for insert to authenticated
  with check (exists (select 1 from public.tasks where tasks.id = agent_logs.task_id and tasks.user_id = (select auth.uid())));

-- reports RLS
create policy "Reports viewable by task owner" on public.reports
  for select to authenticated
  using (exists (select 1 from public.tasks where tasks.id = reports.task_id and tasks.user_id = (select auth.uid())));
create policy reports_insert_by_owner on public.reports
  for insert to authenticated
  with check (exists (select 1 from public.tasks where tasks.id = reports.task_id and (tasks.user_id = (select auth.uid()) or tasks.user_id is null)));

-- consultation_invites RLS
create policy consultation_invites_select_task_owner on public.consultation_invites
  for select to authenticated
  using (exists (select 1 from public.tasks where tasks.id = consultation_invites.task_id and tasks.user_id = (select auth.uid())));
create policy consultation_invites_insert_task_owner on public.consultation_invites
  for insert to authenticated
  with check (exists (select 1 from public.tasks where tasks.id = consultation_invites.task_id and tasks.user_id = (select auth.uid())));
create policy consultation_invites_update_task_owner on public.consultation_invites
  for update to authenticated
  using (exists (select 1 from public.tasks where tasks.id = consultation_invites.task_id and tasks.user_id = (select auth.uid())));

-- consultation_messages RLS
create policy "Consultation messages viewable by task owner" on public.consultation_messages
  for select to authenticated
  using (exists (select 1 from public.tasks where tasks.id = consultation_messages.task_id and tasks.user_id = (select auth.uid())));
create policy "Consultation messages insertable by task owner" on public.consultation_messages
  for insert to authenticated
  with check (exists (select 1 from public.tasks where tasks.id = consultation_messages.task_id and tasks.user_id = (select auth.uid())));

-- audit_logs RLS
create policy audit_logs_select_task_owner on public.audit_logs
  for select to authenticated
  using (task_id is null or exists (select 1 from public.tasks where tasks.id = audit_logs.task_id and tasks.user_id = (select auth.uid())));
create policy audit_logs_insert_authenticated on public.audit_logs
  for insert to authenticated with check (true);

-- system_stats RLS
create policy system_stats_select_all on public.system_stats
  for select to public using (true);

-- Triggers
create trigger set_updated_at before update on public.tasks
  for each row execute function public.set_updated_at();
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();
