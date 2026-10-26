# Mirai Hit Studio 3.0 - Etapa 07: Aplicacao da auditoria

Roadmap **somente de mudancas** derivadas da auditoria setorial (Etapa 06). A auditoria
diagnostica; esta etapa decide, implementa, valida e publica. Nenhum item daqui e
implementado sem autorizacao do responsavel.

## 1. Checkpoint

| Campo | Estado atual |
| --- | --- |
| Status global | Backlog completo (12 setores diagnosticados); execucao por lotes |
| Lote atual | Lotes 4 a 8 concluidos (exceto APL-S01-01) |
| Item em andamento | - |
| Proxima acao | Revisao da Politica de Privacidade (#125) pelo responsavel; camada 2 contra robos (Cloudflare) quando autorizada; limpeza das branches pelo responsavel |
| Ultima atualizacao | 25/10/2026 |

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
| APL-S02-01 | 001, 002 | P1 | Sessao vinculada ao id da conta (`uid`); renomear, desativar ou mudar papel encerra as sessoes | Codigo | Publicado | #96 |
| APL-S02-02 | 003, 010, 013 | P2 | Entrada unica: paineis redirecionam a `/acesso?next=`; `next` validado por papel; remover logins antigos (inclui Enter e placeholder do Admin); `/acesso` com sessao valida oferece continuar | Codigo + testes de navegador | Publicado | #102 |
| APL-S02-03 | 005 | P2 | Admin > Usuarios: conta de cliente editavel (papel somente leitura, filtro "Cliente", link para o cadastro do cliente) | Codigo | Publicado | #103 |
| APL-S02-04 | 004 | P2 | Troca da propria senha (senha atual + nova, encerra outras sessoes, auditoria); texto de recuperacao para produtores e equipe | Codigo + migration `e1a3c5d7f9b2` | Publicado | #128 (decisao a: e-mail nas contas internas; troca da propria senha) |
| APL-S02-05 | 006 | P2 | Login sem diferenciar maiusculas; unicidade por `lower(username)` (dados atuais sem colisao) | Migration `d8f0b2c4e6a3` | Publicado | #126 (decisao a) |
| APL-S02-06 | 007 | P2 | Aplicar a CSP (sair do Report-Only) e "Sair de todos os dispositivos" | Codigo + S12 | Publicado | #130 (CSP aplicada; checkout segue em Report-Only) e #134 (sair de todos os aparelhos) |
| APL-S02-07 | 008, 009 | P3 | Hash ficticio para login inexistente; limite de login por IP e por login em `auth_rate_limits` | Codigo | Publicado | #103 (hash ficticio) e #105 (limite por login) |
| APL-S02-08 | 011 | P3 | Portais exibem o nome de exibicao em vez do login | Codigo | Publicado | #103 |
| APL-S02-09 | 012 | P3 | `/auth/me` e login com campos minimos por papel | Codigo | Publicado | #103 |
| APL-S02-10 | 014 | P3 | Textos das telas de acesso (Privacidade como link, placeholder da senha, peso de "Esqueci minha senha", login apos ativacao, link expirado) | Codigo/texto | Publicado | #102 |
| APL-S02-11 | 015 | P3 | Aviso antes de expirar e renovacao da sessao em uso | Codigo | Publicado | #129 (decisao a: 60 min com aviso 5 min antes) |
| APL-S02-12 | Centralizacao 5.1 | P3 | Menu da conta (perfil, seguranca e senha, sair, sair de todos os dispositivos, ajuda) | Codigo; depende de 04, 06, 08 | Publicado | #134 (menu "Minha conta") |

### S06 - Checkout e pagamentos ([diagnostico](auditoria/S06_CHECKOUT_PAGAMENTOS.md))

| ID | Origem | Sev. | Mudanca | Tipo | Status | PR |
| --- | --- | --- | --- | --- | --- | --- |
| APL-S06-01 | S06-001, S04-001 | P1 | Prazo para reserva de licenca de beat com liberacao automatica; cancelar reserva quando proposta/cobranca for cancelada; acao do Admin "liberar reserva" com motivo | Codigo + migration (prazo) | Publicado | #97 |
| APL-S06-02 | S06-002 | P2 | Reembolso ou anulacao revoga licencas de beat da proposta; exclusivo volta ao catalogo apos decisao do Admin | Codigo | Publicado | #97 |
| APL-S06-03 | S06-004 | P2 | Downloads de beat por streaming ou URL assinada curta, sem carregar o arquivo inteiro na memoria | Codigo | Publicado | #133 (link assinado do R2, 120 s, hash conferido por HEAD) |
| APL-S06-04 | S06-005, S07-007 | P3 | Mensagens humanas para conflitos e indisponibilidade no checkout e nos portais | Codigo/texto | Publicado | #108 (checkout) e #121 (portal do cliente) |
| APL-S06-05 | S06-006, S06-007 | P3 | Catalogo de beats sem N+1; arquivo baixado com o titulo do beat | Codigo | Publicado | #108 |

### S10 - Financeiro ([diagnostico](auditoria/S10_FINANCEIRO.md))

| ID | Origem | Sev. | Mudanca | Tipo | Status | PR |
| --- | --- | --- | --- | --- | --- | --- |
| APL-S10-01 | S10-001 | P2 | Anular pagamento manual (Pix direto) com motivo, auditoria, recalculo da cobranca e revisao das liberacoes | Codigo | Publicado | #98 |
| APL-S10-02 | S10-002 | P2 | Repasse: bloquear ou exigir confirmacao com motivo quando a cobranca nao estiver quitada; mostrar situacao do cliente | Codigo | Publicado | #98 |
| APL-S10-03 | S10-003, S06-003 | P2 | Fila de conciliacao (divergencias, chargeback, reembolso parcial, tentativa externa pendente) com alerta no dashboard | Codigo | Publicado | #113 |
| APL-S10-04 | S10-004 | P3 | Travar a linha ao liberar/pagar repasse | Codigo | Publicado | #98 |

### S07 - Portal do Cliente ([diagnostico](auditoria/S07_PORTAL_CLIENTE.md))

| ID | Origem | Sev. | Mudanca | Tipo | Status | PR |
| --- | --- | --- | --- | --- | --- | --- |
| APL-S07-01 | S07-001 | P2 | Detalhe do projeto por secoes (visao geral, arquivos, mensagens, pagamento) com a pendencia principal no topo | Codigo | Publicado | #120 |
| APL-S07-02 | S07-002 | P3 | Resposta publica do beat sem campos internos | Codigo | Publicado | #109 |
| APL-S07-03 | S07-003, S08-004 | P3 | Botao "Envios" sem sobrepor conteudo (cabecalho ou espaco reservado) | Codigo | Publicado | #109 |
| APL-S07-04 | S07-004, S07-005 | P3 | Ocultar campos vazios; icones distintos no menu | Codigo | Publicado | #109 |
| APL-S07-05 | S07-006 | P3 | Limite diario de solicitacoes por cliente | Codigo | Publicado | #109 |

### S08 - Portal do Produtor ([diagnostico](auditoria/S08_PORTAL_PRODUTOR.md))

| ID | Origem | Sev. | Mudanca | Tipo | Status | PR |
| --- | --- | --- | --- | --- | --- | --- |
| APL-S08-01 | S08-001 | P2 | "Beats" unico (Meus beats / Catalogo) e tag dentro do perfil do produtor, com aviso no dashboard | Codigo; depende de APL-S02-12 | Publicado | #139 |
| APL-S08-02 | S08-002 | P2 | Falha de tag gera pendencia/aviso ao Admin com "Reprocessar" | Codigo; com APL-S11-01 | Publicado | #114 (lista no dashboard com Reprocessar; notificacao ao Admin segue com APL-S11-01) |
| APL-S08-03 | S08-003, S08-005 | P3 | Seletor de arquivo estilizado em portugues; "Enviar para revisao" dentro da etapa | Codigo | Publicado | #110 (seletor) e #118 (acao geral dentro do resumo) |
| APL-S08-04 | S08-007 | P3 | Nao permitir versionar arquivo oculto para o produtor | Codigo | Publicado | #110 |

### S09 - Administracao operacional ([diagnostico](auditoria/S09_ADMIN_OPERACIONAL.md))

| ID | Origem | Sev. | Mudanca | Tipo | Status | PR |
| --- | --- | --- | --- | --- | --- | --- |
| APL-S09-01 | S09-001 | P2 | Pendencias completas no dashboard (solicitacoes, beats e portfolio em revisao, falha de tag, conciliacao, entregas) | Codigo | Publicado | #107 |
| APL-S09-02 | S09-002 | P2 | Paginas centrais de cliente e produtor; links contextuais entre entidades | Codigo (grande) | Publicado | #140 (pagina do produtor; links cliente/producao/orcamento) |
| APL-S09-03 | S09-003, 004, 005 | P3 | Dashboard sem blocos repetidos; carregar secoes sob demanda; textos com acento e erros humanos | Codigo/texto | Publicado | #115 (acentos) e #135 (sem blocos repetidos; secoes sob demanda) |
| APL-S09-04 | S09-006 | P3 | Busca global | Codigo | Publicado | #136 |
| APL-S09-05 | S09-007 | P3 | `PUT /config` sem a linha `id=1` | Codigo | Publicado | #115 |

### S05 - Propostas ([diagnostico](auditoria/S05_PROPOSTAS.md))

| ID | Origem | Sev. | Mudanca | Tipo | Status | PR |
| --- | --- | --- | --- | --- | --- | --- |
| APL-S05-01 | S05-001 | P2 | Validade da proposta: aplicar (status "expirada" e reenvio com valores atuais) ou retirar a frase do PDF | Codigo | Publicado | #127 (decisao a: status "expirada" e "Reabrir para atualizar") |
| APL-S05-02 | S05-002 | P3 | Comparacao entre versoes | Codigo | Publicado | #138 (migration `f2b4d6e8a0c3`) |

### S03 - Orcamentos ([diagnostico](auditoria/S03_ORCAMENTOS.md))

| ID | Origem | Sev. | Mudanca | Tipo | Status | PR |
| --- | --- | --- | --- | --- | --- | --- |
| APL-S03-01 | S03-001 | P2 | Recalcular o orcamento no servidor a partir da selecao; Admin ve "estimado pelo visitante" separado | Codigo | Publicado | #99 |
| APL-S03-02 | S03-002 | P3 | Campo isca e limite persistente no formulario publico | Codigo; com APL-S12-03 | Publicado | #119 (campo isca; limite persistente ja no #105) |

### S04 - Catalogo ([diagnostico](auditoria/S04_CATALOGO.md))

| ID | Origem | Sev. | Mudanca | Tipo | Status | PR |
| --- | --- | --- | --- | --- | --- | --- |
| APL-S04-01 | S04-002, S11-002 | P3 | Notificar o produtor na aprovacao/rejeicao do beat | Codigo | Publicado | #124 |
| APL-S04-02 | S04-003 | P3 | Impedir rejeitar beat com licenca reservada sem decidir a reserva | Codigo | Publicado | #111 |

### S01 - Institucional ([diagnostico](auditoria/S01_INSTITUCIONAL.md))

| ID | Origem | Sev. | Mudanca | Tipo | Status | PR |
| --- | --- | --- | --- | --- | --- | --- |
| APL-S01-01 | S01-001 | P2 | Pagina de Politica de Privacidade e links (rodape, consentimento, cadastro, orcamento, newsletter) | **Decisao** (texto revisado pelo responsavel) | Em validacao | #125 (texto redigido; publica apos revisao do responsavel) |
| APL-S01-02 | S01-002 | P3 | Area clicavel minima nos links de verticais do portfolio | Codigo | Publicado | #112 |

### S11 - IA e comunicacao ([diagnostico](auditoria/S11_IA_COMUNICACAO.md))

| ID | Origem | Sev. | Mudanca | Tipo | Status | PR |
| --- | --- | --- | --- | --- | --- | --- |
| APL-S11-01 | S11-001, S11-002 | P2 | Notificacoes para o Admin e eventos faltantes (beat revisado, falha de tag, portfolio proposto, solicitacao de producao) | Codigo + migration (papel admin) | Publicado | #124 (migration `c6e8a0b2d4f1`) |

### S12 - Infraestrutura ([diagnostico](auditoria/S12_INFRAESTRUTURA.md))

| ID | Origem | Sev. | Mudanca | Tipo | Status | PR |
| --- | --- | --- | --- | --- | --- | --- |
| APL-S12-01 | S12-001, S01-003, S04-004, S05-003, S10-005, S11-003 | P2 | Job de CI com as suites restantes; consertar `flows.cjs`, `public_accessibility.cjs` e `proposta_documento.cjs` | CI | Publicado | #116, #112 e #137 (proposta_documento e performance_h3 no gate) |
| APL-S12-02 | S12-002 | P2 | Worker de tag fora do processo web | Codigo | Publicado | #123 (decisao: manter no processo web, contido: ffmpeg 1 thread e baixa prioridade, uma previa por vez, limites, worker acorda com a fila) |
| APL-S12-03 | S12-003 | P2 | Limitador persistente (tabela `auth_rate_limits`) para login, orcamento e newsletter | Codigo; inclui APL-S02-07 | Publicado | #105 |
| APL-S12-04 | S12-005 | P3 | Estabilizar o passo instavel do Portals E2E | Testes | Em observacao | - (5 repeticoes locais de cada suite do passo sem falha; nao reproduzido) |
| APL-S12-06 | Pedido do responsavel | P3 | Aba "Uso" no Admin: memoria (Render), Supabase, Cloudinary e Cloudflare, com contagens da protecao contra robos | Codigo | Publicado | #131 |
| APL-S12-07 | Pedido do responsavel | P3 | Camada 1 contra robos na API: varreduras -> 404 e bloqueio de 15 min; excesso -> 429. Camada 2 (Cloudflare WAF/Bot Fight e subdominio da API) adiada pelo responsavel | Codigo | Publicado (camada 1) | #132 |
| APL-S12-05 | S12-006, S12-007 | P3 | Limpeza de branches descartaveis; README atualizado | Manutencao | Em correcao | #117 (README); limpeza de branches aguarda o responsavel |

## 4. Lotes de execucao

Ordem por risco e dependencia. Cada lote pode ter varios PRs (um por setor).

| Lote | Tema | Itens | Status |
| --- | --- | --- | --- |
| 1 | Seguranca de sessao | APL-S02-01 | Publicado (PR #96, 24/10/2026) |
| 2 | Integridade comercial e financeira | APL-S06-01, APL-S06-02, APL-S10-01, APL-S10-02, APL-S03-01 (+ APL-S10-04) | Publicado (PRs #97, #98, #99, 24/10/2026) |
| 3 | Entrada e conta | APL-S02-02, APL-S02-03, APL-S02-07 + APL-S12-03, APL-S02-08, APL-S02-09, APL-S02-10 | Publicado (PRs #102, #103 e #105; concluido em 25/10/2026) |
| 4 | Visibilidade da operacao | APL-S09-01, APL-S11-01, APL-S08-02, APL-S10-03, APL-S04-01 | Publicado (R8) |
| 5 | Confiabilidade e CI | APL-S12-01, APL-S12-02, APL-S12-04, APL-S06-03 | Publicado (R8); APL-S12-04 em observacao |
| 6 | Experiencia dos portais | APL-S07-01, APL-S02-12, APL-S08-01, APL-S02-04 (apos decisao), APL-S07-03, APL-S07-04, APL-S08-03 | Publicado (R8) |
| 7 | Conformidade e decisoes | APL-S01-01, APL-S05-01, APL-S02-05, APL-S02-06, APL-S02-11 | Publicado (R8), exceto APL-S01-01 em revisao |
| 8 | Refinamentos | Demais P3 (S04-02, S06-04, S06-05, S07-02, S07-05, S08-04, S09-02 a 05, S10-04, S01-02, S03-02, S05-02, S12-05) | Publicado (R7/R8) |

## 5. Decisoes

| Item | Pergunta | Decisao (25/10/2026) |
| --- | --- | --- |
| APL-S02-04 | Recuperacao de senha para produtores e equipe | (a) e-mail nas contas internas |
| APL-S02-05 | Login sem diferenciar maiusculas | (a) indice unico em `lower(username)` |
| APL-S02-06 | Aplicar a CSP | (a) aplicada; `/checkout` segue em Report-Only |
| APL-S02-11 | Duracao da sessao | (a) 60 min com aviso |
| APL-S05-01 | Validade de 10 dias | (a) status "expirada" e reenvio |
| APL-S01-01 | Politica de Privacidade | Texto redigido (controlador, e-mail e cidade; sem CPF); publica apos revisao |
| APL-S12-02 | Worker de tag | Manter no processo web, contido; sem servico novo |

## 6. Historico

| Data | Item/lote | Resultado | Proxima acao |
| --- | --- | --- | --- |
| 25/10/2026 | Lotes 4 a 8 e decisoes (R8) | PRs #123, #124, #126-#141 (exceto #125) publicados no SHA `07c346e2d942378137139dca965cc93a1f826fe9`: notificacoes do Admin e beat revisado (#124), login sem maiusculas (#126), validade da proposta (#127), e-mail das contas internas e troca de senha (#128), aviso de sessao (#129), CSP aplicada (#130), aba Uso (#131), protecao contra varredura (#132), download direto do R2 (#133), menu Minha conta e sair de todos (#134), dashboard enxuto e secoes sob demanda (#135), busca global (#136), suites restantes no gate (#137), comparacao de versoes (#138), Beats unico (#139), pagina do produtor e links (#140), cadastro com e-mail de cliente existente recebe a confirmacao (#141, incidente do mesmo dia), worker contido (#123). Migrations `c6e8a0b2d4f1`, `d8f0b2c4e6a3`, `e1a3c5d7f9b2` e `f2b4d6e8a0c3` aplicadas no Supabase antes da publicacao. Gate `40246783227`, evidencia Storage `40248089894`, dry-run `40248198223` e publicacao `40248256757` aprovados. Ref. `CTRL-20261025-R8-ETAPA07-DECISOES`; Commercial V2 permaneceu `true` | Revisao da Politica de Privacidade (#125) |
| 25/10/2026 | Lotes 4 a 8 (sem migration) | PRs #107-#121 publicados no SHA `ee2f6b34c4c5af57c9769112426353d59e9d21cf`: pendencias do dashboard (#107), fila de conciliacao (#113), falhas de tag com Reprocessar (#114), detalhe do projeto por secoes (#120), mensagens claras no checkout e no portal (#108, #121), catalogo sem campos internos e limite diario (#109), refinamentos do produtor (#110, #118), beat reservado nao pode ser rejeitado (#111), alvos de toque (#112), `/config` sem 500 e acentos (#115), 18 suites a mais no gate (#112, #116), README (#117), campo isca (#119). Sem migration. Gate `40205419764`, evidencia Storage `40206403229`, dry-run `40206510344` e publicacao `40206565321` aprovados. Ref. `CTRL-20261025-R7-ETAPA07-LOTES4A8`; Commercial V2 permaneceu `true` | APL-S11-01/APL-S04-01 com migration autorizada; restante de APL-S09-03 e APL-S12-01 |
| 25/10/2026 | APL-S09-01 | PR #107 aberto: dashboard passa a reunir solicitacoes, revisoes de beats e portfolio, falhas de tag, conciliacoes e entregas aguardando aprovacao; cadeias de teste ficam fora das contagens | Validar CI e integrar sem misturar os demais setores do Lote 4 |
| 25/10/2026 | Lote 3 concluido | #105 publicou APL-S12-03 e a parte restante de APL-S02-07 no SHA `4ab947b51d2febe0d08ddcd54810e565c2d98c74`. Migration `b5d7f9a1c328` ja estava aplicada no Supabase. Gate `40189023647`, evidencia Storage `40189744411`, dry-run `40189876701` e publicacao `40189945225` aprovados; Render, Cloudflare Pages e smoke de producao verdes. Ref. `CTRL-20261025-R6-LOTE3`; Commercial V2 permaneceu `true` | Iniciar Lote 4 por APL-S09-01 |
| 24/10/2026 | Lote 3 (parcial) | #102: entrada unica pelo /acesso (paineis sem login proprio, next validado por papel, "Continuar" com sessao existente, aviso de sessao expirada, textos de acesso, ativacao entra direto) e 27 suites de navegador migradas; #103: conta de cliente em Usuarios, nome de exibicao nos portais, /auth/me minimo, hash ficticio no login. Publicacao `40147407737` (main `8592ff4`), ref. CTRL-20261024-R5-LOTE3, sem migration | APL-S12-03 |
| 24/10/2026 | Publicacao Lotes 1 e 2 | PRs #95-#99 mesclados (main `7e5b961`). Migration `a4c6e8f0b217` aplicada no Supabase; o DDL de `f3c5d7e9a102` ja existia em producao e so faltava a marca de versao. Evidencia de Storage `40135306198`, dry-run `40135395145`, publicacao `40135448716` (Render, Cloudflare Pages e smoke verdes), ref. CTRL-20261024-R4-ETAPA07 | Lote 3 |
| 24/10/2026 | Lote 2 | PRs #97 (S06: prazo da reserva de beat, liberar reserva, reembolso revoga licenca, devolver ao catalogo; migration `a4c6e8f0b217`), #98 (S10: anular Pix direto, motivo para repasse sem quitacao, trava de linha) e #99 (S03: preco do orcamento recalculado no servidor). Nao existe fluxo de cancelamento de proposta/cobranca; a reserva e liberada por prazo ou pelo Admin | Merge/publicacao dependem de autorizacao explicita |
| 24/10/2026 | Backlog completo | 12 setores diagnosticados; 49 itens em 8 lotes (2 P1 distintos, 26 P2 de origem); 6 decisoes pendentes | Autorizar merge/publicacao do PR #96 e o Lote 2 |
| 24/10/2026 | Etapa 07 criada | Backlog do S02 registrado; APL-S02-01 em validacao no PR #96 | Incluir os itens dos demais setores conforme a auditoria avanca |
