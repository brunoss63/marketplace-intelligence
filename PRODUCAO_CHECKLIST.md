# ✅ CHECKLIST: LEVAR PARA PRODUÇÃO COM CUSTO ZERO

- **Cliente:** 1 único cliente + sua conta de demonstração
  (bruno.ribeirods99@gmail.com)
- **Custo:** R$0 (Streamlit Community Cloud + Supabase Free)
**Prazo estimado:** 3-5 dias de trabalho

---

## 🔍 STATUS ATUAL

✅ **Já existe:**
- Repositório público no GitHub
- Projetos Supabase `marketplace-intelligence-dev`, `Marketplace Intelligence - Piloto` e `Marketplace Intelligence - PROD`
- App DEV e deploy PROD de validação publicados separadamente no Streamlit Community Cloud
- Schema, RLS, e multi-tenant implementados
- OAuth Mercado Livre (DEV)

❌ **Não existe para PRODUÇÃO:**
- OAuth Mercado Livre em PROD (registrado apenas para DEV)
- OAuth Shopee em PROD
- Persistência de login entre reconexões do Streamlit (PROD usa sessão server-side temporária)
- Backup e restauração testados

---

## 📌 PASSO-A-PASSO

### **FASE 1: PREPARAÇÃO (Dia 1-2)**

#### ✅ Tarefa 1.1: Diagnosticar código de ambiente
- [x] Verificar como o código usa `MI_ENV`
- [x] Confirmar leitura de `MI_ENV` por variável de ambiente ou Streamlit Secrets
- [x] Validar a seleção de credenciais DEV/PROD em teste isolado, sem conectar aos projetos Supabase

**Resultado do diagnóstico (6 de outubro de 2026):**
- `autenticacao.py` e `armazenamento.py` aceitam `local`, `development` e
  `production`; no modo hospedado, `MI_ENV` pode ser fornecido em Streamlit
  Secrets. Uma variável de ambiente do processo tem precedência, salvo quando
  a leitura pede explicitamente prioridade para Secrets.
- `development` seleciona `SUPABASE_DEV_URL` e `SUPABASE_DEV_ANON_KEY`.
- `production` seleciona `SUPABASE_PROD_URL` e `SUPABASE_PROD_ANON_KEY`, com
  fallback para `SUPABASE_URL` e `SUPABASE_ANON_KEY`.
- A configuração local observada está em `development`. Isso não confirma
  quais Secrets estão atualmente definidos no Streamlit Community Cloud.
- Mercado Livre e Shopee ainda bloqueiam OAuth fora de `development`; mudar
  `MI_ENV` sozinho não libera essas integrações.
- Um teste isolado com configurações simuladas confirmou que `production`
  escolhe `SUPABASE_PROD_*` e `development` escolhe `SUPABASE_DEV_*`. Não
  executei o app nem conectei aos projetos Supabase.
- Antes de ativar PROD, confirme que as credenciais selecionadas apontam ao
  projeto correto e que os Secrets do deploy estão configurados; isso não pode
  ser confirmado pela configuração local.

#### ✅ Tarefa 1.2: Preparar secrets PROD separados
- [x] Gerar chaves de criptografia PROD independentes para Mercado Livre e Shopee
- [x] Criar e confirmar o projeto Supabase PROD e cadastrar seu URL local como `SUPABASE_PROD_URL`
- [x] Obter a chave anon/publicável do projeto PROD e cadastrá-la como `SUPABASE_PROD_ANON_KEY` sem compartilhá-la no chat ou repositório
- [x] Confirmar que o `secrets.toml` local não contém `service_role`; essa chave nunca deve ser adicionada aos Secrets do app

**Preparação local (6 de outubro de 2026):**
- As duas chaves Fernet foram geradas, validadas e gravadas somente em
  `.streamlit/secrets.toml`, que está ignorado pelo Git. Os valores não foram
  exibidos nem adicionados a este checklist.
- O projeto `Marketplace Intelligence - PROD`, criado no plano Free em São
  Paulo, está saudável e tem Reference ID `awymyrqzdbssgaxkdtmq`.
