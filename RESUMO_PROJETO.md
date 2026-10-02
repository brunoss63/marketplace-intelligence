# Marketplace Intelligence — resumo do projeto

## Objetivo

Construir e publicar uma aplicação web de inteligência para vendedores de
marketplaces, conectada diretamente às APIs dos canais de venda para atualizar
automaticamente pedidos, produtos, estoque e publicidade.

“Tempo real” dependerá dos recursos e limites de cada marketplace: algumas
atualizações poderão chegar por notificações/webhooks; outras precisarão ser
sincronizadas periodicamente.

## Estado atual — 2 de outubro de 2026

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
- Foi escolhido preparar um piloto gratuito e limitado para um amigo usar com
  dados reais da loja, sem criar recursos pagos. O cadastro do amigo e a
  apresentação ficam adiados até as integrações de Mercado Livre e Shopee e a
  sincronização terem sido implementadas e testadas. Nenhuma conta dele foi
  criada nem recebeu dados. O proprietário do produto precisará de acesso
  administrativo entre tenants, restrito e auditável; hoje o RLS só autoriza
  acesso ao tenant vinculado à própria conta, então esse acesso administrativo
  ainda não existe.
- O usuário concordou em criar contas próprias de desenvolvedor/teste para
  Mercado Livre e Shopee. Nenhuma conta de teste ou aplicação de desenvolvedor
  foi criada ainda; não há credenciais para validar OAuth/API. “Tempo real”
  não está garantido: a frequência dependerá de notificações/webhooks e dos
  limites de cada plataforma, além de um mecanismo de sincronização ativo.
  O Community Cloud e os planos gratuitos não oferecem garantias de produção.
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
- A importação disponível é manual, por arquivos CSV. As APIs dos marketplaces,
  OAuth e sincronização automática ainda não foram implementados.
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
- `paginas/marketplaces.py` e `secoes/marketplace.py`: indicadores e gráficos
  comparativos por canal.
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
- `.streamlit/secrets.toml.example`: modelo de configuração local. O arquivo
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
- `dashboard_backup.py` e `dashboard_v1.py`: versões anteriores/protótipos;
  o ponto de entrada atual é `dashboard.py`.

Os gráficos diários da Visão Geral usam agora a série completa de datas do
período, incluindo dias sem vendas com valor zero. Isso mantém a leitura da
tendência correta ao filtrar por produto.

## Próximas etapas recomendadas

1. **Criar contas próprias de desenvolvedor/teste** nas plataformas Mercado
   Livre e Shopee e registrar as aplicações, sem conectar ainda a loja do amigo.
2. **Implementar e validar Mercado Livre em DEV**: OAuth, armazenamento e
   renovação segura de tokens, ingestão idempotente e notificações/webhooks ou
   sincronização periódica, conforme permitido pela API.
3. **Implementar e validar Shopee em DEV** com os mesmos requisitos de
   isolamento, renovação de credenciais, ingestão idempotente e atualização
   automática suportada pela plataforma.
4. **Criar administração entre tenants com auditoria**: autorização explícita,
   acesso mínimo necessário, trilha de consulta/alteração e teste de que
   usuários clientes continuam isolados. Esse privilégio não existe hoje.
5. **Executar uma validação de ponta a ponta**, incluindo falhas, limites de
   API, revogação de acesso, reconexão e consistência dos dados.
6. Só depois de concluir os itens anteriores, obter do amigo autorização e
   dados necessários, criar a conta/tenant exclusivo dele e convidá-lo para
   operar. O plano gratuito continua sendo piloto sem garantias de produção;
   frequência de atualização não deve ser apresentada como tempo real até ser
   medida e comprovada.

## Critério de chegada ao objetivo

O objetivo estará alcançado quando o app estiver publicado e protegido, cada
conta estiver isolada por tenant e os marketplaces conectados atualizarem os
dados de forma automática e confiável dentro da frequência permitida por cada
API.

## Referências internas

- [Guia do piloto privado](./GUIA_PILOTO_PRIVADO.md)
- [Plano de publicidade](./PLANO_PUBLICIDADE.md)
