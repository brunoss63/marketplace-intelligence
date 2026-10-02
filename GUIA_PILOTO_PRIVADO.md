# Preparar o piloto privado

## Estado desta etapa

O painel exige autenticação individual pelo Supabase Auth quando
`MI_ENV=production`, resolve o tenant vinculado à conta e lê/grava pedidos,
produtos, estoque, publicidade e histórico de importação no Postgres usando a
sessão autenticada. As políticas RLS restringem as operações ao tenant do
usuário. O modo local precisa ser ativado explicitamente com `MI_ENV=local` e
continua usando os CSVs locais.

O projeto Supabase do piloto, o schema e o vínculo inicial do tenant já foram
criados e aplicados. A validação autenticada foi concluída com a importação de
30 registros válidos de Pedidos do Mercado Livre: 30 inseridos, 0 atualizados,
0 ignorados e 0 erros. O dashboard confirmou a leitura dos pedidos e o
histórico da importação. Os CSVs fictícios locais não foram enviados. Novas
importações em produção gravam os registros e o histórico no banco, sem criar
cópias CSV/JSON locais. A integração e a sincronização com APIs de marketplaces
ainda não estão implementadas.

As leituras do banco ficam em cache por até 30 segundos, isoladas por tenant e
usuário. Uma importação pelo painel invalida o cache imediatamente para que os
dados recém-importados apareçam sem aguardar o vencimento.

Antes de usar dados reais, valide o caminho completo de leitura/importação na
instância hospedada, configure cópias de segurança e restauração, e confirme
HTTPS, domínio e retenção de dados. A importação de registros e a gravação do
histórico são operações separadas; em caso de falha entre elas, repita a
importação após verificar o histórico. Os registros são atualizados por suas
chaves de negócio, mas a importação não é uma transação única.

## Criar o projeto Supabase

1. Crie um projeto Supabase na organização que controlará o piloto.
2. Em **Authentication > Providers**, mantenha habilitado o provedor de
   e-mail/senha e desative o cadastro público de usuários.
3. Em **Authentication > Users**, crie individualmente as contas autorizadas
   para você e para as pessoas do cliente.
4. Em **Project Settings > API**, copie o Project URL e a chave `anon`/
   publishable. Nunca use a chave `service_role` no aplicativo.

## Configurar o Streamlit

Configure estes valores na área de secrets/environment variables do serviço de
hospedagem:

```toml
MI_ENV = "production"
SUPABASE_URL = "https://<project-id>.supabase.co"
SUPABASE_ANON_KEY = "<publishable-or-anon-key>"
```

Para demonstração local, configure apenas `MI_ENV = "local"` em
`.streamlit/secrets.toml` (não versionar esse arquivo) ou na variável de
ambiente equivalente. O aplicativo falha fechado se `MI_ENV` não estiver
definido ou se as credenciais Supabase de produção estiverem ausentes.

## Antes de importar dados reais

- Validar leitura, importação, atualização por chave, histórico e isolamento
  entre usuários no serviço hospedado.
- Planejar cópias de segurança, restauração e retenção dos dados.
- Configurar domínio e HTTPS no serviço de hospedagem.
- Validar convite, login, expiração de sessão e revogação de conta.