- `SUPABASE_PROD_URL` foi gravado no `secrets.toml` local e corresponde ao
  Reference ID confirmado. `SUPABASE_PROD_ANON_KEY` foi configurada; formato
  `sb_publishable_` confirmado sem expor o valor.
- As credenciais genéricas `SUPABASE_URL` / `SUPABASE_ANON_KEY` permanecem sem
  alteração; não foram reaproveitadas para PROD.
- O `MI_ENV` local continua como `development`; o app não foi conectado ao
  Supabase PROD.
- Foi enviado convite Auth para a conta owner de demonstração
  `bruno.ribeirods99@gmail.com`; o usuário clicou no e-mail e a consulta ao
  Auth confirmou `email_confirmed_at` e `last_sign_in_at`. O convite confirmou
  a conta, mas o redirecionamento final abriu `localhost`.
- Na preparação inicial, a configuração Auth **URL Configuration** do projeto
  PROD estava com Site URL `http://localhost:3000` e sem Redirect URLs. Após
  criar o deploy de validação, ambos foram atualizados para
  `https://marketplace-intelligence-live.streamlit.app`.
- Foi criado `recuperar_senha_prod.py`, um utilitário temporário local que
  aceita somente o URL e a chave `sb_publishable_` do Reference ID PROD
  confirmado, vincula o servidor a `127.0.0.1` e altera a senha apenas após um
  link de recuperação válido. Nunca usa `service_role`.
- O owner pode solicitar **Send password recovery** no Supabase Auth Users
  enquanto o utilitário estiver executando; o link deve abrir
  `http://localhost:3000`. Aceite apenas o formulário servido localmente e
  encerre o servidor depois de definir a senha.
- Em 6 de outubro de 2026, o owner confirmou que redefiniu a senha pelo link
  de recuperação. O servidor local foi encerrado após a confirmação.
- No painel, a organização Free atingiu o limite de dois projetos ativos. O
  Piloto mostrou tráfego recente, itens de Storage e conexões ativas, e nenhum
  backup registrado. Foi pausado somente após autorização explícita.
- O projeto `Marketplace Intelligence - Piloto` foi pausado após autorização
  explícita. O painel informa que ficará indisponível enquanto pausado e que
  pode ser retomado por até um ano; não foi apagado.
- Retome o Piloto quando precisar dele e planeje uma cópia/migração dos dados
  antes de qualquer ação destrutiva.
- O projeto PROD não possui backups configurados; configure e teste a
  restauração antes de armazenar dados reais.
- No formulário de criação, `Automatically expose new tables` estava marcado
  por padrão; as migrations revogaram os acessos `anon` e as consultas
  confirmaram zero tabelas públicas acessíveis a `anon`.
- A organização segue no plano Free, com dois projetos ativos (DEV e PROD).

**Schema e RLS no PROD (6 de outubro de 2026):**
- [x] Aplicar as migrations de schema, auditoria, conexões OAuth Mercado Livre,
  suporte Shopee, onboarding, leases de refresh e fila/permissões de webhooks.
- [x] Confirmar no SQL Editor 12 tabelas públicas, RLS habilitado nas 12, zero
  tabelas com qualquer privilégio de leitura/escrita para `anon`, e 10 tabelas
  com `SELECT` para `authenticated`.
- [x] Criar o primeiro usuário Auth por convite e executar o seed
  `20261002153000_pilot_owner.sql`, que criou o tenant de demonstração e o
  vínculo `owner`.
- [x] Registrar o owner em `pilot_administrators` para habilitar aprovação de
  onboarding.
- [x] Validar no SQL Editor: 1 usuário Auth, 1 tenant, 1 vínculo owner, 1
  administrador, 12 tabelas com RLS e zero tabelas com qualquer privilégio
  para `anon`.
- [x] Definir a senha da conta owner pelo utilitário local de recuperação PROD.
- [x] Criar o deploy PROD separado e testar o login owner nesse deploy.
- [ ] Fazer testes de isolamento com duas contas e tenants antes de produção.

