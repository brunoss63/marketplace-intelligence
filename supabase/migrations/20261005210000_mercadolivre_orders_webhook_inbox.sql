begin;

create table if not exists public.marketplace_webhook_events (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    marketplace text not null,
    external_user_id text not null,
    topic text not null check (topic = 'orders_v2'),
    resource text not null check (resource ~ '^/orders/[0-9]+$'),
    event_sent_at timestamptz not null,
    deduplication_key text not null unique
        check (deduplication_key ~ '^[0-9a-f]{64}$'),
    payload jsonb not null,
    status text not null default 'pending'
        check (status in ('pending', 'processing', 'processed', 'failed')),
    attempt_count integer not null default 0 check (attempt_count >= 0),
    next_attempt_at timestamptz not null default now(),
    lease_id uuid,
    lease_until timestamptz,
    last_error text,
    received_at timestamptz not null default now(),
    processed_at timestamptz,
    updated_at timestamptz not null default now(),
    foreign key (tenant_id, marketplace)
        references public.marketplace_connections(tenant_id, marketplace)
        on delete cascade
);

create index if not exists marketplace_webhook_events_pending_idx
    on public.marketplace_webhook_events(next_attempt_at, received_at)
    where status in ('pending', 'processing');

alter table public.marketplace_webhook_events enable row level security;

revoke all on public.marketplace_webhook_events from public, anon, authenticated;
grant select, insert, update, delete
    on public.marketplace_webhook_events to service_role;

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
    inserted_id uuid;
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
    on conflict (deduplication_key) do nothing
    returning id into inserted_id;

    if inserted_id is not null then
        return true;
    end if;

    return exists (
        select 1
        from public.marketplace_webhook_events as queued_event
        where queued_event.deduplication_key = target_deduplication_key
          and queued_event.external_user_id = target_user_id
          and queued_event.marketplace = 'Mercado Livre'
    );
end;
$$;

revoke all on function public.enqueue_mercadolivre_order_webhook(
    text, text, timestamptz, text, jsonb
) from public, anon, authenticated;
grant execute on function public.enqueue_mercadolivre_order_webhook(
    text, text, timestamptz, text, jsonb
) to service_role;

create or replace function public.claim_mercadolivre_order_webhooks(
    target_lease_id uuid,
    target_batch_size integer default 20
)
returns setof public.marketplace_webhook_events
language plpgsql
security definer
set search_path = ''
as $$
begin
    if target_batch_size < 1 or target_batch_size > 100 then
        raise exception 'Batch size must be between 1 and 100';
    end if;

    return query
    with candidates as (
        select queued_event.id
        from public.marketplace_webhook_events as queued_event
        where (
            queued_event.status = 'pending'
            and queued_event.next_attempt_at <= now()
        ) or (
            queued_event.status = 'processing'
            and queued_event.lease_until < now()
        )
        order by queued_event.received_at
        for update skip locked
        limit target_batch_size
    )
    update public.marketplace_webhook_events as queued_event
    set status = 'processing',
        attempt_count = queued_event.attempt_count + 1,
        lease_id = target_lease_id,
        lease_until = now() + interval '2 minutes',
        updated_at = now()
    from candidates
    where queued_event.id = candidates.id
    returning queued_event.*;
end;
$$;

revoke all on function public.claim_mercadolivre_order_webhooks(uuid, integer)
    from public, anon, authenticated;
grant execute on function
    public.claim_mercadolivre_order_webhooks(uuid, integer) to service_role;

commit;
