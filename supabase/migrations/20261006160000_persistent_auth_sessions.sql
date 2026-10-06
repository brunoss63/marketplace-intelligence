begin;

create table if not exists public.auth_sessions (
    session_hash text primary key
        check (session_hash ~ '^[0-9a-f]{64}$'),
    user_id uuid not null references auth.users(id) on delete cascade,
    access_token_encrypted text not null,
    refresh_token_encrypted text not null,
    expires_at timestamptz not null,
    revoked_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists auth_sessions_user_expiry_idx
    on public.auth_sessions(user_id, expires_at);

alter table public.auth_sessions enable row level security;

drop policy if exists auth_sessions_user_access on public.auth_sessions;
create policy auth_sessions_user_access
    on public.auth_sessions
    for all
    to authenticated
    using (user_id = (select auth.uid()))
    with check (user_id = (select auth.uid()));

revoke all on public.auth_sessions from public, anon, authenticated;
grant select, insert, update on public.auth_sessions to authenticated;

create or replace function public.restore_auth_session(
    target_session_hash text
)
returns table (
    access_token_encrypted text,
    refresh_token_encrypted text
)
language sql
security definer
set search_path = ''
as $$
    select session_row.access_token_encrypted,
           session_row.refresh_token_encrypted
    from public.auth_sessions as session_row
    where target_session_hash ~ '^[0-9a-f]{64}$'
      and session_row.session_hash = target_session_hash
      and session_row.revoked_at is null
      and session_row.expires_at > now()
    limit 1;
$$;

create or replace function public.revoke_auth_session(
    target_session_hash text
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
    if target_session_hash ~ '^[0-9a-f]{64}$' then
        update public.auth_sessions
        set revoked_at = now(),
            updated_at = now()
        where session_hash = target_session_hash
          and revoked_at is null;
    end if;
end;
$$;

revoke all on function public.restore_auth_session(text)
    from public, anon, authenticated;
revoke all on function public.revoke_auth_session(text)
    from public, anon, authenticated;
grant execute on function public.restore_auth_session(text)
    to anon, authenticated;
grant execute on function public.revoke_auth_session(text)
    to anon, authenticated;

commit;
