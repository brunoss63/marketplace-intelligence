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
cópias CSV/JSON locais. O fluxo OAuth de conexão do Mercado Livre já está
implementado em código, mas ainda depende da migração e dos secrets DEV. A
ingestão e a sincronização de dados pelas APIs ainda não estão implementadas.

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

O app também foi publicado para validação no Streamlit Community Cloud em
`https://marketplace-intelligence-dev.streamlit.app/`, ligado somente ao
projeto Supabase DEV. O endereço é público; os dados continuam protegidos pelo
login Supabase, cadastro público desativado e policies RLS. Os secrets da
hospedagem contêm apenas a configuração DEV. O deploy acompanha `main` do
GitHub, portanto commits enviados a essa branch podem atualizar a implantação.
Os logins hospedados das contas A e B foram confirmados. Não use esse deploy de
Community Cloud como ambiente de produção comercial.

## Preparação antes de convidar o primeiro cliente

O usuário do amigo e seu tenant **não devem ser criados ainda**. A apresentação
e o convite ficam para depois que as integrações de Mercado Livre e Shopee
estiverem implementadas e testadas em DEV, e que o acesso administrativo entre
tenants tenha sido criado com auditoria.

O responsável pelo produto solicitou acesso administrativo aos tenants. Hoje
as policies RLS só permitem a cada conta consultar o tenant ao qual está
vinculada; não há acesso global de administrador nem auditoria desse acesso.
Não use chaves `service_role` no navegador ou na aplicação Streamlit para
contornar esse isolamento. A futura implementação deve definir uma identidade
administrativa explícita, registrar consultas e alterações administrativas e
manter bloqueado o acesso cruzado para usuários clientes.

Mercado Livre e Shopee estão no escopo. A conta própria do Mercado Livre foi
vinculada ao portal de desenvolvedores e a aplicação `Marketplace Intelligence
DEV` foi criada como não certificada. Ela usa OAuth Authorization Code com
Refresh Token e PKCE, sem Client Credentials, e a URI inicial de retorno
`https://marketplace-intelligence-dev.streamlit.app/`. As permissões de
vendas/envios, publicações, publicidade e métricas foram configuradas somente
para leitura; a permissão de usuários aparece como leitura e escrita fixa no
portal. Nenhum tópico ou callback de notificações foi configurado. O logotipo
usado é provisório.

A implementação do fluxo OAuth DEV está em `integracao_mercadolivre.py`:
state de uso único, PKCE S256, tokens criptografados no Supabase por tenant e
renovação serializada do refresh token. A migração
`supabase/migrations/20261003170000_mercadolivre_oauth.sql` foi aplicada
somente no Supabase DEV. Também é necessário configurar, nos secrets locais e
hospedados do DEV, `MERCADOLIVRE_DEV_CLIENT_ID`,
`MERCADOLIVRE_DEV_CLIENT_SECRET`, `MERCADOLIVRE_DEV_REDIRECT_URI` e uma chave
Fernet persistente em `MERCADOLIVRE_DEV_TOKEN_ENCRYPTION_KEY`. O endereço de
retorno precisa coincidir exatamente com o cadastrado no portal.

A migração `20261003170000_mercadolivre_oauth.sql` foi aplicada em 3 de
outubro de 2026 pelo SQL Editor do projeto
`marketplace-intelligence-dev`; o Supabase confirmou sucesso. Ela não foi
executada no projeto de produção.

Falta configurar os secrets. Antes de reiniciar o app local:

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
3. Reinicie o app local e, na página **Marketplaces**, inicie a conexão.
   Autorize somente a sua conta própria e use **Validar conexão**. O código
   remove o `code` e o `state` da URL depois de autenticar no Supabase e validar
   o estado da transação. Não envie tokens ou screenshots que mostrem
   credenciais.

A aplicação ainda não foi autorizada por uma conta de loja nem testada contra
a API. Não inclua client secret nem tokens no repositório ou em mensagens.
Depois de aplicar a migração e configurar os secrets, autorize somente a conta
própria e valide operações de leitura no DEV. Configure notificações somente
depois de publicar um endpoint de callback próprio; até lá, avalie
sincronização periódica e limites da API. Depois, fazer o cadastro da
aplicação Shopee Open Platform. Não conectar a loja do amigo antes de obter
sua autorização.

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
