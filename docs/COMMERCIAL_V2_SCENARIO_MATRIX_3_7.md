# Matriz de cenarios comerciais V2 - Fase 3.7

| Fluxo | Estado inicial | Operacao | Resultado esperado | Evidencia |
| --- | --- | --- | --- | --- |
| Aceite V2 | enviada, sem cobranca | Cliente aceita | aceita + uma cobranca; sem Producao | unitario + PG17 E2E |
| Aceite duplicado | enviada/aceita | dois aceites | uma cobranca; estado consistente | PG17 concorrencia |
| Recusa | enviada | Cliente recusa | recusada; sem cobranca nova/Producao | unitario |
| Integral parcial | aceita, integral | aprovado abaixo do total | sem Producao | unitario |
| Integral completa | aceita, integral | aprovado >= total | uma Producao | unitario + PG17 |
| Entrada insuficiente | aceita, 50/50 | aprovado abaixo da entrada | sem Producao | unitario |
| Entrada suficiente | aceita, 50/50 | aprovado >= entrada | uma Producao | unitario + PG17 |
| Saldo posterior | Producao existente | pagamento do saldo | nenhuma Producao adicional | unitario |
| Pagamento pending | aceita | provider pending | tentativa pendente; sem Producao | unitario |
| Pagamento recusado | aceita | provider recusa | tentativa falha; cobranca disponivel | unitario |
| Identidade divergente | aceita | moeda/ref/ordem/valor diverge | rollback; sem liberacao | unitario |
| Webhook duplicado | pagamento persistido | mesmo evento novamente | no-op idempotente | unitario + PG17 |
| Reconciliacao | webhook ausente | provider confirma | pagamento sincronizado; uma Producao | unitario + PG17 |
| Webhook + reconciliacao | aceita | confirmacoes concorrentes | uma Producao | PG17 concorrencia |
| Reembolso | Producao existente | refund | financeiro sinaliza; Producao preservada | unitario |
| Chargeback | Producao existente | chargeback | conflito/intervencao; Producao preservada | unitario |
| Proposta cancelada | cancelada | pagamento/evento tardio | sem nova Producao | unitario |
| Cobranca cancelada | aceita | avaliar liberacao | sem nova Producao | unitario |
| Ownership Cliente | Cliente A/B | A solicita recurso de B | resposta segura sem dados | portal E2E |
| Ownership Produtor | Produtor A/B | A solicita Producao de B | acesso negado | portal E2E |
| Checkout autenticado | Cliente autenticado | abre/paga | valores e identidade do backend | unitario + browser E2E |
| Checkout guest | referencia opaca | abre fluxo legado | fallback preservado com flag OFF | regressao |
| Flag OFF | producao atual | aceite Admin | comportamento legado preservado | unitario |
| Flag ON | proposta enviada | aceite | cobranca sem Producao prematura | unitario |
| Historico com Producao | Producao existente | avaliar politica | retorna existente; nao recria | unitario |
| Historico ambiguo | backfill 50/50 | preflight | revisao administrativa obrigatoria | pendente operacional |

## Cobertura executada

- Local, SQLite/fakes: 63 passed em proposta, financeiro, checkout, provider,
  webhooks, acesso, recovery e portais.
- GitHub Actions run `37852223431`: PostgreSQL 17, Alembic, concorrencia,
  FastAPI real e Playwright, success.
- Integracoes externas: simuladas somente nas fronteiras.
- Producao: nenhuma escrita e nenhum pagamento real.
