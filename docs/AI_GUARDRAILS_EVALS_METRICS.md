# IA Mirai: guardrails, custos, evals e metricas

## Autonomia e autoridade

| Acao | Autonomo | Copilot | Humano |
| --- | --- | --- | --- |
| FAQ, servicos e portfolio publicados | Tools publicas | Tools publicas para sugestao | Consulta administrativa |
| Status privado | Somente identidade verificada + filtro do Cliente | Mesmo controle | Rotas administrativas existentes |
| Briefing | Campos allowlisted, evidencia da mensagem atual | Sem escrita por tool | Leitura na Inbox |
| Enviar briefing | Confirmacao explicita + requisitos deterministas | Sem escrita por tool | Fluxo comercial existente |
| Responder no canal | Apenas conversa open/autonomous | Nunca automaticamente | Operador responsavel |
| Desconto, negociacao, preco customizado | Handoff | Sem tool de mutacao | Fluxos comerciais existentes |
| Pagamento, estorno, proposta, role, SQL, shell, secrets | Proibido | Proibido | Fora do core da IA |

`ToolRegistry` e a fronteira de autorizacao. Nomes desconhecidos nao executam nada;
schemas rejeitam campos extras. Identidade, Cliente, canal, ator e claim sao definidos
pelo servidor, nao pelo modelo. Sessao site, email conhecido, vinculo CRM e briefing
submetido nao elevam `identity_verified`. Leituras privadas filtram o Cliente real.
Negacao de autorizacao encerra o ciclo e encaminha ao humano, sem segunda chamada
ao provider para tentar reinterpretar a decisao de acesso.
As tools de briefing revalidam modo, claim, versao e lease antes da escrita:
assumir atendimento invalida um provider que ainda esteja em andamento.

## Guardrails de resposta

- Orchestrator encaminha negociacao, desconto, preco customizado, pagamento e reclamacao.
- Knowledge, historico, mensagem e resultados sao dados, nunca instrucoes superiores.
- A policy de resposta bloqueia padroes de promessa financeira/prazo/resultado,
  valores monetarios sem preco publicado retornado por tool e omissao do rotulo
  Demo/Concept/Study em referencias ao portfolio retornado.
- Preco base publicado nao representa proposta, preco contratado ou pagamento.
- `pricing_mode` e taxonomia futura nao sao inventados em ServicoModel.
- Briefing so aceita informacao evidenciada; prazo solicitado nao e promessa.
  Confirmacao com negacao e recusada conservadoramente; o usuario pode confirmar
  em uma nova mensagem inequivoca. Nao ha criacao automatica de newsletter/proposta.

Limite importante: checks lexicais sao defesa adicional, nao prova de veracidade de
toda resposta livre. Parafrases e idiomas ainda nao cobertos podem escapar desses
checks; autorizacao de tools continua independente disso. Casos sinteticos nao
substituem avaliacao humana do modelo real. Nao afirmar eliminacao de alucinacoes.

## Usage e custo

O adapter Responses captura provider/model, input/output/total/cached tokens quando
informados, inclusive respostas incompletas com usage. Ausencia ou inconsistencia
fica desconhecida; nao se estima token por tamanho de texto.

`ai_usage_events` armazena somente tentativa de provider, tool, decisao de turno e
geracao/uso de sugestao. Inclui latencia monotonic em ms, ciclo, codigo estavel,
IDs internos e referencia de request UUID/hash. Nao armazena prompt, mensagem,
resposta, contato, argumentos, payload, JWT, segredo ou erro bruto.

Justificativa da tabela: tokens e latencia eram descartados; sugestoes sao sobrescritas
ou removidas. Conversas, respostas e briefings continuam derivados das entidades,
sem duplicar transcript ou criar event store comercial. Retry idempotente ja
concluido nao gera nova tentativa. Tentativas pagas com resultado obsoleto/falha
permanecem contabilizadas. Falha de persistencia tecnica emite apenas categoria
segura e pode deixar lacuna: nao e ledger financeiro nem observabilidade duravel.

Rates ficam em `backend/ai/rates.json`, inicialmente `[]`. Cada entrada validada:
`version`, `provider`, `model`, `effective_from`, `currency`, `input_per_million`,
`output_per_million`, `cached_input_per_million`. Preencher somente apos verificar
a tarifa oficial aplicavel ao modelo exato e revisar a alteracao versionada.
Nao duplicar provider/model/effective_from. Usa a data efetiva mais recente anterior
ao consumo. Moedas USD/BRL/EUR nao sao convertidas nem somadas entre si.

Estimativa = ((input - cached) * input_rate + cached * cached_rate + output * output_rate)
/ 1.000.000. Sem rate/model/contagens necessarias: custo NULL, nunca zero presumido.
Cada registro conserva snapshot da tarifa e moeda; alterar configuracao nao reavalia
consumo anterior. Nao retrocalcular periodos sem dados. Sao estimativas, nao faturas.

## Definicoes do resumo administrativo

`GET /admin/ai/conversations/metrics?days=7|30`: somente operador autenticado e ativo,
mesma permissao da Inbox. Intervalo UTC movel [inicio, fim), canais site/email.
Agregacoes COUNT/SUM/GROUP BY com numero fixo de consultas, sem carregar mensagens.
Nenhum nome, email, telefone, transcript ou ID de Cliente/conversa aparece na resposta.

