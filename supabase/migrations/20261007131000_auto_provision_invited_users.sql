drop function if exists public.provision_pilot_user(
    uuid, text, text, uuid
);

create or replace function public.provision_invited_pilot_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_tenant_name text;
    v_slug text;
    v_tenant_id uuid;
begin
    if new.invited_at is null then
        return new;
    end if;

    if exists (
        select 1
        from public.tenant_members as member
        where member.user_id = new.id
    ) then
        return new;
    end if;

    v_tenant_name := 'Tenant piloto ' || left(new.id::text, 8);
    v_slug := 'tenant-' || left(replace(new.id::text, '-', ''), 24);

    insert into public.tenants (name, slug)
    values (v_tenant_name, v_slug)
    returning id into v_tenant_id;

    insert into public.tenant_members (tenant_id, user_id, role)
    values (v_tenant_id, new.id, 'member');

    return new;
end;
$$;

revoke all on function public.provision_invited_pilot_user()
    from public, anon, authenticated;

drop trigger if exists provision_invited_pilot_user on auth.users;
create trigger provision_invited_pilot_user
    after insert on auth.users
    for each row
    when (new.invited_at is not null)
    execute function public.provision_invited_pilot_user();
