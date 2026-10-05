create table if not exists public.pilot_administrators (
    user_id uuid primary key references auth.users(id) on delete cascade,
    created_at timestamptz not null default now()
);

alter table public.pilot_administrators enable row level security;
revoke all on public.pilot_administrators from public, anon, authenticated;

create or replace function public.user_is_pilot_administrator()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.pilot_administrators as administrator
        where administrator.user_id = (select auth.uid())
    );
$$;

revoke all on function public.user_is_pilot_administrator() from public, anon;
grant execute on function public.user_is_pilot_administrator() to authenticated;

drop policy if exists tenant_access_audit_select_owner
    on public.tenant_access_audit;
create policy tenant_access_audit_select_owner
    on public.tenant_access_audit
    for select
    to authenticated
    using (
        actor_user_id = (select auth.uid())
        or public.user_is_tenant_owner(actor_tenant_id)
        or (
            action = 'pilot_onboarding_request'
            and public.user_is_pilot_administrator()
        )
    );

create or replace function public.approve_pilot_onboarding(
    p_user_id uuid,
    p_tenant_name text,
    p_role text,
    p_actor_tenant_id uuid,
    p_target_tenant_id uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_request_id uuid;
    v_tenant_id uuid;
    v_tenant_name text;
    v_slug_base text;
    v_slug text;
begin
    if (select auth.uid()) is null then
        raise exception 'Authentication is required to approve pilot onboarding.';
    end if;

    if not public.user_is_pilot_administrator() then
        raise exception 'Only a pilot administrator can approve onboarding requests.';
    end if;

    if p_user_id is null then
        raise exception 'The requested user ID is required.';
    end if;

    if p_role is null or p_role not in ('owner', 'member') then
        raise exception 'The requested tenant role is invalid.';
    end if;

    if not exists (
        select 1
        from public.tenant_members as member
        where member.tenant_id = p_actor_tenant_id
          and member.user_id = (select auth.uid())
          and member.role = 'owner'
    ) then
        raise exception 'Only an owner of the acting tenant can approve onboarding.';
    end if;

    select request.id
    into v_request_id
    from public.tenant_access_audit as request
    where request.actor_user_id = p_user_id
      and request.actor_tenant_id is null
      and request.target_tenant_id is null
      and request.action = 'pilot_onboarding_request'
    order by request.created_at desc
    limit 1
    for update;

    if v_request_id is null then
        raise exception 'No pending pilot onboarding request exists for this user.';
    end if;

    if exists (
        select 1
        from public.tenant_members as member
        where member.user_id = p_user_id
    ) then
        raise exception 'The requested user is already linked to a tenant.';
    end if;

    if p_target_tenant_id is null then
        v_tenant_name := coalesce(
            nullif(btrim(p_tenant_name), ''),
            'Tenant piloto ' || left(p_user_id::text, 8)
        );
        v_slug_base := trim(
            both '-'
            from regexp_replace(lower(v_tenant_name), '[^a-z0-9]+', '-', 'g')
        );
        v_slug := left(coalesce(nullif(v_slug_base, ''), 'tenant-piloto'), 45)
            || '-'
            || left(replace(p_user_id::text, '-', ''), 8);

        insert into public.tenants (name, slug)
        values (v_tenant_name, v_slug)
        returning id into v_tenant_id;
    else
        if not public.user_is_tenant_owner(p_target_tenant_id) then
            raise exception 'Only an owner of the target tenant can add this user.';
        end if;
        v_tenant_id := p_target_tenant_id;
    end if;

    insert into public.tenant_members (tenant_id, user_id, role)
    values (v_tenant_id, p_user_id, p_role);

    update public.tenant_access_audit
    set target_tenant_id = v_tenant_id
    where actor_user_id = p_user_id
      and actor_tenant_id is null
      and target_tenant_id is null
      and action = 'pilot_onboarding_request';

    insert into public.tenant_access_audit (
        actor_user_id,
        actor_tenant_id,
        target_tenant_id,
        action,
        reason
    )
    values (
        (select auth.uid()),
        p_actor_tenant_id,
        v_tenant_id,
        'grant',
        'Pilot onboarding approved for user ' || p_user_id::text || '.'
    );

    return jsonb_build_object(
        'tenant_id', v_tenant_id,
        'user_id', p_user_id,
        'role', p_role,
        'request_id', v_request_id
    );
end;
$$;

revoke all on function public.approve_pilot_onboarding(
    uuid, text, text, uuid, uuid
) from public, anon;
grant execute on function public.approve_pilot_onboarding(
    uuid, text, text, uuid, uuid
) to authenticated;
