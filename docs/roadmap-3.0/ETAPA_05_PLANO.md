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

### Ordem de merge

Se o PR #26 (classificacao de testes, migration `d8a7b1c9e240`) entrar antes, trocar
`down_revision` de `a7d3e5f9c210` para `d8a7b1c9e240` e atualizar os testes que fixam o
head do Alembic.
