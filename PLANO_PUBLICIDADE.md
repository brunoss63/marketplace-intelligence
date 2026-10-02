# Planejamento: dados de publicidade

## Situação atual

O dashboard lê investimento e receita atribuída da tabela `dados/publicidade.csv`.
Esses dados podem ser enviados pela importação CSV; ainda não existe conexão
direta com APIs de publicidade.

## Mercado Livre

Foi identificado que os relatórios do Mercado Livre podem estar disponíveis
somente pela API do Product Ads. Antes de implementar a integração, confirmar
na documentação oficial quais recursos e métricas estão disponíveis para a
conta, incluindo a granularidade por data, campanha e produto, além da definição
e janela de atribuição da receita.

## Próximos passos

1. Verificar a documentação oficial e os requisitos de acesso ao Product Ads.
2. Definir o fluxo de autorização OAuth e armazenar credenciais fora do código
   e dos arquivos versionados.
3. Mapear as métricas disponíveis para o esquema interno de publicidade:
   marketplace, data, SKU, campanha, investimento e receita atribuída.
4. Integrar os dados sem alterar a fonte CSV existente, para que a importação
   manual continue disponível para Shopee e outros canais sem integração.
5. Validar totais, períodos, atribuição e comportamento de sincronizações
   repetidas antes de usar os dados nos indicadores de resultado, margem e ROAS.

Até a integração e a validação serem concluídas, indicadores de publicidade
devem ser interpretados como baseados apenas nos dados que foram importados;
ausência de registros não confirma que não houve investimento em anúncios.
