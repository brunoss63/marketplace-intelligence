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
- Aplicações OAuth separadas para Mercado Livre DEV e PROD; a integração PROD
  foi preparada localmente, mas ainda não publicada nem ativada por secrets.

❌ **Não existe para PRODUÇÃO:**
- OAuth Mercado Livre em PROD validado (cadastro criado; credenciais, secrets e
  teste real ainda pendentes)
- OAuth Shopee em PROD
- Persistência de login entre reconexões do Streamlit (PROD usa sessão server-side temporária)
- Backup manual e restauração testados (o plano Free não inclui backup automático)
- Validação ponta a ponta com duas contas Auth reais; o teste transacional de RLS foi concluído com uma identidade sintética não associada

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
- Em 6 de outubro de 2026, o painel Database → Backups do PROD informou
  explicitamente que o plano Free não inclui backups do projeto; a seção de
  backups agendados está desabilitada. Não há backup automático disponível.
- A documentação oficial recomenda que projetos Free exportem regularmente
  usando `supabase db dump` e mantenham cópias fora do projeto. Nenhum dump foi
  gerado: o CLI Supabase, Docker, `pg_dump` e `psql` não foram encontrados no
  PATH deste computador e a senha de conexão do banco não foi usada.
- A restauração manual exige um projeto de destino. Como DEV e PROD ocupam os
  dois projetos ativos permitidos no Free, um teste de restauração exigiria
  pausar um deles (interrupção temporária) ou mudar de plano. Não faça isso sem
  escolher e aprovar o impacto primeiro.
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
- [x] Executar teste transacional de isolamento RLS com tenant de teste e
  identidade sintética não associada; todas as 14 verificações passaram e os
  fixtures foram confirmados ausentes após `ROLLBACK`.
- [ ] Fazer validação ponta a ponta com duas contas Auth reais antes de
  produção; a conta do cliente ainda não existe e não foi criada.

**Backups no Supabase Free (6 de outubro de 2026):**
- O painel PROD confirma que o Free não inclui backups automáticos.
- A orientação oficial para o Free é exportar regularmente com Supabase CLI
  (`supabase db dump`) e manter cópia fora do projeto. O procedimento oficial
  requer CLI, Docker Desktop e connection string/senha do banco.
- Nenhum arquivo de backup foi criado. O destino local fora do repositório foi
  escolhido, mas o Windows negou a consulta que confirmaria a criptografia do
  volume; por segurança, a geração foi adiada até existir um destino
  comprovadamente criptografado. Não armazenar dumps no repositório nem nos
  Secrets do Streamlit, e não enviar a senha pelo chat.
