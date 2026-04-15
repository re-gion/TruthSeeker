-- TruthSeeker full-fix migration

alter table if exists public.tasks
  add column if not exists metadata jsonb default '{}'::jsonb;

alter table if exists public.tasks
  add column if not exists storage_paths jsonb default '{}'::jsonb;

alter table if exists public.tasks
  add column if not exists priority_focus text default 'balanced';

alter table if exists public.tasks
  add column if not exists started_at timestamptz;

alter table if exists public.tasks
  add column if not exists completed_at timestamptz;

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

create index if not exists idx_analysis_states_task_round on public.analysis_states(task_id, round_number);
create index if not exists idx_agent_logs_task_round on public.agent_logs(task_id, round_number);
create index if not exists idx_reports_share_token on public.reports(share_token);
create index if not exists idx_consultation_invites_token on public.consultation_invites(token);
