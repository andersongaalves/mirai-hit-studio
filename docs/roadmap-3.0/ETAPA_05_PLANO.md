# Mirai Hit Studio 3.0 - Etapa 05: ordem de execucao

Criterio definido pelo responsavel em 14/10/2026: priorizar pela facilidade de
integracao. Ordem adotada para as fases independentes:

| Ordem | Fase | Motivo | Impacto de dados |
| --- | --- | --- | --- |
| 1 | 5.02 Observacoes nos arquivos | Uma coluna opcional em `producao_arquivos`; reaproveita upload, versionamento e visibilidade existentes nos tres portais | Migration aditiva, sem backfill |
| 2 | 5.01 Configuracoes basicas dos portais | Exige parametros tipados, validados e versionados, mais tela no Admin; nao toca regras comerciais | Nova tabela/JSON versionado |
| 3 | 5.03 Mensagens por producao | Exige historico bidirecional, autorizacao por papel e notificacoes | Nova tabela e integracao com e-mail (S11) |

As fases 5.04 a 5.13 seguem os portoes de dependencia do roadmap
(5.04 -> 5.05 -> 5.06 -> 5.07 ...) e dependem da Etapa 01 aplicada (PR #26).

## 5.02 - Observacoes nos arquivos (implementada)

- Coluna `producao_arquivos.observacao` (`VARCHAR(1000)`, opcional), migration
  `a7d3e5f9c210`.
- A nota e escrita por quem envia, junto com o upload, e pertence a uma versao especifica:
  nao ha edicao posterior. Autoria vem de `remetente_usuario_id`; o historico e a propria
  cadeia de versoes.
- O backend remove caracteres de controle (mantendo quebra de linha e tabulacao),
  descarta notas vazias e recusa mais de 1000 caracteres (422).
- A nota segue a visibilidade do arquivo: quem nao ve o arquivo nao ve a nota.
- UI: campo opcional nos formularios de upload do cliente, do produtor e do Admin;
  exibicao como texto puro (sem HTML).

### Ordem das migrations

Cadeia: `c5f2a7d9e184` -> `a7d3e5f9c210` (5.02, observacoes) -> `d8a7b1c9e240`
(Etapa 01, classificacao de testes) -> `b4e6f8a1c302` (5.01) -> `c9d2e4f6a813` (5.03) ->
`d3f5a7b9c124` (5.04). Todas aplicadas em producao em 14/10/2026 (ver registro abaixo).

## 5.01 - Configuracoes basicas dos portais

- Tabela `portal_configuracoes` (migration `b4e6f8a1c302`): versoes append-only por portal
  (`cliente`, `produtor`), com autor, origem de restauracao e data. A versao em uso e a
  mais recente; restaurar cria uma nova versao com o conteudo antigo.
- Parametros tipados e validados (`schemas/portal_config.py`, `extra=forbid`): aviso
  (ativo, nivel, texto ate 280), textos do dashboard e de ajuda, indicadores (subconjunto
  ordenado e sem repeticao), filtros iniciais e, no cliente, a area de propostas.
- Publicar exige `base_versao` igual a versao em uso (409 em edicao concorrente);
  conteudo identico nao gera versao. Toda publicacao/restauracao gera AuditLog.
- Fora do escopo por regra do roadmap: autenticacao, permissoes, auditoria e valores
  financeiros. Esconder uma area so afeta a interface; o backend continua autoritativo.
- Portais carregam a configuracao como chamada secundaria: se falhar, usam os padroes.
- Admin: Configuracoes > Portais (editor, valores padrao, historico e restauracao).

**Publicacao:** aplicar a migration `b4e6f8a1c302` no banco **antes** do release protegido
(o release nao migra o banco).

## 5.03 - Mensagens por producao

- Tabela `producao_mensagens` (migration `c9d2e4f6a813`): mensagens imutaveis por
  producao, com papel do autor, audiencia, resposta opcional e vinculo opcional a arquivo.
- Audiencia: `todos` (cliente, produtor e equipe) ou `equipe` (nota interna, so produtor
  e admin). O cliente sempre escreve para `todos` e nunca ve notas internas (regra no
  servidor e constraint no banco).
- Respostas e arquivos so podem apontar para itens da mesma producao que o autor ja ve.
  Uma mensagem para `todos` nao pode citar arquivo oculto ao cliente; se um arquivo for
  ocultado depois, o vinculo some da visao do cliente.
- Ownership igual aos arquivos: cliente pelo orcamento, produtor pela producao atribuida,
  admin em todas. Limite de 20 mensagens por minuto por autor (429).
- UI: painel de mensagens nos detalhes do Portal do Cliente, do Portal do Produtor e no
  modal de producao do Admin; carregado depois do detalhe, sem bloquear a tela.
- Notificacoes por e-mail ficam para a integracao INT-10 (S11).

**Publicacao:** aplicar `b4e6f8a1c302` e `c9d2e4f6a813` no banco antes do release.

## 5.04 - Servicos e etapas avancadas

- Tabela `servico_etapas` (migration `d3f5a7b9c124`): ordem, nome, descricao, peso
  percentual (`NUMERIC(5,2)`), prazo em dias, unidade, revisoes incluidas, dependencia da
  etapa anterior e marca de etapa administrativa.
- Regras (servidor e banco): soma dos pesos exatamente 100,00% quando houver etapas; peso
  0% so para etapas administrativas; a primeira etapa nao depende de outra; nomes unicos
  por servico; ate 20 etapas.
- `GET/PUT /servicos/{id}/etapas` (Admin): substitui a lista inteira de forma atomica e
  registra AuditLog. Excluir o servico remove as etapas do catalogo.
- O catalogo e um modelo: propostas e producoes existentes nao mudam. O congelamento de
  preco e percentuais no contrato e a fase 5.05; a criacao de etapas na producao, a 5.06.
- Admin: secao "Etapas e pesos" no editor de servicos, com total em tempo real.

**Publicacao:** aplicar `b4e6f8a1c302`, `c9d2e4f6a813` e `d3f5a7b9c124` antes do release.

## Registro de publicacao (14/10/2026)

| Item | Valor |
| --- | --- |
| Fases publicadas | 5.01, 5.03, 5.04 e a correcao AUD-S12-004 (PR #33) |
| PRs na `main` | #33, #32, #34, #35, #36 (nessa ordem) |
| Commit publicado | `4cbc10b207936765447f6f233c7dee969252c3b0` |
| Migrations | `b4e6f8a1c302`, `c9d2e4f6a813`, `d3f5a7b9c124`, aplicadas em uma transacao pelo SQL Editor do Supabase antes do release (~08:45 BRT) |
| Storage Integration Gate | run `38557322609` (sucesso) |
| Storage Provider Rollout Evidence | run `38560110202` (sucesso) |
| Protected Production Release | run `38561548878`, modo `publish`, `commercial_pipeline_v2=true` (sucesso, smokes finais verdes) |
| Autorizacao | `CTRL-20261014-R3-501-504` |

Verificacao pos-migration: `alembic_version = d3f5a7b9c124`; tres tabelas novas vazias, 3
indices e 22 constraints; dados existentes inalterados (7 servicos, 19 projetos, 4 producoes,
7 arquivos, 8 usuarios, 5 orcamentos, 5 pagamentos). O frontend oficial ja serve o novo
`config.js` (previews fora dos dominios oficiais nao chamam a API de producao).

Licao aplicada do incidente da publicacao anterior: o release protegido nao migra o banco,
entao as migrations foram aplicadas e verificadas antes de disparar o release.

## 5.05 - Catalogo nas propostas

- Cada item da proposta pode apontar para um servico do catalogo (`servico_id`, opcional).
  No Admin, "Servico do catalogo" adiciona a linha com o preco-base; o valor unitario
  continua editavel (preco negociado) e a linha mostra a origem e a marca "Preco negociado".
  Itens avulsos continuam permitidos.
- Snapshot economico (`propostas.snapshot_economico` + `snapshot_congelado_em`, migration
  `e5a7c9d1f246`): no envio da proposta, o sistema congela por item o servico, o preco-base
  da epoca, quantidade, valor unitario negociado, desconto, valor contratado e as etapas do
  catalogo com peso e valor. Depois de gravado, nunca e reescrito.
- Distribuicao em centavos: cada etapa recebe o piso do valor exato e os centavos que sobram
  vao para os maiores restos (empate pela ordem). A soma das etapas e sempre exatamente o
  valor contratado da linha; etapas administrativas de 0% recebem 0. Exemplo do roadmap:
  contrato de R$ 800 com 20/50/30 -> R$ 160 / R$ 400 / R$ 240.
- O desconto da linha e distribuido pelos pesos (o valor distribuido ja e o liquido).
- Bloqueios no envio: servico removido do catalogo ou etapas que nao somam 100% (409, nada
  e enviado). Em rascunho, `servico_id` inexistente e recusado (422).
- Propostas enviadas antes da 5.05 recebem o snapshot no aceite, de forma tolerante (linha
  sem etapas se o servico nao existir mais), para nunca bloquear o aceite. Propostas ja
  aceitas antes da 5.05 ficam sem snapshot: o catalogo atual nao reescreve contratos antigos.
- Admin: o separador Itens mostra "Valores congelados" (somente leitura) com etapas, pesos e
  valores. O portal do cliente nao muda nesta fase.
- Fora do escopo: criar etapas na producao a partir do snapshot (5.06) e repasses (5.13).

**Publicacao:** aplicar `e5a7c9d1f246` antes do release (duas colunas novas e nulas em
`propostas`, sem backfill).

### Publicacao da 5.05 (14/10/2026)

| Item | Valor |
| --- | --- |
| PRs na `main` | #37 (registro anterior) e #38 (5.05) |
| Commit publicado | `c5a50dff1d94f0bc299b83f6e9484088219f8d9d` |
| Migration | `e5a7c9d1f246`, aplicada pelo responsavel no SQL Editor do Supabase antes do release; conferida (`alembic_version = e5a7c9d1f246`, duas colunas nulas, nenhuma proposta com snapshot ainda) |
| Storage Integration Gate | run `38565620992` (sucesso) |
| Portals E2E | run `38565620921`: falha intermitente em `proposta_comercial.cjs` (corrida do teste, anterior a 5.05), verde na reexecucao; corrigido no PR #39 |
| Storage Provider Rollout Evidence | run `38567428573` (sucesso) |
| Protected Production Release | run `38568360462`, `publish`, `commercial_pipeline_v2=true` (sucesso, smokes finais verdes) |
| Autorizacao | `CTRL-20261014-R3-505` |

## 5.06 - Etapas automaticas na producao

- Tabela `producao_etapas` (migration `f7b9d1e3a568`): uma linha por etapa do contrato, com
  origem (proposta, item, servico), ordem geral e dentro do item, nome, peso, valor, prazo
  em dias, unidade, revisoes incluidas, dependencia, etapa administrativa, status, prazo,
  responsavel e datas de inicio e conclusao.
- Criacao automatica e unica quando a producao nasce (aceite no fluxo v1, liberacao por
  pagamento no fluxo v2), a partir dos valores congelados na proposta (5.05). Nome, peso e
  valor sao dados do contrato: editar o catalogo depois nao muda a producao.
- Prazo inicial: soma dos dias das etapas do mesmo item a partir da liberacao; o Admin pode
  ajustar ou remover o prazo de cada etapa. O responsavel inicial e o produtor da producao
  (atribuicao por etapa e a fase 5.07).
- Status: pendente -> em andamento -> em revisao -> concluida. O produtor inicia, envia para
  revisao e retoma; concluir e aprovacao do Admin. Uma etapa que depende da anterior so
  avanca depois que a anterior for concluida; reabrir uma etapa concluida e bloqueado se a
  seguinte ja comecou. Cada mudanca exige o status atual (409 se outra pessoa mudou antes) e
  gera AuditLog (`production.stage_status_changed`, `production.stage_deadline_changed`).
- Status da producao e das etapas sao independentes: concluir todas as etapas nao finaliza
  a producao automaticamente.
- Progresso: percentual do valor das etapas concluidas (ou da contagem, se o valor for zero).
- Visibilidade: cliente ve nome, status, prazo e progresso; produtor ve tambem unidade,
  revisoes e as acoes permitidas; valores e pesos so no Admin.
- Producoes criadas antes da 5.06 com proposta congelada: botao "Gerar etapas do contrato"
  no Admin. Producoes sem etapas de catalogo continuam com o checklist antigo.
- Telas: painel "Etapas do contrato" no Admin (aprovar, reabrir, prazo, gerar) e nos
  detalhes dos portais do produtor e do cliente, substituindo o checklist antigo quando o
  contrato tem etapas.

**Publicacao:** aplicar `f7b9d1e3a568` antes do release (tabela nova, sem alterar dados).

### Publicacao da 5.06 (14/10/2026)

| Item | Valor |
| --- | --- |
| PRs na `main` | #39 (teste instavel + registro da 5.05) e #40 (5.06) |
| Commit publicado | `d5082e338e9e489b728c03d4babb7cad194a838b` |
| Migration | `f7b9d1e3a568`, aplicada pelo responsavel no SQL Editor do Supabase antes do release; conferida (tabela vazia, 11 constraints, indice; dados existentes inalterados) |
| CI da `main` | Storage Integration Gate `38595088397`, Portals E2E e Client access migration verdes |
| Storage Provider Rollout Evidence | run `38595988568` (sucesso) |
| Protected Production Release | run `38596390562`, `publish`, `commercial_pipeline_v2=true` (sucesso, smokes finais verdes) |
| Autorizacao | `CTRL-20261014-R3-506` |

## 5.07 - Varios produtores por producao

- Cada etapa do contrato tem um responsavel principal (um por etapa nesta versao). O Admin
  atribui, troca ou deixa sem responsavel em "Etapas do contrato", com motivo opcional.
- Historico append-only `producao_etapa_atribuicoes` (migration `a9c1e3f5b702`): anterior,
  novo, quem atribuiu, motivo e data. Etapas ja criadas recebem o registro "Atribuicao
  inicial" na migration; etapas novas, na criacao.
- Quem executou: ao concluir, a etapa grava o responsavel do momento
  (`executor_usuario_id`); reabrir limpa. Etapa concluida nao pode ser reatribuida (409) ate
  ser reaberta, preservando autoria e base para os repasses (5.13).
- Acesso do produtor: ve a producao se for o coordenador (`producoes.produtor_id`) ou
  responsavel por pelo menos uma etapa. Vale para lista, detalhe, arquivos visiveis ao
  produtor, upload e mensagens. Ao perder a ultima etapa, perde o acesso.
- Coordenador nao concentra poderes: so o responsavel move a propria etapa; o coordenador
  move apenas o andamento geral da producao (o produtor so de etapas recebe 403 e nao ve
  esse botao).
- Isolamento: o produtor ve "Voce" ou "Outro produtor", nunca o nome ou id de outros
  produtores; nomes, executor e historico ficam no Admin. O cliente nao ve responsaveis.
- Concorrencia otimista na troca (`responsavel_atual`, 409) e AuditLog
  `production.stage_assigned` (`old_assigned_user_id`, `new_assigned_user_id`).
- Fora do escopo: repasse por etapa (5.13) e colaboracao simultanea na mesma etapa.

**Publicacao:** aplicar `a9c1e3f5b702` antes do release (coluna nula + tabela nova; insere
o historico inicial das etapas existentes).

### Publicacao da 5.07 (14/10/2026)

| Item | Valor |
| --- | --- |
| PRs na `main` | #41 (registro da 5.06) e #42 (5.07) |
| Commit publicado | `8a2aa7f09265697fcbada78ffe37ee7671d754f3` |
| Migration | `a9c1e3f5b702`, aplicada pelo responsavel no SQL Editor do Supabase antes do release; conferida (coluna `executor_usuario_id` inteira, tabela de historico vazia, dados inalterados) |
| CI da `main` | Storage Integration Gate `38609324628`, Portals E2E e Client access migration verdes |
| Storage Provider Rollout Evidence | run `38610503081` (sucesso) |
| Protected Production Release | run `38614580711`, `publish`, `commercial_pipeline_v2=true` (sucesso, smokes finais verdes) |
| Autorizacao | `CTRL-20261014-R3-507` |

Nota tecnica: `executor_usuario_id` ficou sem chave estrangeira (registro historico, como
`servico_id`), apos divergencia de nome de constraint entre `create_all` e migration nos
testes de downgrade.

## 5.08 - Combos modulares

- Catalogo de combos (migration `b2d4f6a8c913`): `combos` (nome, descricao, preco de
  referencia, ativo) e `combo_itens` (servicos em ordem, sem repeticao, minimo 2). Admin em
  Servicos > Combos: criar, editar e desativar; servico que esta em um combo nao pode ser
  excluido (409). Decisao de preco: o combo tem preco de referencia no catalogo e o preco
  final e negociado na proposta, como nos servicos.
- Proposta: cada item aponta para um servico ou para um combo ativo (`combo_id`), nunca os
  dois. A linha comeca no preco de referencia; o valor unitario continua negociavel.
- Distribuicao em dois niveis, congelada no envio (5.05): o valor contratado da linha e
  dividido entre os servicos do combo pelo preco de catalogo de cada um (maior resto em
  centavos; divisao igual se todos custarem zero) e, depois, a parcela de cada servico entre
  as suas etapas pelos pesos. Soma dos servicos = valor da linha; soma das etapas = parcela
  do servico. Descontos ficam distribuidos pelo mesmo caminho.
- Envio bloqueado (409) se o combo foi removido, ficou sem servicos ou algum servico tem
  etapas que nao somam 100%. Aceite de proposta antiga continua tolerante.
- Producao (5.06): as etapas do combo sao criadas com o servico de origem de cada uma e
  agrupadas por "combo — servico"; dependencias valem dentro de cada servico.
- Telas: painel Combos no Admin; seletor de itens da proposta com grupos Servicos e Combos;
  valores congelados mostram a parcela de cada servico e suas etapas.
- Fora do escopo: venda de combos no site publico e regra comercial explicita de desconto
  diferente da proporcional.

**Publicacao:** aplicar `b2d4f6a8c913` antes do release (duas tabelas novas).
