begin;

create table if not exists public.marketplace_connections (
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    marketplace text not null check (marketplace = 'Mercado Livre'),
    external_user_id text not null,
    access_token_encrypted text not null,
    refresh_token_encrypted text not null,
    scope text not null,
    expires_at timestamptz not null,
    refresh_lease_id uuid,
    refresh_lease_until timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (tenant_id, marketplace)
);

create table if not exists public.marketplace_oauth_transactions (
    state_hash text primary key,
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    code_verifier_encrypted text not null,
    expires_at timestamptz not null,
    created_at timestamptz not null default now()
);

create index if not exists marketplace_oauth_transactions_expiry_idx
    on public.marketplace_oauth_transactions(expires_at);

alter table public.marketplace_connections enable row level security;
alter table public.marketplace_oauth_transactions enable row level security;

drop policy if exists marketplace_connections_tenant_access
    on public.marketplace_connections;
create policy marketplace_connections_tenant_access
    on public.marketplace_connections
    for all
    to authenticated
    using (public.user_has_tenant_access(tenant_id))
    with check (public.user_has_tenant_access(tenant_id));

drop policy if exists marketplace_oauth_transactions_user_access
    on public.marketplace_oauth_transactions;
create policy marketplace_oauth_transactions_user_access
    on public.marketplace_oauth_transactions
    for all
    to authenticated
    using (
        user_id = (select auth.uid())
        and public.user_has_tenant_access(tenant_id)
    )
    with check (
        user_id = (select auth.uid())
        and public.user_has_tenant_access(tenant_id)
    );

revoke all on public.marketplace_connections,
    public.marketplace_oauth_transactions from anon, authenticated;
grant select, insert, update, delete on public.marketplace_connections
    to authenticated;
grant select, insert, delete on public.marketplace_oauth_transactions
    to authenticated;

create or replace function public.claim_marketplace_token_refresh(
    target_tenant_id uuid,
    target_lease_id uuid
)
returns boolean
language plpgsql
security invoker
set search_path = ''
as $$
declare
    affected_rows integer;
begin
    update public.marketplace_connections
    set refresh_lease_id = target_lease_id,
        refresh_lease_until = now() + interval '45 seconds'
    where tenant_id = target_tenant_id
      and marketplace = 'Mercado Livre'
      and (
          refresh_lease_until is null
          or refresh_lease_until < now()
          or refresh_lease_id = target_lease_id
      );

    get diagnostics affected_rows = row_count;
    return affected_rows = 1;
end;
$$;

create or replace function public.release_marketplace_token_refresh(
    target_tenant_id uuid,
    target_lease_id uuid
)
returns boolean
language plpgsql
security invoker
set search_path = ''
as $$
declare
    affected_rows integer;
begin
    update public.marketplace_connections
    set refresh_lease_id = null,
        refresh_lease_until = null
    where tenant_id = target_tenant_id
      and marketplace = 'Mercado Livre'
      and refresh_lease_id = target_lease_id;

    get diagnostics affected_rows = row_count;
    return affected_rows = 1;
end;
$$;

revoke all on function public.claim_marketplace_token_refresh(uuid, uuid)
    from public, anon;
revoke all on function public.release_marketplace_token_refresh(uuid, uuid)
    from public, anon;
grant execute on function
    public.claim_marketplace_token_refresh(uuid, uuid) to authenticated;
grant execute on function
    public.release_marketplace_token_refresh(uuid, uuid) to authenticated;

commit;
