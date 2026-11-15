# Mirai Hit Labs — idiomas e contas

## Idiomas

- A loja (`labs/`) abre em inglês em `/` e tem a versão em português em `/pt/`. Cada página existe nos dois idiomas, com `hreflang` e `canonical` próprios.
- O seletor EN | PT leva para a mesma página no outro idioma e guarda a escolha no navegador (`labs-lang`). Quem escolheu português e abre `/` vai para `/pt/`.
- Os textos montados pelos scripts ficam em `labs/js/i18n.js`.
- Cada plugin tem textos em inglês (`tagline_en`, `descricao_en`, `categoria_en`, `recursos_en_json`, `requisitos_en`), editados no Admin. O catálogo público devolve esses textos no objeto `en`. Se um campo em inglês estiver vazio, a loja mostra o texto em português.

## Contas

Para comprar na Labs não é preciso ter conta na Mirai Hit Studio.

| Quem | Como entra | O que pode |
|---|---|---|
| Conta da Labs (`usuarios.somente_labs = true`) | cria a conta na loja e confirma pelo e-mail | comprar, ver Meus plugins e baixar na Labs; **não** abre o portal do cliente do estúdio |
| Cliente do estúdio | usa o mesmo usuário e senha na Labs | tudo do portal do estúdio, mais a Labs |

- **Cadastro:** a loja usa o cadastro público existente (`POST /auth/client-signup`) com `canal: "labs"` e `idioma`. O acesso guarda `canal`, `idioma` e `somente_labs`. O e-mail de confirmação usa o modelo da Labs no idioma escolhido e leva para `LABS_PUBLIC_URL[/pt]/activate`. A ativação marca o usuário com `somente_labs`.
- **E-mail de um cliente que o estúdio já tinha:** quem se cadastra pela Labs com o e-mail de um cliente criado pelo estúdio (orçamento, proposta) entra no cadastro existente. A conta dele **não** fica só da Labs.
- **Recuperação de senha:** pedida na loja (`canal: "labs"`), leva para `LABS_PUBLIC_URL[/pt]/reset-password`. A senha é a mesma nos dois sites.
- **Permissões:**
  - `require_client` (portal do estúdio) recusa contas `somente_labs`, e as notificações do portal também.
  - `require_labs_customer` aceita os dois tipos de conta. Ele protege a compra (`POST /labs/plugins/{slug}/comprar`), Meus plugins (`GET /labs/conta/plugins`) e os downloads (`GET /labs/conta/plugins/{id}/download/{sistema}`).
  - As rotas `/portal/cliente/plugins*` continuam só para clientes do estúdio.
- **Sessão:** a loja guarda o próprio token (`mirai.labs.access_token`), sem compartilhar com o site do estúdio. Uma conta da Labs que tenta entrar no site do estúdio é levada para entrar na loja.

## Compra e pagamento

O preço é um só por plugin e aparece na moeda da loja **com o mesmo número**, sem conversão: R$ 149,90 na loja em português e US$ 149.90 na loja em inglês.

**Loja em português (`/pt`): checkout da Mirai, em BRL**
- A compra passa pelo fluxo do estúdio (orçamento → proposta → cobrança).
- A resposta traz `checkout_url`, o link público e opaco do checkout daquela cobrança, para quem não tem portal do estúdio. Pedidos aguardando pagamento em Meus plugins também trazem esse link.
- Pix ou cartão pelo Mercado Pago.

**Loja em inglês (`/`): Stripe, em USD**
- `POST /labs/plugins/{slug}/comprar-internacional` (com `Idempotency-Key`):
  - abre um pedido em `plugin_pedidos_stripe`;
  - reserva a licença (`origem = 'stripe'`, sem proposta);
  - cria uma Checkout Session no Stripe, com valor em centavos de dólar e `Idempotency-Key` próprio por pedido;
  - devolve a URL da página do Stripe.
- Clicar de novo, ou voltar antes de pagar, reabre a mesma página.
- **Confirmação:**
  - o webhook `POST /labs/stripe/webhook` confere a assinatura (`Stripe-Signature`, HMAC-SHA256, tolerância de 5 minutos) e ativa a licença em `checkout.session.completed` quando valor e moeda conferem;
  - ao voltar para `/my-plugins?checkout=success&session_id=...`, a loja chama `POST /labs/stripe/sessoes/{id}/confirmar`, que consulta o Stripe. Assim o plugin aparece mesmo se o webhook atrasar.
- **Sessão expirada** (`checkout.session.expired`): a reserva é liberada; a licença fica `cancelada` com motivo `checkout_expirado`.
- **Reembolso total** (`charge.refunded`) **ou contestação** (`charge.dispute.created`): a licença é suspensa (`pagamento_revertido`), como no checkout do estúdio.
- Os pedidos do Stripe **não** entram no financeiro do estúdio (cobranças em BRL). Ficam em `plugin_pedidos_stripe`, nas licenças do plugin no Admin ("Compra internacional (Stripe, USD)") e no painel do Stripe.

## Configuração

- `LABS_PUBLIC_URL` (padrão `https://labs.miraihitstudio.com.br`): endereço da loja, usado nos e-mails da Labs.
- `STRIPE_SECRET_KEY`: chave secreta, `sk_test_...` em teste e `sk_live_...` em produção. Sem ela, a compra internacional responde 503 e a loja em inglês mostra "International payment is unavailable".
- `STRIPE_WEBHOOK_SECRET` (`whsec_...`): segredo do endpoint de webhook criado no painel do Stripe.
  - URL: `https://api.miraihitstudio.com.br/labs/stripe/webhook`.
  - Eventos: `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `checkout.session.expired`, `charge.refunded` e `charge.dispute.created`.
- CORS: `cors_origins` já inclui a origem da Labs quando o domínio principal está em `ALLOWED_ORIGINS`. `Authorization` e `Idempotency-Key` já são cabeçalhos permitidos.
