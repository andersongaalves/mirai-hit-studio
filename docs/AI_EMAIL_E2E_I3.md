# Mirai AI + Email E2E - I.3

## Status

A integracao Groq e a jornada conectada foram implementadas e validadas com transportes
sinteticos e com um smoke live controlado da Groq. A chave foi detectada somente no
processo, sem ser exibida ou persistida. A validacao live do Resend inbound foi
transferida para I.4, onde endpoint publico e signing secret podem ser configurados com
seguranca.

## Provider architecture

O contrato continua vendor-neutral: `AIProvider.generate(ProviderInput)` devolve
`ProviderResponse`. `DisabledProvider` permanece o default e `OpenAIProvider` continua
usando Responses API. O mesmo adapter agora aceita metadados server-side para um
endpoint OpenAI-compatible. A factory suporta:

| AI_PROVIDER | Protocolo | Base URL | Particularidade |
| --- | --- | --- | --- |
| disabled | nenhuma rede | nenhuma | deterministico ou handoff |
| openai | Responses API | `https://api.openai.com/v1` | envia `store=false` |
| groq | Responses API | `https://api.groq.com/openai/v1` | omite `store` |

Para Groq, qualquer `AI_BASE_URL` diferente da URL oficial desabilita o provider. A
origem e sempre configuracao do servidor; navegador, mensagem e tool nao a controlam.
OpenAI preserva configuracao e parsing anteriores.

## Groq compatibility

Documentacao oficial consultada em 2026-09-29:

- [Responses API](https://console.groq.com/docs/responses-api)
- [API reference](https://console.groq.com/docs/api-reference)
- [Local tool calling](https://console.groq.com/docs/tool-use/local-tool-calling)
- [Structured outputs](https://console.groq.com/docs/structured-outputs)
- [Supported models](https://console.groq.com/docs/models)
- [Rate limits](https://console.groq.com/docs/rate-limits)
- [Errors](https://console.groq.com/docs/errors)

Groq oferece `POST /openai/v1/responses`, function tools, `tool_choice`,
`parallel_tool_calls`, `max_output_tokens`, usage e structured outputs. Nao suporta
alguns campos da OpenAI, incluindo `store` e `previous_response_id`. A Mirai conserva
historico internamente e nao usa ID de conversa do fornecedor; por isso basta omitir
`store` para o contrato atual.

Modelo recomendado para o primeiro smoke: `openai/gpt-oss-20b`, atualmente listado
como modelo de producao, com contexto suficiente e suporte a Responses/structured
outputs. O modelo continua configuravel por `AI_MODEL`; nenhuma disponibilidade de
conta foi presumida. O free tier documentado informa 30 RPM, 1.000 RPD, 8.000 TPM e
200.000 TPD para esse modelo, sujeitos aos limites reais da organizacao.

```dotenv
AI_ENABLED=true
AI_PROVIDER=groq
AI_BASE_URL=https://api.groq.com/openai/v1
AI_MODEL=openai/gpt-oss-20b
AI_API_KEY=<secret>
```

## Routing and tools

O roteamento deterministico agora ocorre antes de qualquer provider disponivel.
Saudacao, FAQ clara, servicos, portfolio e pedido explicito de humano nao consomem
Groq/OpenAI. Perguntas flexiveis continuam indo ao provider. Handoff deterministico
precede geracao.

Tools continuam executadas somente pelo core. O provider recebe definicoes publicas
ou privadas filtradas por `ToolExecutionContext`; nao recebe capacidade livre de HTTP,
SQL ou shell. Tools privadas continuam bloqueadas sem identidade verificada. Desconto,
preco customizado, pagamento, reembolso e aprovacao permanecem fora da autonomia.

## Connected PostgreSQL and browser evidence

O teste opt-in `test_ai_postgres_i3.py` usa PostgreSQL autorizado na head
`b8c41e7d290a`, backend FastAPI real e frontend real servido em loopback. Microsoft
Edge executa a jornada em desktop e 390 px:

- sessao e mensagem deterministica;
- pergunta flexivel pelo provider sintetico com contrato Groq;
- replay do mesmo `message_id` com um unico efeito;
- refresh e historico;
- pedido de humano sem provider;
- conversa na Inbox;
- atribuicao ao operador;
- Copilot como rascunho, nunca autoenvio;
- edicao e envio humano;
- resposta humana visivel no historico do site.

O mesmo harness valida no PostgreSQL real e-mail flexivel, threading por
`Message-ID`/`In-Reply-To`/`References`, replay duplicado e idempotency key outbound.
Somente provider e transporte de e-mail sao sinteticos. Testes offline preservam
Svix, body retrieval, HTML como texto, anexos nao recuperados, autoresponders/self
ignorados, DisabledProvider, late response, conflito de cliente e briefing atomico.

O teste PostgreSQL I.1 reutilizado confirma briefing concorrente criando exatamente um
Cliente e um Orcamento, alem de lease recovery e descarte de resposta tardia. Fixtures
I.3 usam prefixo `i3_` e enderecos `@example.invalid`; cleanup remove somente IDs
descobertos por esses marcadores. O digest de usuarios preexistentes deve permanecer
identico.

## Metrics, cost and privacy

Usage da Groq e registrada com `provider=groq`, modelo e tokens quando presentes.
Latencia continua medida ao redor da chamada. Nao foi adicionada tarifa: free quota
nao significa custo permanente zero, portanto custo permanece desconhecido ate existir
snapshot tarifario oficial adotado pela Mirai.

Somente system policy, mensagem da propria conversa, historico limitado, knowledge
publico e resultados normalizados das tools autorizadas podem ir ao provider. Nao sao
enviados automaticamente cliente completo, Inbox administrativa, dados financeiros,
JWT, telefone, access token, API key ou payload bruto do canal. Logs continuam sem
prompt, corpo de e-mail, resposta bruta ou credencial.

## Failure behavior

Unit tests cobrem timeout, 429, 5xx e resposta malformada sem rede. Falhas viram os
codigos seguros existentes e seguem para retry/handoff conforme o core; nao ha retry
HTTP automatico novo. `DisabledProvider` conserva respostas deterministicas e encaminha
perguntas flexiveis. OpenAI continua coberto pelo contrato anterior.

## Live Groq validation

- `AI_API_KEY` detectada no processo: sim.
- Provider: `groq`.
- Modelo: `openai/gpt-oss-20b`.
- Endpoint: Responses API oficial da Groq.
- Smoke real: aprovado em 962 ms, com usage presente e 270 tokens.
- Live evals: 4/4 aprovados.
- Tool calling publico: aprovado.
- Pricing e acoes financeiras: handoff aprovado.
- Prompt injection: guardrail aprovado.
- Grounded context: aprovado.
- Custo: desconhecido; nenhuma tarifa foi presumida.
- Nenhuma chave, header ou arquivo de secret foi persistido.

## Remaining I.4 gates

- Resend live inbound/outbound: transferido para I.4, pois depende de signing secret,
  endpoint HTTPS implantado e endereco inbound controlado.
- A Resend documenta enderecos `*.resend.app` para inbound e destinatarios de teste
  para eventos de envio, mas a configuracao de conta/webhook nao deve ser inventada.
- Render, Cloudflare, DNS, rate limit distribuido e deploy permanecem para I.4.
- Nenhum pagamento ou migration fez parte da validacao live da Groq.

## LeanDev

Leitura limitada aos contratos/provider, core/orchestrator, Chat, briefing,
Inbox/Copilot, e-mail, testes I.1/I.2 e documentos F2. Financeiro, SEO, checkout e CRM
amplo nao foram reabertos. O contexto expandiu somente quando o browser revelou que o
roteamento deterministico estava condicionado incorretamente ao provider desabilitado.
Nenhum cache `.codex/lean-dev` foi criado.
