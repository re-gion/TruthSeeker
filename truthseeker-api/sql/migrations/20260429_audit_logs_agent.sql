-- Add agent column and index to audit_logs for better traceability.

alter table if exists public.audit_logs
  add column if not exists agent text;

create index if not exists idx_audit_logs_agent_created
  on public.audit_logs(agent, created_at desc);
