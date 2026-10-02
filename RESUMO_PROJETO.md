# Marketplace Intelligence — resumo do projeto

## Objetivo

Construir e publicar uma aplicação web de inteligência para vendedores de
marketplaces, conectada diretamente às APIs dos canais de venda para atualizar
automaticamente pedidos, produtos, estoque e publicidade.

“Tempo real” dependerá dos recursos e limites de cada marketplace: algumas
atualizações poderão chegar por notificações/webhooks; outras precisarão ser
sincronizadas periodicamente.

## Estado atual — 2 de outubro de 2026

- O painel está funcional como piloto privado em Streamlit e ainda é acessado
  localmente. A aplicação não foi publicada para acesso externo.
- O repositório Git local está na branch `main` e já tem um commit inicial;
  ainda não há repositório remoto no GitHub.
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
- O URL padrão de recuperação do Supabase DEV era `http://localhost:3000`.
  Foi criado e iniciado `recuperar_senha_dev.py`, um callback local limitado
  ao loopback. O primeiro fluxo de recuperação foi concluído, mas a senha
  resultante continuou sem autenticar. A conta B foi então atualizada e
  autenticada diretamente no projeto DEV por um utilitário local descartável.
  A divergência seguinte no app foi resolvida ao corrigir `MI_ENV` de
  `production` para `development` nos secrets locais.
- As alterações da separação DEV/PROD e do callback local estão sendo
  registradas no repositório Git local; ainda não há remoto no GitHub.
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

1. **Registrar as alterações locais** e configurar um remoto GitHub antes de
   automatizar os deploys. O remoto não é pré-requisito para desenvolver ou
   validar o DEV.
2. **Preparar e publicar o app web** em um serviço de hospedagem, mantendo o
   acesso privado e configurando segredos fora do código, HTTPS e domínio.
3. **Planejar a integração inicial com um marketplace**, começando pelo Mercado
   Livre, já usado no piloto. Registrar a aplicação, implementar OAuth e
   armazenar/renovar tokens com segurança.
4. **Automatizar a ingestão** conforme os recursos da API: webhooks quando
   disponíveis e sincronização periódica nos demais casos, com tratamento de
   limites, falhas, repetição e duplicidades.
5. **Validar a operação hospedada**: importações e atualizações, expiração e
   revogação de acesso, backups e restauração, monitoramento e desempenho.
6. **Ampliar para outros marketplaces** após validar a integração inicial com
   dados e uso reais.

## Critério de chegada ao objetivo

O objetivo estará alcançado quando o app estiver publicado e protegido, cada
conta estiver isolada por tenant e os marketplaces conectados atualizarem os
dados de forma automática e confiável dentro da frequência permitida por cada
API.

## Referências internas

- [Guia do piloto privado](./GUIA_PILOTO_PRIVADO.md)
- [Plano de publicidade](./PLANO_PUBLICIDADE.md)
