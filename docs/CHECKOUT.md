# Mirai Hit Studio - Checkout

## Acesso

O checkout e publico e nao exige conta de cliente. O acesso usa a referencia UUID aleatoria da cobranca:

`/checkout/<referencia-opaca>`

IDs sequenciais, dados pessoais, valores, JWT e IDs do Mercado Pago nao fazem parte da URL. A referencia funciona como credencial compartilhavel; deve ser enviada somente ao cliente correspondente. O endpoint autenticado `GET /checkout/proposta/{proposta_id}/link` fornece o link depois que a proposta aprovada possui cobranca.

## API publica

- `GET /checkout/config`: retorna somente a Public Key do Mercado Pago.
- `GET /checkout/{token}`: resumo seguro, saldo e opcoes comerciais validas.
- `GET /checkout/{token}/status`: estado financeiro local para polling.
- `GET /checkout/{token}/pending-payment`: recuperacao pontual de Pix ou desafio pendente.
- `POST /checkout/{token}/pix`: cria ou recupera Pix.
- `POST /checkout/{token}/card`: processa token temporario de cartao.

O resumo nao inclui e-mail, telefone, observacoes, IDs administrativos, provider order ID ou historico interno.

## Valores e opcoes

O frontend envia apenas `payment_option`: `integral`, `entrada` ou `saldo`. O backend calcula o valor usando `financial_service` e rejeita campos extras, inclusive `amount`.

- `integral`: total, antes de qualquer pagamento aprovado.
- `entrada`: metade comercial definida pelo dominio, antes de qualquer pagamento aprovado.
- `saldo`: saldo exato depois de pagamento parcial aprovado.

Parcelamento comercial e `installments` do cartao sao conceitos distintos. O Mercado Pago define as parcelas validas do cartao; elas nao criam novas cobrancas Mirai.

## Pix

O backend cria uma Order com chave de idempotencia persistida antes da chamada externa. A resposta publica normaliza status, QR, copia-e-cola, expiracao e ticket URL. Gerar o Pix nao significa pagamento aprovado.

Uma tentativa pendente equivalente e reutilizada. Se ela possui Order, a recuperacao consulta o provider uma vez e atualiza o banco por reconciliacao. Se ocorreu timeout antes de obter a Order, o checkout bloqueia nova tentativa automatica e aguarda webhook/conciliacao; nao cria duplicata ambigua.

## Cartao e 3DS

O navegador usa MercadoPago.js v2 e Card Payment Brick, recomendados para Checkout API via Orders API. PAN, CVV e validade ficam nos campos seguros do Mercado Pago. A Mirai recebe apenas token temporario, meio de pagamento, tipo, parcelas e os dados minimos do pagador exigidos pelo provider.

O token nao e persistido, logado, colocado em URL, storage ou analytics. Orders de cartao ativam 3DS com `on_fraud_risk` e `liability_shift=required`. Quando o provider retorna `action_required/pending_challenge`, a URL HTTPS validada do Mercado Pago e exibida em iframe. A conclusao do iframe apenas inicia nova consulta; webhook/reconciliacao continua sendo autoridade.

## Estados e polling

O frontend representa:

- aprovado: pagamento confirmado pelo backend;
- pendente/processando: aguarda webhook ou reconciliacao;
- recusado: permite uma nova tentativa real;
- parcialmente pago: confirma entrada e mostra saldo;
- pago: remove formularios de pagamento;
- cancelado: bloqueia novas tentativas.

Polling consulta apenas o banco a cada cinco segundos, pausa com pagina oculta e termina em estado terminal ou apos dez minutos. Ele nao chama o Mercado Pago a cada ciclo.

## Seguranca e privacidade

- Checkout guest nao usa cookie nem JWT administrativo; o token opaco na URL e o controle de acesso.
- Endpoints de criacao possuem limite local por IP; a recuperacao pontual tem limite separado. Protecao distribuida continua dependendo da borda/infraestrutura.
- CORS continua restrito a `ALLOWED_ORIGINS` e sem credenciais.
- Conteudo remoto e inserido com `textContent`; URLs e base64 sao validados antes de uso.
- Access Token e webhook secret nunca chegam ao frontend.
- O checkout nao entrega arquivos nem altera producao diretamente.

## Analytics

Com consentimento aceito, o checkout pode emitir `begin_checkout`, `payment_method_selected` e `payment_attempt`. A allowlist aceita apenas metodo, opcao comercial e resultado normalizado. Nome, e-mail, documento, token, referencia, ID do provider e codigo Pix sao proibidos. `purchase` nunca e emitido pelo frontend.

## Configuracao e limites

Configurar `MERCADO_PAGO_PUBLIC_KEY`, `MERCADO_PAGO_ACCESS_TOKEN`, `MERCADO_PAGO_WEBHOOK_SECRET` e `PUBLIC_FRONTEND_URL`. O arquivo `frontend/_redirects` fornece o rewrite do Cloudflare Pages.

O rate limit atual usa armazenamento SQLite compartilhado pelo processo/host e nao substitui protecao de borda em multiplas instancias. Compartilhamento automatico por e-mail e gestao financeira permanecem para F3.5.
