# Mirai AI - Canal de E-mail

## Escopo

O canal de e-mail e um segundo `ChannelAdapter` do core de IA. Ele e separado de:

- newsletter e campanhas;
- e-mails transacionais de proposta, checkout e pagamento;
- Inbox/Copilot, que pertencem a F2.6.

O canal vem desabilitado por padrao e nao cria Clientes automaticamente.

## Resend e configuracao

O provider atual e Resend. A aplicacao usa o evento `email.received` em um endpoint dedicado:

```text
POST /webhooks/resend
```

Variaveis:

```text
AI_EMAIL_ENABLED=false
AI_EMAIL_FROM=assistente@dominio autorizado
AI_EMAIL_INBOUND_ADDRESS=assistente@dominio de recebimento
AI_EMAIL_MAX_BODY_CHARS=8000
RESEND_WEBHOOK_SECRET=whsec_...
```

`RESEND_API_KEY` e compartilhada somente como configuracao de servidor com os demais fluxos Resend. O segredo do webhook nunca vai para o frontend, banco, logs ou analytics.

Sem `AI_EMAIL_ENABLED`, endereco inbound, segredo do webhook ou `RESEND_API_KEY`, o endpoint responde indisponivel e a aplicacao continua iniciando; nenhum processamento de IA ou envio e tentado.

Para ativar o canal, configure no Resend o recebimento do dominio/endereco, assine o webhook `email.received` e copie o signing secret para o ambiente. O dominio `.resend.app` pode ser usado apenas conforme a disponibilidade do ambiente de desenvolvimento; DNS nao e configurado pela aplicacao.

O endpoint verifica o corpo raw com o helper oficial do SDK Resend e os headers Svix `svix-id`, `svix-timestamp` e `svix-signature`. JSON invalido, assinatura ausente/invalida ou secret ausente nao criam conversa nem mensagem.

## Normalizacao inbound

O webhook identifica o `email_id` do recurso Resend e recupera o e-mail pela API oficial quando o evento nao possui `text` ou `html`. O core recebe somente o contrato normalizado:

- `channel=email`;
- identificador externo estavel;
- remetente normalizado;
- referencia opaca da conversa;
- texto limitado a `AI_EMAIL_MAX_BODY_CHARS`;
- timestamp e request id tecnico seguro.

`text/plain` tem prioridade. HTML e convertido para texto sem executar scripts, estilos, imagens, URLs ou handlers. Conteudo citado e assinaturas nao sofrem heuristica destrutiva; o limite de tamanho reduz o contexto. O corpo nao e colocado em logs.

Anexos nao sao baixados, executados, interpretados ou enviados ao modelo nesta fase. O texto do e-mail pode ser processado quando for suficiente; pedidos que dependam do anexo devem seguir para atendimento humano em uma fase posterior.

## Threading e idempotencia

O matching usa `Message-ID`, `In-Reply-To` e `References`. O assunto sozinho nunca identifica uma conversa. Um e-mail sem referencia conhecida cria nova conversa; referencia para conversa fechada inicia uma nova conversa sem reabrir a anterior.

`AIEmailThreadModel` guarda somente dados especificos do canal: remetente, assunto original, root `Message-ID` e ultimo `Message-ID` inbound. O core continua sem campos de e-mail.

O `email_id` do Resend e usado para deduplicar a mensagem inbound. Reentregas do mesmo webhook reutilizam a mesma `AIMessage` e a mesma resposta gerada.

## Cliente e identidade

O remetente e normalizado e pode ser associado a exatamente um `ClienteModel` por e-mail. Endereco desconhecido permanece sem Cliente e nunca cria cadastro automaticamente. Uma correspondencia nao torna `identity_verified=true`: tools privadas continuam bloqueadas porque From nao e autenticacao forte.

## Handoff e protecao contra loops

O core continua decidindo respostas publicas e handoff. Negociacao, desconto, pagamento, reclamacao, pedido humano e falhas relevantes permanecem em `waiting_human`. Enquanto a conversa aguarda humano, novas mensagens sao persistidas sem novas respostas autonomas.

Mensagens do proprio remetente configurado, mailer-daemon, postmaster, no-reply e autorespostas detectadas por headers como `Auto-Submitted`, `X-Autoreply`, `X-Autorespond` e `Precedence` sao ignoradas. Tambem existem limites conservadores por thread e remetente.

## Outbound

Respostas sao enviadas como texto simples. `From`, `To` e assunto sao definidos pelo servidor; o modelo nao escolhe destinatario. O assunto preserva a thread com `Re:` e os headers `In-Reply-To` e `References` apontam para a mensagem inbound.

Cada resposta gerada usa a chave estavel:

```text
ai-email/reply/<ai_message_id>
```

O id da resposta Resend e salvo em `AIMessage.external_message_id` quando disponivel. Timeout ou falha depois da chamada nao cria outra resposta do modelo: o retry reutiliza a mesma mensagem, destinatario e chave de idempotencia. Geracao de resposta e entrega de e-mail permanecem estados distintos.

## Seguranca e limites

- nenhum JWT, token, segredo, telefone, corpo, HTML, anexo ou resposta bruta do provider e logado;
- nenhum dado do canal e enviado para analytics;
- e-mail nao libera leitura de orcamento, proposta, producao ou pagamento;
- nao ha fila externa: o webhook persiste/processa usando o lease do core e pode repetir com seguranca;
- testes usam SQLite descartavel, provider de IA fake e client Resend fake;
- validacao real de DNS, webhook publico e PostgreSQL fica para a fase de release.

Referencias oficiais utilizadas: [Resend inbound email](https://resend.com/blog/inbound-emails), [Resend webhooks](https://www.resend.com/features/webhooks), [verificacao de webhooks](https://resend.com/changelog/managing-webhooks-via-api) e [idempotency keys](https://resend.com/changelog/idempotency-keys).
