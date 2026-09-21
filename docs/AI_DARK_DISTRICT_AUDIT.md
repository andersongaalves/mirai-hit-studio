# Mirai Hit Studio - Dark District Agent Audit

## 1. Escopo e conclusao

Esta auditoria leu somente o backend do agente Dark District e os pontos Mirai
necessarios para a futura integracao. Nenhum codigo do Dark District foi alterado.

Conclusao: o Dark District oferece bons padroes para conversas duraveis, idempotencia,
leases, handoff, provider e ferramentas com allowlist. A implementacao nao deve ser
copiada diretamente: ela mistura e-commerce, WhatsApp/Meta e dois caminhos de
orquestracao parcialmente divergentes. A Mirai deve extrair os principios e construir
um core proprio, independente de canal e de dominio comercial.

## 2. Arquitetura atual do Dark District

### Conversa web

```text
POST /api/chat/sessions
  -> Customer + ChannelIdentity(web, credential hash, expiry)
  -> Conversation(channel=web)

POST /api/chat/messages
  -> web_channel.receive_message
  -> conversation_service.receive
  -> Message idempotente + lease da conversa
  -> ai_agent.respond (fora do lock final)
  -> grava resposta ou handoff
```

### WhatsApp hibrido

```text
Meta webhook assinado
  -> whatsapp_channel.parse_messages
  -> whatsapp_hybrid_service.receive_messages
  -> Conversation/Message + DeliveryJob(channel=whatsapp)
  -> consumer/worker com lease
  -> whatsapp_ai_service.decide
  -> ai_agent + tools de catalogo/FAQ
  -> decisao: answer | clarify | handoff | no_action
  -> DeliveryJob outbound
  -> Meta send_text
```

### Atendimento humano

```text
Webhook ou inbox administrativo WhatsApp
  -> estado WAITING_HUMAN/HUMAN
  -> resposta manual enviada pela integracao Meta
```

O modelo possui `Customer`, `ChannelIdentity`, `Conversation`, `Message` e
`DeliveryJob`. `Conversation` guarda canal, estado, modo de IA, ciclo, motivo de
handoff, contexto JSON versionado, versao otimista e lease de processamento.
`Message` usa chave externa para idempotencia e limita historico. Isto e uma fundacao
solida, embora o fluxo ativo de web e o hibrido de WhatsApp nao compartilhem a mesma
orquestracao final.

## 3. Matriz de reaproveitamento

| Componente Dark District | Classe | Recomendacao Mirai |
| --- | --- | --- |
| Conversation, Message, historico limitado, versao e lease | B | Recriar modelos e servicos com nomes/relacoes Mirai. |
| ChannelIdentity e credencial web armazenada como hash | B | Adaptar para visitante anonimo e, depois, associar Cliente opcionalmente. |
| Idempotencia de mensagem externa | A | Reutilizar o principio e os testes de colisao/conteudo. |
| Lock curto, LLM fora da transacao e verificacao de versao | A | Aplicar ao orquestrador Mirai. |
| Estados AI, WAITING_HUMAN, HUMAN, CLOSED e ai_mode | B | Adaptar os nomes e transicoes ao atendimento Mirai. |
| Handoff deterministico antes do modelo | A | Preservar como guardrail central. |
| Clarificacao limitada e handoff por baixa confianca | B | Recriar sem regras de catalogo/produto. |
| Protocolo LLMProvider e cliente OpenAI compativel | B | Reaproveitar a fronteira; configurar provider/modelo no ambiente Mirai. |
| Tool registry com schemas estritos e allowlist | A | Reaproveitar o padrao, nunca as tools de catalogo. |
| Testes de isolamento, concorrencia, falha e handoff | B | Adaptar aos contratos Mirai. |
| `ai_agent.py` com prompt/catalogo/FAQ Dark District | C | Usar apenas como referencia de separacao entre plano e fatos. |
| `whatsapp_ai_service.py` | C | Aproveitar regras de decisao; nao portar o arquivo monolitico. |
| `DeliveryJob` e worker WhatsApp | C | Aproveitar lease/retry; projetar fila generica apenas quando canal exigir entrega assincrona. |
| Parser, renderer, webhook, cliente Meta e templates WhatsApp | D | Fora do escopo Mirai por ADR-007. |
| Catalogo, estoque, frete, pedidos, trocas e devolucoes | D | Dominio de e-commerce, sem equivalente direto. |
| Inbox WhatsApp | C | Referencia para futuro inbox Mirai, sem reaproveitar transporte ou UI. |

Legenda: A = quase direto; B = adaptado; C = somente conceito; D = descartar.

## 4. O que nao e uma abstracao de canal completa

O Dark District tem `channel` no modelo e `ChannelIdentity`, mas ainda possui limites
relevantes:

- `web_channel.py` e um adaptador pequeno para `conversation_service`;
- `whatsapp_channel.py` conhece payload, assinatura e formato Meta;
- `conversation_service` bloqueia WhatsApp no caminho web;
- `whatsapp_hybrid_service` concentra persistencia, decisao e entrega Meta;
- `DeliveryJob` aceita somente `channel=whatsapp` e seu worker conhece janela de 24h;
- inbox, notificacoes e mensagens de negocio dependem de WhatsApp.

Portanto, a Mirai nao deve copiar essa divisao. O canal entrega um `InboundMessage`
normalizado e recebe um `OutboundMessage`; o core decide, persiste e faz handoff sem
conhecer site, e-mail, Meta ou interface administrativa.

## 5. Limites de negocio e seguranca

O Dark District aplica regras deterministicas antes do LLM, schemas Pydantic em tools,
allowlist fixa, limite de tool calls, tamanho maximo de resposta e logs sem texto bruto
do cliente. Esses principios devem permanecer.

O que precisa mudar para a Mirai:

