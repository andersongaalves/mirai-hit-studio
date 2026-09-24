# Mirai AI - Inbox e Copilot (F2.6)

## Operacao

A Inbox do Admin agrega conversas `site` e `email` sem fundir threads. A fonte de verdade permanece `AIConversationModel` e `AIMessageModel`; assunto e remetente do email vem de `AIEmailThreadModel`. O menu usa o shell administrativo existente. Admin e produtor ativos podem consultar; um operador precisa assumir a conversa para mudar modo, sugerir, responder, ignorar sugestao ou encerrar. Dois operadores nao podem assumir a mesma conversa: a transacao trava a linha e devolve conflito ao segundo.

A listagem e paginada (20 por pagina; maximo 50), ordenada por atividade recente e filtravel por status, modo, canal, handoff, responsavel, busca restrita e periodo. A busca considera ID de conversa, nome do Cliente vinculado e assunto do email. O detalhe traz as ultimas 100 mensagens; `before` permite carregar anteriores. Texto de cliente, IA, remetente e assunto e exibido como texto, sem HTML. O token da sessao do site, hashes internos, payloads do provider e segredos nao fazem parte da resposta.

## Estados e modos

Ao assumir, `waiting_human` passa a `open/human`, preservando o motivo do handoff. A atribuicao explicita interrompe qualquer claim da IA em andamento. Conversas abertas podem mudar entre `human` e `copilot`; uma conversa autonoma assumida passa a `human`. O Admin nao reativa `autonomous` nesta fase. Enviar uma resposta humana nao reativa autonomia; se a conversa estava em `copilot`, permanece nesse modo para proximas sugestoes. `closed` conserva o historico e bloqueia novas acoes.

## Copilot

`POST /admin/ai/conversations/{id}/suggestions` reutiliza `AIOrchestrator`, conhecimento, historico e tools do core. O contexto usa `identity_verified=false` mesmo quando um operador esta autenticado. Uma sugestao (`AIMessage.kind=suggestion`) e rascunho, nunca entrega. Regenerar atualiza o mesmo registro. Ignorar apaga apenas o rascunho; mensagens enviadas nao sao apagadas. O operador pode editar o texto no composer e so `Enviar` cria uma nova mensagem humana. O backend compara a mensagem inbound mais recente com `reply_to_id`; se houver nova mensagem, rejeita a sugestao antiga. Falha do provider ou de tool nao bloqueia resposta manual.

## Entrega humana

O browser envia apenas texto, referencia opcional da sugestao e chave idempotente. Canal, identidade e destino vem do servidor. `AIMessage.kind=message` com direcao outbound identifica resposta humana. A mesma chave de request e a trava da conversa evitam mensagem logica duplicada. O detalhe distingue `draft`, `pending` e `sent`.

- Site: a mensagem persistida fica disponivel no endpoint de historico da sessao do visitante. O widget consulta a cada 15 segundos apenas com dialog aberto, pagina visivel e atendimento humano em curso; nao ha WebSocket. A consulta de historico continua disponivel se o provider de IA estiver desabilitado.
- Email: a mensagem usa `EmailChannelAdapter` e a mesma thread RFC da F2.5. `From`, `To`, assunto e headers sao definidos no backend. A chave Resend `ai-email/reply/<ai_message_id>` permanece estavel. Falha de entrega deixa a mensagem `pending`; o operador pode repetir o envio do mesmo ID. O UI nao confirma entrega ate o provider retornar ID.

Assumir, trocar modo, criar resposta humana e encerrar geram AuditLog com metadata em allowlist. Corpo de mensagem, email, token e erro bruto nao entram na auditoria nem em analytics publico.

## Endpoints

Todos exigem usuario interno ativo (`admin` consistente ou `produtor`):

- `GET /admin/ai/conversations`
- `GET /admin/ai/conversations/{id}` (`before` opcional)
- `POST /admin/ai/conversations/{id}/assign`
- `PATCH /admin/ai/conversations/{id}/mode`
- `POST /admin/ai/conversations/{id}/suggestions`
- `DELETE /admin/ai/conversations/{id}/suggestions/{suggestion_id}`
- `POST /admin/ai/conversations/{id}/messages`
- `POST /admin/ai/conversations/{id}/messages/{message_id}/retry`
- `POST /admin/ai/conversations/{id}/close`

Nao existe PATCH generico de conversa nem escolha de destinatario pelo browser.

## Limites

O site depende da sessao anonima ainda valida para recuperar resposta posterior. Nao ha notificacao push, presenca, leitura ou transporte duravel de jobs. A Inbox nao verifica identidade de Cliente; isso permanece para F2.7. O retry de email depende da idempotencia do Resend quando uma chamada remota teve resultado incerto. Testes locais usam banco descartavel e clients sinteticos; PostgreSQL/Resend reais ficam para a validacao de release.
