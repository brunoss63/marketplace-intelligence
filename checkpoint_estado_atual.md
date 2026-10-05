# Estado atual do projeto

## Contexto

Atualizado em 5 de outubro de 2026. O objetivo comercial imediato é validar valor
com um primeiro cliente em um piloto pequeno, autorizado e acompanhado, antes de
investir em escala ou integrações que não façam parte do escopo desse cliente.

## Estado funcional

- O app usa Streamlit + Supabase, com isolamento de dados por tenant.
- O Mercado Livre é a integração operacional principal em DEV. OAuth e leitura
  autenticada foram exercitados; a sincronização manual de pedidos, produtos e
  estoque está disponível, com ressalvas de validação de dados reais da conta.
- A governança do tenant inclui papéis owner/member, controles administrativos e
  auditoria de acesso.
- A Shopee tem uma base de OAuth e conexão segura, mas sincronização real de
  pedidos/estoque não está operacional. Não é requisito universal para o piloto.
- Nenhum primeiro cliente adicional foi cadastrado. Antes de acessar os dados
  de um cliente, obter autorização, acordar escopo e criar/acessar seu tenant de
  forma restrita.

## Atualizações automáticas de pedidos do Mercado Livre

- As Edge Functions `mercadolivre-orders-webhook` e
  `mercadolivre-orders-worker` foram publicadas no Supabase DEV.
- Os secrets necessários estão configurados; `supabase_url` e o segredo do
  worker ficam no Vault.
- Os jobs Cron estão ativos: worker a cada minuto e reconciliação de
  `missed_feeds` a cada seis horas.
- Chamadas recentes via Cron receberam HTTP 200, sem timeout, com
  `processed: 0`. A reconciliação autenticada retornou HTTP 200 para uma conexão
  e uma página vazia (`messages: null`); isso confirma a consulta sem eventos,
  não a recuperação nem o processamento de notificações reais.
- O callback não foi configurado no portal do Mercado Livre. Não foi validado
  um evento aceito para vendedor conectado nem processado um pedido real pelo
  worker. Também não foi medida a latência do caminho de sucesso. Não prometer
  SLA de 500 ms ou “tempo real” antes dessas verificações.
- Não ativar `orders_v2` até existir um pedido de teste real e autorizado para
  confirmar callback, deduplicação, gravação no tenant correto e reconciliação.
- A correção recente trata `messages: null` como página vazia. Os 12 testes
  Deno passaram, `deno check` e `deno fmt --check` passaram.

## Arquivos e componentes relevantes

- `GUIA_PILOTO_PRIVADO.md`: instruções operacionais do piloto e estado validado.
- `RESUMO_PROJETO.md`: estratégia de primeiro cliente, estado e próximas etapas.
- `integracao_mercadolivre.py` e `sincronizacao_mercadolivre.py`: OAuth e
  sincronização do Mercado Livre.
- `supabase/functions/mercadolivre-orders-webhook/`: callback de pedidos.
- `supabase/functions/mercadolivre-orders-worker/`: worker, fila e reconciliação.
- `supabase/schedules/mercadolivre_orders_worker.sql`: jobs Cron do worker e da
  reconciliação.
- `administracao.py` e `autenticacao.py`: governança e isolamento por tenant.
- `integracao_shopee.py` e `sincronizacao_shopee.py`: base não operacional da
  integração Shopee.

## Próximo passo

Conduzir o piloto inicial com o marketplace e problema que o primeiro cliente
realmente precisa, sem prometer funcionalidades não validadas. Para validar
atualização automática, obter um pedido de teste real e autorizado na conta DEV,
então testar callback, inbox, worker, isolamento do tenant, latência e
reconciliação ponta a ponta. Até lá, tratar atualizações como manuais ou apenas
na frequência comprovadamente disponível.
