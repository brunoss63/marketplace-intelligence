# Preparar o piloto privado

## Estado desta etapa

O painel exige autenticação individual pelo Supabase Auth quando
`MI_ENV=development` ou `MI_ENV=production`, resolve o tenant vinculado à
conta e lê/grava pedidos, produtos, estoque, publicidade e histórico de
importação no Postgres usando a sessão autenticada. Cada ambiente usa
credenciais Supabase próprias. As políticas RLS restringem as operações ao
tenant do usuário. O modo local precisa ser ativado explicitamente com
`MI_ENV=local` e continua usando os CSVs locais.

O projeto Supabase do piloto, o schema e o vínculo inicial do tenant já foram
criados e aplicados. A validação autenticada foi concluída com a importação de
30 registros válidos de Pedidos do Mercado Livre: 30 inseridos, 0 atualizados,
0 ignorados e 0 erros. O dashboard confirmou a leitura dos pedidos e o
histórico da importação. Os CSVs fictícios locais não foram enviados. Novas
importações em produção gravam os registros e o histórico no banco, sem criar
cópias CSV/JSON locais. O fluxo OAuth do Mercado Livre está conectado no DEV,
e a sincronização manual de produtos e estoque já foi executada pela interface.
A sincronização de pedidos está implementada, mas ainda precisa ser validada
com pedidos reais. Não há sincronização agendada.

As leituras do banco ficam em cache por até 30 segundos, isoladas por tenant e
usuário. Uma importação pelo painel invalida o cache imediatamente para que os
dados recém-importados apareçam sem aguardar o vencimento.

O ambiente DEV separado já foi criado na organização BRDS Insights, na região
São Paulo (`sa-east-1`), com o schema e as políticas RLS aplicados. Há duas
contas de teste confirmadas e vinculadas a tenants distintos, e o cadastro
público está desativado. Uma conta provisória, criada com um endereço de teste
inacessível, permanece sem vínculo com tenant no DEV. As credenciais DEV foram
adicionadas somente ao `.streamlit/secrets.toml` local, que é ignorado pelo
Git; as credenciais do piloto foram preservadas.

O login da conta A foi confirmado no app local. A senha da conta B foi
redefinida no Supabase DEV e o login imediato por e-mail/senha foi confirmado
via Auth API e pela interface Streamlit. O app está rodando somente em
`http://127.0.0.1:8501`. O valor local `MI_ENV` deve ser `development` ao
trabalhar contra o DEV; `production` no arquivo local causou a falha de login
da conta B e foi corrigido.

No deploy DEV, a sessão Supabase continua persistida por até 30 dias em um
cookie do navegador para facilitar os testes do piloto. Em HTTPS o cookie usa
`Secure` e `SameSite=Lax`, mas não `HttpOnly`; portanto, JavaScript executado na
origem do aplicativo pode ler os tokens. Não use essa persistência do DEV com
dados comerciais.

No deploy PROD, os tokens não são gravados em cookie: permanecem somente na
`st.session_state` server-side durante a sessão ativa do Streamlit. Um cookie
legado de sessão é removido e nunca é usado para restaurar a autenticação.
Como a sessão está vinculada à conexão do Streamlit, recarregar a página ou
reconectar pode exigir novo login. Essa escolha evita expor os tokens em
JavaScript e mantém o deploy gratuito, mas não cria um cookie `HttpOnly`
persistente nem substitui um backend próprio se a persistência entre sessões
for necessária.

O app também foi publicado para validação no Streamlit Community Cloud em
`https://marketplace-intelligence-dev.streamlit.app/`, ligado somente ao
projeto Supabase DEV. O endereço é público; os dados continuam protegidos pelo
login Supabase, cadastro público desativado e policies RLS. Os secrets da
hospedagem contêm apenas a configuração DEV. O deploy acompanha `main` do
GitHub, portanto commits enviados a essa branch podem atualizar a implantação.
Os logins hospedados das contas A e B foram confirmados. Não use esse deploy de
Community Cloud como ambiente de produção comercial.

## Objetivo: conquistar e atender o primeiro cliente