- prompts, FAQ, intents e respostas sao especificos de musica/servicos, nao de loja;
- o agente nao decide preco customizado, desconto, pagamento, estorno ou fechamento;
- checkout, Mercado Pago, propostas, producoes e dados de outros clientes nao sao tools
  livres do modelo;
- falha de provider, resposta invalida, baixa confianca e pedido fora do escopo geram
  handoff seguro;
- custo/modelo/latencia devem ser observaveis sem registrar PII, prompt integral,
  token, e-mail, WhatsApp, briefing livre ou segredo;
- o Dark District registra latencia e tokens, mas nao persiste custo ou correlacao de
  uso suficiente para governanca. Isso e pendencia de F2.8.

## 6. Arquitetura alvo da Mirai

```text
Site chat adapter       Email adapter          Admin inbox (futuro)
       |                     |                         |
       +---------- InboundMessage normalizado ---------+
                              |
                     Conversation core
          (identidade, mensagem, contexto, estado, lease)
                              |
             Policy / decisao / handoff deterministico
                              |
                 Orchestrator + provider adapter
                              |
                    Tools estritas em allowlist
                              |
                     OutboundMessage normalizado
       +----------------------+------------------------+
       |                      |                        |
   Site chat              Email sender          Fila/inbox humano
```

O core nao conhece browser, e-mail, WhatsApp, Meta, Mercado Pago ou componentes HTML.
Site e e-mail sao os canais iniciais. WhatsApp fica explicitamente fora da IA Mirai.

### Identidade e contexto

`ClienteModel` continua sendo a identidade comercial autoritativa. A conversa deve
permitir `cliente_id` nullable: visitante anonimo usa uma identidade/sessao opaca e so
e associado a um Cliente por fluxo comercial explicito. Orcamento, Proposta, Producao,
Cobranca e Pagamento nao sao reescritos pela conversa; quando consultados, fornecem
somente dados permitidos e contextualizados ao solicitante.

O contexto deve ser pequeno, versionado e estruturado. Historico e mensagens podem
conter texto livre, mas analytics, logs e metricas devem usar somente codigos, contagens
e identificadores tecnicos minimizados.

### Modos de operacao

| Modo | Papel da IA | Papel humano |
| --- | --- | --- |
| Autonomo | Responde informacao publica e executa tools permitidas. | Recebe handoff quando necessario. |
| Copiloto | Produz sugestao, nunca envia por conta propria. | Revisa, edita e envia. |
| Handoff | Pausa automacao daquela conversa. | Assume, resolve e pode devolver ao modo permitido. |

Handoff obrigatorio: negociacao, desconto/preco customizado, fechamento, reclamacao,
reembolso, controversia de pagamento, baixa confianca, falha do provider e qualquer
pedido fora da allowlist.

## 7. Tools permitidas e proibidas

### Futuras permitidas, com contrato explicito

- consulta de servicos e informacao publica aprovada;
- FAQ/knowledge aprovado;
- coleta guiada de briefing;
- criacao de lead/orcamento por fluxo validado;
- consulta de status permitido e vinculado ao solicitante;
- sugestao de resposta para operador humano.

### Proibidas ao modelo

- aplicar desconto, negociar preco ou confirmar escopo customizado;
- aprovar, criar ou alterar pagamentos livremente;
- reembolso, chargeback ou alteracao de status financeiro;
- acesso cruzado entre clientes;
- SQL, arquivos, secrets, configuracao, HTTP arbitrario ou tool fora da allowlist.

F2.3 deve definir schemas de entrada/saida, autorizacao por tool, limites e auditoria.
Nao deve expor CRUD generico ou objetos ORM ao provider.

## 8. Plano exato para F2.2

1. Definir contratos pequenos: `InboundMessage`, `OutboundMessage`, decisao, motivo de
   handoff, estado da conversa e interface de canal/provider.
2. Criar persistencia Mirai para conversa, mensagem e identidade de canal/sessao com
   cliente opcional, chaves de idempotencia, historico limitado, timestamps, versao e
   lease. Avaliar uma migration especifica nesta fase, sem alterar entidades comerciais.
3. Implementar um servico de conversa unico: validar entrada, persistir idempotente,
   adquirir lease, chamar orquestrador fora do lock, revalidar estado e persistir a
   decisao.
4. Implementar politica deterministica de handoff e modos autonomo/copiloto/humano,
   sem intents ou texto de negocio do Dark District.
5. Criar adapter de sessao para site; definir interface de e-mail sem integrar envio
   autonomo ainda.
6. Criar provider abstrato desabilitado por padrao e adapter configuravel, com erros
   sanitizados, timeouts e limites.
7. Testar idempotencia, isolamento de sessao, lease concorrente, handoff, falha de
   provider, contexto limitado e ausencia de PII em logs/metricas.

Nao criar inbox completo, tools de negocio, UI de chat ou integracao de e-mail em F2.2.

## 9. Pendencias para as fases seguintes

- F2.3: knowledge, FAQ Mirai, contracts de tools e autorizacao por tool.
- F2.4: chat publico do site sobre o core ja testado.
- F2.5: adaptador de e-mail e regras de thread/destinatario.
- F2.6: inbox e copilot administrativo.
- F2.7: briefing e CRM com consentimento e vinculo explicito ao Cliente.
- F2.8: guardrails ampliados, avaliacoes, limites, custo/latencia e metricas sem PII.

## 10. Decisao operacional

Nao ha necessidade de banco analitico, vector store, fila distribuida ou WhatsApp na
F2.2. A menor fundacao segura e conversa persistida + adapter de canal + orquestrador
com handoff + provider desabilitado/limitado. Uma fila generica so sera adicionada se o
canal de e-mail ou entrega assincrona demonstrar essa necessidade.
