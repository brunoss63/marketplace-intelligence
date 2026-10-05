create table if not exists public.tenant_access_audit (
    id uuid primary key default gen_random_uuid(),
    actor_user_id uuid not null references auth.users(id) on delete cascade,
    actor_tenant_id uuid references public.tenants(id) on delete cascade,
    target_tenant_id uuid references public.tenants(id) on delete set null,
    action text not null check (action in ('view', 'invite', 'grant', 'revoke', 'sync', 'pilot_onboarding_request')),
    reason text not null default '',
    created_at timestamptz not null default now()
);

create index if not exists tenant_access_audit_actor_tenant_created_idx
    on public.tenant_access_audit(actor_tenant_id, created_at desc);

create or replace function public.user_is_tenant_owner(target_tenant_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.tenant_members as member
        where member.tenant_id = target_tenant_id
          and member.user_id = (select auth.uid())
          and member.role = 'owner'
    );
$$;

revoke all on function public.user_is_tenant_owner(uuid) from public, anon;
grant execute on function public.user_is_tenant_owner(uuid) to authenticated;

alter table public.tenant_access_audit enable row level security;

drop policy if exists tenant_access_audit_insert_owner on public.tenant_access_audit;
create policy tenant_access_audit_insert_owner
    on public.tenant_access_audit
    for insert
    to authenticated
    with check (
        actor_user_id = (select auth.uid())
        and (
            actor_tenant_id is null
            or public.user_is_tenant_owner(actor_tenant_id)
        )
    );

drop policy if exists tenant_access_audit_select_owner on public.tenant_access_audit;
create policy tenant_access_audit_select_owner
    on public.tenant_access_audit
    for select
    to authenticated
    using (
        actor_user_id = (select auth.uid())
        or public.user_is_tenant_owner(actor_tenant_id)
    );

revoke all on public.tenant_access_audit from anon, authenticated;
grant select, insert on public.tenant_access_audit to authenticated;