| Campo | Definicao |
| --- | --- |
| conversations_started | Conversas criadas no periodo (coorte) |
| cohort_closed | Dessas conversas, quantas estao closed atualmente |
| cohort_handoffs | Dessas conversas, quantas possuem handoff_reason |
| handoff_rate | cohort_handoffs / conversations_started; denominador zero = NULL |
| handoff_reasons | Ultimo motivo persistido por conversa da coorte; nao numero de reencaminhamentos |
| autonomous_replies | Outbound kind=reply criado no periodo; site persistido ou email com ID de envio |
| human_replies | Outbound kind=message, mesma regra de entrega |
| copilot_generated | Geracoes de sugestao persistidas no periodo, incluindo regeneracoes |
| copilot_used | Uso em resposta humana criada no periodo e entregue; retry nao duplica |
| briefings_started | Briefings criados no periodo |
| briefings_submitted | Status atual submitted desses briefings |
| budgets_created | Esses briefings com orcamento_id |
| briefing_conversion | budgets_created / briefings_started; denominador zero = NULL |
| provider_calls | Tentativas tecnicas registradas no periodo |
| usage_known_calls | Tentativas com input/output/total conhecidos |
| input/output/total_tokens | Subtotal das contagens conhecidas; nenhuma observacao = NULL |
| costs | Subtotais estimados por moeda, acompanhados de numero de chamadas cobertas |
| cost_unknown_calls | Tentativas sem custo estimavel |
| operations | Contagens por tool/provider/turn, resultado e codigo; latencia media observada |

Nao exibimos resolution rate: closed nao comprova resolucao, satisfacao nem ausencia
de intervencao externa. Nao calculamos acceptance rate a partir de geradas/enviadas
no mesmo periodo: uma sugestao pode ter sido gerada antes, e regeneracao muda o
denominador. Contagens sao operacionais; uma coorte por geracao seria evolucao futura.
Nao fazemos comparacao textual edited/unchanged nem similarity.

Coverage tecnica comeca no primeiro evento observado e nao garante ausencia de
lacunas. Historico anterior a F2.8 nao e reconstruido como zero consumo. Briefing
e conversa usam coortes; respostas e usage sao atividades, com rotulos distintos.

Inbox carrega metricas sob demanda ao expandir, sem polling. Estados loading/erro,
zeros, subtotais desconhecidos e retry usam foundation existente. Logout limpa o
resumo e invalida resposta pendente. Nada e enviado ao analytics publico/GA4.

## Limites e retencao

- Provider: timeout configurado 1-10s; output 1200 tokens por padrao,
  `AI_MAX_OUTPUT_TOKENS` entre 128 e 4096; sem retry automatico do adapter.
- Tools: 3 ciclos/4 chamadas por turno por padrao; schemas tipados; resultado JSON
  limitado a 32.000 caracteres por chamada; argumentos ate 8.000 caracteres.
- Mensagem ate 8.000 caracteres; historico ate 20 mensagens; contexto ate 8 itens
  de no maximo 8.000 caracteres. Limites nao equivalem a teto monetario diario.
- Site: 60 requisicoes/IP/minuto, 10 novas sessoes/IP/hora, 20 mensagens/sessao/minuto.
- Email: 5 mensagens/thread/10min e 20/remetente/hora; assinatura e idempotencia mantidas.
- Copilot: 20 geracoes/operador/minuto; 429 com Retry-After, 503 se limiter indisponivel.
- Limiter SQLite compartilha processos no mesmo host, nao multiplas instancias.
  Edge/armazenamento compartilhado e validacao de proxy ficam para I.4.
- Nao foi criada rotina de purge. Transcript, briefing e usage permanecem conforme
  armazenamento atual. Antes de producao ampliada, definir prazo operacional e
  obrigacoes comerciais por entidade; executar eventual descarte com revisao, backup
  e ordem explicita das FKs. Nao apagar contatos/transcripts nesta fase.
- Habilitar monitoramento de custo/limites no fornecedor; este resumo nao e circuit
  breaker de gasto, nem substitui alertas de falha de gravacao.

## Evals e validacao

Fixtures versionadas em `backend/tests/ai_evals/cases.json`; runner unittest em
`test_ai_guardrails.py`. 35 cenarios comportamentais: FAQ, descoberta, preco publicado,
custom, portfolio, briefing, negociacao, pagamento, refund, reclamacao, injection,
privado/cross-client, falhas de tool/provider, handoff, email/site/copilot, estados
human/waiting/closed, preco/prazo/politica/prova social falsos, rotulo Demo e desconhecidos.
Casos adicionais: negacao de envio, takeover obsoleto, payload grande, loop e resultado
excessivo. Suite knowledge/briefing complementa isolamento real entre Clientes.

Rodar em backend, somente ambiente descartavel:
`$env:PYTHONPATH='tests'; .\venv\Scripts\python.exe -m unittest test_ai_guardrails test_ai_metrics`
Fixtures usam provider e transport falsos, inclusive hostis. Assert principal e acao,
autorizacao e efeito no banco, nao frase exata. Live eval nao executado e nao obrigatorio;
qualquer execucao real futura exige credencial isolada, limite explicito e revisao humana.

Migration nova `f2a8c4e6d901`, filha de `e8b2c6d4f701`, cria apenas ai_usage_events.
RLS e revogacao anon/authenticated seguem tabelas privadas existentes. Backend usa
credencial de servidor; sem policy publica. Bootstrap inclui a mesma protecao.
Validacao local: SQLite descartavel, metadata e compilacao SQL PostgreSQL/RLS offline.
Concorrencia/roles/migration em PostgreSQL real isolado permanecem requisito de I.1.
Nao houve acesso ao banco real, envio externo ou cobranca de fornecedor nesta fase.
