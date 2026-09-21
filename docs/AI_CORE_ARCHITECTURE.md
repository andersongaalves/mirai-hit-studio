# Mirai Hit Studio - AI Core Architecture

## Escopo F2.2

Core interno, sem endpoint publico, widget, e-mail, inbox, tools comerciais ou provider
remoto ativo. Reutiliza os padroes documentados em F2.1; nao importa codigo Dark District.

```text
ChannelAdapter (contrato futuro)
  -> InboundMessage -> ConversationService.receive (persistencia idempotente)
  -> claim (transacao curta e lease)
  -> AIOrchestrator -> AIProvider.generate (sem conexao DB aberta)
  -> complete (confere lease/token/versao e grava decisao)
  -> ProcessingResult / OutboundMessage
```

`ConversationService` possui as transacoes e recebe uma session factory dedicada.
`AIOrchestrator` decide; nao acessa ORM, transportes ou modelos comerciais.
`AIProvider` e um Protocol. `DisabledProvider` e o padrao, sem credenciais, rede ou SDK.
Nao foi portado provider concreto: implementacoes futuras devem impor timeout de rede
menor que o lease e retornar somente `ProviderResponse` validada.

## Persistencia

Migration `c8a1d6e4b209`, filha de `f6c2a8d4e1b9`. Somente duas tabelas novas:

| Entidade | Campos |
| --- | --- |
| ai_conversations | UUID id; cliente_id nullable; anonymous_session_id UUID nullable/unique; assigned_user_id nullable; channel; external_thread_id; sender_reference; status; mode; handoff_reason; version; claim_token; lease_until; created_at; updated_at; closed_at |
| ai_messages | UUID id; conversation_id; direction; role; channel; external_message_id; reply_to_id; kind; content; received_at; created_at; processing_status; attempts; result_action; reason; error_code; request_id |

FKs preservam Cliente e Usuario existentes. Responsavel precisa existir e estar ativo
na criacao. Nao existe entidade duplicada de Cliente nem merge automatico de identidade.
Sem cliente, `create` gera referencia anonima aleatoria; nao usa IP/fingerprint.

A referencia anonima identifica a sessao interna, **nao e um mecanismo de autenticacao**.
F2.4 devera implementar credencial opaca, hash/expiracao e verificacao de propriedade
antes de invocar este servico. Nenhum metodo interno deve ser exposto diretamente.

Uma conversa pertence a um canal e, quando informado, a um thread externo unico por
canal. `sender_reference` deve ser referencia opaca do adapter, nunca email/telefone.
`receive` exige coincidencia exata desses identificadores. Conversa fechada nao reabre;
nova identidade/thread depende da politica futura do adapter.

## Estados e modos

| Estado | Processamento |
| --- | --- |
| open | Permite processamento conforme mode. |
| waiting_human | Persiste entradas, retorna no_action e nao chama provider. |
| closed | Recusa novas entradas/processamento; conserva historico e closed_at. |

| Modo | Resultado permitido |
| --- | --- |
| autonomous | reply persistida; o core nunca envia ao canal. |
| copilot | suggestion persistida; sem envio automatico e fora do historico do provider. |
| human | Entrada persistida, no_action, provider nao chamado. |

O default conservador e `human`. `set_mode` atua somente em conversa aberta e invalida
claims anteriores. Handoff e close tambem incrementam versao e revogam o claim.
Retomada apos handoff e politica de operador para F2.6, nao implicita nesta fase.

## Handoff e decisoes

Decisoes explicitas: `reply`, `suggestion`, `handoff`, `no_action`, `error`.
Handoff coloca `waiting_human` + `human`, preservando o primeiro motivo em repeticoes.
Nao cria mensagem artificial, notificacao, envio ou registro AuditLog por mensagem.

Motivos: negotiation, discount, custom_pricing, payment_issue, complaint,
low_confidence, tool_failure, provider_failure, manual_request, other.

Politica deterministica anterior ao provider cobre termos de negociacao, desconto,
preco personalizado, fechamento, estorno/reembolso, reclamacao e pedido humano.
E uma protecao inicial conservadora, nao um classificador semantico completo.
Provider pode solicitar handoff tipado; resposta truncada vai para low_confidence.
Falha ou resposta invalida leva a provider_failure, sem expor excecao original.

## Contratos de fronteira

- `InboundMessage`: canal site/email; external_message_id obrigatorio; thread/remetente
  opacos opcionais; texto de 1 a 8000 caracteres; received_at com timezone; metadata
  limitada ao request_id opcional no formato do middleware (8-64 caracteres seguros).
  Adapter deve reutilizar a mesma chave no retry.
- `OutboundMessage`: UUID persistida, conversation_id, texto, reply_to externo, kind
  reply/suggestion e request_id. Sua UUID e a futura chave de deduplicacao de entrega.
- `ChannelAdapter`: normalize(payload, received_at) e send(outbound); nenhum adapter real.
  Nunca enviar suggestion automaticamente. Autenticacao, roteamento e entrega sao do adapter.
- `ProviderInput`: system separado de mensagem, ate 20 entradas de historico e ate oito
  trechos de contexto preparados pelo backend. Nao recebe ORM nem payload bruto do canal.
