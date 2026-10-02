create table if not exists public.tenants (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    slug text not null unique,
    created_at timestamptz not null default now()
);

create table if not exists public.tenant_members (
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    role text not null check (role in ('owner', 'member')),
    created_at timestamptz not null default now(),
    primary key (tenant_id, user_id)
);

create index if not exists tenant_members_user_id_idx
    on public.tenant_members(user_id);

create table if not exists public.products (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    marketplace text not null,
    sku text not null,
    product_name text not null,
    category text,
    unit_cost numeric(14, 2),
    sale_price numeric(14, 2),
    initial_stock numeric(14, 3),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (tenant_id, marketplace, sku)
);

create table if not exists public.orders (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    marketplace text not null,
    order_id text not null,
    order_date date not null,
    sku text not null default '',
    product_name text not null default '',
    quantity numeric(14, 3) not null,
    unit_price numeric(14, 2),
    gross_revenue numeric(14, 2) not null,
    discount numeric(14, 2) not null default 0,
    marketplace_fee numeric(14, 2) not null default 0,
    seller_shipping numeric(14, 2) not null default 0,
    status text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (tenant_id, marketplace, order_id, sku, product_name)
);

create index if not exists orders_tenant_date_idx
    on public.orders(tenant_id, order_date desc);
create index if not exists orders_tenant_sku_idx
    on public.orders(tenant_id, sku);

create table if not exists public.inventory (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    marketplace text not null,
    sku text not null,
    product_name text not null default '',
    current_stock numeric(14, 3) not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (tenant_id, marketplace, sku)
);

create table if not exists public.ad_performance (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    marketplace text not null,
    ad_date date not null,
    sku text not null,
    campaign text not null,
    spend numeric(14, 2) not null,
    attributed_revenue numeric(14, 2) not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (tenant_id, marketplace, ad_date, sku, campaign)
);

create index if not exists ad_performance_tenant_date_idx
    on public.ad_performance(tenant_id, ad_date desc);

create table if not exists public.import_batches (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    marketplace text not null,
    data_type text not null
        check (data_type in ('Pedidos', 'Produtos', 'Estoque', 'Publicidade')),
    source_filename text not null,
    fingerprint text not null,
    source_records integer not null check (source_records >= 0),
    imported_records integer not null check (imported_records >= 0),
    inserted_records integer not null check (inserted_records >= 0),
    updated_records integer not null check (updated_records >= 0),
    ignored_records integer not null check (ignored_records >= 0),
    error_records integer not null check (error_records >= 0),
    status text not null,
    imported_at timestamptz not null default now(),
    unique (tenant_id, fingerprint)
);

create or replace function public.user_has_tenant_access(target_tenant_id uuid)
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
    );
$$;

revoke all on function public.user_has_tenant_access(uuid) from public, anon;
grant execute on function public.user_has_tenant_access(uuid) to authenticated;

alter table public.tenants enable row level security;
alter table public.tenant_members enable row level security;
alter table public.products enable row level security;
alter table public.orders enable row level security;
alter table public.inventory enable row level security;
alter table public.ad_performance enable row level security;
alter table public.import_batches enable row level security;

drop policy if exists tenant_members_read_self on public.tenant_members;
create policy tenant_members_read_self
    on public.tenant_members
    for select
    to authenticated
    using (user_id = (select auth.uid()));

drop policy if exists tenants_read_member on public.tenants;
create policy tenants_read_member
    on public.tenants
    for select
    to authenticated
    using (public.user_has_tenant_access(id));

drop policy if exists products_tenant_access on public.products;
create policy products_tenant_access
    on public.products
    for all
    to authenticated
    using (public.user_has_tenant_access(tenant_id))
    with check (public.user_has_tenant_access(tenant_id));

drop policy if exists orders_tenant_access on public.orders;
create policy orders_tenant_access
    on public.orders
    for all
    to authenticated
    using (public.user_has_tenant_access(tenant_id))
    with check (public.user_has_tenant_access(tenant_id));

drop policy if exists inventory_tenant_access on public.inventory;
create policy inventory_tenant_access
    on public.inventory
    for all
    to authenticated
    using (public.user_has_tenant_access(tenant_id))
    with check (public.user_has_tenant_access(tenant_id));

drop policy if exists ad_performance_tenant_access on public.ad_performance;
create policy ad_performance_tenant_access
    on public.ad_performance
    for all
    to authenticated
    using (public.user_has_tenant_access(tenant_id))
    with check (public.user_has_tenant_access(tenant_id));

drop policy if exists import_batches_tenant_access on public.import_batches;
create policy import_batches_tenant_access
    on public.import_batches
    for all
    to authenticated
    using (public.user_has_tenant_access(tenant_id))
    with check (public.user_has_tenant_access(tenant_id));

revoke all on public.tenants, public.tenant_members, public.products,
    public.orders, public.inventory, public.ad_performance,
    public.import_batches from anon, authenticated;

grant select on public.tenants, public.tenant_members to authenticated;
grant select, insert, update, delete on public.products, public.orders,
    public.inventory, public.ad_performance, public.import_batches
    to authenticated;
