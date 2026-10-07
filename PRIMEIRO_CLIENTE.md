# Do primeiro contato ao primeiro cliente usando a plataforma

Este roteiro descreve o onboarding ponta a ponta para um piloto acompanhado.
Ele diferencia o que pode ser feito com o ambiente atual de desenvolvimento
(DEV) do que ainda precisa ser preparado para uso comercial em produção.

## Situação atual — leia antes de convidar o cliente

- O endereço publicado
  `https://marketplace-intelligence-dev.streamlit.app/` usa o projeto Supabase
  **DEV**, não um projeto de produção.
- O cadastro público está desativado. Uma conta precisa ser criada ou
  convidada pelo responsável no Supabase Auth antes que o cliente possa entrar.
- O responsável deve vincular a conta convidada a um tenant exclusivo antes de
  o cliente aceitar o convite. O app não oferece solicitação pública de acesso.
- O OAuth do Mercado Livre está configurado apenas para `development` e para
  a aplicação/URI de retorno do DEV. A própria aplicação informa que a
  integração está disponível somente nesse ambiente até a configuração de uma
  aplicação de produção.
- O deploy DEV persiste os tokens de sessão em cookie acessível a JavaScript,
  não `HttpOnly`, e é adequado somente para um piloto confiável e acompanhado.
  O deploy PROD não grava tokens em cookie e os mantém apenas na sessão
  server-side ativa do Streamlit; uma nova autenticação pode ser necessária
  após refresh ou reconexão.
- A sincronização é manual. A sincronização de produtos e estoque foi
  exercitada no DEV; a sincronização de pedidos ainda precisa ser validada com
  pedidos reais. A importação manual é o caminho mais previsível para iniciar.
- A Shopee ainda está indicada como “Em breve”.

**Decisão antes do acesso:** para uma conversa ou demonstração, use dados
fictícios. Para um piloto controlado, só use o DEV com autorização explícita,
escopo limitado e ciência das limitações acima. Para uso regular com dados
reais, use o deploy PROD separado, valide novamente a sessão server-side e
conclua os demais itens de segurança e isolamento abaixo.

## Fase 1 — combinar o piloto

- [ ] Escolher com o cliente o problema que o piloto vai resolver e o
  marketplace inicial.
- [ ] Definir duração, responsáveis, frequência de acompanhamento e o que será
  considerado um resultado útil.
- [ ] Explicar quais dados serão processados, como serão obtidos, quem terá
  acesso e quando serão removidos.
- [ ] Registrar a autorização do cliente antes de receber arquivos ou conectar
  uma conta.
- [ ] Explicar que a Shopee está em desenvolvimento, que não há sincronização
  agendada e que a integração de pedidos do Mercado Livre ainda requer
  validação.
- [ ] Decidir se a etapa será apenas uma demonstração com dados fictícios, um
  piloto DEV controlado ou uma implantação de produção. Não misturar dados de
  demonstração de clientes diferentes.

## Fase 2 — preparar o acesso do cliente

### Se for demonstração

1. Use a conta de demonstração existente e dados fictícios.
2. Não peça senha, token, arquivo real ou autorização OAuth do cliente.
3. Mostre as limitações como estão: por exemplo, Shopee “Em breve”.

### Se for um piloto controlado no DEV

1. Confirme por escrito a autorização e o escopo do piloto.
2. No projeto Supabase **DEV**, crie ou convide uma conta Auth usando o e-mail
   individual informado pelo cliente. O cadastro público fica desativado.
3. Não use uma conta compartilhada nem a conta provisória de teste sem vínculo.
   Não envie senhas por e-mail ou mensagem aberta; use o fluxo seguro de convite
   ou credencial temporária permitido e configurado no Supabase. O app não
   possui cadastro público nem recuperação de senha própria.
4. Envie ao cliente o endereço
   `https://marketplace-intelligence-dev.streamlit.app/` e as instruções para
   concluir o acesso à conta Supabase.
5. Antes de o cliente aceitar, copie o User ID criado no Supabase Auth e use a
   seção “Preparar acesso por convite” do painel administrativo. Crie um tenant
   exclusivo e vincule a conta; use `member` por padrão e `owner` somente se o
   cliente precisar administrar o próprio tenant.
6. Confirme que o tenant e o vínculo foram criados. Depois, envie ao cliente o
   endereço do app e peça que conclua o convite e entre. Após aceitar, ele deve
   chegar diretamente ao tenant preparado.
7. Se o cliente aceitar antes do provisionamento, o app informa que o acesso
   está pendente e não mostra dados. Conclua o vínculo no painel e peça que
   atualize a página.
8. Com o cliente conectado, confira o isolamento do tenant antes de carregar
   qualquer dado. O acesso deve ficar limitado aos registros desse tenant pelas
   policies RLS.

O aprovador precisa estar previamente autorizado em `pilot_administrators` e
estar autenticado em um tenant para usar o fluxo administrativo. Ser owner de
um tenant, por si só, não concede permissão global de aprovação. A primeira
autorização administrativa é feita separadamente pelo responsável do projeto
Supabase.

## Fase 3 — conectar o Mercado Livre, se fizer parte do piloto

1. Faça esta etapa somente depois de o cliente ter login e tenant aprovados.
2. O próprio cliente deve abrir **Marketplaces** e iniciar a conexão. Ele
   autentica no Mercado Livre e autoriza a aplicação; nunca solicite a senha
   do Mercado Livre.
