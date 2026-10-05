begin;

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
      and marketplace in ('Mercado Livre', 'Shopee')
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
      and marketplace in ('Mercado Livre', 'Shopee')
      and refresh_lease_id = target_lease_id;

    get diagnostics affected_rows = row_count;
    return affected_rows = 1;
end;
$$;

commit;
