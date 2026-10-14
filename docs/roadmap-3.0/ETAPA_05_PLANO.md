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

Cadeia final: `c5f2a7d9e184` -> `a7d3e5f9c210` (5.02, observacoes) -> `d8a7b1c9e240`
(Etapa 01, classificacao de testes). As duas sao aplicadas juntas no proximo release
protegido.

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
