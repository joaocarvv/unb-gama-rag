# unb-gama-rag

RAG da Equipe 09 da Residência em IA do Instituto Eldorado (Challenge 2). O objetivo é ajudar estudantes da UnB Gama (FCTE) a encontrar informações confiáveis e verificáveis sobre prédios, ambientes, serviços e orientações do campus, sempre mostrando de onde cada informação veio.

> Projeto em andamento. Este documento descreve o que já foi feito e o que está planejado. Nenhum resultado de avaliação aparece aqui porque nenhum foi medido ainda.

## O projeto em 1 minuto

| Pergunta | Resposta curta |
|---|---|
| De onde vem? | Challenge 2 da Residência em IA do Instituto Eldorado: uma solução com IA que apoie decisões ligadas à qualidade de vida |
| Qual o recorte? | A rotina dos estudantes no campus UnB Gama (FCTE). Escolha da equipe |
| Qual o problema? | Informações do campus espalhadas ou sem detalhe na hora da consulta. É uma hipótese, ainda não medida |
| O que este repositório faz? | Um RAG: o estudante pergunta e recebe uma resposta baseada em documentos curados, com as fontes citadas |
| Onde entra a outra IA? | No Coleta FCTE (outro repositório): fotos de locais, sugestão do Gemini e revisão humana. As fichas revisadas viram fonte do RAG |
| Em que pé está? | Passos 1 a 4 de 9 feitos (catálogo, aquisição, extração, chunking, embeddings e índice). Próximo: busca sem LLM |

## Sumário

