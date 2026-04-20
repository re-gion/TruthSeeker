-- TruthSeeker report integrity and audit trail migration.

alter table if exists public.reports
  add column if not exists report_hash text;

create index if not exists idx_reports_report_hash on public.reports(report_hash);

create table if not exists public.audit_logs (
  id uuid default gen_random_uuid() primary key,
  action text not null,
  task_id uuid references public.tasks(id) on delete set null,
  user_id text,
  actor_role text default 'user',
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create index if not exists idx_audit_logs_task_created on public.audit_logs(task_id, created_at desc);
create index if not exists idx_audit_logs_action_created on public.audit_logs(action, created_at desc);
