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

### Publicacao da 5.08 (14/10/2026)

| Item | Valor |
| --- | --- |
| PRs na `main` | #43 (registro da 5.07) e #44 (5.08) |
| Commit publicado | `af2ef7bd72fc265154ad5c127671a2d32c114c17` |
| Migration | `b2d4f6a8c913`, aplicada pelo responsavel no SQL Editor do Supabase antes do release; conferida (`combos` e `combo_itens` presentes) |
| CI da `main` | Storage Integration Gate `38658303952`, Portals E2E e Client access migration verdes |
| Storage Provider Rollout Evidence | run `38659118302` (sucesso) |
| Protected Production Release | run `38660859481`, `publish`, `commercial_pipeline_v2=true` (sucesso, smokes finais verdes) |
| Autorizacao | `CTRL-20261014-R3-508` |

## 5.09 - Cotas de arquivos por contrato

- Catalogo (migration `c4e6a8b0d215`): cada servico pode limitar, por tipo de arquivo
  (materiais, referencias, previas, entregas), a quantidade de arquivos, as versoes por
  arquivo, o tamanho por arquivo, o espaco total e os formatos aceitos. Tipo sem cota =
  sem limite contratual (valem so os limites gerais, 50 MB por arquivo). Editor no Admin
  em Servicos, ao lado das etapas.
- Contrato: as cotas de cada servico (inclusive os servicos de um combo, 5.08) ficam
  congeladas no snapshot da proposta no envio (5.05). Mudar o catalogo depois nao altera
  contratos nem producoes ja criadas.
- Producao: ao ser criada, recebe as cotas somadas do contrato. Por tipo: so ha limite se
  todos os servicos contratados o definem; arquivos e espaco somam (x quantidade,
  arredondada para cima; teto de 100 arquivos e 5000 MB); versoes e tamanho usam o maior
  valor; formatos sao a uniao. Contratos anteriores a 5.09 ficam sem cotas.
- Envio: o servidor confere formato e tamanho (422) e quantidade, versoes e espaco (409)
  nos envios do cliente e do produtor, com a producao travada (`SELECT ... FOR UPDATE`)
  para que dois envios simultaneos nao estourem a cota. O Admin nao e limitado.
- Excecao: o Admin pode substituir as cotas de uma producao no modal da producao
  (origem `admin`), com auditoria (`production.file_quotas_updated`); mudancas no catalogo
  ficam em `service.file_quotas_updated`.
- Portais: o formulario de envio mostra a cota do tipo escolhido com o uso atual e avisa
  quando o limite foi atingido (nova versao de arquivo existente continua possivel enquanto
  houver versoes e espaco). O cliente ve so materiais e referencias; o produtor, previas e
  entregas.
- Fora do escopo: cobranca de espaco extra e limpeza automatica de versoes antigas.

**Publicacao:** aplicar `c4e6a8b0d215` antes do release (duas tabelas novas, aditivo).

### Publicacao da 5.09 (15/10/2026)

| Item | Valor |
| --- | --- |
| PRs na `main` | #45 (registro da 5.08) e #46 (5.09) |
| Commit publicado | `6d9850de542a0d4daea1428d2634f09ff46eb2a5` |
| Migration | `c4e6a8b0d215`, aplicada pelo responsavel no SQL Editor do Supabase antes do release; conferida (`servico_cotas_arquivo` e `producao_cotas_arquivo` com 7 restricoes e 2 indices) |
| CI da `main` | Storage Integration Gate `38674897587` (verde na repeticao; a 1a tentativa falhou ao baixar imagem Docker), Portals E2E e Client access migration verdes |
| Storage Provider Rollout Evidence | run `38675814622` (sucesso) |
| Protected Production Release | run `38676188660`, `publish`, `commercial_pipeline_v2=true` (sucesso, smokes finais verdes) |
| Autorizacao | `CTRL-20261015-R3-509` |

## 5.10 - Configuracoes avancadas dos portais (politicas por contrato)

