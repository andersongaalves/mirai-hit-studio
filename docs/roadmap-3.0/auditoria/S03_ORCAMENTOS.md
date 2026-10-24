# Auditoria setorial - S03 Orcamentos

Status do setor: **DIAGNOSTICADO**. Mudancas derivadas: [Etapa 07](../ETAPA_07_APLICACAO_AUDITORIA.md).

## 1. Baseline

| Campo | Valor |
| --- | --- |
| SHA | `18caa5b` (main) |
| Data | 24/10/2026 |
| Ambiente | Leitura estatica; `catalogo`, `promocoes`, `public_contracting` verdes |

## 2. Inventario

- Publico: `calculadora.html`, `POST /orcamentos` (limite 5/10 min por IP, idempotencia).
- Admin: lista, filtros, detalhe, criacao de proposta a partir do orcamento.
- O total e calculado no navegador e enviado em `valor_total`.

## 3. Fluxos

Visitante escolhe servicos/combos -> envia contato -> Admin analisa -> cria proposta
(rascunho) com o valor do orcamento como item inicial.

## 4. Achados

| ID | Sev. | Categoria | Achado | Status |
| --- | --- | --- | --- | --- |
| AUD6-S03-001 | P2 | 4.7 / 4.12 | O rascunho da proposta nasce com o valor enviado pelo navegador do visitante (`valor_total`), sem recalculo no servidor | Aberto |
| AUD6-S03-002 | P3 | 4.6 | Formulario publico sem protecao anti-spam alem do limite por IP em armazenamento local do processo | Aberto |

### AUD6-S03-001 - Valor do visitante vira preco da proposta (P2)

- Evidencia: `OrcamentoCreate.valor_total` aceita qualquer valor >= 0;
  `proposta_service.criar_por_orcamento` usa `orcamento.valor_total` como `valor_unitario`
  do item inicial.
- Impacto: um pedido adulterado chega com preco baixo; se o Admin nao revisar o item, a
  proposta sai com valor errado.
- Recomendacao: enviar a selecao (ids de servico/combo e parametros) e recalcular no
  servidor; exibir no Admin "valor estimado pelo visitante" separado do preco de catalogo.

### P3

- **002**: campo isca (honeypot) e limite em `auth_rate_limits` (persistente).

## 5-13. Resumo

- Candidatas: resumo fixo, rascunho salvo, recomendacao de combos.
- Lacunas de teste: recalculo no servidor com payload adulterado.
- Dependencias: S04 (catalogo/promocoes), S05.
- Validacao: 001 com teste de contrato.
