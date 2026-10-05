# Marketplace Intelligence — resumo do projeto

## Objetivo

Construir e publicar uma aplicação web de inteligência para vendedores de
marketplaces, conectada diretamente às APIs dos canais de venda para atualizar
automaticamente pedidos, produtos, estoque e publicidade.

“Tempo real” dependerá dos recursos e limites de cada marketplace: algumas
atualizações poderão chegar por notificações/webhooks; outras precisarão ser
sincronizadas periodicamente.

## Estratégia imediata

A primeira meta comercial é conquistar e atender bem **um primeiro cliente**,
com um piloto pequeno e acompanhado de perto. Não é necessário terminar agora
uma plataforma escalável nem implementar todas as integrações antes de conversar
com esse cliente. O escopo inicial deve se limitar ao problema e ao marketplace
que ele realmente usa; validar valor e recolher feedback antes de decidir o que
construir para o próximo cliente. Segurança básica, autorização para acessar os
dados e transparência sobre limitações continuam obrigatórias. Shopee,
automação completa, operação comercial ampla e escala ficam para depois, salvo
se forem indispensáveis para o primeiro cliente.

## Estado atual — 5 de outubro de 2026

- O painel está funcional como piloto em Streamlit. Além do acesso local, foi
  publicado para validação no Streamlit Community Cloud em
  `https://marketplace-intelligence-dev.streamlit.app/`, conectado somente
  ao Supabase DEV. O URL é público, mas o painel exige login Supabase, o
  cadastro público está desativado e o RLS limita dados por tenant. Os logins
  hospedados das contas A e B foram confirmados.
- O repositório Git está na branch `main`, com o remoto público
  `https://github.com/brunoss63/marketplace-intelligence`. O commit inicial e
  a configuração DEV/PROD já foram enviados ao GitHub; a branch local acompanha
  `origin/main`. O repositório foi tornado público a pedido do usuário para
  permitir a implantação no Community Cloud; qualquer pessoa pode ver e copiar
  o código e o histórico.
- O projeto Supabase `marketplace-intelligence-dev` foi criado separado do
  piloto, na região São Paulo. O schema e as políticas RLS foram aplicados,
  há uma conta de teste confirmada por tenant, e o cadastro público está
  desativado. A conta B atual está vinculada ao seu próprio tenant; uma conta
  provisória criada com o endereço de teste anterior permanece sem vínculo no
  DEV.
- O app aceita `MI_ENV=development` e as credenciais DEV estão no
  `.streamlit/secrets.toml` local, sem substituir as credenciais do piloto.
  Os logins das contas A e B foram confirmados no app local. A conta B também
  foi autenticada diretamente no Auth API após redefinir a senha. O login B
  inicialmente falhava porque o `MI_ENV` dos secrets locais ainda estava como
  `production`; o valor foi corrigido para `development` e o app reiniciado.
  O teste dinâmico de isolamento RLS entre A e B também foi concluído no DEV.
- O app de desenvolvimento foi iniciado em `127.0.0.1:8501`, limitado à
  máquina local. Um processo anterior que escutava em todas as interfaces foi
  encerrado. O projeto Supabase do piloto não foi alterado.
- A hospedagem usa somente as credenciais do projeto DEV nos secrets
  criptografados do Streamlit Cloud; nenhum secret de produção foi configurado.
  A implantação acompanha `main`, então novos commits nessa branch podem
  atualizar automaticamente o app hospedado.
- A prioridade do produto foi ajustada: conquistar e validar valor com um
  primeiro cliente em um piloto pequeno e assistido; usar o feedback dele para
  decidir a próxima etapa antes de escalar. Não exigir Shopee nem automação
  completa como pré-requisitos universais: acordar o escopo com o cliente e
  demonstrar apenas capacidades efetivamente testadas. Qualquer integração com
  a loja exige autorização explícita e acesso restrito ao tenant. Nenhum
  primeiro cliente adicional foi ainda cadastrado ou recebeu dados; a conta de
  teste e as conexões existentes continuam sendo DEV.