- Politicas tipadas e fechadas (migration `d6f8b0c2e437`), com valores padrao iguais ao
  comportamento anterior, de modo que nada muda no deploy:
  - `publicacao_previa`: previa do produtor vai direto ao cliente (`automatica`) ou so
    depois de o Admin publicar (`aprovacao_admin`). Fecha o AUD-S05-001 como politica.
  - `revisoes_excedentes`: cada retorno de uma etapa de "em revisao" para "em andamento"
    conta uma revisao (`producao_etapas.revisoes_usadas`). Esgotadas as incluidas, a
    revisao segue permitida e marcada como extra (`permitir`) ou so o Admin libera
    (`exigir_admin`). O AuditLog registra a rodada e se ela e extra.
  - `cliente_ve_etapas` e `cliente_ve_prazos_etapas`: o cliente ve ou nao as etapas do
    contrato (sem elas, so o progresso geral) e os prazos de cada etapa.
  - `financeiro_cliente`: `completo` ou `resumido` (status, saldo, vencimento e link de
    pagamento; sem valores cobrados/pagos nem historico).
- Heranca, por chave: excecao da producao > contrato > padrao global > padrao do sistema.
  - Padrao global: versoes append-only com concorrencia otimista, historico e restauracao
    (como a 5.01). Admin em Configuracoes > Portais.
  - Servico: guarda so o que sobrescreve; o resto segue o padrao global. Editor no Admin em
    Servicos, ao lado das etapas e cotas.
  - Contrato: as politicas resolvidas de cada servico (inclusive dentro de combos) ficam
    congeladas no snapshot no envio da proposta. Mudancas globais ou no catalogo depois nao
    alteram contratos ("o contrato vigente prevalece"). Com varios servicos, vale a opcao
    mais favoravel ao cliente. Contratos anteriores a 5.10 seguem o padrao global atual.
  - Excecao: o Admin altera chaves de uma producao no modal da producao, com motivo
    obrigatorio; pode remover (volta ao contrato). Auditoria em
    `production.policies_exception_set` / `_removed`; catalogo em
    `service.policies_updated`; global em `policy.global_published` / `_restored`.
- O backend aplica as politicas (upload do produtor, transicoes de etapa, endpoints do
  cliente). Nenhuma politica desliga autenticacao, permissoes ou auditoria.
- A politica de etapas vale para as etapas do contrato (5.06); o checklist manual antigo
  continua sob controle do Admin.
- Fora do escopo: produtor concluir etapas (afeta a elegibilidade de repasses da 5.13) e
  cobranca automatica de revisoes extras.

**Publicacao:** aplicar `d6f8b0c2e437` antes do release (tres tabelas novas e uma coluna com
padrao 0, aditivo).

### Publicacao da 5.10 (15/10/2026)

