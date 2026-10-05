begin;

alter table public.marketplace_connections
    drop constraint if exists marketplace_connections_marketplace_check;

alter table public.marketplace_connections
    add constraint marketplace_connections_marketplace_check
    check (marketplace in ('Mercado Livre', 'Shopee'));

commit;