O primeiro passo comercial é um piloto pequeno, autorizado e acompanhado de
perto com um cliente, para validar uma necessidade real e recolher feedback.
Não é preciso concluir Shopee, automação total ou preparação para escala antes
de iniciar essa conversa. Escolha com o cliente o marketplace e o problema que
serão o foco; só apresente como disponível o que já foi testado. O amigo pode
ser esse primeiro cliente se continuar sendo o candidato, mas isso não é um
pré-requisito.

Antes de acessar dados reais, confirme a autorização do cliente, explique o
escopo e as limitações, crie um tenant exclusivo e acompanhe o onboarding. Se
uma capacidade importante ainda não estiver validada, mantenha-a manual ou
fora do escopo do piloto, em vez de prometer automação ou “tempo real”. Ao
final, recolha feedback e decida com base nele se vale ampliar a integração ou
atender outro cliente.

O acesso operacional continua restrito ao tenant ao qual cada conta está
vinculada: owners administram o próprio tenant, mas não podem consultar dados
de outros tenants. O painel registra ações administrativas no tenant, e a
identidade global autorizada para aprovar onboarding não concede acesso
cruzado aos dados operacionais. O primeiro piloto não exige esse acesso
cruzado: o cliente deve operar seu próprio tenant. Qualquer futura função de
administração entre tenants precisa de autorização explícita e auditoria
própria. Não use chaves `service_role` no navegador ou na aplicação Streamlit
para contornar o isolamento RLS.

### Fluxo de onboarding do piloto

O processo de onboarding do piloto privado segue a seguinte sequência:

1. O usuário autenticado, mas sem vínculo com tenant, entra na tela de acesso e
   escolhe o fluxo de solicitação de onboarding.
2. O app grava um evento de `pilot_onboarding_request` em
   `tenant_access_audit` sem tenant associado, evitando a criação de acesso
   irrestrito antes da aprovação.
3. O administrador global do piloto acessa o painel e visualiza as solicitações
   pendentes. A autorização fica explícita em `pilot_administrators`; ser owner
   de um tenant, por si só, não concede visibilidade ou aprovação global.
4. O administrador informa o nome do tenant e o papel do usuário (`member` ou
   `owner`) e aprova a solicitação.
5. O sistema cria o tenant, registra o vínculo em `tenant_members` e mantém a
   auditoria da aprovação para rastreabilidade.
6. Com o tenant vinculado, a sessão do usuário passa a ter acesso ao ambiente
   isolado e aos dados do piloto de forma restrita ao tenant aprovado.

O fluxo depende também da migração
`supabase/migrations/20261005190000_pilot_onboarding_approval.sql`, que permite
ao administrador explicitamente autorizado consultar pedidos pendentes e
executa a aprovação em uma única transação no banco. A função valida o
administrador, o owner do tenant de auditoria, a existência de um pedido
pendente e a ausência de vínculo anterior antes de criar tenant, associação e
evento de auditoria. A primeira conta administradora deve ser autorizada
separadamente no Supabase pelo responsável do projeto.

Mercado Livre e Shopee são possibilidades do produto, não pré-requisitos para
o primeiro piloto: priorize o marketplace que o cliente escolhido realmente
usa. A conta própria do Mercado Livre foi vinculada ao portal de desenvolvedores
e a aplicação `Marketplace Intelligence DEV` foi criada como não certificada.
Ela usa OAuth Authorization Code com Refresh Token e PKCE, sem Client
Credentials, e a URI inicial de retorno
`https://marketplace-intelligence-dev.streamlit.app/`. As permissões de
vendas/envios, publicações, publicidade e métricas foram configuradas somente
para leitura; a permissão de usuários aparece como leitura e escrita fixa no
portal. Nenhum tópico ou callback de notificações foi configurado. O logotipo
usado é provisório.