| Item | Valor |
| --- | --- |
| PRs na `main` | #47 (registro da 5.09) e #48 (5.10) |
| Commit publicado | `23c7b58b43193f8da15a1268979112f7f2e985a2` |
| Migration | `d6f8b0c2e437`, aplicada pelo responsavel no SQL Editor do Supabase antes do release; conferida (tres tabelas de politicas e `producao_etapas.revisoes_usadas` com padrao 0, nenhuma etapa alterada) |
| CI da `main` | Storage Integration Gate `38746570385`, Portals E2E e Client access migration verdes (o gate dos PRs #47 e #48 foi repetido por falha ao baixar imagem Docker; no #48 tambem houve linha em branco no fim de arquivo, corrigida) |
| Storage Provider Rollout Evidence | run `38747574863` (sucesso) |
| Protected Production Release | run `38749661557`, `publish`, `commercial_pipeline_v2=true` (sucesso, smokes finais verdes) |
| Autorizacao | `CTRL-20261015-R3-510` |

## Ajuste do catalogo (pedido do responsavel em 15/10/2026)

Antes da 5.11, a pedido do responsavel: o servico deixa de escolher "avulso ou combo" e as
secoes de texto livre viram limites que o sistema aplica (migration `e8a0c2d4f659`).

- Servico (sempre avulso): "O que o servico inclui" com campos tipados.
  - Faixas enviadas pelo cliente e duracao maxima por faixa: viram a cota de materiais do
    cliente (5.09). O servidor le a duracao do audio (MP3, WAV, FLAC, M4A, com `mutagen`) e
    recusa faixas acima do limite do contrato, ou audios cuja duracao nao pode ser lida.
  - Revisoes incluidas: valem na ultima etapa do servico (a entrega); o editor de etapas
    deixa de ter revisoes por etapa. A contagem e a politica de excedentes seguem a 5.10.
  - Melodias e artistas: so exibicao; a conferencia e do estudio, ouvindo.
  - Destaques: textos curtos sem limite (ex.: "Instrumentos eletronicos").
  - Estrutura v2 em `estrutura_servico` (`versao`, `intro`, `destaques`, `limites`); o
    formato antigo (secoes/beneficios) e convertido na leitura e ao salvar.
- Combo (catalogo da 5.08): ganha subtitulo, descricao de ate 1000 caracteres, escolha de
  desconto e destaques; preco editavel. Combos ativos aparecem no site (`GET /catalogo/combos`)
  com o que cada servico inclui; limites, etapas, cotas e politicas vem dos servicos. Na
  calculadora, os parametros do combo sao a uniao dos parametros dos servicos.
- Servicos antigos marcados como combo ("Launch", "Legend") ficam guardados e saem do site;
  o Admin os identifica como "Combo antigo". O Launch e recriado como combo novo
  (Instrumental + Mixagem + Masterizacao, mesmo preco e desconto) pelo SQL de dados.
- Fora do escopo: limites contratados a mais pela calculadora (ex.: mais canais pagos)
  continuam ajustados pelo Admin na producao (excecao de cotas/politicas).

**Publicacao:** rodar `e8a0c2d4f659` antes do release; o SQL de dados (conversao das secoes,
cotas derivadas e combo Launch) depois do release, conferindo o conteudo de cada servico.

### Publicacao do ajuste do catalogo (15/10/2026)

| Item | Valor |
| --- | --- |
| PRs na `main` | #50 (registro da 5.10) e #49 (catalogo) |
| Commit publicado | `c87ab414257dfb7faa059505c5f1ae1f83ccff3a` |
| Migration | `e8a0c2d4f659`, aplicada pelo responsavel no SQL Editor do Supabase |
| Dados | SQL de dados rodado pelo responsavel junto com a migration, antes do release: Mixagem, Letra, Instrumental e Masterizacao no formato novo; cotas de materiais (Mixagem 5 faixas/3 min; Instrumental e Masterizacao 3 min); combo "Launch" recriado (Instrumental + Mixagem + Masterizacao, com desconto). Entre o SQL e o release os cards do site ficaram sem limites/destaques |
| CI da `main` | Storage Integration Gate `38751905240`, Portals E2E e Client access migration verdes |
| Storage Provider Rollout Evidence | run `38752852078` (sucesso) |
| Protected Production Release | run `38753370096`, `publish`, `commercial_pipeline_v2=true` (sucesso, smokes finais verdes) |
| Conferencia | `GET /catalogo/combos` em producao lista "Start" e "Launch" com os servicos e os parametros unidos |
| Autorizacao | `CTRL-20261015-R3-CAT` |

## Novos itens do roadmap (pedido do responsavel em 15/10/2026)

Itens 5.14 a 5.22, com as sugestoes aceitas pelo responsavel. As fases 5.11 a 5.13
(creditos e repasses 80/20) continuam no roadmap; a ordem entre as duas trilhas e
decidida a cada fase.

### Ordem sugerida

| Ordem | Fase | Setores | Complexidade | Depende de |
| --- | --- | --- | --- | --- |
| 1 | 5.14 Entrega final so com quitacao | S06 / S07 / S08 | Media | 5.05 (politica de pagamento) |
| 2 | 5.15 Contato do cliente para o produtor | S07 / S08 / S09 | Baixa | 5.07, 5.10 |
| 3 | 5.16 Cards do catalogo (site e calculadora) | S01 / S04 | Baixa-media | ajuste do catalogo |
| 4 | 5.17 Promocoes de servicos e combos | S04 / S05 | Media | 5.16 |
| 5 | 5.18 Notificacoes nos portais | S07 / S08 / S11 | Media | 5.03 |
| 6 | 5.19 Creditos de produtores no portfolio | S02 / S09 | Media | - |
| 7 | 5.20 Produtor envia projetos ao portfolio | S02 / S08 | Media | 5.19 |
| 8 | 5.21 Tag automatica nas previas | S07 / S08 / S12 | Alta | 5.09 (leitura de audio) |
| 9 | 5.22 Catalogo interno de beats | S04 / S05 / S07 / S08 | Alta | 5.21, 5.16, 5.17 |

### 5.14 - Entrega final so com quitacao
- Hoje nada impede baixar a entrega final com saldo pendente. Com politica 50/50 e saldo
  em aberto, o cliente ve que a entrega existe ("pronta, aguardando pagamento") e o link de
  pagamento, mas o download de arquivos `entrega` e recusado pelo servidor.
- Liberacao automatica quando o segundo pagamento for confirmado (webhook do Mercado Pago),
  idempotente. Excecao do Admin com motivo obrigatorio e auditoria para acordos fora do
  sistema. Previas continuam liberadas.

### 5.15 - Contato do cliente para o produtor
- Nome, e-mail e WhatsApp do cliente no detalhe da producao do Portal do Produtor, somente
  para quem trabalha nela (coordenador e responsaveis de etapa, 5.07).
- Nova politica (5.10) para o Admin esconder o contato quando quiser intermediar.

### 5.16 - Cards do catalogo (site e calculadora)
- Um componente unico de card: o servico avulso no formato do card de combo.
- Na calculadora, cards no estilo do Admin, com informacoes do cliente: preco, o que inclui
  e prazo; sem dados internos (etapas com valores, cotas avancadas, politicas).

### 5.17 - Promocoes de servicos e combos
- Promocao por servico avulso ou combo: percentual especial, inicio e fim opcionais, ativa
  ou nao.
- Decisao do responsavel: nao soma com o desconto geral; vale o maior dos dois.
- Card com preco riscado e selo de promocao; a calculadora usa o preco promocional.
- O preco promocional fica congelado na proposta enviada (snapshot da 5.05).

### 5.18 - Notificacoes nos portais
- Notificacoes por usuario (cliente e produtor) com "vista em". Ao abrir o portal, as nao
  vistas aparecem uma vez na tela; um sino guarda o historico.
- Eventos iniciais: nova mensagem, nova previa ou entrega, etapa concluida, pagamento
  confirmado, proposta enviada, revisao liberada, entrega liberada (5.14).
- Cada evento vira notificacao no portal e, quando fizer sentido, o e-mail que ja existe.

### 5.19 - Creditos de produtores no portfolio
- Projetos do portfolio com produtores responsaveis e funcoes de uma lista fixa (producao,
  mixagem, masterizacao, composicao, gravacao, beat, outra com texto).
- Aceita colaborador externo sem conta (apenas nome). Exibicao dos creditos no site; base
  para uma pagina por produtor no futuro.

### 5.20 - Produtor envia projetos ao portfolio
- Area no Portal do Produtor para propor um projeto ao portfolio: entra como rascunho e so
  e publicado com aprovacao do Admin; quem enviou ja entra nos creditos (5.19).
- Pode ser ligado a uma producao do estudio (sem duplicar dados) e exige confirmar a
  autorizacao do artista para publicar.

### 5.21 - Tag automatica nas previas
- Cada produtor cadastra a propria tag de audio no perfil; existe uma tag padrao do estudio
  para quem nao tiver. O Admin define o intervalo (padrao 10 segundos) e o volume da tag.
- Previas de audio enviadas na producao ganham uma versao com tag, gerada em segundo plano
  (aviso de "processando"); o cliente recebe a versao com tag e o original fica so para o
  estudio. A entrega final nunca leva tag.

### 5.22 - Catalogo interno de beats
- Produtores com permissao "painel de beats" (definida pelo Admin no cadastro do usuario)
  enviam beats para revisao; aprovados, aparecem num catalogo visivel apenas para clientes
  logados, ouvidos com tag (5.21).
- Decisao do responsavel: cada beat pode ser comprado como exclusivo ou lease (precos
  proprios). Na compra exclusiva o beat sai do catalogo; o lease pode ser vendido varias
  vezes enquanto o beat nao for vendido como exclusivo.
- Compra pelo fluxo atual: o beat vira item de proposta, como um servico, com promocoes
  (5.17) e regras de pagamento existentes.
