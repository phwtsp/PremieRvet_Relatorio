# Instruções para o Codex CLI – Extração de Métricas de Prints do Instagram

Você está em um diretório raiz que contém várias pastas, uma por influenciador.\
Cada pasta pode ter **subpastas** e contém **prints de métricas do Instagram** (Stories e Feed).

## Objetivo

1. Percorrer **todas as pastas e subpastas** a partir do diretório atual.
2. Considerar que **o nome da pasta de nível imediatamente abaixo da raiz** é o **nome do influenciador**.
   - Exemplo: `./influencer_a/...`, `./influencer_b/...`.
3. A partir dos prints, extrair para cada influenciador:
   - Total de **visualizações** (soma de todas as visualizações dos posts).
   - Total de **interações** (soma de todas as interações relevantes dos posts).
   - **Taxa de interação** = interações / visualizações (em decimal ou porcentagem, mas seja consistente).
   - Quantidade de **posts de Feed**.
   - Quantidade de **posts de Stories**.
4. Detectar **posts/prints duplicados** (mesmos dados de métricas) e **desconsiderar duplicatas** na contagem final.
5. Gerar um arquivo CSV no diretório raiz com o resumo por influenciador.

## Assumptions / Interpretação

- Os prints podem estar em formatos como `.png`, `.jpg`, `.jpeg`.
- Os prints podem ter textos em português (ex.: "Visualizações", "Alcance", "Interações", "Contas alcançadas", "Curtidas", "Comentários", "Compartilhamentos", etc.).
- Use visão/OCR (via modelo ou MCP de OCR, se disponível) para ler os números de cada print.
- Pode haver variação visual entre prints (tema claro/escuro, layout diferente, etc.), então seja robusto ao reconhecer campos equivalentes.
- Se não for possível inferir com segurança se um print é de **Feed** ou **Stories**, marque o tipo como `desconhecido` internamente e **não conte** esse item nem como Feed nem como Stories, mas inclua suas métricas de visualizações/interações se a leitura for confiável.

## Detecção de duplicados

Ao processar os prints, evite contar duas vezes o mesmo post ou o mesmo conjunto de métricas:

- Considere dois registros como **duplicados** se tiverem, ao mesmo tempo:
  - Mesmo influenciador,
  - Mesmo tipo de post (Feed/Stories, quando conhecido),
  - Mesmo valor de visualizações,
  - Mesmo valor de interações,
  - E, se disponível, alguma identificação extra (data, horário, nome do post ou ID) igual.
- Quando detectar duplicatas, mantenha **apenas um** registro e ignore os demais na soma de métricas e contagem de posts.

## Classificação: Feed vs Stories

Ao analisar cada print, tente inferir se é Feed ou Stories usando:

- Elementos visuais e texto:
  - Stories: indicadores tipo “Stories”, “Histórias”, interface de stories, barras de progresso no topo, indicadores de “Respostas”, “Saídas”, “Avanços”, etc.
  - Feed: layout padrão de post do feed, presença de “Curtidas”, “Comentários”, “Salvos” em formato típico do Instagram Feed.
- Labels que apareçam explicitamente no print:
  - Ex.: “Desempenho de Stories”, “Dados de Stories”, “Publicação no feed”, “Publicação”, etc.
- Se as evidências forem fracas ou contraditórias, deixe o tipo como `desconhecido` e **não incremente a contagem de Feed nem de Stories** para esse registro.

## Lógica de extração e agregação

1. **Varredura de arquivos**

   - Percorra recursivamente todas as pastas e subpastas a partir do diretório atual.
   - Para cada arquivo de imagem (`.png`, `.jpg`, `.jpeg`):
     - Identifique o **influenciador** pelo nome da pasta de nível imediatamente abaixo da raiz.
       - Ex.: `./NOME_INFLUENCER/subpasta1/subpasta2/print1.png` → influenciador = `NOME_INFLUENCER`.

