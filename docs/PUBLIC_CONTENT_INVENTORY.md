# Mirai Hit Studio - Public Content Inventory

## Escopo e regra de uso

Este inventario registra somente material verificavel no repositorio em G.0. A existencia de um registro no banco, arquivo de projeto ou campo de formulario nao comprova autoria, contratacao nem autorizacao de publicacao.

Tipos editoriais adotados para o site: `real_client`, `personal_project`, `demo`, `concept` e `study`. Todo trabalho sem evidencia suficiente permanece fora das alegacoes publicas ate revisao humana.

## Material verificavel

| Asset | Tipo | Vertical | Autorizado? | Pode publicar? | Material disponivel | Falta |
|---|---|---|---|---|---|---|
| `frontend/img/logo-principal.webp` | Identidade da Mirai | Todas | Proprio da marca | Sim | Logo principal | Nada para uso institucional |
| `frontend/img/logo-horizontal.png` | Identidade da Mirai | Todas | Proprio da marca | Sim | Logo horizontal | Nada para uso institucional |
| `frontend/assets/logo_mirai_BnW.png` | Identidade da Mirai | Todas | Proprio da marca | Sim | Logo monocromatico | Nada para uso institucional |
| `frontend/assets/banner-social.png` | Identidade da Mirai | Todas | Proprio da marca | Sim | Banner social existente | Revisar copy e enquadramento antes de reutilizar em novas paginas |
| Catalogo dinamico de `Projeto` | Nao classificado | Nao informada | Nao verificavel no repositorio | Nao automaticamente | Titulo, artista, categoria, descricao, capa, audio e destaque suportados pelo sistema | Exportar registros reais, confirmar autoria, tipo editorial e autorizacao |

Nao ha arquivo de audio, link de player, depoimento, before/after, metrica de resultado, credito verificavel ou case completo versionado no repositorio.

## Artists

### Existente

- Estrutura publica e administrativa capaz de exibir projetos com capa, audio, artista, categoria e descricao.
- Ofertas documentadas para instrumental, producao musical, vocal production, mixagem e masterizacao.
- Nenhuma faixa ou relacao de cliente verificavel localmente.

### Falta

- Selecionar faixas publicaveis e classifica-las como `real_client`, `personal_project` ou `demo`.
- Registrar creditos, servicos executados e autorizacao de nome, capa e audio.
- Obter before/after ou depoimento somente com consentimento explicito.
- Identificar segmentos reais, como `rap`, `trap`, `drill`, `funk` ou `geek_music`.

## Creators

### Existente

- Posicionamento e ofertas conceituais documentados para tema, intro/outro, trilha e sound branding.
- Nenhum projeto, aplicacao em conteudo, marca ou depoimento verificavel localmente.

### Falta

- Produzir ou selecionar uma demonstracao claramente rotulada.
- Quando houver cliente, documentar autorizacao, contexto de uso e servicos realizados.
- Capturar midia que mostre a aplicacao real do audio no conteudo.

## Media & Games

### Existente

- Capabilities documentadas para soundtrack, loops, menu music, ambient e sound design.
- Nenhum cliente, gameplay, soundtrack ou demo verificavel localmente.

### Falta

- Criar `demo`, `concept` ou `study` proprio com rotulo visivel.
- Preparar player e, quando aplicavel, video ou captura de gameplay autorizada.
- Nao publicar alegacao de cliente ate existir evidencia e permissao.

## Dados necessarios antes de G.5

Para cada item candidato, coletar:

| Campo | Obrigatorio para publicar? |
|---|---|
| Titulo e tipo editorial | Sim |
| Vertical e segmentos | Sim |
| Audio ou midia acessivel | Sim |
| Autoria e creditos | Sim |
| Autorizacao de publicacao | Sim para trabalho de cliente |
| Servicos realizados | Sim |
| Capa e texto alternativo | Sim quando houver imagem |
| Resultado ou depoimento | Somente quando verificavel e autorizado |

## Decisao para o bloco G

G.1–G.4 podem usar identidade de marca, capacidades reais, processo e ofertas documentadas. Nao devem exibir logos de terceiros, contadores, reviews ou nomes de clientes. G.5 deve renderizar apenas registros classificados e autorizados; na ausencia deles, deve apresentar um estado vazio honesto e permitir demos/concepts/studies claramente identificados.
