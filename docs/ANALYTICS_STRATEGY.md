# Mirai Hit Studio - Analytics Strategy

## 1. Principios

- Medir apenas o que orienta decisoes de produto, CRO e crescimento.
- Nunca enviar PII para analytics: nome, e-mail, WhatsApp, briefing, conversa, JWT, erros brutos ou identificador administrativo.
- Analytics nao e fonte de verdade comercial. Banco/CRM sao fonte de verdade para lead, proposta, pagamento e producao.
- Eventos sao semanticos e independentes do texto visivel de botoes.
- Analytics, logs tecnicos e auditoria sao sistemas distintos.
- Consentimento precede tracking nao essencial.
- A integracao deve ter baixo acoplamento e permitir troca de fornecedor.

## 2. Funil canonico

`session -> view_vertical -> view_service -> listen_portfolio -> begin_briefing -> generate_lead -> qualify_lead -> proposal_created -> proposal_sent -> proposal_accepted -> begin_checkout -> purchase -> production_started -> production_completed`

| Evento | Tipo | Fonte autoritativa |
|---|---|---|
| `page_view` | Publico/frontend | Navegacao do navegador |
| `view_vertical` | Futuro | Navegacao publica da vertical |
| `view_service` | Publico/frontend | Selecao significativa de servico |
| `listen_portfolio` | Publico/frontend | Acao real de ouvir faixa |
| `begin_briefing` | Publico/frontend | Inicio do segundo passo da calculadora |
| `generate_lead` | Frontend apos backend | Criacao confirmada do orcamento |
| `qualify_lead` | Futuro comercial | CRM/backend |
| `proposal_created`, `proposal_sent`, `proposal_accepted` | Futuro comercial | Backend de propostas |
| `begin_checkout` | Publico/frontend | Checkout carregado com sucesso |
| `purchase` | Backend/comercial | Webhook/verificacao Mercado Pago |
| `production_started`, `production_completed` | Futuro comercial | Backend de producao |

O frontend nunca determina `purchase`, aprovacao ou qualquer transicao comercial critica.

## 3. Implementado agora

O arquivo `frontend/js/analytics.js` centraliza a integracao. Nenhum outro modulo chama `gtag` diretamente.

O GA4 ja existia no site. Seu Measurement ID existente foi preservado em meta tag e o script e carregado dinamicamente somente apos consentimento aceito. Sem ID valido, a camada falha silenciosamente e nao afeta a UX. Nenhum ID novo ou falso foi criado.

| Evento | Gatilho atual | Parametros permitidos | Proibidos |
|---|---|---|---|
| `page_view` | Pagina carregada com consentimento aceito | `page_path` sem query string | URL completa, query string, PII |
| `view_service` | Selecao de servico na calculadora | `service_id` | Nome, preco, contato, briefing |
| `begin_briefing` | Primeiro avanco real para o briefing | `service_id` | Dados do formulario |
| `generate_lead` | `POST /orcamentos` confirmado | `service_id` | Nome, e-mail, WhatsApp, detalhes, erro da API |
| `listen_portfolio` | Link real de ouvir faixa | `project_id` | URL de audio, artista, dados de contato |
| `newsletter_subscribe` | Inscricao confirmada pelo backend | Nenhum | E-mail, nome, token, origem ou erro |
| `begin_checkout` | Checkout valido carregado | Nenhum | Referencia, proposta, cliente, valor |
| `payment_method_selected` | Selecao de Pix/cartao | `payment_method` | Dados do pagador ou cartao |
| `payment_attempt` | Resposta normalizada da tentativa | `payment_method`, `payment_option`, `outcome` | Token, documento, provider ID, codigo Pix |

Eventos usam `snake_case`. Eventos genericos como `button_click` e `click_cta` nao devem ser introduzidos quando houver um evento semantico.

## 4. Identificadores e propriedades

Analytics pode usar IDs internos nao pessoais e taxonomia publicada quando ela existir: `service_id`, `project_id`, `vertical`, `segment`, `pricing_mode` e `commercial_level`.

No estado atual, somente `service_id` e `project_id` sao enviados. Os demais aguardam a taxonomia da F.2/G. As propriedades sao filtradas por allowlist na camada frontend; propriedades extras sao descartadas antes de chamar o fornecedor.

## 5. Atribuicao

Campos de atribuicao candidatos: `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`, `referrer` e `landing_page`.

Decisao atual: nao persistir atribuicao no frontend nem enviar ao backend enquanto o contrato de consentimento e o schema de lead nao existirem. O frontend tambem nao deve manter esses dados em localStorage para analytics.

Quando implementada, a atribuicao deve:

1. Capturar somente apos a decisao de consentimento aplicavel.
2. Manter durante a jornada apenas valores limitados e normalizados.
3. Usar origem do referrer e caminho da landing page, nunca URL com query completa.
4. Ser anexada ao orcamento/lead por contrato backend validado, sem confiar nela para seguranca ou regras comerciais.
5. Sobreviver ao envio do orcamento como contexto do lead, nao como metadado do servico ou do cliente.

Recomendacao para F0.3 posterior/F.2: usar uma estrutura controlada de atribuicao no orcamento, com chaves fixas e limites, em vez de colunas para cada UTM. A migration so deve existir quando consentimento, retencao e uso no CRM estiverem definidos.

## 6. Consentimento

Categorias:

- Essencial: autenticacao, sessao tecnica, seguranca e funcionamento da aplicacao. Nao depende do banner.
- Analytics: metricas opcionais do GA4 ou fornecedor equivalente. Depende de aceite.
- Marketing: inexistente no momento; requer decisao separada no futuro.

Estados armazenados sob a chave local `mirai.analytics_consent.v1`:

- `unknown`
- `accepted`
- `rejected`

O banner apresenta copy curta e neutra, botoes com destaque equivalente, navegacao por teclado, foco visivel e botao permanente de preferencias. Aceitar ou recusar nao bloqueia conteudo essencial. O estado fica apenas no navegador; nao ha PII e nao ha necessidade de banco agora.

Se a preferencia for revogada depois do aceite, novos eventos sao bloqueados e a camada envia a atualizacao de negacao de armazenamento ao fornecedor ja carregado.

## 7. Eventos planejados

`view_vertical` aguarda navegacao real por vertical. `qualify_lead` aguarda CRM. Eventos de proposta, compra e producao devem ser emitidos pelo backend ou webhook correspondente, nunca simulados no navegador. `purchase` permanece exclusivamente backend-authoritative; `payment_attempt` nao equivale a compra.

## 8. Decisao de persistencia

1. Tabela propria de eventos: nao e necessaria agora.
2. Orcamento guardar UTM: sim, no futuro, quando houver contrato de atribuicao controlada e consentimento definido.
3. Campos que precisam sobreviver: UTM normalizada, origem do referrer e caminho da landing page; sem query completa ou PII.
4. Consentimento no banco: nao agora; preferencia local atende a camada frontend atual.
5. Minimo para CRO futuro: eventos semanticos, IDs internos, funil definido, consentimento e atribuicao de lead planejada.

## 9. Privacidade e seguranca

- Nenhum dado pessoal e incluido em eventos ou armazenamento de analytics.
- Nenhum token, senha, erro bruto ou conteudo livre sai da camada de aplicacao.
- Analytics nao altera estado comercial nem envia requisicoes ao backend.
- O script do fornecedor nao e inserido antes do aceite.
- CSP report-only permite a origem do GA4 existente; a aplicacao efetiva de CSP permanece uma pendencia documentada da Fase E.