- O login da conta própria no Mercado Livre e o vínculo com o portal de
  desenvolvedores foram concluídos. A aplicação `Marketplace Intelligence DEV`
  foi criada como não certificada, para uso de negócios e faixa prevista de
  1 a 10 usuários. Foi configurado um logotipo provisório, OAuth Authorization
  Code com Refresh Token e PKCE, sem Client Credentials, e a URI de retorno
  inicial `https://marketplace-intelligence-dev.streamlit.app/`. As permissões
  de vendas/envios, publicações, publicidade e métricas foram limitadas a
  leitura; o portal mantém a permissão de usuários como leitura e escrita.
  Nenhum tópico ou callback de notificações foi configurado no portal. A
  [documentação atual de notificações](https://developers.mercadolivre.com.br/pt_br/produto-receba-notificacoes)
  foi consultada: `orders_v2` cobre criação e alterações de vendas confirmadas;
  o callback deve responder HTTP 200 em até 500 ms, e `missed_feeds` permite
  recuperar notificações perdidas por até dois dias. A documentação consultada
  não especifica um header de assinatura criptográfica para autenticar o
  remetente.
- O fluxo de conexão OAuth DEV foi implementado em `integracao_mercadolivre.py`:
  Authorization Code, state aleatório de uso único, PKCE S256, troca e
  renovação de tokens e armazenamento criptografado no Supabase por tenant.
  A migração `20261003170000_mercadolivre_oauth.sql` foi aplicada no SQL
  Editor do projeto `marketplace-intelligence-dev` em 3 de outubro de 2026; o
  Supabase confirmou sucesso. Ela cria as tabelas com RLS e um lock de
  renovação para evitar reutilização concorrente do refresh token. Os secrets
  locais e hospedados do DEV foram configurados sem versionar credenciais.
  Em 3 de outubro de 2026, a conexão OAuth foi concluída com sucesso: o app
  confirmou que as credenciais do Mercado Livre foram armazenadas
  criptografadas no tenant DEV. Em 5 de outubro, “Validar conexão” confirmou
  uma chamada autenticada à API e que o identificador retornado corresponde
  à conta armazenada.
- O diagnóstico publicado confirmou que o app Cloud lê Client ID e Client
  Secret de **Streamlit Secrets**, e que o Client ID corresponde à aplicação
  DEV. O código prioriza Streamlit Secrets sobre variáveis de ambiente para as
  credenciais `MERCADOLIVRE_DEV_*`; uma variável antiga do processo já não deve
  sobrepor os valores salvos em Secrets. As tentativas anteriores retornaram
  `invalid_client`, mas uma nova tentativa foi bem-sucedida depois. Não há
  necessidade atual de repetir o consentimento. Nunca incluir Client Secret,
  códigos OAuth ou tokens no repositório, logs, capturas ou mensagens.
- As alterações de diagnóstico e prioridade dos secrets foram publicadas em
  `main` até o commit `7f3ec31` (`Prefer Streamlit secrets for OAuth
  credentials`). Os 10 testes focados de OAuth passaram. A integração Shopee
  ainda não começou. A documentação oficial do Mercado Livre recomenda o tópico
  `orders_v2` para criação e alteração de vendas confirmadas; a notificação
  traz o caminho do recurso e os detalhes devem ser buscados com GET em
  `/orders/{order_id}`. O callback precisa confirmar o recebimento com HTTP 200
  em até 500 ms, então o processamento deve ser assíncrono e enfileirado.
  `missed_feeds` permite recuperar notificações perdidas por até dois dias.
  O tópico e o callback ainda não foram configurados no portal; as funções
  correspondentes já estão publicadas no Supabase DEV.
  “Tempo real” não garante latência zero: pedidos poderão seguir um fluxo
  orientado a eventos com reconciliação; outros dados e indisponibilidades
  precisarão de sincronização periódica. O Community Cloud e os planos gratuitos
  não oferecem garantias de produção.
- Foi preparada localmente a primeira parte da infraestrutura de webhooks:
  Edge Function `mercadolivre-orders-webhook` e migration para uma inbox
  durável, isolada por conexão/tenant, com deduplicação e leases para o futuro
  worker. A função verifica aplicação, tópico, formato do pedido e vendedor
  conectado antes de enfileirar. A migration
  `supabase/migrations/20261005210000_mercadolivre_orders_webhook_inbox.sql`
  foi aplicada ao DEV; verificações no SQL Editor confirmaram RLS habilitado,
  acesso à tabela e execução das RPCs negados a `anon`/`authenticated` e
  concedidos a `service_role`. Também foram preparados localmente o worker de
  pedidos e a migration `20261005220000_mercadolivre_webhook_worker_permissions.sql`,
  que corrige a deduplicação para múltiplos tenants e concede ao worker as
  permissões mínimas de consulta/atualização. Ela foi aplicada ao DEV. As
  verificações confirmaram a chave única `(tenant_id, deduplication_key)`,
  permissões de leitura/atualização da conexão e execução das RPCs de refresh,
  enqueue e claim concedidas a `service_role`. O RPC de enqueue aceitou a conta
  conectada dentro de uma transação revertida; a consulta confirmou zero linhas
  sintéticas persistidas. A reconciliação paginada de `missed_feeds` para
  `orders_v2` reutiliza a mesma inbox e chave de deduplicação. As Edge Functions
  `mercadolivre-orders-webhook` e `mercadolivre-orders-worker` foram publicadas
  no Supabase DEV; secrets foram configurados, com URL e segredo do worker
  guardados no Vault. Os jobs estão ativos: worker a cada minuto e reconciliação
  a cada seis horas. As respostas recentes em `net._http_response` confirmaram
  HTTP 200 sem timeout para as chamadas do worker (`processed: 0`). A
  reconciliação manual autenticada respondeu HTTP 200 com uma conexão, uma
  página e zero eventos aceitos; a API retornou `messages: null`, normalizado
  como página vazia. Isso comprova a chamada de reconciliação, não a recuperação
  nem o processamento de um pedido. O caso válido do callback para vendedor
  conectado ainda não foi exercitado; o teste existente com vendedor
  desconectado confirmou apenas o 404 esperado. Também não foi processado pedido
  real nem medida latência de sucesso, e `orders_v2` não foi configurado no
  portal. Os 12 testes Deno passaram e `deno check` passou nas funções e testes.
  O callback usa um segredo-capability no caminho, não uma assinatura do
  Mercado Livre; manter a URL confidencial. Aguardamos um pedido de teste real
  e autorizado para validar callback, inbox, worker, tenant e latência antes
  de ativar notificações.
- O URL padrão de recuperação do Supabase DEV era `http://localhost:3000`.
  Foi criado e iniciado `recuperar_senha_dev.py`, um callback local limitado
  ao loopback. O primeiro fluxo de recuperação foi concluído, mas a senha
  resultante continuou sem autenticar. A conta B foi então atualizada e
  autenticada diretamente no projeto DEV por um utilitário local descartável.
  A divergência seguinte no app foi resolvida ao corrigir `MI_ENV` de
  `production` para `development` nos secrets locais.
- O arquivo `.streamlit/secrets.toml` permanece ignorado pelo Git; somente o
  modelo `.streamlit/secrets.toml.example` está versionado.
- As telas incluem visão geral, vendas e pedidos, marketplaces, produtos e
  estoque, inteligência e importação.
- O Supabase está configurado para autenticação, vínculo usuário/tenant,
  persistência dos dados e histórico de importações. O modo local com CSV foi
  mantido.
- A importação por CSV continua disponível. Na tela Marketplaces, o Mercado
  Livre agora oferece sincronização manual idempotente de pedidos por período
  e de produtos/estoque das publicações ativas. O fluxo ainda não é automático;
  publicidade segue manual até confirmar a API Product Ads e o mapeamento das
  métricas. Custos de produto, taxas e frete não são obtidos por estas leituras;
  valores manuais existentes são preservados.
- Os 20 testes focados de OAuth e sincronização passam localmente; os testes de
  sincronização usam respostas simuladas. Em 5 de outubro, o usuário confirmou
  que o fluxo de sincronização de produtos/estoque pela interface DEV executou
  conforme esperado. Como a conta não tem produtos com estoque, ainda não foi
  possível comparar saldos positivos com a loja; a precisão de saldos não nulos
  segue sem validação. Pedidos também não foram validados com dados reais
  porque a conta conectada não tem vendas.
- As cargas de teste do Mercado Livre registram 30 pedidos, 8 produtos,
  8 itens de estoque e 15 registros de publicidade, sem erros de importação.
- A auditoria realizada não encontrou SKUs sem correspondência nem valores
  inválidos nos campos examinados.
- Leituras Supabase usam cache de até 30 segundos, invalidado após importações.
  Isso melhora a navegação, mas não fornece atualização em tempo real.
- Autenticação, filtro por tenant e políticas RLS estão implementados. O teste
  dinâmico real com as contas A e B passou em 70 verificações nas tabelas de
  produtos, pedidos, estoque, publicidade e histórico de importações: cada
  conta leu seus registros, não leu registros alheios, não conseguiu inserir,
  alterar ou excluir dados do outro tenant, e os registros sentinela foram
  removidos ao final.

## Estrutura do projeto

```text
marketplace_demo/
├── dashboard.py
├── autenticacao.py
├── armazenamento.py
├── integracao_mercadolivre.py
├── sincronizacao_mercadolivre.py
├── filtros.py
├── componentes.py
├── dados_periodo.py
├── importador.py
├── paginas/
├── secoes/
├── dados/
├── supabase/migrations/
└── .streamlit/
```

### Aplicação e módulos centrais

- `dashboard.py` é o ponto de entrada do Streamlit. Configura a página,
  aplica o estilo, exige autenticação, registra a navegação e exibe os filtros
  globais antes da página selecionada.
- `autenticacao.py` faz o login pelo Supabase Auth, restaura a sessão e associa
  a conta ao tenant autorizado.
- `armazenamento.py` centraliza a leitura e gravação dos dados. No modo local
  lê arquivos CSV; em produção acessa tabelas Supabase com isolamento por
  tenant, cache e histórico de importações.
- `integracao_mercadolivre.py` gerencia o início e callback OAuth, o
  armazenamento criptografado das credenciais DEV e a renovação serializada
  dos tokens do Mercado Livre.
- `filtros.py` renderiza e mantém o período, produto e marketplace escolhidos
  globalmente.
- `dados_periodo.py` calcula KPIs financeiros, desempenho de produtos,
  oportunidades e análises de estoque para os períodos selecionados.
- `importador.py` interpreta arquivos de origem, reconhece e normaliza colunas
  de pedidos, produtos, estoque e publicidade antes de encaminhar a importação
  ao armazenamento.
- `componentes.py` reúne elementos visuais e utilitários compartilhados, como
  cartões, cabeçalhos, tabelas, estilo e gráficos do dashboard.

### Páginas e seções

- `paginas/visao_geral.py`: indicadores executivos, tendências de vendas,
  gráficos diários e resumo da operação.
- `paginas/vendas_pedidos.py`: consulta, filtros, detalhes e exportação dos
  pedidos.
- `paginas/marketplaces.py` e `secoes/marketplace.py`: conexão OAuth DEV do
  Mercado Livre, indicadores e gráficos comparativos por canal.
- `paginas/produtos_estoque.py`, `secoes/produtos.py` e `secoes/estoque.py`:
  portfólio, desempenho de produtos, saldos e alertas de estoque.
- `paginas/inteligencia.py`: oportunidades e alertas derivados dos indicadores.
- `paginas/importar_dados.py`: fluxo de importação e consulta do histórico.
- `secoes/insights.py` e `secoes/recomendacoes.py`: blocos reutilizáveis de
  insights e recomendações.

### Dados e configuração

- `dados/`: CSVs de demonstração e arquivos importados. Os arquivos
  `pedidos.csv`, `produtos.csv`, `estoque.csv` e `publicidade.csv` são as bases
  locais correspondentes às quatro categorias do painel. `dados/importacoes/`
  guarda arquivos de origem e histórico local da demonstração.
- `supabase/migrations/20261002150000_pilot_schema.sql`: define tenants,
  membros, tabelas de negócio, histórico, índices e políticas RLS.
- `supabase/migrations/20261002153000_pilot_owner.sql`: associa a conta inicial
  ao tenant de piloto.
- `supabase/migrations/20261003170000_mercadolivre_oauth.sql`: cria o
  armazenamento isolado por tenant para conexões e transações OAuth, com RLS
  e lock de renovação de refresh tokens.
- `.streamlit/secrets.toml.example`: modelo de configuração local, incluindo
  os nomes dos secrets necessários para o Mercado Livre DEV. O arquivo
  `.streamlit/secrets.toml` contém segredos locais e não deve ser compartilhado
  ou versionado.
- `.gitignore`: exclui secrets, arquivos `.env`, caches Python e fontes/histórico
  de importações locais; os CSVs fictícios usados na demonstração permanecem
  disponíveis para versionamento.
- `requirements.txt`: dependências Python da aplicação.
- `GUIA_PILOTO_PRIVADO.md`: instruções para configurar e operar o piloto.
- `PLANO_PUBLICIDADE.md`: decisões pendentes para futura integração de dados
  de publicidade por API.
- `analise_*.py`, `calcular_indicadores.py`, `gerar_*.py` e
  `validar_dados.py`: scripts auxiliares de análise, geração e validação de
  dados usados no desenvolvimento e na demonstração.
- `dashboard.py`: ponto de entrada atual do app. As versões antigas
  `dashboard_backup.py` e `dashboard_v1.py` foram removidas da árvore de
  trabalho; permanecem recuperáveis pelo histórico Git.

Os gráficos diários da Visão Geral usam agora a série completa de datas do
período, incluindo dias sem vendas com valor zero. Isso mantém a leitura da
tendência correta ao filtrar por produto.

## Próximas etapas recomendadas

1. **Descobrir o problema do primeiro cliente**: confirmar qual decisão ou
   tarefa ele quer melhorar, qual marketplace usa e quais dados são necessários.
   Combinar um piloto limitado, acompanhado e com autorização explícita para
   acessar os dados. Não prometer integrações, atualização ou resultados ainda
   não validados.
2. **Fechar o menor escopo demonstrável**: priorizar o marketplace que esse
   cliente usa. Para Mercado Livre, a conexão OAuth e a leitura de produtos/
   estoque foram exercitadas em DEV, mas faltam validar pedidos reais e
   consistência/idempotência. Se os webhooks não estiverem validados, tratar
   atualização como manual ou na frequência realmente testada; não anunciar
   “tempo real”. Shopee e Product Ads só entram se forem necessários para
   comprovar valor ao primeiro cliente.
3. **Fazer onboarding assistido e medir uso**: criar um tenant exclusivo,
   configurar a conta com o próprio cliente, observar uma tarefa real,
   registrar falhas e feedback e combinar como desconectar/remover os dados ao
   encerrar o piloto. Não é necessário dar ao operador acesso irrestrito aos
   dados de outros tenants.
4. **Corrigir bloqueios encontrados no piloto**: validar fluxos de pedidos,
   permissões, renovação/revogação de OAuth e consistência dos dados que forem
   parte do escopo acordado. Callback, worker e schedules estão implantados no
   DEV, mas falta validar um callback aceito e um pedido real de ponta a ponta.
   Ativar `orders_v2` apenas se atualização por evento fizer parte da promessa;
   antes, medir o callback de sucesso, confirmar gravação no tenant correto e
   testar reconciliação com um evento disponível.
5. **Decidir a próxima aposta com evidências**: após o feedback, priorizar
   melhorias para esse cliente e só então avaliar Shopee, automação, produção
   mais robusta e aquisição de mais clientes. Antes de cobrar, alinhar preço,
   limites, suporte, privacidade e obrigações aplicáveis ao piloto.

## Critério de chegada ao objetivo

O primeiro objetivo estará alcançado quando um cliente autorizado usar o
produto para resolver uma necessidade concreta, os dados dele permanecerem
isolados, as limitações forem transparentes e o feedback orientar a decisão
seguinte. A prontidão para atender vários clientes e ampliar as integrações é
uma etapa posterior, guiada pelo que for aprendido nesse piloto.

## Referências internas

- [Guia do piloto privado](./GUIA_PILOTO_PRIVADO.md)
- [Plano de publicidade](./PLANO_PUBLICIDADE.md)