A implementação do fluxo OAuth DEV está em `integracao_mercadolivre.py`:
state de uso único, PKCE S256, tokens criptografados no Supabase por tenant e
renovação serializada do refresh token. A conexão da conta própria foi
concluída em 3 de outubro de 2026 e o app confirmou o armazenamento
criptografado das credenciais no tenant DEV. Em 5 de outubro, a tela
“Validar conexão” confirmou uma chamada autenticada à API e a identidade da
conta. A sincronização manual de produtos e estoque das publicações ativas
também foi executada na conta DEV e o usuário confirmou que o fluxo funcionou.
Como a conta não tem produtos com estoque, ainda não foi possível comparar
saldos retornados com quantidades positivas na loja; o teste confirma a
execução do fluxo, não a precisão de saldos não nulos. A sincronização de
pedidos está implementada, mas ainda não foi validada com pedidos reais porque
essa conta não tem vendas. As operações são idempotentes e preservam custos,
taxas e frete que tenham sido informados manualmente. Não há agendamento
automático; produtos ou saldos antigos também não são removidos
automaticamente. Publicidade continua pela importação manual até validar os
recursos e métricas da API Product Ads. A migração
`supabase/migrations/20261003170000_mercadolivre_oauth.sql` foi aplicada
somente no Supabase DEV. Os secrets locais e hospedados do DEV incluem
`MERCADOLIVRE_DEV_CLIENT_ID`,
`MERCADOLIVRE_DEV_CLIENT_SECRET`, `MERCADOLIVRE_DEV_REDIRECT_URI` e uma chave
Fernet persistente em `MERCADOLIVRE_DEV_TOKEN_ENCRYPTION_KEY`. O endereço de
retorno precisa coincidir exatamente com o cadastrado no portal.

A migração `20261003170000_mercadolivre_oauth.sql` foi aplicada em 3 de
outubro de 2026 pelo SQL Editor do projeto
`marketplace-intelligence-dev`; o Supabase confirmou sucesso. Ela não foi
executada no projeto de produção.

Os secrets DEV já estão configurados. Para uma configuração futura ou
reconstrução do ambiente, siga estes passos sem compartilhar credenciais:

1. Gere localmente uma chave Fernet usando Python:

   ```powershell
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Copie a chave diretamente para os secrets locais e para os secrets do app
   Streamlit DEV. Ela precisa ser idêntica nos dois ambientes e permanecer
   estável enquanto houver tokens criptografados no banco. Não a envie por
   chat, não a versione e não a gere novamente depois de conectar uma conta.
2. Acrescente as quatro configurações `MERCADOLIVRE_DEV_*` ao
   `.streamlit/secrets.toml` local e ao painel **Settings > Secrets** do app
   hospedado. Use o Client ID e Client Secret da aplicação criada no portal e
   como redirect exatamente `https://marketplace-intelligence-dev.streamlit.app/`.
   Para as credenciais OAuth, o app hospedado prioriza esses Streamlit Secrets
   sobre variáveis de ambiente de mesmo nome.
   Preserve todas as configurações existentes e não inclua esses valores no
   `.streamlit/secrets.toml.example`.
3. Reinicie o app local e, na página **Marketplaces**, use **Validar conexão**
   para confirmar uma chamada autenticada. Uma nova autorização só é necessária
   se a conexão falhar ou for revogada. O código remove o `code` e o `state` da
   URL depois de autenticar no Supabase e validar o estado da transação. Não
   envie tokens ou screenshots que mostrem credenciais.

A chamada autenticada à API e a leitura de produtos/estoque foram executadas
no DEV. A conta de teste não tem produtos com estoque positivo nem vendas;
portanto, os saldos não nulos e os pedidos reais continuam sem validação live.
Não inclua client secret nem tokens no repositório ou em mensagens. Configure
notificações do Mercado Livre somente depois de publicar e validar um endpoint
de callback próprio. O worker está agendado no DEV, mas a conta permanece sem
notificações do Mercado Livre; até validar um evento autorizado, trate a
atualização como manual.

A Shopee ainda não tem aplicação registrada, credenciais elegíveis ou loja
autorizada para testes live. O código atual prepara OAuth, persistência segura
e sincronização, mas chamadas reais, sincronização pela interface e webhooks
permanecem bloqueados até confirmar acesso e contratos oficiais da Open
Platform. Não conectar a loja de terceiros antes de obter sua autorização.

### Atualizações automáticas de pedidos no Mercado Livre