**Deploy PROD de validação (6 de outubro de 2026):**
- [x] Criar a branch remota `main-prod` a partir do mesmo commit validado em
  `main` (`6a75c9ec7ce545029c677fc2cb3269255bf703f3`); nenhum secret ou arquivo
  local não rastreado foi enviado ao GitHub.
- [x] Criar o app Streamlit
  `https://marketplace-intelligence-live.streamlit.app/`, usando
  `main-prod`, `dashboard.py` e Python 3.11.
- [x] Configurar nos Secrets desse app somente `MI_ENV = "production"`,
  `SUPABASE_PROD_URL` e `SUPABASE_PROD_ANON_KEY`. Os valores não são registrados
  neste arquivo; o app DEV e os secrets locais permaneceram inalterados.
- [x] Configurar no Auth PROD o Site URL e a Redirect URL para o domínio do
  deploy, corrigindo o destino que antes apontava para `localhost`.
- [x] Entrar no deploy com a conta owner e abrir o painel autenticado do tenant
  de demonstração.
- O app PROD acompanha `main-prod`; alterações em `main` não são copiadas
  automaticamente. Promova para essa branch apenas mudanças revisadas.
- Este deploy serve para validação do owner. Não convide o cliente nem use
  dados reais até resolver os bloqueadores de segurança e concluir os testes
  de isolamento indicados abaixo.

As migrations foram executadas pelo SQL Editor do painel, não por `supabase db
push`. Antes de usar o CLI ou aplicar novas migrations, reconcilie o histórico
de migrations do projeto para evitar reaplicações/confusão de estado.

**Arquivo esperado:**
```toml
MI_ENV = "production"
SUPABASE_PROD_URL = "https://awymyrqzdbssgaxkdtmq.supabase.co"
SUPABASE_PROD_ANON_KEY = "<chave anon/publicável do projeto PROD>"
```

Os três campos acima já estão nos Secrets do deploy PROD. Não cole os valores
de chaves neste documento nem no repositório. Chaves de OAuth/criptografia dos
marketplaces devem ser adicionadas somente quando o código de produção
consumir os nomes correspondentes e as integrações forem liberadas.

#### ✅ Tarefa 1.3: Validar o deploy PROD de forma isolada
- [x] Não apontar o app DEV/local para o banco PROD nem sobrescrever as
  credenciais genéricas atuais.
- [x] Criar um deploy/configuração Streamlit PROD separado, com
  `MI_ENV=production` e somente `SUPABASE_PROD_*` nos secrets desse deploy.
- [x] Fazer a validação de login e tenant nesse deploy isolado, após schema,
  seed do owner e testes RLS.

---

### **FASE 2: OAUTH PRODUÇÃO (Dia 2-3)**

#### ⏸️ Tarefa 2.1: Registrar aplicação Mercado Livre em PROD
Faça esta etapa somente depois de implementar o suporte OAuth PROD e confirmar
no código o callback HTTPS exato. Crie uma aplicação separada da DEV em
https://developers.mercadolibre.com.br/pt_BR/admin/applications e configure
como callback o domínio
`https://marketplace-intelligence-live.streamlit.app/` com a rota exata que a
integração implementar.

Depois da alteração e dos testes, guarde client ID, client secret, redirect URI
e chave Fernet PROD em Secrets do app `marketplace-intelligence-live`; não os
adicione a `.streamlit/secrets.toml` versionado ou ao repositório.

#### ✅ Tarefa 2.2: Registrar aplicação Shopee em PROD
1. Acessar https://developer.shop.shopee.br (requere aprovação)
2. Criar NOVA aplicação
   - Environment: Production
   - Redirect URI: `https://SEU_DOMINIO_PROD.streamlit.app/callback-shopee`

#### ⏸️ Tarefa 2.3: Implementar configuração OAuth PROD
Atualizar `integracao_mercadolivre.py` para selecionar credenciais e chave de
criptografia separadas por `MI_ENV`, preservar o fluxo DEV e acrescentar testes
que confirmem a escolha dos Secrets PROD e o callback HTTPS. O código atual
recusa explicitamente OAuth fora de `development`; não configure credenciais
PROD até essa alteração estar pronta e validada.

