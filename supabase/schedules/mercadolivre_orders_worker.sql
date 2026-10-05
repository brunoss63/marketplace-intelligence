-- Run this script in the Supabase DEV SQL Editor only after both Edge
-- Functions are deployed, their secrets are configured, and these two values
-- exist in Vault:
--   supabase_url
--   mercadolivre_worker_secret
--
-- The first job drains one queued order every minute. The second periodically
-- replays orders_v2 entries still available in Mercado Livre missed_feeds.

create extension if not exists pg_cron;
create extension if not exists pg_net;

do $$
begin
    if not exists (
        select 1 from vault.decrypted_secrets
        where name = 'supabase_url' and decrypted_secret <> ''
    ) or not exists (
        select 1 from vault.decrypted_secrets
        where name = 'mercadolivre_worker_secret' and decrypted_secret <> ''
    ) then
        raise exception
            'Set supabase_url and mercadolivre_worker_secret in Supabase Vault before scheduling the worker';
    end if;
end;
$$;

select cron.unschedule(jobid)
from cron.job
where jobname in (
    'mercadolivre-orders-worker',
    'mercadolivre-orders-missed-feeds'
);

select cron.schedule(
    'mercadolivre-orders-worker',
    '* * * * *',
    $job$
    select net.http_post(
        url := (
            select decrypted_secret
            from vault.decrypted_secrets
            where name = 'supabase_url'
        ) || '/functions/v1/mercadolivre-orders-worker',
        headers := jsonb_build_object(
            'content-type', 'application/json',
            'authorization', 'Bearer ' || (
                select decrypted_secret
                from vault.decrypted_secrets
                where name = 'mercadolivre_worker_secret'
            )
        ),
        body := '{}'::jsonb
    );
    $job$
);

select cron.schedule(
    'mercadolivre-orders-missed-feeds',
    '0 */6 * * *',
    $job$
    select net.http_post(
        url := (
            select decrypted_secret
            from vault.decrypted_secrets
            where name = 'supabase_url'
        ) || '/functions/v1/mercadolivre-orders-worker?mode=reconcile',
        headers := jsonb_build_object(
            'content-type', 'application/json',
            'authorization', 'Bearer ' || (
                select decrypted_secret
                from vault.decrypted_secrets
                where name = 'mercadolivre_worker_secret'
            )
        ),
        body := '{}'::jsonb
    );
    $job$
);
