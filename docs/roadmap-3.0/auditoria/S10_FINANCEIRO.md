# Auditoria setorial - S10 Financeiro

Status do setor: **DIAGNOSTICADO**. Mudancas derivadas: [Etapa 07](../ETAPA_07_APLICACAO_AUDITORIA.md).

## 1. Baseline

| Campo | Valor |
| --- | --- |
| SHA | `18caa5b` (main) |
| Data | 24/10/2026 |
| Ambiente | Leitura estatica; suites `financeiro_admin`, `dashboard`, `service_credits`, `credit_allocations`, `stage_payouts` verdes |
| Limitacoes | Suites Python nao rodam localmente; sem acesso a dados financeiros individuais |

## 2. Inventario

- Admin: `GET /financeiro/resumo`, `/cobrancas`, `/cobrancas/{id}`;
  `POST /financeiro/cobrancas/{id}/pagamentos-manuais` (Pix direto, idempotente);
  `POST /financeiro/pagamentos/{id}/reconciliar`.
- Repasses: `/producoes/{id}/repasse*` (valor unico) e repasse por etapa 80/20 (5.13).
- Creditos de servico (5.11-5.12): carteira do cliente, alocacao por producao,
  movimentos (reserva, consumo, devolucao).
- Servicos: `financial_service`, `financeiro_admin_service`, `repasse_produtor_service`,
  `carteira_creditos_service`, `credito_alocacao_service`, `credito_producao_service`,
  `producao_liberacao_service`.
- Tabelas: `cobrancas`, `pagamentos`, `repasses_produtor`, tabelas de creditos e alocacoes.

## 3. Fluxos

- Pagamento aprovado (provider ou Pix direto) -> `avaliar_cobranca_bloqueada`: confirma
  beats, credita carteira (propostas de creditos) ou cria a producao (pipeline V2).
- Pix direto: quitar saldo ou valor parcial, com referencia e chave de repeticao.
- Repasse simples: definir -> liberar -> pagar (com comprovante) -> correcao auditada.

## 4. Achados

| ID | Sev. | Categoria | Achado | Status |
| --- | --- | --- | --- | --- |
| AUD6-S10-001 | P2 | 4.7 | Pix direto registrado por engano nao tem estorno nem anulacao | Aberto |
| AUD6-S10-002 | P2 | 4.7 | Repasse simples pode ser liberado e pago sem a cobranca quitada nem a producao concluida | Aberto |
| AUD6-S10-003 | P2 | 4.11 / 4.8 | Nao ha fila de conciliacao: chargeback, reembolso parcial e divergencias ficam espalhados na lista | Aberto |
| AUD6-S10-004 | P3 | 4.1 | Liberar e pagar repasse nao travam a linha (cliques concorrentes geram auditoria duplicada) | Aberto |
| AUD6-S10-005 | P3 | 4.12 / S12 | `financeiro_admin.cjs` e `beat_preview.cjs` nao rodam no CI | Aberto |

### AUD6-S10-001 - Pix direto sem estorno (P2)

- Evidencia: `financeiro_admin_service.registrar_pix_manual` grava pagamento `aprovado`
  com `provider = manual_admin` e dispara liberacoes; nao existe rota ou servico para
  anular/estornar pagamento manual (busca por estorno/anulacao/reversao sem resultado).
- Impacto: valor ou cobranca errados liberam producao, entrega, beats ou creditos sem
  caminho seguro de correcao; restaria alterar o banco manualmente.
- Recomendacao: "Anular pagamento manual" com motivo obrigatorio, auditoria, recalculo da
  cobranca e revisao das liberacoes (mesma politica do reembolso, AUD6-S06-002).

### AUD6-S10-002 - Repasse sem trava de pagamento (P2)

- Evidencia: `repasse_produtor_service.release` e `mark_paid` so verificam o status do
  repasse; nao consultam a cobranca do cliente nem o status da producao.
- Impacto: pagar o produtor antes de receber do cliente (ou de concluir) por engano.
- Recomendacao: bloquear ou exigir confirmacao com motivo quando a cobranca nao estiver
  quitada; mostrar a situacao financeira do cliente na tela do repasse.

### AUD6-S10-003 - Fila de conciliacao (P2)

- Evidencia: situacoes "requer conciliacao" (divergencia, chargeback, reembolso parcial,
  tentativa externa pendente) so aparecem como filtro na lista de cobrancas; sem alerta.
- Recomendacao: fila dedicada com motivo legivel, contagem no dashboard e acao sugerida.

### P3

- **004**: `release`/`mark_paid` sem `with_for_update`; o status protege a transicao, mas
  dois cliques simultaneos podem registrar duas auditorias.
- **005**: suites existentes fora do CI (ver S12).

## 5-7. Corrigir, centralizar, implementar

- Corrigir: 001, 002.
- Centralizar: visao por cliente/producao (cobrancas, pagamentos, creditos, repasses).
- Candidatas: fila de conciliacao (003); registro guiado de pagamento externo.

## 8-10. Tutoriais, linguagem, links

- Tutorial: "Registrar pagamento externo no Admin" e "Quando liberar repasse".
- Links: cobranca -> proposta e producao; repasse -> cobranca do cliente.

## 11. Lacunas de teste

- Anulacao de Pix manual; repasse com cobranca aberta; concorrencia de liberacao.

## 12. Dependencias

- S06 (reembolso/chargeback), S09 (paginas centrais), S12 (CI).

## 13. Criterios de validacao

001 e 002 com regressao; fila de conciliacao definida; suites no CI.