---

### **FASE 3: DEPLOY STREAMLIT CLOUD (Dia 3)**

#### ✅ Tarefa 3.1: Desacoplar DEV de PROD no GitHub
**Concluída:** branch remota `main-prod` criada no mesmo commit de `main`.
Os secrets são configurados separadamente por app no Streamlit Cloud; não
grave credenciais de produção em `.streamlit/secrets.toml` versionado.

#### ✅ Tarefa 3.2: Criar deployment PROD no Streamlit Cloud
**Concluída:** `https://marketplace-intelligence-live.streamlit.app/`
(`main-prod`, `dashboard.py`, Python 3.11). O Streamlit não permite usar
`prod` no subdomínio personalizado.

#### ✅ Tarefa 3.3: Adicionar secrets PROD no Streamlit Cloud
**Concluída** em Settings → Secrets. A configuração é:
```toml
MI_ENV = "production"
SUPABASE_PROD_URL = "https://awymyrqzdbssgaxkdtmq.supabase.co"
SUPABASE_PROD_ANON_KEY = "<chave pública sb_publishable_ do projeto PROD>"
```
Não definir `SUPABASE_URL`/`SUPABASE_ANON_KEY` genéricos neste app. Secrets de
OAuth ficam pendentes até a implementação e aprovação das integrações PROD.

---

### **FASE 4: DADOS DO CLIENTE (Dia 4)**

#### ✅ Tarefa 4.1: Preparar dados de demonstração
- [ ] Gerar dados fictícios com `gerar_dados.py`
- [ ] Importar via painel **Importar Dados**
- [ ] Confirmar que aparecem apenas para seu tenant (bruno.ribeirods99@gmail.com)

#### ⏸️ Tarefa 4.2: Criar conta e tenant do cliente
Não envie convite ainda. Embora o login por senha do owner já esteja validado,
o app não tem telas próprias de definir/recuperar senha e o callback do convite
do cliente ainda não foi testado no domínio PROD. Antes de convidar, implemente
e valide esse fluxo de forma segura, resolva os bloqueadores de sessão e
isolamento e obtenha o e-mail do cliente.

Depois de liberada a produção:
1. Convide a conta individual em Supabase PROD → Auth → Users.
2. Teste o link de convite e a definição inicial da senha no próprio domínio
   PROD, sem compartilhar credenciais por e-mail ou chat.
3. Confirme o tenant exclusivo e aprove o onboarding com papel `member`.
4. Valide o acesso da conta do cliente antes de importar dados autorizados.

#### ✅ Tarefa 4.3: Validar isolamento de dados
```python
# Seu tenant (bruno.ribeirods99@gmail.com):
# - Acessa dados_bruno_prod.xlsx (fictícios)

# Tenant do cliente (cliente@example.com):
# - NÃO vê seus dados
# - Pode importar e usar seus próprios dados
```

---

### **FASE 5: SEGURANÇA MÍNIMA (Dia 5)**

#### ✅ Tarefa 5.1: Remover tokens de cookies no PROD
**Concluída para o escopo gratuito escolhido:** no ambiente `production`, os
tokens Supabase ficam apenas em `st.session_state` server-side. O app não os
grava nem restaura de cookies e remove um cookie de autenticação legado na
primeira execução da sessão. O DEV mantém seu comportamento de cookie para
testes.

Como a sessão depende da conexão do Streamlit, uma atualização/reconexão pode
exigir novo login. Isso evita expor tokens Supabase em JavaScript sem contratar
um gateway/backend; não oferece persistência por cookie `HttpOnly`. Se login
persistente se tornar requisito, será necessário desenhar e hospedar uma camada
de autenticação server-side separada.

