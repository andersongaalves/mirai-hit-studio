# Auditoria comercial V2 - Fase 3.7

## Decisao

- FASE 3.7: BLOCKED
- COMERCIAL V2: NAO PRONTA PARA HOMOLOGACAO OPERACIONAL
- Flag: `COMMERCIAL_PIPELINE_V2_ENABLED=false`

O dominio integrado foi aprovado pelos testes locais e pelo workflow PostgreSQL 17 da
`main`. A ativacao permanece bloqueada porque as propostas historicas receberam
`entrada_50_50` por backfill conservador e ainda nao foram conciliadas contra os
contratos reais. Nenhum dado de producao foi consultado ou alterado nesta auditoria.

## Evidencias

- Base auditada: `2d83c8047c76614264cee2d4804fbf13a6740fc7`.
- Alembic head unico esperado: `c5f2a7d9e184`.
- Testes locais focados: 63 passed, 0 failed.
- GitHub Actions `Portals E2E PostgreSQL 17`, run `37852223431`: success.
- O workflow executou PostgreSQL 17, bootstrap, Alembic, testes de concorrencia,
  FastAPI real, Playwright e limpeza dos dados sinteticos.
- Providers externos foram simulados; nenhum pagamento, e-mail ou dado comercial
  real foi utilizado.

## Jornada auditada

1. Proposta enviada habilita acesso, convite e leitura autenticada pelo Cliente.
2. Com V2 ativa, aceite/recusa valida ownership e trava orcamento antes da proposta.
3. Aceite cria ou reutiliza uma unica cobranca e nao cria Producao.
4. Checkout autenticado deriva cliente, valor e opcoes no backend.
5. Resultado do provider valida provider, ordem, referencia, moeda, valor e status.
6. Webhook/reconciliacao persistem Pagamento e sincronizam Cobranca na mesma
   unidade transacional usada para avaliar a liberacao.
7. `producao_liberacao_service` cria no maximo uma Producao quando a proposta esta
   aceita, a cobranca e valida e o valor aprovado satisfaz a politica.
8. Portal Cliente e Portal Produtor reutilizam a mesma Producao com ownership no
   backend.

## Integridade e seguranca

- `integral`: exige valor aprovado igual ou superior ao total.
- `entrada_50_50`: usa a divisao monetaria autoritativa do backend.
- Pagamentos pending/recusados nao liberam Producao.
- Eventos duplicados e reconciliacao concorrente convergem pela transacao, locks e
  unicidade da Producao por orcamento.
- Reembolso/chargeback nao apagam uma Producao existente; exigem conciliacao.
- O browser nao informa valor autoritativo nem dispara a criacao da Producao.
- Checkout guest permanece fallback legado por referencia opaca.
- Rotas autenticadas derivam `cliente_id` do usuario atual e falham fechadas para
  recursos alheios.
- Tokens, secrets, PII e referencias privadas do provider nao devem aparecer em
  logs ou respostas publicas.

## Achados

### BLOCKER - politicas historicas nao conciliadas

O backfill de `politica_pagamento` nao prova a modalidade contratada. Propostas com
Producao existente nao devem ser reavaliadas; propostas sem Producao precisam ser
classificadas antes da ativacao. A conciliacao deve usar documento/decisao comercial
humana, nunca URLs, `pagamentos_json` ou heuristica.

### MEDIUM - observabilidade operacional distribuida

Existem audit logs e logs tecnicos nos pontos criticos, mas nao ha um painel unico
para a jornada. O rollout deve agregar os indicadores listados no runbook antes de
ser considerado estavel. Nao foi adicionada instrumentacao nesta fase para evitar
alterar o produto sem uma plataforma de metricas definida.

## Inventario historico sanitizado

Executar somente com acesso administrativo autorizado, em sessao read-only, e
registrar apenas contagens agregadas:

- propostas por status e politica;
- propostas com/sem cobranca;
- propostas com/sem Producao;
- propostas por faixa de valor aprovado versus limite de inicio;
- pagamentos por estado agregado;
- propostas aceitas sem Producao e propostas com Producao sem pagamento suficiente.

Classificacao:

- Producao existente: preservar; nao reavaliar nem recriar.
- Contrato comprovadamente integral: corrigir por operacao administrativa revisada.
- Contrato comprovadamente 50/50: manter.
- Evidencia ambigua: bloquear ativacao para o registro e exigir revisao individual.

## Riscos residuais

- Provider Mercado Pago real nao foi chamado nesta auditoria.
- Nenhuma proposta historica real foi classificada.
- Ativar e depois desligar a V2 pode deixar propostas aceitas com cobranca, mas sem
  Producao; o rollback exige conciliacao, nao apenas troca de flag.
- Storage real nao faz parte da prova comercial deste relatorio.

## LeanDev

Foram abertos somente configuracao, dominio comercial, financeiro, checkout,
Mercado Pago, acesso do Cliente, testes relacionados e workflows E2E. A busca por
simbolos precedeu as leituras. Nao houve auditoria geral, refatoracao, migration,
artefato `.codex/lean-dev`, deploy ou alteracao em arquivos protegidos.
