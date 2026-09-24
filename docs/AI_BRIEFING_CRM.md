# Mirai AI - Briefing e CRM (F2.7)

## Fluxo

Conversa do site ou email -> briefing progressivo -> confirmacao explicita -> Orcamento + Cliente pelo service comercial existente -> atendimento humano. Antes desta fase, o pedido do formulario publico era salvo em `OrcamentoModel.detalhes`; conversas da IA nao tinham draft estruturado. O briefing nao substitui Orcamento, Cliente ou Proposta.

Cada Conversation pode ter um `AIBriefingModel` (chave `conversation_id`). O draft sobrevive a handoff e fechamento; outra conversa recebe outro briefing. `orcamento_id` e unico, e o submit usa transacao/trava da conversa para nao criar dois orcamentos. O status e apenas `draft` ou `submitted`.

## Dados e tools

Campos estaveis: servico real opcional, interesse custom, nome, email, telefone opcional, status, referencia ao orcamento e timestamps. `data_json` aceita somente `project_type`, `style`, `track_count`, `requested_deadline`, `goal`, ate cinco `references` e `notes`, com tipos, comprimentos e protocolos validados. Campos ausentes permanecem ausentes; `missing_fields` e calculado pelo servidor. Nao ha entrevista fixa por servico: a IA usa o contexto coletado para perguntar apenas o proximo dado util.

`update_briefing` e `submit_briefing` sao `CONTROLLED_WRITE` com schemas estritos. O servidor fixa Conversation e mensagem inbound atual no `ToolExecutionContext`; argumentos do modelo nao escolhem IDs de Cliente, Orcamento, status, preco, desconto, pagamento ou responsavel. Cada valor novo precisa de evidencia na mensagem do cliente. Updates fazem merge por campo e aceitam correcao explicita posterior. `submit_briefing` exige confirmacao, interesse/servico, nome e email; no email o remetente da thread pode suprir o contato. A IA nao trata remetente ou sessao guest como identidade verificada.

`ServicoModel` e consultado quando houver ID de servico; interesse custom nao cria servico novo. O prazo informado e apenas `requested_deadline`, nunca prazo prometido pela Mirai. Referencias nao sao buscadas automaticamente; uploads nao fazem parte da fase.

## Conversao comercial

`submit_briefing` chama `orcamento_service.criar_sem_commit` na mesma transacao, que reutiliza `cliente_service.resolver_para_orcamento`: email e depois telefone, sem merge automatico. Conflito entre dois Clientes cancela toda a transacao e encaminha para humano. Um Cliente novo so nasce na criacao confirmada do Orcamento. A associacao CRM nao eleva `identity_verified` nem libera tools privadas.

O Orcamento recebe `valor_total=null` (a definir), servico/interesse e resumo legivel dos dados informados; proposta e precificacao permanecem humanas. O Admin mostra `A definir` para esse valor. Lead comercial nao e inscricao em newsletter. O contato e usado para o pedido, conforme aviso no chat; nenhum campo financeiro ou documento pessoal e solicitado. A resposta de tool omite email e telefone.

## Operacao e privacidade

A Inbox exibe briefing, contato, campos faltantes e Orcamento vinculado como texto inerte. Copilot recebe o briefing como contexto, mas sugerir texto nao altera dados. Resposta humana tambem nao atualiza automaticamente o draft. Handoff preserva tudo para o operador; pedido custom e negociacao de preco seguem para atendimento comercial, sem venda autonoma.

No chat, `begin_briefing` e disparado apos a API confirmar o primeiro draft; `generate_lead` somente apos confirmar a conversao. Ambos respeitam consentimento, sao deduplicados por sessao e nao incluem PII. Email nao envia eventos de analytics publico. Logs de tools usam apenas IDs internos, nome da tool, status, duracao e categoria de erro; nao registram briefing, contato ou mensagens.

## Limites

Nao ha verificacao forte de identidade, newsletter automatica, envio automatico de proposta, definicao de preco/desconto, pagamento nem edicao de CRM pela Inbox. O formulario publico continua exigindo estimativa; o caminho da IA aceita `valor_total=null` sem alterar o banco. A migration cria somente `ai_briefings`, com RLS e revogacao para roles publicas no PostgreSQL. Testes locais de migration usam banco descartavel/SQLite; aplicar e verificar a politica no PostgreSQL real fica para o processo normal de release, nao para esta fase.
