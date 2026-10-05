begin;

alter table public.marketplace_webhook_events
    drop constraint if exists marketplace_webhook_events_deduplication_key_key;

alter table public.marketplace_webhook_events
    add constraint marketplace_webhook_events_tenant_deduplication_key
    unique (tenant_id, deduplication_key);

create or replace function public.enqueue_mercadolivre_order_webhook(
    target_user_id text,
    target_resource text,
    target_sent_at timestamptz,
    target_deduplication_key text,
    target_payload jsonb
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
    inserted_rows integer;
begin
    if target_user_id !~ '^[0-9]+$'
       or target_resource !~ '^/orders/[0-9]+$'
       or target_deduplication_key !~ '^[0-9a-f]{64}$'
       or jsonb_typeof(target_payload) <> 'object' then
        raise exception 'Invalid Mercado Livre order notification';
    end if;

    insert into public.marketplace_webhook_events (
        tenant_id,
        marketplace,
        external_user_id,
        topic,
        resource,
        event_sent_at,
        deduplication_key,
        payload
    )
    select
        connection_row.tenant_id,
        connection_row.marketplace,
        connection_row.external_user_id,
        'orders_v2',
        target_resource,
        target_sent_at,
        target_deduplication_key,
        target_payload
    from public.marketplace_connections as connection_row
    where connection_row.marketplace = 'Mercado Livre'
      and connection_row.external_user_id = target_user_id
    on conflict (tenant_id, deduplication_key) do nothing;

    get diagnostics inserted_rows = row_count;
    return inserted_rows > 0 or exists (
        select 1
        from public.marketplace_webhook_events as queued_event
        where queued_event.external_user_id = target_user_id
          and queued_event.marketplace = 'Mercado Livre'
          and queued_event.deduplication_key = target_deduplication_key
    );
end;
$$;

grant select, update on public.marketplace_connections to service_role;
grant execute on function public.claim_marketplace_token_refresh(uuid, uuid)
    to service_role;
grant execute on function public.release_marketplace_token_refresh(uuid, uuid)
    to service_role;
grant execute on function public.enqueue_mercadolivre_order_webhook(
    text, text, timestamptz, text, jsonb
) to service_role;
grant execute on function public.claim_mercadolivre_order_webhooks(uuid, integer)
    to service_role;

commit;
