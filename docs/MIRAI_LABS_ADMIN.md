# Mirai Hit Labs — painel de admin

Endereço: `https://labs.miraihitstudio.com.br/admin/`. Entra com uma conta de administrador da Mirai Hit Studio (`role = admin`, `is_admin`). A sessão fica só neste site (`mirai.labs.admin.access_token`), separada da sessão de cliente da loja. A página é `noindex`.

## Áreas

| Área | O que faz | Rotas |
|---|---|---|
| Visão geral | receita BRL (licenças `compra` ativas, já com desconto) e USD (pedidos Stripe pagos), vendas, downloads, licenças, contas da Labs, licenças por dia e resumo por plugin. Clientes `is_test` ficam fora. | `GET /admin/labs/resumo?dias=` |
| Plugins | página PT/EN, preço, capa (recortada em 1200×1200), instaladores (upload direto no Render, até 150 MB, ou link), versões e licenças | rotas de `/admin/labs/plugins` já existentes + versões |
| Pedidos | checkout Mirai (BRL) e Stripe (USD) numa lista, com cupom; reembolso de pedido Stripe pago | `GET /admin/labs/pedidos`, `POST /admin/labs/pedidos/stripe/{id}/reembolsar` |
| Clientes | quem tem conta da Labs ou alguma licença; detalhe com licenças e pedidos | `GET /admin/labs/clientes[/{id}]` |
| Licenças | busca por chave, nome ou e-mail; revogar, reativar (só revogadas) e cortesia por e-mail | `GET /admin/labs/licencas`, `POST /admin/labs/licencas/{id}/reativar`, `POST /admin/labs/plugins/{id}/cortesias/email` |
| Cupons | porcentagem ou valor fixo, por plugin ou todos, período e limite de usos | `/admin/labs/cupons` |
| Loja | ordem e destaques do catálogo; aviso no topo da loja (PT/EN) | `PUT /admin/labs/ordem`, `PUT /admin/labs/conteudo/banner` |

Estorno de compra em BRL continua no Financeiro do Admin do estúdio (Mercado Pago).

## Versões e aviso de atualização

`plugin_versoes` guarda o histórico (versão, canal `estavel`/`beta`, novidades PT/EN, `obrigatoria`, publicada ou rascunho). Publicar uma versão estável atualiza `plugins.versao`; apagar a atual volta para a estável anterior.

Os plugins e o app leem, no máximo uma vez por dia (cache público de 5 minutos):

- `GET /labs/plugins/{slug}/atualizacao[?canal=beta]` → `{plugin, nome, versao, canal, publicada_em, obrigatoria, notas, notas_en, pagina, download}`
- `GET /labs/atualizacoes` → `{gerado_em, plugins: {slug: ...}}` (só estáveis de plugins publicados)

## Cupons

- O cliente aplica o código na página do plugin; `POST /labs/cupons/validar` mostra o preço final (limitado por endereço, sem dado pessoal).
- A compra envia `{"cupom": "CODIGO"}` em `POST /labs/plugins/{slug}/comprar` e `.../comprar-internacional`.
- Checkout Mirai: o preço unitário da proposta continua o de catálogo e o cupom vira o `desconto` da linha; a cobrança sai pelo total. A licença guarda o valor pago.
- Stripe: a sessão é criada com o valor já com desconto.
- Desconto que cobre o preço todo libera o plugin na hora como `cortesia`.
- Um uso (`labs_cupom_usos`) conta enquanto a licença está ativa ou aguardando pagamento (ou nas 2 primeiras horas, antes de existir licença). Cada conta usa um cupom uma vez. Cupom já usado não muda de código nem é apagado; desative.
- Valor fixo é o mesmo número nas duas moedas, como o preço.

## Banco

Migration `c6f8a0b2d4e5`: `plugin_versoes`, `labs_cupons`, `labs_cupom_usos`, `labs_conteudo` (RLS ligado, sem acesso para `anon`/`authenticated`). Plugins existentes ganham a primeira versão com a versão que já mostravam.

## Testes

`backend/tests/test_labs_admin.py` e `frontend/tests/labs_admin_panel.cjs` (API simulada).
