# Auditoria setorial - S04 Catalogo de servicos

Status do setor: **DIAGNOSTICADO**. Mudancas derivadas: [Etapa 07](../ETAPA_07_APLICACAO_AUDITORIA.md).

## 1. Baseline

| Campo | Valor |
| --- | --- |
| SHA | `18caa5b` (main) |
| Data | 24/10/2026 |
| Ambiente | Leitura estatica; `combos_admin`, `servico_etapas_admin`, `file_quotas`, `promocoes`, `catalogo`, `beat_preview` verdes; `flows.cjs` falha (ver 004) |

## 2. Inventario

- Servicos (estrutura v2, etapas, cotas, politicas, promocoes), combos, beats (envio pelo
  produtor, revisao e edicao pelo Admin, limites de upload, precos por licenca).

## 4. Achados

| ID | Sev. | Categoria | Achado | Status |
| --- | --- | --- | --- | --- |
| AUD6-S04-001 | P1 | 4.7 | Reserva de beat sem expiracao (registrado em AUD6-S06-001) | Ver S06 |
| AUD6-S04-002 | P3 | 4.11 / S11 | Aprovacao ou rejeicao de beat nao notifica o produtor | Aberto |
| AUD6-S04-003 | P3 | 4.7 | Beat aprovado pode ser rejeitado com licenca reservada; o pagamento posterior ainda libera os arquivos | Aberto |
| AUD6-S04-004 | P3 | 4.12 / S12 | `flows.cjs` desatualizado (Admin agora chama `/combos` e `/admin/audio-tag` ao iniciar) e fora do CI | Aberto |

### Detalhes

- **002**: `beat_service.review` grava status e auditoria; nenhuma chamada a
  `portal_notificacao_service`.
- **003**: `review` so bloqueia `vendido`; nao verifica `beat_licencas` reservadas.
  Recomendacao: impedir ou exigir decisao sobre as reservas.
- **004**: atualizar a lista esperada de chamadas e incluir a suite no CI.

## 5-13. Resumo

- Centralizar: "central de promocoes" e detalhe do item (candidatas da Etapa 06).
- Tutorial: explicacao de licencas (lease, WAV, multitrack, exclusivo).
- Dependencias: S06, S08, S11.
- Validacao: 002 e 003 com regressao; suite no CI.
