drop function if exists public.approve_pilot_onboarding(
    uuid, text, text, uuid, uuid
);

drop policy if exists tenant_access_audit_select_owner
    on public.tenant_access_audit;
create policy tenant_access_audit_select_owner
    on public.tenant_access_audit
    for select
    to authenticated
    using (
        actor_user_id = (select auth.uid())
        or public.user_is_tenant_owner(actor_tenant_id)
    );

create or replace function public.provision_pilot_user(
    p_user_id uuid,
    p_tenant_name text,
    p_role text,
    p_actor_tenant_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_user_id uuid;
    v_tenant_id uuid;
    v_tenant_name text;
    v_slug_base text;
    v_slug text;
begin
    if (select auth.uid()) is null then
        raise exception 'Authentication is required to provision a pilot user.';
    end if;

    if not public.user_is_pilot_administrator() then
        raise exception 'Only a pilot administrator can provision invited users.';
    end if;

    if p_user_id is null then
        raise exception 'The invited user ID is required.';
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
        raise exception 'Only an owner of the acting tenant can provision a pilot user.';
    end if;

    select invited.id
    into v_user_id
    from auth.users as invited
    where invited.id = p_user_id
    for update;

    if v_user_id is null then
        raise exception 'The user must be invited or created in Supabase Auth first.';
    end if;

    if exists (
        select 1
        from public.tenant_members as member
        where member.user_id = p_user_id
    ) then
        raise exception 'The invited user is already linked to a tenant.';
    end if;

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

    insert into public.tenant_members (tenant_id, user_id, role)
    values (v_tenant_id, p_user_id, p_role);

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
        'Provisioned invited pilot user ' || p_user_id::text || '.'
    );

    return jsonb_build_object(
        'tenant_id', v_tenant_id,
        'user_id', p_user_id,
        'role', p_role
    );
end;
$$;

revoke all on function public.provision_pilot_user(
    uuid, text, text, uuid
) from public, anon;
grant execute on function public.provision_pilot_user(
    uuid, text, text, uuid
) to authenticated;