- `ProviderResponse`: texto OU handoff_reason, modelo/uso opcionais, finish_reason tipado.
  Campos extras e tool calls arbitrarias sao rejeitados.
- `ProcessingResult`: acao, outbound opcional, motivo, error_code e retryable.

O contexto e texto de conhecimento preparado externamente; nao concede permissoes.
Mensagens e contexto sao conteudo nao confiavel. A futura implementacao do provider
deve preservar roles, sem concatenar entrada do usuario como instrucao de sistema.

## Idempotencia, ordenacao e concorrencia

Unique DB `(conversation_id, channel, external_message_id)` deduplica inbound;
mesma chave com texto diferente e `idempotency_conflict`. A resolucao autorizada de
conversa pelo adapter e indispensavel: IDs nao sao globais entre conversas distintas.
Unique `reply_to_id` garante no maximo uma resposta/rascunho por mensagem original.
Reprocessamento concluido retorna a mesma identidade persistida, sem chamar provider.
Replay de resposta autonoma apos handoff/troca para modo humano retorna no_action.

Toda mutacao primeiro adquire lock curto da conversa por UPDATE. O claim guarda UUID
de propriedade + lease_until; mensagem guarda processing_status e attempts. A transacao
fecha antes do provider. Complete exige token, versao, modo, estado e prazo ainda validos.
Uma resposta atrasada nao pode sobrescrever a resposta do novo worker ou handoff humano.

Pending/processing/failed sao recuperaveis por chamada explicita a process/claim;
completed nao volta para processamento. Processa a primeira entrada nao concluida,
ordenada por created_at/id, sem ultrapassar uma anterior pendente ou com timeout.
Historico usa ordem de persistencia e inclui respostas de entradas anteriores mesmo
quando a proxima pergunta chegou antes da conclusao. Rascunhos nunca entram no contexto.

Lease default: 60s, configuravel de 1 a 300s. Maximo: tres tentativas, configuravel
de 1 a 5. Timeout mantem inbound e marca failed/retryable. Nao existe retry automatico
nem worker. Esgotamento, inclusive por workers interrompidos, causa handoff.
Erro ao persistir resultado faz rollback; inbound permanece e lease expirado permite
recuperacao. Nenhuma chamada longa ocorre sob row lock/conexao de banco.

Isso garante efeito persistido unico, **nao chamada ao provider exatamente uma vez**:
apos lease expirado, geracoes podem se sobrepor e apenas o claim valido grava.
Tambem nao garante entrega exatamente uma vez; F2.4/F2.5 deverao tratar confirmacao,
resultado incerto e idempotencia do transporte. Resposta gerada nao significa entregue.

## Tools e seguranca

`ToolRegistry` usa registro explicito, schemas estritos de entrada/saida e categorias de
risco. `ToolExecutionContext` e construido pelo servidor; o modelo nunca escolhe o
cliente autorizado. Tools privadas exigem identidade verificada, tools desconhecidas
sao bloqueadas e nao ha `getattr` dinamico, `eval`, SQL, shell ou HTTP livre.

O provider pode solicitar tools por contrato vendor-neutral. O orquestrador limita cada
turno a tres ciclos e quatro chamadas, devolve resultados normalizados e converte falhas
criticas em handoff. Knowledge publico pequeno e tools implementadas estao descritos em
`AI_KNOWLEDGE_TOOLS.md`; dados dinamicos nao ficam hardcoded no prompt.

Logs usam somente UUIDs tecnicas, action, error_code e request_id (hash SHA-256 quando
nao for UUID, evitando copiar dados pessoais disfarcados de correlacao). Nenhum prompt,
mensagem, resposta, exception bruta, token, email ou telefone e copiado para logging.
Conteudo livre pode conter PII no historico; nao e duplicado em JSON ou telemetria.
Retencao, exclusao por privacidade e controle de leitura dos canais ficam para as fases
de integracao. O core interno pressupoe chamador confiavel; nao altera autenticacao.

PostgreSQL: migration e bootstrap por metadata habilitam RLS nas tabelas novas e
revogam grants de anon/authenticated, quando esses papeis existem. Nenhuma politica
publica e criada. Backend deve conectar como dono das tabelas ou papel BYPASSRLS
restrito ao servidor; validar esse papel em ambiente descartavel antes do deploy.
Referencia: [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security).

## Validacao e limites

Testes isolados usam SQLite temporario com FK habilitada no core e provider fake.
Cobrem identidade, estados/modos, handoff, historico, idempotencia DB, disputa entre
threads, expiracao/fencing, timeout, persistencia interrompida, tools e logs.
Migration: upgrade/downgrade/upgrade, comparacao de metadata e compilacao offline do
DDL PostgreSQL incluindo RLS/grants; configure_mappers tambem exercitado.

SQLite nao comprova isolamento/locking/RLS PostgreSQL. Validacao formal em PostgreSQL
descartavel segue pendente para I.1/I.3. Nenhum banco real ou provider real foi acessado.
F2.3 conclui knowledge e tools. F2.4/F2.5/F2.6 continuam separados.