As duas Edge Functions estão publicadas e ativas no Supabase DEV. Os secrets
necessários foram configurados; `supabase_url` e o segredo do worker estão no
Vault, e os jobs definidos em
`supabase/schedules/mercadolivre_orders_worker.sql` estão ativos:

- `mercadolivre-orders-worker`: a cada minuto.
- `mercadolivre-orders-missed-feeds`: a cada seis horas.

O worker foi chamado pelo Cron e as respostas recentes em `net._http_response`
confirmam HTTP 200, sem timeout, com `processed: 0`. A reconciliação manual
autenticada também retornou HTTP 200 para uma conexão, uma página e zero eventos
enfileirados. A API devolveu `messages: null` (tratado como página vazia); isso
confirma que a consulta funciona, mas não exercita o processamento de uma
notificação perdida. Os testes locais das Edge Functions passaram (12/12) e
`deno check` passou.

Ainda não há callback configurado no portal, evento `orders_v2` aceito para um
vendedor conectado nem pedido real processado pelo worker. O teste anterior do
callback com vendedor desconectado só confirmou o 404 esperado. Também não há
medição representativa do caminho de sucesso; portanto, não prometer prazo de
500 ms nem “tempo real”.

Próximo passo para habilitar `orders_v2` no piloto:

1. Obter um pedido de teste real e autorizado na conta conectada do DEV.
2. Depois de configurar o callback privado no portal, confirmar que o evento
   é aceito, enfileirado uma única vez e respondido com HTTP 200 em até 500 ms;
   verificar que o worker busca o pedido e o grava no tenant correto.
3. Acompanhar os resultados do Cron e repetir a reconciliação com um evento
   disponível antes de considerar validada a recuperação de falhas.

O segredo no caminho do callback é uma capability do endpoint, não uma
assinatura criptográfica fornecida pelo Mercado Livre. Mantenha a URL privada,
não a inclua em mensagens e não ative notificações antes de haver um pedido
autorizado para validar o fluxo completo.

O Streamlit Community Cloud e o Supabase DEV são ambientes gratuitos de piloto,
sem garantias de produção. Só usar dados reais após revisar o conteúdo e
necessidade dos dados importados, obter autorização do dono da loja, e manter
cópias de segurança independentes. Os limites, disponibilidade e recursos dos
planos gratuitos podem mudar.

O URL de recuperação padrão do Supabase DEV estava configurado como
`http://localhost:3000`, onde não havia um servidor. O utilitário local
`recuperar_senha_dev.py` atende esse endereço somente na máquina local,
valida o token de recuperação no navegador e atualiza a senha diretamente no
Supabase DEV. Esse fluxo foi tentado; depois a senha da conta B foi redefinida
por um utilitário local descartável usando o Admin API e validada por um login
imediato no Auth. O utilitário administrativo não é mantido no repositório.
Não compartilhe links de recuperação, senhas ou chaves administrativas.

Antes de usar dados reais, valide o caminho completo de leitura/importação na
instância hospedada, configure cópias de segurança e restauração, e confirme
HTTPS, domínio e retenção de dados. A importação de registros e a gravação do
histórico são operações separadas; em caso de falha entre elas, repita a
importação após verificar o histórico. Os registros são atualizados por suas
chaves de negócio, mas a importação não é uma transação única.

## Criar o projeto Supabase

Crie projetos Supabase distintos para desenvolvimento e produção. Não use o
projeto que já contém dados do piloto como ambiente de desenvolvimento.

O projeto DEV já criado chama-se `marketplace-intelligence-dev`. Para
reproduzir essa configuração em outro ambiente:

1. Crie um projeto Supabase novo, com nome que identifique claramente DEV.
2. Em **Authentication > Providers**, mantenha habilitado o provedor de
   e-mail/senha e desative o cadastro público de usuários.
3. Aplique primeiro
   `supabase/migrations/20261002150000_pilot_schema.sql` no SQL Editor do
   projeto DEV.
4. Em **Authentication > Users**, crie somente o primeiro usuário de teste.
   Depois aplique
   `supabase/migrations/20261002153000_pilot_owner.sql`. Essa migration exige
   exatamente um usuário Auth e o associa ao tenant inicial.