2. **Leitura das métricas (OCR/visão)**

   - Use o modelo com visão ou um servidor MCP de OCR para:
     - Ler todo o texto do print.
     - Detectar os valores numéricos referentes a:
       - Visualizações (views, “Visualizações”, “Alcance”, “Contas alcançadas” – seja consistente e escolha o campo que melhor representa visualizações, justificando internamente).
       - Interações (somatória de ações relevantes: curtidas, comentários, compartilhamentos, salvamentos, respostas, cliques, etc., conforme exibido no print).
   - Normalize:
     - Remova separadores de milhares (`.`, `,`, espaços) e trate “k” / “mil” / “M” corretamente.
     - Converta vírgula decimal em ponto, se necessário.

3. **Determinação de Feed vs Stories**

   - A partir do layout e dos textos do print, classifique como:
     - `feed`
     - `stories`
     - `desconhecido` (quando não houver sinal claro).
   - Essa classificação será usada apenas para **contar quantidade de posts de Feed e Stories**.

4. **Construção de um registro por print**

   - Para cada print processado, construa um registro com:
     - `influencer`
     - `tipo_post` (feed, stories ou desconhecido)
     - `visualizacoes` (número)
     - `interacoes` (número)
     - Campos auxiliares para identificar duplicidade (ex.: data do print, ID do post ou título, se disponível).
   - Antes de adicionar o registro à lista final, compare com os registros já existentes para o mesmo influenciador:
     - Se bater em todos os campos relevantes (visualizações, interações, tipo_post e, quando houver, identificadores), considere duplicado e **não adicione**.
     - Caso contrário, adicione à lista.

5. **Agregação por influenciador**

   - Para cada influenciador:
     - Some as `visualizacoes` de todos os registros (incluindo `desconhecido`).
     - Some as `interacoes` de todos os registros (incluindo `desconhecido`).
     - Conte:
       - `qtd_posts_feed` = número de registros com `tipo_post = feed`.
       - `qtd_posts_stories` = número de registros com `tipo_post = stories`.
     - Calcule a **taxa de interação**:
       - `taxa_interacao = interacoes_totais / visualizacoes_totais`
       - Se `visualizacoes_totais` for zero ou não disponível, deixe a taxa em branco ou como `0`.

## Formato da saída (CSV)

Gere um arquivo CSV no diretório raiz chamado, por exemplo, `instagram_influencers_metrics.csv` com **uma linha por influenciador**, contendo as colunas:

- `influencer`
- `visualizacoes_totais`
- `interacoes_totais`
- `taxa_interacao` (decimal ou porcentagem; escolha uma convenção e mantenha-a consistente)
- `qtd_posts_feed`
- `qtd_posts_stories`

Exemplo de cabeçalho:

```csv
influencer,visualizacoes_totais,interacoes_totais,taxa_interacao,qtd_posts_feed,qtd_posts_stories
```

Certifique-se de:

- Usar sempre o mesmo separador de campos (vírgula por padrão).
- Não incluir linhas em branco.
- Tratar corretamente caracteres especiais no nome dos influenciadores (UTF-8).

## Qualidade e validação

- Faça uma amostra de checagem:
  - Liste alguns prints e os respectivos registros extraídos, para garantir que os números e a classificação (Feed/Stories) fazem sentido.
- Verifique se:
  - Não há influenciadores faltando em relação às pastas existentes.
  - As somas de visualizações/interações parecem razoáveis (sem explodir por conta de duplicatas não filtradas).
- Caso encontre prints muito ruidosos ou ilegíveis:
  - Ignore-os ou registre-os separadamente, mas não deixe que corrompam as métricas agregadas.

## Resumo do que você deve fazer

1. Explorar recursivamente o diretório atual, processando todas as imagens.
2. Usar visão/OCR para extrair visualizações e interações de cada print.
3. Inferir o influenciador pelo nome da pasta e o tipo de post (Feed/Stories) por layout/conteúdo.
4. Detectar e remover registros duplicados.
5. Agregar métricas por influenciador e calcular taxa de interação.
6. Gerar o CSV final `instagram_influencers_metrics.csv` conforme especificado.