- Documentação: [Backups](https://supabase.com/docs/guides/platform/backups) e
  [Backup/Restore via CLI](https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore).

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

#### ✅ Tarefa 2.1: Registrar aplicação Mercado Livre em PROD
Em 6 de outubro de 2026, foi criada a aplicação separada `Marketplace
Intelligence PROD`, com o callback HTTPS fixo
`https://marketplace-intelligence-live.streamlit.app/` (raiz do app). Foram
selecionados Authorization Code, Refresh Token e PKCE; leitura de publicações
e vendas; sem VIS, permissões de escrita adicionais ou tópicos de notificação.
Foi usado um ícone temporário simples com “MI”. O portal mostra configuração
de segurança em 70% e classifica a aplicação como não certificada; a revisão
das opções restantes foi aberta após a verificação da conta por telefone. O
estado de segurança continua em 70%; nenhuma configuração adicional do app foi
alterada durante a inspeção.

Secrets esperados no deploy PROD: `MERCADOLIVRE_PROD_CLIENT_ID`,
`MERCADOLIVRE_PROD_CLIENT_SECRET`, `MERCADOLIVRE_PROD_REDIRECT_URI` e
`MERCADOLIVRE_PROD_TOKEN_ENCRYPTION_KEY`. Gere uma chave Fernet independente;
não reutilize a chave DEV nem grave qualquer segredo no repositório.

Após rotacionar o Client Secret no portal, guarde Client ID, Client Secret,
redirect URI e chave Fernet PROD somente nos Secrets do app
`marketplace-intelligence-live`; não os adicione à `.streamlit/secrets.toml`
ou ao repositório. Nunca compartilhe o Client Secret no chat.

#### ✅ Tarefa 2.2: Registrar aplicação Shopee em PROD
1. Acessar https://developer.shop.shopee.br (requere aprovação)
2. Criar NOVA aplicação
   - Environment: Production
   - Redirect URI: `https://SEU_DOMINIO_PROD.streamlit.app/callback-shopee`

#### ✅ Tarefa 2.3: Implementar configuração OAuth PROD
O código seleciona credenciais e chave Fernet `MERCADOLIVRE_DEV_*` ou
`MERCADOLIVRE_PROD_*` conforme `MI_ENV`, mantém o conjunto DEV isolado e exige
que o callback PROD seja exatamente
`https://marketplace-intelligence-live.streamlit.app/`. Testes offline
confirmam a seleção de secrets PROD e a rejeição de callback divergente.
O código foi testado e publicado em `main-prod` no commit `7db91a2`; o deploy
PROD voltou a apresentar a tela de login após a publicação. Ainda faltam os
secrets próprios no deploy e a validação do OAuth real. Antes de usar o Client
Secret exibido pelo portal durante a inspeção, faça a rotação dele no painel.

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

#### 🟡 Tarefa 4.3: Validar isolamento de dados
- [x] No SQL Editor PROD, executar uma transação com fixtures temporários para
  dois tenants; o owner viu o tenant A (1 linha) e não viu o tenant B (0).
- [x] RLS bloqueou leitura do tenant de teste em produtos, conexão de
  marketplace e transação OAuth; INSERT/UPDATE cruzados em produtos e INSERT
  cruzado na auditoria foram negados.
- [x] Uma identidade sintética sem membership não viu nenhum dos tenants nem
  os fixtures e não conseguiu inserir; as tabelas administrativas e a inbox
  de webhooks não concedem `SELECT` ao papel `authenticated`.
- [x] As 14 verificações retornaram `passed=true`; a transação terminou com
  `ROLLBACK`. Uma consulta posterior confirmou zero tenants, produtos,
  conexões, transações OAuth e eventos de auditoria de teste persistidos.
- [ ] Repetir o fluxo de leitura/importação no app com duas contas Auth reais
  quando a conta do cliente estiver disponível; nenhuma segunda conta foi
  criada para este teste.

As policies observadas em `orders`, `inventory`, `ad_performance` e
`import_batches` usam a mesma função `user_has_tenant_access(tenant_id)` das
tabelas centrais; ainda assim, não houve fixture de dados nessas quatro tabelas
durante a validação transacional.

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
- [x] Validar no deploy publicado (6 de outubro de 2026): login owner refeito
  após a atualização, painel autenticado carregado e cookie
  `mi_auth_session` ausente do navegador após a autenticação.

#### ✅ Tarefa 5.2: Verificar RLS do Supabase
No PROD, a consulta de policies confirmou as regras de isolamento por tenant
nas tabelas públicas. O teste controlado simulou `authenticated` e
`auth.uid()` dentro de uma transação, sem criar usuário/tenant permanente:
- O owner consultou apenas seus fixtures do tenant A; não leu o tenant B.
- INSERT cruzado foi rejeitado pela policy `WITH CHECK`; UPDATE cruzado afetou
  zero linhas pela policy `USING`.
- A auditoria rejeitou INSERT atribuído a um tenant do qual o usuário não é
  owner.
- A identidade sem vínculo não leu os fixtures de nenhum tenant e não inseriu.
- Os dados temporários foram revertidos e a consulta de verificação posterior
  encontrou zero fixtures.

O teste não substitui uma validação de ponta a ponta com duas contas Auth
distintas; essa conta ainda não foi criada.

#### ✅ Tarefa 5.3: Documentar processo de suporte
- [ ] Como resetar senha do cliente
- [ ] Como remover dados do cliente
- [ ] Política de retenção
- [ ] Contato de emergência

---

### **FASE 6: TESTE FINAL (Dia 5)**

#### ✅ Checklist de Validação

**Login & Sessão:**
- [x] Consegue fazer login com bruno.ribeirods99@gmail.com no deploy PROD.
- [ ] Consegue fazer login com cliente@example.com
- [ ] Logout funciona
- [ ] Validar logout e a reautenticação quando necessária após refresh/reconexão.
- Não manter login ao fechar/reabrir o navegador é comportamento intencional do
  modo server-side sem cookie persistente.

**Isolamento de dados:**
- [x] RLS está ativo nas 12 tabelas públicas e o teste transacional acima
  bloqueou acesso cruzado nos fixtures das tabelas exercitadas.
- [ ] Confirmar no app que Bruno vê apenas seus dados fictícios.
- [ ] Confirmar com uma segunda conta real que o cliente vê apenas os dados
  do próprio tenant e nenhum dado do Bruno.

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
   - O teste estrutural transacional RLS passou; ainda falta a validação no app
     com duas contas reais, backup/restauração e validação das integrações
     PROD. O login pode precisar ser repetido após refresh/reconexão do Streamlit.
   - O Supabase Free não fornece backup automático. Antes de dados reais,
     definir destino protegido para o dump manual e liberar espaço para um
     teste de restauração sem interromper PROD.

2. **OAuth Mercado Livre PROD cadastrado, porém ainda não habilitado**
   - A aplicação independente usa o callback HTTPS do deploy PROD; código e
     testes estão publicados em `main-prod`. A tela de login do deploy voltou
     a responder após a atualização, mas os quatro secrets ainda não foram
     configurados.
   - O portal indica segurança em 70% e a aplicação não está certificada.
     A conta foi verificada por telefone; as opções configuradas foram
     revisadas sem ampliar permissões ou habilitar tópicos não usados.
   - Por prudência, rotacione o Client Secret no portal antes de adicioná-lo
     aos Secrets do Streamlit PROD. Nunca o compartilhe no chat.
   - Não conectar nem sincronizar uma conta até configurar os quatro secrets
     no app e validar o OAuth real.

3. **Shopee em breve**
   - Status: Ainda não tem OAuth pronto
   - Solução: Adicionar quando estiver pronto

4. **Login PROD não persiste entre reconexões**
   - Decisão: manter tokens somente na sessão server-side do Streamlit para
     preservar o plano gratuito; um novo login pode ser exigido após refresh.

---

## 📞 PRÓXIMAS AÇÕES

1. Definir destino protegido e rotina do dump manual gratuito; preparar CLI e
   Docker e gerar um backup sem expor a senha. Planejar restauração somente
   após aprovar a pausa temporária de um projeto ativo ou outra alternativa.
2. Concluir verificação de segurança da aplicação Mercado Livre, publicar a
   integração PROD, configurar secrets direto no Streamlit e validar OAuth
   antes de sincronizar.
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

**Estado atual:** deploy PROD de validação criado e login owner confirmado;
teste transacional RLS concluído sem fixtures persistentes. O plano Free não
tem backup automático; o dump manual foi adiado até confirmar armazenamento
criptografado e a restauração ainda não foi testada. Resolva esses e os demais
bloqueadores antes de cadastrar o cliente.
