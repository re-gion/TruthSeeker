-- Add missing consultation message storage used by consultation API and Challenger agent.

create table if not exists public.consultation_messages (
  id uuid default gen_random_uuid() primary key,
  task_id uuid references public.tasks(id) on delete cascade not null,
  role text not null default 'expert',
  message text not null,
  expert_name text,
  created_at timestamptz default now()
);

create index if not exists idx_consultation_messages_task_created
  on public.consultation_messages(task_id, created_at);