5. Crie o segundo usuário de teste. No SQL Editor DEV, crie um tenant separado
   e associe esse usuário a ele, substituindo o e-mail abaixo pelo e-mail de
   teste:

   ```sql
   do $$
   declare
       test_user_id uuid;
       test_tenant_id uuid;
   begin
       select id into strict test_user_id
       from auth.users
       where email = 'usuario-b-dev@example.invalid';

       insert into public.tenants (name, slug)
       values ('Tenant B DEV', 'tenant-b-dev')
       returning id into test_tenant_id;

       insert into public.tenant_members (tenant_id, user_id, role)
       values (test_tenant_id, test_user_id, 'owner');
   end
   $$;
   ```

6. Em **Project Settings > API**, obtenha o Project URL e a chave
   `anon`/publishable do DEV. Nunca use a chave `service_role` no aplicativo.

A migration `20261002153000_pilot_owner.sql` só deve ser executada quando o
projeto tiver exatamente um usuário Auth. Não a execute novamente ao criar os
usuários de teste nem aplique-a como parte da preparação de outro ambiente sem
verificar essa condição.

## Configurar o Streamlit

Para desenvolvimento local conectado ao Supabase DEV, configure em
`.streamlit/secrets.toml` (arquivo local, não versionado):

```toml
MI_ENV = "development"
SUPABASE_DEV_URL = "https://<dev-project-id>.supabase.co"
SUPABASE_DEV_ANON_KEY = "<chave-publishable-do-dev>"
```

Neste workspace, `MI_ENV` está definido como `development` e os valores
`SUPABASE_DEV_URL` e `SUPABASE_DEV_ANON_KEY` estão no arquivo local,
preservando as configurações legadas do piloto. Para iniciar o app conectado
ao DEV em uma janela PowerShell:

```powershell
$env:MI_ENV = "development"
streamlit run dashboard.py
```

Para concluir uma recuperação de senha DEV, abra outra janela PowerShell na
pasta do projeto e execute:

```powershell
python recuperar_senha_dev.py
```

O utilitário atende `http://localhost:3000` exclusivamente no loopback local.
Com ele em execução, solicite um novo link em **Authentication > Users >
conta B > Send password recovery**, abra o e-mail e defina a senha na página
local. Links de recuperação expiram em 60 minutos. Depois entre no dashboard
DEV em `http://127.0.0.1:8501`.

Na hospedagem de produção, configure secrets independentes:

```toml
MI_ENV = "production"
SUPABASE_PROD_URL = "https://<prod-project-id>.supabase.co"
SUPABASE_PROD_ANON_KEY = "<chave-publishable-da-producao>"
```

O app exige apenas as credenciais do ambiente selecionado: DEV não usa as
credenciais de PROD. Os nomes legados `SUPABASE_URL` e
`SUPABASE_ANON_KEY` continuam aceitos somente em `MI_ENV=production` para
manter a configuração atual do piloto até a migração planejada dos secrets.
Para demonstração apenas com CSV, configure `MI_ENV = "local"` sem credenciais
Supabase. Nunca use a chave `service_role` no app.

Não copie os secrets de DEV para a hospedagem de produção. Mantenha cada URL e
chave no respectivo ambiente e confirme o valor de `MI_ENV` antes de executar
importações.

## Antes de importar dados reais

- Confirmar o login da conta B na interface Streamlit em `http://127.0.0.1:8501`.
- Manter `recuperar_senha_dev.py` rodando apenas durante a recuperação da
  senha, e encerrá-lo com `Ctrl+C` depois.
- A validação dinâmica RLS foi concluída no DEV com as duas contas. Foram
  aprovadas 70 verificações de leitura, inserção, atualização e exclusão
  cruzadas nas cinco tabelas de negócio; os registros sentinela foram
  removidos. Repita essa validação se alterar policies, memberships ou o
  caminho de persistência.
- Validar leitura, importação, atualização por chave, histórico e isolamento
  entre usuários no serviço hospedado.
- Planejar cópias de segurança, restauração e retenção dos dados.
- Configurar domínio e HTTPS no serviço de hospedagem.
- Validar convite, login, expiração de sessão e revogação de conta.
