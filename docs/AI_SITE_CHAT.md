# Mirai - Site Chat (F2.4)

## Architecture and endpoints

Browser -> site router -> SiteChatService / SiteChannelAdapter -> ConversationService
-> orchestrator -> existing knowledge, ToolRegistry and OpenAI provider.
No new commercial logic in the router. No streaming, polling, SDK in browser,
CRM writes, email, WhatsApp, Inbox or migration.

| Endpoint | Input | Output |
| --- | --- | --- |
| POST /ai/chat/session | empty object | session_token, expires_at (201) |
| GET /ai/chat/history | Authorization: Bearer session_token | status and last 100 public messages |
| POST /ai/chat/messages | same header; message_id UUID, message | status, action, text, retryable |

The token never travels in a URL. No internal conversation PK is returned.
The only message reference exposed is the UUID supplied by the browser, used to
recognize already-delivered replies when recovering history. System prompts,
suggestions, tool results and internal processing metadata are not exposed.
Closed conversations remain readable until expiry but reject new messages.
Explicit **Nova conversa** creates a separate conversation without deleting history.

## Session and identity

- Token: 32 cryptographically random bytes encoded as 43 URL-safe characters.
- Database stores only SHA-256 with `site-session:` prefix in sender_reference;
  external_thread_id is an independent random UUID. Existing model fields suffice.
- Expiry: created_at + AI_SESSION_HOURS (default 24h, allowed 1..168h).
  Changing this setting also changes validity of existing sessions; no automatic deletion.
- Browser: sessionStorage contains token, expiry and, only while confirmation is
  missing, the pending message text/UUID required for retry after reload. No complete
  transcript is cached; confirmed messages remove pending text. Storage failures
  fall back to page memory. A new session discards local pending content.
- Possession authorizes only that conversation, never a verified customer identity.
  No client-selected conversation ID, cliente_id, mode, tool or identity_verified.
- Core always receives identity_verified=False. Public tools reuse the real registry;
  private budget/proposal/production/payment reads remain denied.

## OpenAI configuration

Provider chosen explicitly by the owner: OpenAI. Backend calls Responses API with
native function definitions, no automatic HTTP retry and `store=false`.
Conversation history stays in Mirai; each request supplies bounded core history,
knowledge and prior tool results as untrusted input. No vendor conversation ID.
Only the core executes tools. Provider handoff requests map to the core's enum.

Configure on the backend, never in frontend assets:

```dotenv
AI_ENABLED=false
AI_MODEL=
AI_API_KEY=
AI_TIMEOUT_SECONDS=8
AI_SESSION_HOURS=24
```

Set a model available to the OpenAI project and its server-side API key, then enable
AI_ENABLED. No model or credential is fabricated. SecretStr masks key representations.
Startup performs no provider request. Missing/disabled configuration returns 503
without disabling the website or creating fake AI answers. History access also
stays unavailable while the channel is disabled.

Reference: [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling).
`store=false` is not a promise of zero vendor retention; review the account's data
policy before production activation. Messages/history are sent to OpenAI for replies.

## Processing, retry and handoff

- 4000-character limit in browser and schema; empty/invalid/oversized messages: 400.
- One browser request at a time; stable message_id for retry. No automatic retry.
- Core uniqueness, reply uniqueness and lease fencing remain authoritative.
- Provider timeout is configurable 1..10s per HTTP operation (default 8s), up to
  the existing bounded tool loop. Browser aborts at 55s; server lease remains 60s.
  A disconnected browser does not cancel server processing: retry reuses the UUID.
- Timeout preserves inbound; retry exhaustion follows the existing core handoff.
- 409 means closed/conflict/in-flight. UI checks status and otherwise offers retry.
- waiting_human stops automation. UI disables further input and honestly explains
  that the request is recorded for atendimento na Inbox. A resposta humana posterior
  aparece pelo history polling quando o dialog esta aberto e a pagina esta visivel.
  API can still record messages in waiting_human without calling the provider.
- Copilot suggestions are never delivered or shown in public history.

## Rate limits and security

- Existing process-shared local SQLite limiter, not process-memory counters.
- IP: 60 requests/minute across chat; session creation: 10/hour/IP.
- Session: 20 requests/minute across history and message endpoints.
- Responses: 429 + Retry-After; unavailable limiter fails closed with 503.
- IP is only a temporary rate key, never customer identity. Configure trusted
  reverse proxies correctly; raw X-Forwarded-For is not trusted by these routes.
- Multi-instance deployment still needs edge/shared distributed enforcement.
  Apply a request-body size ceiling at the edge as defense in depth.
- Existing explicit CORS origins/headers reused. No credentialed cookies or admin
  JWT. CSRF cannot silently attach this bearer; token theft/XSS remains a threat.
- HTTP no-store on successful chat responses. Never log message, bearer, provider
  body/key or raw errors. Public errors contain only generic text/status.
- UI uses textContent; links and HTML remain inert text. No Markdown parser.
- Existing report-only CSP is unchanged; no provider domain was added to browser.
  SessionStorage is accessible to same-origin scripts: do not weaken XSS controls.
- Persisted transcript retention/erasure policy remains F2.8/I; no auto-deletion.

## Widget and analytics

Lazy module in public main.js; no session/network until opening. Native dialog with
explicit Tab boundary, Escape, initial/return focus, labels and live status/log.
Compact desktop layout and constrained dynamic mobile viewport; independent scroll
only follows new messages when already near the bottom. Reduced motion supported.
Launcher avoids the consent banner/preferences. No dependency on analytics consent.

Events use existing consent-gated analytics: ai_chat_open, ai_chat_message (confirmed
response), ai_chat_handoff. Their property allowlists are empty. No transcript,
identity, token, email, message UUID or raw error goes to analytics.

## Validation and boundaries

Backend tests: disposable SQLite, fake provider/HTTP transport; session isolation,
expiry, closed, validation, idempotency, timeout, handoff, public/private tools,
injection, CORS and local rate windows. Existing core/knowledge tests retained.
Browser tests: mocked API, keyboard, double-submit, recovery, errors, handoff,
safe text, consent, and widths 320/360/375/390/414/768/1024/1440.
No production database, real provider, email or real customer was used.

LeanDev scope: core contracts/service/provider, channel HTTP/rate configuration,
public main/config/analytics, shared CSS and directly related test harnesses.
Expanded only for official OpenAI contract, consent placement and inherited CSS.
No financial/admin/email audit and no new `.codex/lean-dev` context cache.

Next: F2.5 email channel. Inbox/notification remains F2.6; no push in F2.4.
