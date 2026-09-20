# Mirai Hit Studio - Financial Model

## Escopo

O dominio separa quatro conceitos:

- Proposta: oferta e snapshot comercial.
- Cobranca: obrigacao financeira contratada.
- Pagamento: tentativa ou movimento associado a cobranca.
- Producao: execucao do servico.

Proposta aceita, link de checkout e pagamento confirmado nao sao equivalentes.

## Entidades

`Cobranca` possui uma relacao 1:1 com a proposta, cliente opcional, valor contratado, moeda BRL, status, vencimento opcional e referencia UUID opaca. O orcamento e derivado pela proposta; nao ha FK redundante.

`Pagamento` pertence a uma cobranca e registra tipo (`integral`, `entrada`, `saldo`), valor, status, metodo, provider e identificadores externos. `provider_order_id` identifica a Order externa e `provider_idempotency_key` preserva a identidade unica e reutilizavel da tentativa. Pendencias e conflitos de reconciliacao ficam explicitos sem substituir o status financeiro.

## Dinheiro e status

Valores novos usam `Numeric(12, 2)` no banco e `Decimal` no dominio. Float nao e usado como autoridade financeira.

O valor pago e a soma dos pagamentos `aprovado`:

- zero: cobranca `pendente`;
- maior que zero e menor que o total: `parcialmente_paga`;
- igual ao total: `paga`;
- acima do total: conflito de reconciliacao, nunca truncamento silencioso.

Pagamentos pendentes, recusados, cancelados ou reembolsados nao compoem o valor pago. Reembolso integral preserva o registro e recalcula a cobranca. Reembolso parcial e chargeback sao detectados como conflitos; movimentos contabilmente completos continuam adiados.

## Integral e 50/50

Uma cobranca representa o total contratado. O pagamento integral e um movimento de 100%; entrada e saldo sao dois movimentos parciais. A divisao 50/50 e deterministica: a entrada e arredondada para baixo e o saldo recebe o centavo restante. Exemplo: R$ 199,99 vira R$ 99,99 + R$ 100,00.

`pagamentos_json` da proposta continua sendo snapshot de apresentacao e links, nao confirmacao financeira. Checkout/provider criarao os movimentos na fase apropriada. Valores customizados futuros deverao somar exatamente o contratado.

## Criacao e transacao

A aprovacao de uma proposta cria a cobranca de forma idempotente na mesma transacao que aceita proposta/orcamento e cria a producao. `UNIQUE(proposta_id)` e o guard final contra duplicidade. Falha financeira reverte toda a aprovacao.

A cobranca copia o total calculado dos itens da proposta naquele momento; alteracoes posteriores em servico ou orcamento nao mudam o historico.

Propostas aprovadas antes da F3.1 permanecem validas e podem nao possuir cobranca. Nao ha backfill automatico. Uma conciliacao explicita devera tratar legados quando houver regra operacional definida.

## Regras adiadas

- Checkout e tokenizacao frontend: F3.4. A integracao backend Mercado Pago foi definida em F3.2.
- Acao ativa de refund e tratamento contabil completo de refund parcial/chargeback: fase futura.
- Gates de inicio/entrega da producao: fase posterior, apos validacao operacional.
- CRUD e interface administrativa financeira: F3.5.
- Nenhum evento `purchase` e emitido antes de confirmacao autoritativa do backend/provider.