3. Para o piloto no DEV, use somente o app e o endereço DEV já cadastrados. O
   callback OAuth verifica usuário e tenant e grava as credenciais criptografadas
   por tenant.
4. Confirme o estado “Conectado” e execute apenas a sincronização manual que
   estiver dentro do escopo.
5. Valide os produtos/estoque sincronizados. Não dependa da sincronização de
   pedidos até fazer um teste acompanhado com pedidos reais e comparar os
   resultados com a fonte.
6. Caso a autorização falhe ou seja revogada, pare a sincronização, mostre a
   mensagem da interface e peça ao cliente para autorizar novamente. Não
   compartilhe tokens nem informações técnicas.

**Bloqueio para produção:** o código seleciona secrets separados para
`development` e `production`, e valida em PROD o callback fixo
`https://marketplace-intelligence-live.streamlit.app/`. Isso não habilita a
conexão por si só: ainda é preciso cadastrar uma aplicação separada no Mercado
Livre, configurar os quatro secrets `MERCADOLIVRE_PROD_*` no deploy PROD (com
chave Fernet própria), publicar a alteração e validar o fluxo OAuth real antes
de conectar ou sincronizar uma conta.

## Fase 4 — inserir dados e orientar o cliente

Se a sincronização não estiver validada ou não cobrir o dado necessário,
comece por uma importação manual autorizada:

1. Combine quais relatórios/arquivos serão usados, período, colunas e
   marketplace.
2. Oriente o cliente a exportar os dados pela conta dele e transferi-los por
   um canal acordado e protegido.
3. Confira se os arquivos estão no formato aceito pela tela **Importar dados**.
   Faça primeiro uma importação pequena de validação, não a carga completa.
4. Revise o resumo da importação: registros inseridos/atualizados, ignorados e
   erros. Compare uma amostra com o relatório original.
5. Confirme os filtros de período, marketplace, produto e os indicadores
   resultantes. Uma importação invalida o cache para os dados aparecerem
   atualizados.
6. Depois da validação, importe o conjunto acordado. Não prometa atualização
   automática: não há sincronização agendada.
7. Demonstre os fluxos que o cliente usará:
   - **Visão Geral:** indicadores e filtros de período;
   - **Vendas & Pedidos:** localizar pedido e abrir detalhes;
   - **Produtos & Estoque:** abas, portfólio, busca por SKU e detalhes do
     produto;
   - **Marketplaces:** estado da conexão e comparação disponível.
8. Combine como o cliente reportará divergências, quem fará novas importações e
   quando será a revisão do piloto.

## Fase 5 — checklist de liberação do usuário

- [ ] Cliente consegue entrar e atualizar a página sem perder a sessão.
- [ ] O logout encerra a sessão e o cliente sabe como pedir suporte se perder
  acesso.
- [ ] Nome e tenant exibidos correspondem ao cliente correto.
- [ ] Teste de isolamento confirmou que a conta não lê dados de outro tenant.
- [ ] Um arquivo pequeno foi importado e reconciliado com a fonte.
- [ ] Cliente consegue navegar pelos indicadores, pedidos e detalhes de
  produto relevantes ao piloto.
- [ ] Cliente sabe que precisa iniciar manualmente as sincronizações e/ou
  importações incluídas no escopo.
- [ ] Limitações, suporte, retenção e data de encerramento/revisão foram
  alinhados.
- [ ] Nenhuma chave secreta, senha do Mercado Livre ou token foi compartilhado
  ou adicionado ao repositório.

## Antes de transformar o piloto em produção

Não use o deploy DEV como ambiente comercial. Prepare e valide separadamente:

- [ ] Projeto Supabase PROD com migrations/schema, RLS, backups e política de
  retenção revisados.
- [x] Deploy PROD de validação em
  `https://marketplace-intelligence-live.streamlit.app/`, branch `main-prod`,
  `MI_ENV=production` e apenas credenciais `SUPABASE_PROD_*` nos secrets;
  nunca incluir `service_role` no app.
- [x] No deploy PROD, não persistir tokens em cookie JavaScript; mantê-los
  somente na `st.session_state` server-side durante a sessão ativa.
- [ ] Validar o comportamento de logout, expiração e novo login após refresh ou
  reconexão do Streamlit.
- [ ] Registrar a aplicação OAuth de produção do Mercado Livre com o callback
  HTTPS confirmado; adicionar os secrets PROD apenas no deploy e validar o
  fluxo real antes de conectar a conta.
- [ ] Contas e tenants de clientes criados sem reutilizar dados do DEV.
- [ ] Testes de isolamento entre tenants, login, refresh da sessão, logout,
  revogação, importação, OAuth, sincronização e restauração de backup.
- [ ] Processo de suporte, incidente, exclusão/retention de dados e janela de
  manutenção definidos.
- [ ] Deploy validado em ambiente de homologação antes de apontar o cliente.

O deploy DEV atual acompanha a branch `main`; qualquer push para ela pode
atualizar a demonstração publicada. Para produção, use configuração e
credenciais separadas e não copie os secrets DEV. O deploy PROD acima foi
testado somente com a conta owner e está em uma branch independente, que não
recebe atualizações automáticas de `main`. Não convide o cliente nem processe
dados reais até concluir os demais itens desta lista, especialmente o fluxo de
convite, OAuth de produção, backups e teste de isolamento entre tenants. A
sessão PROD pode não sobreviver a reconexões; implemente backend com cookie
`HttpOnly` somente se a operação exigir login persistente.
