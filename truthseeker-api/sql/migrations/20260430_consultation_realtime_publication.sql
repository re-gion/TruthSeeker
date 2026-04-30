-- Enable Supabase Realtime for consultation sessions and messages.
-- Idempotent: adding an already-published table raises duplicate_object.

do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    begin
      alter publication supabase_realtime add table public.consultation_sessions;
    exception
      when duplicate_object then null;
      when undefined_table then null;
    end;

    begin
      alter publication supabase_realtime add table public.consultation_messages;
    exception
      when duplicate_object then null;
      when undefined_table then null;
    end;
  end if;
end $$;
