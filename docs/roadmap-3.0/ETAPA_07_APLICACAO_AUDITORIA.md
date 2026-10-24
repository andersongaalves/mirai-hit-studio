# Mirai Hit Studio 3.0 - Etapa 07: Aplicacao da auditoria

Roadmap **somente de mudancas** derivadas da auditoria setorial (Etapa 06). A auditoria
diagnostica; esta etapa decide, implementa, valida e publica. Nenhum item daqui e
implementado sem autorizacao do responsavel.

## 1. Checkpoint

| Campo | Estado atual |
| --- | --- |
| Status global | Backlog em formacao (auditoria em andamento) |
| Lote atual | Lote 1 - Seguranca de sessao |
| Item em andamento | APL-S02-01 (PR #96, em validacao) |
| Proxima acao | Concluir o CI do PR #96 e pedir autorizacao de merge/publicacao |
| Ultima atualizacao | 24/10/2026 |

## 2. Regras

- Cada item nasce de um achado `AUD6-*` e aponta para ele. Sem achado, nao entra.
- Um PR por item ou por grupo do mesmo setor; nunca misturar setores.
- Itens marcados **Decisao** param ate o responsavel escolher; a opcao escolhida e
  registrada na coluna antes de implementar.
- Migration: SQL entregue ao responsavel ou aplicada com autorizacao explicita, sempre
  antes do release (o release protegido nao roda migrations).
- Publicacao segue o fluxo da Etapa 05 (CI da main, evidencia de storage, dry-run,
  publish) e e registrada aqui.
- Ao fechar um item: status `Publicado`, PR e release. O achado na Etapa 06 passa a
  `Corrigido` e o setor so vira `VALIDADO` pela regra da Etapa 06, secao 11.

### Status

`Proposto` -> `Autorizado` -> `Em correcao` -> `Em validacao` -> `Publicado`;
ou `Decisao` (aguarda escolha), `Descartado` (com motivo).

## 3. Backlog por setor

### S02 - Identidade e acesso ([diagnostico](auditoria/S02_IDENTIDADE_ACESSO.md))

| ID | Origem | Sev. | Mudanca | Tipo | Status | PR |
| --- | --- | --- | --- | --- | --- | --- |
| APL-S02-01 | 001, 002 | P1 | Sessao vinculada ao id da conta (`uid`); renomear, desativar ou mudar papel encerra as sessoes | Codigo | Em validacao | #96 |
| APL-S02-02 | 003, 010, 013 | P2 | Entrada unica: paineis redirecionam a `/acesso?next=`; `next` validado por papel; remover logins antigos (inclui Enter e placeholder do Admin); `/acesso` com sessao valida oferece continuar | Codigo + testes de navegador | Proposto | - |
| APL-S02-03 | 005 | P2 | Admin > Usuarios: conta de cliente editavel (papel somente leitura, filtro "Cliente", link para o cadastro do cliente) | Codigo | Proposto | - |
| APL-S02-04 | 004 | P2 | Troca da propria senha (senha atual + nova, encerra outras sessoes, auditoria); texto de recuperacao para produtores e equipe | Codigo; **Decisao**: produtores passam a ter e-mail para recuperacao? | Decisao | - |
| APL-S02-05 | 006 | P2 | Login sem diferenciar maiusculas; unicidade por `lower(username)` (dados atuais sem colisao) | Migration; **Decisao** | Decisao | - |
| APL-S02-06 | 007 | P2 | Aplicar a CSP (sair do Report-Only) e "Sair de todos os dispositivos" | Codigo + S12; **Decisao** sobre a CSP | Decisao | - |
| APL-S02-07 | 008, 009 | P3 | Hash ficticio para login inexistente; limite de login por IP e por login em `auth_rate_limits` | Codigo | Proposto | - |
| APL-S02-08 | 011 | P3 | Portais exibem o nome de exibicao em vez do login | Codigo | Proposto | - |
| APL-S02-09 | 012 | P3 | `/auth/me` e login com campos minimos por papel | Codigo | Proposto | - |
| APL-S02-10 | 014 | P3 | Textos das telas de acesso (Privacidade como link, placeholder da senha, peso de "Esqueci minha senha", login apos ativacao, link expirado) | Codigo/texto | Proposto | - |
| APL-S02-11 | 015 | P3 | Aviso antes de expirar e renovacao da sessao em uso | **Decisao**: duracao e refresh | Decisao | - |
| APL-S02-12 | Centralizacao 5.1 | P3 | Menu da conta (perfil, seguranca e senha, sair, sair de todos os dispositivos, ajuda) | Codigo; depende de 04, 06, 08 | Proposto | - |

## 4. Lotes de execucao

Definidos ao fim da auditoria completa, por risco e dependencia entre setores.

| Lote | Tema | Itens | Status |
| --- | --- | --- | --- |
| 1 | Seguranca de sessao | APL-S02-01 | Em validacao |

## 5. Decisoes pendentes

| Item | Pergunta | Opcoes |
| --- | --- | --- |
| APL-S02-04 | Recuperacao de senha para produtores e equipe | (a) cadastrar e-mail nas contas internas; (b) manter reset so pelo Admin |
| APL-S02-05 | Login sem diferenciar maiusculas | (a) aplicar com migration de indice unico; (b) manter |
| APL-S02-06 | Aplicar a CSP | (a) aplicar apos revisar os relatorios; (b) manter Report-Only por mais um ciclo |
| APL-S02-11 | Duracao da sessao | (a) manter 60 min com aviso; (b) renovacao silenciosa em uso |

## 6. Historico

| Data | Item/lote | Resultado | Proxima acao |
| --- | --- | --- | --- |
| 24/10/2026 | Etapa 07 criada | Backlog do S02 registrado; APL-S02-01 em validacao no PR #96 | Incluir os itens dos demais setores conforme a auditoria avanca |