1. [Por que este repositório existe](#1-por-que-este-repositório-existe)
2. [O Challenge 2](#2-o-challenge-2)
3. [A proposta da equipe](#3-a-proposta-da-equipe)
4. [O que o RAG faz e o que não faz](#4-o-que-o-rag-faz-e-o-que-não-faz)
5. [Como o RAG funciona, em linguagem simples](#5-como-o-rag-funciona-em-linguagem-simples)
6. [Passo a passo da implementação](#6-passo-a-passo-da-implementação)
7. [Como replicar](#7-como-replicar)
8. [Estrutura do repositório](#8-estrutura-do-repositório)
9. [Regras que seguimos](#9-regras-que-seguimos)
10. [Pendências](#10-pendências)

## 1. Por que este repositório existe

A equipe tem duas soluções de IA no mesmo projeto:

- **Coleta FCTE** (repositório `FcteMapping`, FastAPI): visão computacional na coleta. Um integrante fotografa um local do campus, o Gemini sugere informações a partir da foto, e a pessoa revisa e salva. A revisão humana é obrigatória e só registros revisados formam a base verificada.
- **Este RAG**: a parte de consulta. O estudante faz uma pergunta e recebe uma resposta baseada em documentos oficiais e nas fichas revisadas do Coleta, com as fontes citadas.

Os dois foram criados pela equipe e fazem parte do mesmo Challenge 2.

Como o Coleta entra no RAG:

- As fichas revisadas, exportadas do Coleta, são uma das fontes do corpus, junto com os documentos oficiais.
- A sugestão original da IA fica separada e não entra como fato.
- As fotos ficam ligadas só pelo ID da ficha, sem indexação visual.

O RAG fica num repositório separado para não mexer na aplicação de coleta nem no deploy dela. Ele não importa código do Coleta: só lê o arquivo de fichas que o Coleta exporta.

## 2. O Challenge 2

### O que veio da residência

A residência funciona por challenges, sem aulas. O enunciado do Challenge 2 (slide "Challenge Statement"):

> **Projetar e desenvolver uma solução baseada em IA capaz de apoiar a tomada de decisão em um contexto relacionado à qualidade de vida.**
>
> Cada grupo deverá construir sua própria *Essential Question* a partir da *Big Idea*.
>
> Restrições:
> - Entender o problema antes da solução
> - Justificar decisões técnicas
> - Explicitar riscos e limitações
> - Validar com métricas objetivas
> - Utilizar evidências confiáveis

Além do enunciado, os mentores definiram que:

- Cada grupo precisa ter sua própria aplicação e sua própria solução com IA. Dois grupos que dividiam uma aplicação só tiveram que separar.
- O uso de RAG é obrigatório para todos os grupos, mesmo que básico.
- Métricas de avaliação e boas práticas (validação, reprodutibilidade, justificativa das escolhas) são cobradas ao longo do projeto. Os mentores acompanham perguntando sobre o que foi definido.

Prazo: cerca de 2 meses a partir do início de novembro de 2026. Datas exatas, formato da apresentação final e rubrica formal de avaliação: ainda não temos (ver [Pendências](#10-pendências)).

### O que foi decisão da equipe

- O recorte: a rotina dos estudantes no campus UnB Gama (FCTE). "Qualidade de vida" é o tema geral da residência; o campus foi escolha nossa.
- A Essential Question, o escopo, a arquitetura do RAG e os critérios de conclusão listados na seção 10. Esses critérios são da equipe, não do Instituto.
- O formato da demo: uma execução real por terminal ou notebook, com consulta, trechos recuperados, resposta fundamentada, fontes rastreáveis e um caso sem resposta.

## 3. A proposta da equipe

### Essential Question

> Como apoiar estudantes da UnB Gama a tomar decisões mais informadas sobre deslocamento, espaços de estudo e alimentação, a partir de informações confiáveis e acessíveis sobre o campus?

Questões complementares:

> Como a IA pode transformar fotos e documentos em informações úteis, verificáveis e atualizáveis? Como oferecer esse apoio respeitando privacidade, acessibilidade e as limitações dos dados?

Depois da divisão entre grupos, a alimentação (Restaurante Universitário) ficou com outro grupo. Por isso o RU está fora do escopo deste projeto.

### O problema (hipótese)

A rotina dos estudantes da FCTE envolve se deslocar entre salas e serviços, escolher onde estudar e usar os intervalos. Informações sobre localização, recursos dos ambientes e serviços podem estar espalhadas em várias páginas ou sem o detalhe necessário na hora da consulta. O estudante acaba perguntando a colegas, abrindo várias páginas ou andando pelo campus até achar o que precisa.

**Isso é uma hipótese, não um fato medido.** A frequência dessas dificuldades, quem é mais afetado e o impacto ainda vão ser medidos, com um questionário de 10 perguntas e testes com estudantes.

As personas usadas no planejamento são hipotéticas (não são pessoas entrevistadas): estudante recém-chegado, estudante com intervalos longos, estudante com necessidades de acessibilidade e integrante coletor ou revisor.

### Objetivo

Apoiar decisões do dia a dia dos estudantes com informações compreensíveis, verificáveis e atualizadas, avaliando a utilidade com tarefas reais. Não prometemos redução de riscos nem melhoria de qualidade de vida antes da validação. A solução apoia decisões, não substitui serviços institucionais.

### Escopo da Equipe 09 (épicos)

| Épico | Onde fica |
|---|---|
| E1 Mapa e orientação no campus | projeto da equipe |
| E2 Espaços de estudo e descanso | projeto da equipe |
| E4 Consulta ao conhecimento com RAG | **este repositório** |
| E5 Coleta e manutenção do mapa | Coleta FCTE |
| E6 Transporte e caronas | aqui, só como conteúdo documental (onde consultar linhas e horários) |
| E8 Acessibilidade e trajetos | parcial |

A proposta completa está em três documentos internos da equipe, que não estão neste repositório: "Qualidade de vida no campus UnB Gama", "Organização do projeto UnB Gama" e "Plano da entrega de conhecimento e RAG". Este repositório implementa o terceiro.

## 4. O que o RAG faz e o que não faz

**Faz:**

- Responde perguntas sobre prédios, ambientes, laboratórios, serviços e orientações da FCTE usando só documentos que passaram por curadoria humana.
- Mostra quais trechos foram usados e de onde vieram (documento, URL, seção, versão, data).
- Diz quando não encontrou informação suficiente, em vez de inventar.
- Registra cada execução para que dê para conferir depois.

**Não faz:**

- Restaurante Universitário e cardápios.
- Planejador de rotas de ônibus e caronas.
- Busca por imagens (fotos ficam ligadas só pelo ID da ficha).
- Usar a sugestão da IA do Coleta como fato: só entram campos revisados por pessoas.
- Substituir a secretaria, a DASU ou qualquer outro serviço da universidade.

## 5. Como o RAG funciona, em linguagem simples

RAG (Retrieval-Augmented Generation) é "buscar antes de responder". Em vez de perguntar direto para um modelo de linguagem, que pode inventar, o sistema primeiro procura trechos relevantes numa base de documentos confiáveis e só depois pede ao modelo para escrever a resposta usando apenas esses trechos.

Uma analogia para quem vem de backend: é como um endpoint de busca com um índice bem cuidado, só que a busca é por significado e não por palavra exata, e no final um modelo de linguagem resume os resultados com citações.

O caminho tem duas partes:

**Ingestão (preparar a base, roda uma vez e depois quando as fontes mudam)**

```
fontes.csv -> baixar originais -> extrair texto -> curadoria humana
           -> marcar entidades -> dividir em chunks -> embeddings -> índice (Chroma)
```

**Consulta (cada pergunta)**

```
pergunta -> embedding da pergunta -> buscar chunks parecidos no índice
         -> filtrar (aprovado, campus, validade) -> Gemini escreve a resposta citando os chunks
         -> conferir citações -> registrar execução
```

Componentes escolhidos:

| Parte | Escolha | Por quê |
|---|---|---|
| Embeddings | `intfloat/multilingual-e5-small`, local | Entende português, roda sem GPU e sem custo. 384 dimensões, até 512 tokens |
| Banco vetorial | Chroma com `PersistentClient`, distância cosseno | Simples, roda local e guarda o índice em disco |
| Geração | Gemini | Só redige a resposta a partir dos trechos recuperados. Entra no passo 7 |

Glossário rápido:

- **Chunk**: um pedaço de documento, do tamanho certo para a busca (alvo de ~300 tokens).
- **Token**: a unidade que o modelo lê. Uma palavra pode virar um ou mais tokens.
- **Embedding**: uma lista de 384 números que representa o significado de um texto. Textos com sentido parecido ficam com números parecidos.
- **SHA-256**: uma "impressão digital" do arquivo. Se um byte muda, ela muda. Serve para provar que o texto usado veio daquele original.

## 6. Passo a passo da implementação

Cada passo é pequeno e só começa depois que o anterior é aprovado.

| # | Passo | Situação |
|---|---|---|
| 1 | Esqueleto, configuração e validação do catálogo | feito |
| 2 | Aquisição e extração (HTML) | feito (PDF e fichas adiados) |
| 3 | Chunking e normalização | feito |
| 4 | Embeddings e índice | feito |
| 5 | Busca e demo sem LLM | próximo |
| 6 | Gabarito e métricas de busca (E5 vs BM25) | planejado |
| 7 | Geração com Gemini e checagem de citações | planejado |
| 8 | Avaliação das respostas | planejado |
| 9 | Diagrama e relatório | planejado |

### Passo 1: esqueleto e catálogo

- `config/rag.yaml` concentra toda a configuração. Os scripts não têm números fixos no código.
- `catalogo/fontes.csv` lista cada fonte com campus, abrangência, datas, status de curadoria, SHA-256 e versão. Hoje tem 20 fontes, todas `pendente`.
- `scripts/03_validar_catalogo.py` confere o catálogo (campos obrigatórios, datas, status, duplicados, relações) e sai com erro se algo estiver errado.
- Campos técnicos (`data_coleta`, `sha256`, `versao`) são preenchidos pelos scripts. Campos de curadoria (`status`, `revisor`, `motivo`, `data_revisao`) são só de pessoas: o script nunca aprova uma fonte.

### Passo 2: aquisição e extração

- `scripts/01_adquirir.py` baixa cada página, respeitando o `robots.txt` e esperando entre downloads. Guarda o original em `data/originais/<source_id>/<versao>/` com o SHA-256 e os metadados da requisição. Rodar de novo não baixa o que já existe.
- `scripts/02_extrair.py` tira menus, rodapés e scripts do HTML e guarda o texto em seções, cada uma com o caminho de títulos (ex.: "Laboratórios > LaSE"). O resultado vai para `data/extraido/<source_id>__<versao>.json`, com o SHA-256 do original que o gerou.
- Sites diferentes têm regras diferentes no `rag.yaml` (ex.: DF no Ponto usa outro seletor de conteúdo).

### Passo 3: chunking e normalização

- `scripts/04_chunks.py` divide cada documento em chunks e grava `data/chunks/chunks.jsonl`.
- Estratégia padrão `agrupar_irmaos`: junta seções vizinhas com o mesmo título-pai até ~300 tokens. A alternativa `por_secao` (uma seção por chunk) fica disponível para comparar no passo 6.
- Seção longa é subdividida com ~40 tokens de sobreposição, feita só com parágrafos ou frases inteiros. Cortar no meio fazia uma sala aparecer junto do laboratório errado.
- Os tokens são contados com o tokenizer do próprio E5, incluindo o prefixo `passage: ` e o título. Nada passa de 512: o script dá erro em vez de cortar em silêncio.
- Cada chunk tem um `chunk_id` estável (hash da fonte, versão, seção, posição e configuração), então rodar de novo gera os mesmos IDs.
- `config/entidades.yaml` liga siglas e nomes ao mesmo ID (ex.: "UAC" e "Unidade Acadêmica"). Só entra equivalência escrita numa fonte do catálogo. O texto do chunk não muda: as entidades vão só para os metadados. Exemplo: FGA e FCTE ficaram separadas porque nenhuma fonte do catálogo diz que são a mesma unidade.
- Como ainda não há fontes aprovadas, o modo `--rascunho` trata as pendentes como aprovadas para testar. O resultado vai para `chunks_rascunho.jsonl`, fora do git e fora do índice real.

Números do modo rascunho em 2026-11-09 (20 fontes pendentes, só para conferência do pipeline, não é avaliação): 76 chunks com `agrupar_irmaos` (mediana de 191 tokens, máximo de 296) e 114 com `por_secao` (mediana de 123).

### Passo 4: embeddings e índice

- `src/unb_gama_rag/embeddings.py` carrega o E5 na revisão fixada e é o único lugar que coloca os prefixos (`passage: ` nos chunks, `query: ` nas perguntas). Os vetores saem normalizados. Os testes usam um embedder falso, que não baixa o modelo.
- `scripts/05_indexar.py` grava os vetores no Chroma (distância cosseno, sem a função de embedding padrão do Chroma) e sincroniza pelo `chunk_id`:
  - id novo: codifica e insere;
  - id que já existe: não recodifica (o mesmo id garante o mesmo texto), só atualiza metadados, como o status depois da curadoria;
  - id que sumiu dos chunks (versão superada): remove.
- Rodar de novo não duplica nada. Se não houver chunk novo, o modelo nem é carregado.
- `data/index/manifesto.json` registra modelo, revisão, prefixos, tokenizer, config de chunking, versão do corpus (hash das fontes, versões e SHAs), config do índice e versões das bibliotecas. Se o modelo, a revisão, a dimensão, o prefixo, a normalização ou a distância mudarem, o script se recusa a misturar vetores e pede `--reconstruir`.
- `scripts/06_conferir.py` reabre o índice num processo novo, sem ingestão, e confere total, ids, dimensão, distância, compatibilidade com a config e se o vetor salvo de um chunk é igual ao que o modelo gera hoje. Depois roda 3 perguntas do `rag.yaml` só para ver o ranking (não é avaliação).
- O índice das pendentes fica separado em `data/index/chroma_rascunho/`, com manifesto próprio. O índice real só aceita chunks de fontes aprovadas.

Execução em 2026-11-09 (modo rascunho): 76 chunks indexados; na 2ª execução, 0 novos e total 76; a conferência passou nas 6 checagens.

### Próximos passos

- **5. Busca**: `perguntar.py` mostra o ranking (posição, `chunk_id`, fonte, seção, distância) sem usar LLM.
- **6. Métricas de busca**: gabarito com ~30 perguntas (respondíveis, sem resposta e com premissa errada), Hit@5 e MRR, E5 comparado com BM25.
- **7. Geração**: Gemini responde só com os trechos, cita os `chunk_id`, e o sistema confere se cada citação foi mesmo recuperada.
- **8. Avaliação das respostas**: com RAG e sem RAG, julgamento manual com rubrica escrita antes.
- **9. Diagrama e relatório** com os resultados observados e as limitações.

## 7. Como replicar

Tudo roda em Docker, então não é preciso instalar Python na máquina.

### Pré-requisitos

- Docker Desktop (ou Docker Engine com Compose)
- Git

### Preparar

```bash
git clone https://github.com/joaocarvv/unb-gama-rag.git
cd unb-gama-rag
cp .env.example .env          # a chave do Gemini só será usada a partir do passo 7
docker compose build
```

O projeto é montado dentro do container em `/app`. O cache do modelo de embeddings fica num volume Docker (`hf-cache`), então ele é baixado uma vez só.

### Rodar o pipeline

```bash
# testes (sem rede, sem Gemini, sem baixar o modelo)
docker compose run --rm rag pytest

# 1. conferir o catálogo
docker compose run --rm rag python scripts/03_validar_catalogo.py

# 2. baixar os originais e preencher sha256, data_coleta e versao no catálogo
docker compose run --rm rag python scripts/01_adquirir.py

# 3. extrair o texto
docker compose run --rm rag python scripts/02_extrair.py
docker compose run --rm rag python scripts/02_extrair.py --mostrar DOC-005

# 4. gerar os chunks (rascunho enquanto não houver fontes aprovadas)
docker compose run --rm rag python scripts/04_chunks.py --rascunho
docker compose run --rm rag python scripts/04_chunks.py --rascunho --estrategia por_secao
docker compose run --rm rag python scripts/04_chunks.py --rascunho --mostrar DOC-015

# 5. embeddings e índice (na 1ª vez baixa o modelo, ~470 MB)
docker compose run --rm rag python scripts/05_indexar.py --rascunho
docker compose run --rm rag python scripts/05_indexar.py --rascunho     # de novo: 0 novos
docker compose run --rm rag python scripts/05_indexar.py --rascunho --reconstruir

# 6. reabrir o índice sem ingestão e conferir
docker compose run --rm rag python scripts/06_conferir.py --rascunho
```

### Observações para quem replicar

- As páginas mudam com o tempo. Se você baixar hoje, o SHA-256 pode ser diferente do que está no catálogo, e o script avisa. Para uma versão nova, use `01_adquirir.py --atualizar`.
- Os originais baixados (`data/originais/`) não vão para o git. O texto extraído (`data/extraido/`) vai, para que dê para conferir o que foi usado.
- Para usar seus próprios documentos, edite `catalogo/fontes.csv` e rode o pipeline. Uma fonte só entra no índice real depois de uma pessoa marcar `status = aprovado` e preencher revisor e data de revisão.

## 8. Estrutura do repositório

```
config/rag.yaml           configuração central
config/entidades.yaml     siglas e nomes ligados a IDs, com a fonte que comprova
catalogo/fontes.csv       catálogo de fontes e curadoria
data/originais/           originais baixados (fora do git)
data/extraido/            texto extraído por fonte e versão
data/chunks/              chunks gerados
data/index/               índices Chroma (real e rascunho) e manifestos (fora do git)
src/unb_gama_rag/         lógica (catalogo, aquisicao, extracao, tokens, chunking, normalizacao,
                          embeddings, indice, manifesto)
scripts/                  scripts finos, um por etapa
tests/                    testes sem rede, sem Gemini e sem baixar modelo
Dockerfile, compose.yaml  ambiente Python 3.12
```

## 9. Regras que seguimos

- Não inventar dados. Dados de exemplo nos testes são pequenos e marcados como exemplo.
- Sugestão da IA nunca é apresentada como fato verificado.
- Nenhum resultado de avaliação é publicado sem ter sido medido.
- Privacidade: sem pessoas nas fotos e dados mínimos. Fotos, dados reais da coleta e chaves de API não vão para o git.
- A chave do Gemini fica só no `.env`.
- Reprodutibilidade: modelo e revisão do E5, versões das bibliotecas e configuração ficam registrados.

## 10. Pendências

**Critérios de conclusão definidos pela equipe:**

1. Pelo menos 20 documentos curados, catalogados e usados, com originais preservados.
2. Chunking e embeddings documentados com as configurações realmente executadas.
3. Chunks e banco vetorial persistido, com reconstrução e reabertura demonstradas.
4. Uma execução real com consulta, recuperação, resposta fundamentada e fontes rastreáveis, mais um caso sem resposta.
5. Diagrama e pipeline coerentes com o implementado.
6. Relatório da avaliação com resultados observados e limitações.

**Em aberto:**

- Curadoria humana das 20 fontes (todas ainda pendentes). A meta é 20 aprovadas, então talvez seja preciso incluir mais fontes candidatas.
- Revisão humana de `config/entidades.yaml`.
- Fontes em PDF e fichas do Coleta (adiadas no passo 2).
- Datas exatas de entrega e formato da apresentação final: a definir.
- Texto exato da Big Idea da residência: não temos.
- Rubrica formal da residência: não temos.
- Validação do problema com estudantes (questionário e testes): ainda não feita.
