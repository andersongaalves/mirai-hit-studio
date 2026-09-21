# Mirai Hit Studio - AI Knowledge and Tools

## Escopo

F2.3 conecta o core de conversas a fontes reais sem RAG, embeddings ou provider real.
Knowledge fornece contexto publico pequeno; tools consultam dados dinamicos por contratos
estritos. Mensagem, historico, contexto e resultados de tools sao sempre dados, nunca
instrucoes superiores.

## Fontes de conhecimento

| Informacao | Fonte autoritativa | Exposicao |
|---|---|---|
| Posicionamento, verticais e orientacoes publicas | `backend/ai/knowledge/public.json` | Publica |
| Servicos e valor base | `servicos` | Publica, conforme a API publica atual |
| Portfolio/cases | `projetos` com vertical e `case_type` publicos | Publica |
| Orcamento | `orcamentos` filtrado por `cliente_id` | Privada |
| Proposta | `propostas` via orcamento do cliente | Privada |
| Producao | `producoes` via proposta/orcamento do cliente | Privada |
| Pagamento | dominio financeiro e `cobrancas` | Privada |

`AIKnowledgeService` nao retorna ORM, clientes ou tabelas completas. O contexto inclui
marca e, somente quando relevante, ate tres servicos, tres projetos ou politicas por
topico. Historico continua limitado a 20 mensagens; contexto a oito itens; resultados
de tools a quatro por turno.

## Knowledge publico

O arquivo versionado contem apenas fatos estaveis: posicionamento, verticais, fluxo de
contratacao e orientacoes sobre prazo, revisoes, direitos e pagamento. Quando prazo,
revisao ou direitos dependem do escopo, a resposta exige confirmacao na proposta. Nao
ha politica comercial inventada.

Servicos e precos nao ficam no prompt. As tools leem o cadastro atual sem arredondar ou
aplicar desconto. O modelo atual de `servicos` ainda nao possui `ativo`, `vertical`,
`segmentos_json`, `pricing_mode` ou `commercial_level`. Por isso:

- todos os registros atualmente publicados pelo endpoint publico continuam consultaveis;
- a resposta marca a taxonomia como indisponivel;
- `valor_base` e identificado como valor base, nao como promessa de preco fechado;
- quando esses campos forem persistidos, a camada ja filtra `ativo = true` e deriva o
  comportamento de `pricing_mode` sem listas de nomes.

Portfolio retorna somente registros com vertical `artists`, `creators` ou `media_games`
e `case_type` entre `client_case`, `demo`, `concept_project` e `study`. O rotulo original
e preservado; demo nunca vira cliente real.

## Prompt base e injection boundary

O prompt estrutural e curto: representa a Mirai, usa somente tools oferecidas, nao
inventa fatos, nao negocia e pede humano em assunto sensivel ou sem fonte. Texto do
usuario, banco e tool output nao podem registrar tools, mudar autorizacao ou elevar o
papel da conversa. Nao existem resolucao dinamica, `eval`, SQL livre, shell ou HTTP
arbitrario.

## ToolExecutionContext

O servidor cria separadamente:

- `conversation_id`;
- `cliente_id` opcional;
- `identity_verified`;
- modo da conversa;
- ator e canal de origem;
- `request_id` tecnico.

O modelo escolhe apenas argumentos funcionais. Nunca escolhe `cliente_id`. Ter um
`cliente_id` vinculado sem `identity_verified = true` nao autoriza leitura privada.
Mecanismos concretos de verificacao pertencem aos adaptadores de F2.4/F2.5.

## Registry e categorias

Cada tool possui nome, descricao, categoria, schema de entrada, schema de saida e
handler explicito. Schemas rejeitam extras; resultados sao normalizados em `success`,
`data` e `error_code`.

- `PUBLIC_READ`: disponivel anonimamente.
- `PRIVATE_READ`: exige identidade verificada e cliente no contexto confiavel.
- `CONTROLLED_WRITE`: categoria prevista, nenhuma tool registrada nesta fase.
- `HUMAN_ONLY`: nunca pode ser registrada para execucao autonoma.

### Tools publicas

- `list_services`
- `get_service_details`
- `get_public_portfolio`
- `get_public_faq`

### Tools privadas

- `get_budget_status`
- `get_proposal_status`
- `get_production_status`
- `get_payment_status`

Nao existe listagem privada geral. Proposta, producao e pagamento usam o numero de
proposta quando possivel; a query sempre inclui o `cliente_id` do contexto. Item de
outro cliente responde `not_found`, sem confirmar sua existencia. Financeiro retorna
somente estado confirmado, total, pago, saldo e disponibilidade de checkout; nao expoe
provider IDs, webhooks, cartao ou conciliacao interna.

## Writes e acoes humanas

Nenhuma escrita foi implementada. `create_lead`, interesse e briefing continuam para
F2.7, usando o CRM existente. Permanecem exclusivamente humanas:

- desconto ou alteracao de preco;
- edicao/cancelamento de proposta;
- marcar pagamento, refund ou cancelar cobranca paga;
- usuarios, roles e operacoes administrativas;
- SQL, shell e mutacoes arbitrarias.

Handoff continua uma decisao deterministica do orquestrador. Negociacao, desconto,
preco customizado, reclamacao e problema de pagamento nao dependem de tool sugerida
pelo provider.

## Tool calling e limites

Fluxo: provider pede tool, registry valida allowlist/politica/schema, handler executa,
resultado normalizado retorna ao provider e ele responde ou pede handoff.

- maximo de tres ciclos de tools por turno;
- maximo de quatro chamadas por turno;
- maximo de tres chamadas por resposta do provider;
- argumentos limitados por schema, quantidade de campos e tamanho serializado;
- tool desconhecida, falha temporaria ou output invalido geram handoff `tool_failure`;
- input invalido, nao autorizado ou item ausente retornam erro controlado para uma
  possivel resposta segura; repeticao termina pelo limite de ciclo/chamadas.

O contrato e vendor-neutral. Provider desabilitado continua sendo o padrao e nenhuma
chave externa e necessaria.

## Logging e privacidade

Logs tecnicos registram somente nome da tool, sucesso, codigo de erro, duracao,
conversation UUID e request ID protegido. Argumentos, resultados, mensagens, email,
telefone, briefing, tokens e exceptions nao sao copiados. Leituras rotineiras nao
poluem o `AuditLog` administrativo.

## Lacunas

- Persistir taxonomia/visibilidade de servicos continua uma evolucao de dominio, nao
  uma migration de IA.
- Nao ha prazo, revisoes ou direitos universais alem do que a proposta confirma.
- Verificacao concreta de identidade depende do canal em F2.4/F2.5.
- Escrita estruturada de briefing/CRM permanece em F2.7.
- Provider real, rate limit do chat, custos e evals permanecem posteriores.
- Locking e RLS reais ainda precisam de PostgreSQL descartavel em I.1/I.3.

F2.3 nao cria tabela, migration, RAG ou copia de dados privados em knowledge.