#### ✅ Tarefa 5.2: Verificar RLS do Supabase
```sql
-- Conectar ao Supabase PROD SQL Editor
-- Verificar policies:
SELECT * FROM pg_policies WHERE tablename LIKE 'clients_tenants_roles%';

-- Exemplo de política correta:
CREATE POLICY "isolate_by_tenant"
ON clients_tenants_roles
FOR SELECT
USING (tenant_id = (
  SELECT tenant_id FROM clients_tenants_roles
  WHERE user_id = auth.uid()
  LIMIT 1
));
```

#### ✅ Tarefa 5.3: Documentar processo de suporte
- [ ] Como resetar senha do cliente
- [ ] Como remover dados do cliente
- [ ] Política de retenção
- [ ] Contato de emergência

---

### **FASE 6: TESTE FINAL (Dia 5)**

#### ✅ Checklist de Validação

**Login & Sessão:**
- [ ] Consegue fazer login com bruno.ribeirods99@gmail.com
- [ ] Consegue fazer login com cliente@example.com
- [ ] Logout funciona
- [ ] Refresh da página não perde a sessão
- [ ] Fechar e reabrir navegador mantém a sessão

**Isolamento de dados:**
- [ ] Bruno vê apenas seus dados fictícios
- [ ] Cliente vê apenas seus dados
- [ ] Não há vazamento de dados entre tenants
- [ ] RLS está ativo (testar via SQL)

**Mercado Livre OAuth:**
- [ ] Bruno consegue conectar MercadoLivre (com app PROD)
- [ ] Cliente consegue conectar MercadoLivre (com app PROD)
- [ ] Tokens são armazenados criptografados por tenant

**Shopee OAuth:**
- [ ] Bruno consegue conectar Shopee
- [ ] Cliente consegue conectar Shopee
- [ ] Status mostra "Conectado"

**Funcionalidades:**
- [ ] Importar dados funciona
- [ ] Sincronização manual funciona
- [ ] Relatórios carregam sem erro
- [ ] Indicadores calculam corretamente

---

## 🚨 BLOQUEADORES CONHECIDOS

1. **Deploy PROD validado somente com a conta owner**
   - O app usa a branch `main-prod` e secrets separados de DEV; login owner e
     acesso ao painel autenticado foram confirmados.
   - Ainda não convide o cliente: faltam teste de isolamento entre dois
     tenants, backup/restauração e validação das integrações PROD. O login pode
     precisar ser repetido após refresh/reconexão do Streamlit.

2. **OAuth Mercado Livre recusa PROD**
   - Solução: Registrar aplicação nova e implementar/testar a configuração de
     produção; o domínio de callback deverá usar
     `marketplace-intelligence-live.streamlit.app`.

3. **Shopee em breve**
   - Status: Ainda não tem OAuth pronto
   - Solução: Adicionar quando estiver pronto

4. **Login PROD não persiste entre reconexões**
   - Decisão: manter tokens somente na sessão server-side do Streamlit para
     preservar o plano gratuito; um novo login pode ser exigido após refresh.

---

## 📞 PRÓXIMAS AÇÕES

1. Configurar e testar backup/restauração do Supabase PROD.
2. Liberar Mercado Livre OAuth em PROD e testar isolamento com dois tenants.
3. Validar convite, logout e novo login após refresh/reconexão.
4. Só então cadastrar o cliente quando o e-mail dele estiver disponível.

---

## CONFIGURAÇÃO E PENDÊNCIAS DE CÓDIGO

- Deploy Streamlit separado e secrets PROD: configurados no painel do
  Community Cloud; não gravar os valores em arquivos versionados.
- App DEV e `MI_ENV` local continuam isolados do banco PROD.
- Login owner no domínio PROD validado.
- Ainda é necessário implementar o callback seguro para convite/definição de
  senha antes de cadastrar o cliente.
- A persistência de login por cookie `HttpOnly` exigiria uma camada de
  autenticação externa; o plano atual usa somente a sessão temporária do
  Streamlit para manter custo zero.

---

**Estado atual:** deploy PROD de validação criado e login owner confirmado.
O próximo marco é resolver os bloqueadores de segurança acima, não cadastrar o
cliente ainda.
