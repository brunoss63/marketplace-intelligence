do $$
declare
    auth_user_count integer;
    pilot_user_id uuid;
    pilot_tenant_id uuid;
begin
    select count(*)
    into auth_user_count
    from auth.users;

    if auth_user_count <> 1 then
        raise exception
            'Expected exactly one initial auth user; found %.',
            auth_user_count;
    end if;

    select id
    into pilot_user_id
    from auth.users
    limit 1;

    insert into public.tenants (name, slug)
    values ('Marketplace Intelligence - Piloto', 'marketplace-intelligence-piloto')
    on conflict (slug)
    do update set name = excluded.name
    returning id into pilot_tenant_id;

    insert into public.tenant_members (tenant_id, user_id, role)
    values (pilot_tenant_id, pilot_user_id, 'owner')
    on conflict (tenant_id, user_id)
    do update set role = excluded.role;
end
$$;
