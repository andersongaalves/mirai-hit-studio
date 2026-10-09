# Runbook de rollout da pipeline comercial V2

## Regra de ouro

Manter `COMMERCIAL_PIPELINE_V2_ENABLED=false` ate todos os gates abaixo serem
aprovados. A mudanca da flag nao substitui conciliacao nem rollback de dados.

## Pre-requisitos

1. `main` aprovada, Alembic em `c5f2a7d9e184` e CI PostgreSQL 17 verde.
2. Backup externo recente, checksum verificado e restore drill valido.
3. Ambiente com credenciais Mercado Pago corretas e webhook assinado.
4. URLs publicas, CORS, Resend e checkout legado saudaveis.
5. Inventario historico sanitizado concluido e revisado pelo Admin.
6. Nenhuma proposta historica ambigua elegivel para operacao automatica.
7. Responsavel operacional, janela de mudanca e canal de incidente definidos.

## Preflight historico

Executar consultas agregadas em transacao read-only. Nao exportar PII, valores por
cliente, textos, tokens ou referencias privadas. Revisar:

- status e politica de propostas;
- existencia de cobranca e Producao;
- pagamentos aprovados agregados contra o limite de inicio;
- propostas aceitas sem Producao;
- Producao sem evidencia financeira suficiente;
- cobrancas/pagamentos em conflito ou reconciliacao.

Preservar Producao historica existente. Corrigir politica somente com evidencia
contratual e dupla revisao. Registro ambiguo permanece bloqueado.

## Ativacao

1. Congelar alteracoes comerciais durante a janela.
2. Confirmar backup e estado do banco imediatamente antes da mudanca.
3. Confirmar health, head Alembic e flag ainda desligada.
4. Habilitar `COMMERCIAL_PIPELINE_V2_ENABLED=true` em uma unica implantacao.
5. Nao criar proposta ou pagamento sintetico em producao.
6. Validar read-only: health, Admin, acesso, Portal Cliente, Portal Produtor e
   checkout de referencia controlada sem confirmar pagamento.
7. Liberar trafego e observar os indicadores por toda a janela.

## Indicadores

- propostas enviadas, aceitas e recusadas;
- convites entregues/falhos;
- cobrancas criadas e conflitos por proposta;
- tentativas por estado e falhas de identidade financeira;
- webhooks recebidos, rejeitados, duplicados e atrasados;
- reconciliacoes executadas e divergentes;
- Producoes liberadas e falhas de liberacao;
- propostas aceitas sem Producao apos pagamento suficiente;
- Producoes sem pagamento suficiente;
- taxa de 4xx/5xx nos endpoints comerciais.

Alertas imediatos: duplicacao, mismatch financeiro, assinatura de webhook invalida,
pagamento aprovado sem convergencia ou Producao sem condicao satisfeita.

## Smoke operacional

1. Cliente correto ve somente sua proposta.
2. Politica integral nao oferece entrada.
3. Politica 50/50 oferece entrada calculada pelo backend.
4. Browser nao envia valor autoritativo.
5. Evento duplicado nao duplica cobranca, pagamento ou Producao.
6. Portais mostram a mesma Producao respeitando ownership.
7. Checkout guest legado continua disponivel durante a transicao.

## Rollback

1. Suspender novos aceites/pagamentos se houver risco financeiro.
2. Registrar o horario e desabilitar a flag.
3. Nao apagar cobrancas, pagamentos, Producoes ou arquivos.
4. Identificar propostas aceitas durante a janela:
   - com Producao: preservar e conciliar;
   - com pagamento suficiente sem Producao: executar reconciliacao controlada;
   - sem pagamento suficiente: manter cobranca e revisar continuidade;
   - com divergencia: bloquear e escalar ao Admin.
5. Reverter backend somente se necessario; nao executar downgrade destrutivo.
6. Restaurar banco apenas por procedimento de desastre aprovado e com cutover.

## Criterio de encerramento

O rollout passa quando nao houver duplicacao, mismatch nao tratado, 5xx comercial,
Producao indevida ou pagamento aprovado sem convergencia durante a janela definida.
Caso contrario, manter a V2 desligada e concluir a conciliacao antes de nova tentativa.
