# Decisions

## ADR-001 - Stack atual permanece

Decisao: manter frontend vanilla HTML/CSS/JS e backend FastAPI durante a Mirai 2.0.

Motivo: evitar reescrita sem necessidade comprovada.

## ADR-002 - Arquitetura comercial Mirai 2.0

Decisao: organizar a comunicacao e as ofertas em Artists, Creators e Media & Games.

Geek Music permanece especialidade transversal.

## ADR-003 - Projeto e Producao sao entidades distintas

Decisao: Projeto representa portfolio/conteudo; Producao representa execucao comercial.

## ADR-004 - Proposta independente

Decisao: Proposta possui persistencia propria e snapshot. Alterar a proposta nao reescreve a solicitacao original do cliente.

## ADR-005 - Alembic controla schema

Decisao: nao usar `create_all` no startup normal e nao editar migrations historicas.

## ADR-006 - Mercado Pago

Decisao: Mercado Pago sera o gateway inicial. O status financeiro sera confirmado no backend, preferencialmente por webhook e verificacao no provedor.

## ADR-007 - IA sem WhatsApp

Decisao: a IA Mirai tera apenas chat do site e e-mail.

## ADR-008 - IA com human-in-the-loop

Decisao: a IA nao fecha negociacoes sensiveis, nao aplica descontos especiais e nao confirma pagamentos por conta propria.

## ADR-009 - Metricas antes de CRO

Decisao: instrumentar o funil antes das fases avancadas de UX/CRO.

## ADR-010 - Git por checkpoints

Decisao: manter commits locais frequentes e fazer push somente nos checkpoints definidos no roadmap.

## ADR-011 - Quatro niveis comerciais

Decisao: usar `entry`, `launch`, `premium` e `custom` como niveis comerciais conceituais, sem impor precos.

## ADR-012 - Vertical e segmento sao distintos

Decisao: vertical organiza a necessidade comercial; segmento descreve o contexto ou especialidade. As verticais canonicas sao `artists`, `creators` e `media_games`.

## ADR-013 - Tres modalidades de preco

Decisao: usar `fixed`, `starting_at` e `custom` como modalidades comerciais, mantendo preco publicado e negociado como conceitos distintos quando necessario.

## ADR-014 - Taxonomia de servico flexivel e validada

Decisao: vertical, modalidade e nivel usam strings validadas pela aplicacao; segmentos usam lista JSON tipada. Nao criar enums nativos ou tabelas de taxonomia inicialmente.

## ADR-015 - Cliente normalizado sem apagar snapshots

Decisao: criar Cliente somente em F.2, com vinculo nullable ao Orcamento. Dados originais do pedido e snapshots de proposta permanecem historicos.

## ADR-016 - Snapshot comercial na conversao

Decisao: Orcamento guarda vertical/segmento do momento da conversao e Proposta os incorpora ao snapshot; mudancas no catalogo nao reclassificam documentos antigos.

## ADR-017 - Portfolio taxonomico antes de relacao explicita

Decisao: Projeto recebe vertical, segmentos e tipo de case. Servico e case serao relacionados por taxonomia; N:N somente se curadoria explicita se tornar necessaria.

## ADR-018 - Analytics por camada frontend

Decisao: modulos chamam uma camada unica de analytics; fornecedor nao e acessado diretamente fora dela.

## ADR-019 - PII fora de analytics

Decisao: eventos aceitam apenas nomes semanticos e propriedades em allowlist; PII, tokens, texto livre e erros brutos sao descartados.

## ADR-020 - Conversoes comerciais confirmadas pelo backend

Decisao: `generate_lead` ocorre somente apos resposta bem-sucedida do backend. Proposta, compra e producao dependem futuramente de fontes comerciais autoritativas.

## ADR-021 - Consentimento antes de tracking opcional

Decisao: GA4 e fornecedores equivalentes so carregam apos aceite explicito; recusa nao bloqueia funcionamento essencial.

## ADR-022 - Atribuicao pertence ao lead

Decisao: UTM, referrer e landing page pertencem a atribuicao do orcamento/lead, nao ao catalogo de servicos ou Cliente. Persistencia aguarda contrato de F0.3/F.2.

## ADR-023 - Tokens visuais compativeis

Decisao: tokens semanticos centralizados complementam, sem substituir, as variaveis CSS atuais. Componentes novos devem reutiliza-los.

## ADR-024 - Direcao visual music-tech premium

Decisao: Mirai 2.0 prioriza audio, estudio e tecnologia musical; referencias geek/japonesas sao assinatura secundaria e efeitos visuais nao podem prejudicar leitura.

## ADR-025 - Prova social verificavel

Decisao: cases, depoimentos e metricas exigem evidencia e autorizacao. `demo`, `concept_project` e `study` sao categorias distintas de `client_case`.

## ADR-026 - Portfolio compartilha taxonomia comercial

Decisao: portfolio futuro usa vertical, segmentos e tipo de case; nao criar relacao direta servico-case antes de necessidade curatorial comprovada.

## ADR-027 - Shell administrativo compartilhado

Decisao: o Admin evolui para um shell vanilla compartilhado, com navegacao acessivel, contexto de pagina e area principal comum, sem introduzir framework de componentes.

## ADR-028 - Fundacao visual sem abstrair dominio

Decisao: headers, filtros, badges, estados, tabelas/cards responsivos e modais podem ser reutilizados; regras de status, prazo, etapas e persistencia permanecem nos modulos de dominio.

## ADR-029 - Lista responsiva por contexto

Decisao: listagens densas usam tabela em desktop e card de entidade em mobile quando a compactacao de colunas comprometer leitura ou toque.

## ADR-030 - Modal antes de drawer

Decisao: modal acessivel e o padrao para foco em edicao ou detalhe. Drawer permanece adiado ate haver necessidade real de consulta contextual paralela.

## ADR-031 - Identidade de Cliente conservadora

Decisao: Cliente e a identidade comercial viva e Orcamento mantem snapshot historico com vinculo nullable. Matching automatico usa email normalizado e telefone; nome isolado nunca une cadastros e identificadores conflitantes exigem revisao sem merge automatico.

## ADR-032 - Dashboard operacional consolidado

Decisao: o Dashboard administrativo recebe um resumo autenticado e agregado pelo backend. KPIs usam somente estados e timestamps persistidos; nao ha receita presumida, event store ou dados pessoais desnecessarios na atividade recente.

## ADR-033 - Contas internas preservam historico

Decisao: usuarios internos usam apenas os papeis `admin` e `produtor`; o gerenciamento e exclusivo de administradores. Contas sao desativadas, nao excluidas, para preservar autoria e vinculos historicos. A lista operacional de responsaveis permanece disponivel para usuarios autenticados e retorna somente contas ativas.

## ADR-034 - Newsletter por opt-in e campanha manual

Decisao: Newsletter e comunicacao transacional sao dominios separados. A newsletter exige inscricao voluntaria, usa token opaco para cancelamento e nao cria Cliente automaticamente. Campanhas sao rascunhos enviados manualmente por administradores; cada entrega registra resultado individual e endereco de destino como snapshot historico.

## ADR-035 - Auditoria estruturada e transacional

Decisao: acoes administrativas criticas geram registros imutaveis com ator, acao, entidade, request ID e metadata em allowlist. Auditoria acompanha a transacao da mutacao quando possivel e permanece separada de logging tecnico e analytics.

## ADR-036 - Backup e restore fora da aplicacao

Decisao: backup/restore PostgreSQL usa ferramentas oficiais por scripts operacionais, nunca endpoints web. Restore e destrutivo, exige confirmacao explicita e protecao adicional para producao; dumps nao substituem backup de object storage.

## ADR-037 - Cobranca e pagamento sao dominios distintos

Decisao: uma proposta aprovada cria uma cobranca idempotente com valor em `Decimal`/`Numeric(12, 2)`. Pagamentos sao movimentos separados; somente os aprovados determinam o status financeiro. Provider e checkout permanecem externos ao nucleo do dominio.

## ADR-038 - Mercado Pago via Orders API

Decisao: Mercado Pago e o primeiro provider e usa a Orders API por HTTP direto. O backend controla valores e Access Token; cartoes chegam somente como token temporario. Cada tentativa persiste uma chave de idempotencia estavel antes da chamada, timeout permanece pendente e respostas externas sao normalizadas antes de atingir o dominio.

## ADR-039 - Webhook apenas sinaliza; Order consultada e autoritativa

Decisao: notificacoes Mercado Pago exigem HMAC oficial e nunca determinam status financeiro pelo corpo recebido. O backend consulta a Order, valida identidade, valor e moeda e aplica transicoes conservadoras sob lock curto. Entregas possuem deduplicacao tecnica; refund parcial, chargeback e divergencias ficam como conflito explicito.

## ADR-040 - Checkout guest por referencia opaca

Decisao: o checkout nao exige conta e usa a UUID publica da cobranca como credencial compartilhavel. O backend determina valores e estados; PAN/CVV permanecem no Mercado Pago, parcela comercial nao se confunde com parcelas do cartao e webhook/reconciliacao continuam autoritativos. O checkout nao entrega arquivos nem altera producao.

## ADR-041 - Core de IA independente de canal

Decisao: o core de conversas da Mirai separa adaptadores de canal, persistencia, politica de handoff, orquestracao, provider e tools em allowlist. Site e e-mail sao os canais iniciais; WhatsApp permanece fora da IA. Handoff e um estado central, nao um comportamento exclusivo da interface.

## ADR-042 - Identidade e estados de conversa separados do CRM

Decisao: Conversation vincula Cliente opcionalmente e admite referencia anonima opaca. Status operacional (open/waiting_human/closed) e modo (autonomous/copilot/human) sao independentes. Handoff idempotente pausa autonomia e conserva o primeiro motivo; copiloto gera rascunho sem envio.

## ADR-043 - Processamento de IA com lease e efeitos idempotentes

Decisao: mensagens possuem idempotencia e resposta unica no banco. Claim curto por conversa usa token, versao e lease recuperavel; provider opera fora da transacao e resultados obsoletos sao descartados. O provider padrao fica desabilitado e tools exigem registro explicito. Entrega de canal nao e responsabilidade deste core.

## ADR-044 - Knowledge pequeno e dados dinamicos via fonte autoritativa

Decisao: a IA usa conhecimento publico estruturado e versionado, sem RAG inicial. Servicos, portfolio e estados comerciais sao consultados por tools no dominio real; contexto e resultados permanecem limitados e nunca viram instrucoes de sistema.

## ADR-045 - Autorizacao de tool pertence ao servidor

Decisao: tools sao allowlisted e categorizadas. Leituras privadas exigem identidade verificada e `cliente_id` fornecido pelo contexto confiavel, nunca pelos argumentos do modelo. Queries privadas filtram o cliente e nao permitem enumeracao cruzada.

## ADR-046 - Mutacoes comerciais sensiveis permanecem humanas

Decisao: desconto, preco, proposta, pagamento, refund, usuarios e operacoes administrativas nao sao tools autonomas. Escritas de lead/briefing aguardam F2.7; preco customizado, negociacao e falhas criticas geram handoff controlado.

## ADR-047 - Canal site anonimo nao autentica Cliente

Decisao: SiteChannelAdapter reutiliza o core; token aleatorio autoriza apenas a conversa, com hash persistido e expiracao. Frontend nao controla identidade, cliente ou modo. UUID de mensagem permanece no retry; private tools continuam bloqueadas. SessionStorage conserva so sessao e eventual envio pendente, nunca transcript em analytics.

## ADR-048 - OpenAI apenas no backend

Decisao: por escolha explicita do responsavel, o primeiro provider concreto usa OpenAI Responses, configuracao por ambiente e startup independente de credenciais. Browser acessa somente API Mirai. Handoff permanece waiting_human sem alegar notificacao inexistente; Inbox segue em F2.6. Detalhes em AI_SITE_CHAT.md.

## ADR-049 - Resend como canal de e-mail da IA

Decisao: o canal bidirecional de e-mail usa Resend e permanece separado de newsletter e e-mails transacionais. O recurso e desabilitado por padrao e usa configuracao server-side dedicada.

## ADR-050 - E-mail assinado e thread por referencias RFC

Decisao: somente `email.received` e processado apos verificacao oficial dos headers Svix sobre o corpo raw. Threading usa `Message-ID`, `In-Reply-To` e `References`; assunto sozinho nao une conversas. Dados especificos ficam em `AIEmailThreadModel`.

## ADR-051 - From nao autentica Cliente

Decisao: remetente normalizado pode vincular uma conversa a um Cliente unico, mas nao eleva `identity_verified` e nao libera tools privadas. Remetentes desconhecidos nao criam Cliente automaticamente.

## ADR-052 - Entrega de e-mail idempotente e conservadora

Decisao: anexos nao entram automaticamente na IA, loops de autoresposta sao bloqueados e cada resposta outbound usa idempotency key estavel por `AIMessage`. Retry de entrega nao gera nova resposta do modelo.

## ADR-053 - Inbox unificada com responsabilidade explicita

Decisao: a Inbox agrega site e email sem fundir conversas. Operador ativo assume a conversa sob lock antes de alterar modo ou responder; assumir handoff volta a `open/human` e nao reativa autonomia. O browser nao escolhe canal nem destino.

## ADR-054 - Copilot e rascunho humano

Decisao: sugestao reutiliza o core, nunca e enviada automaticamente e pode ser regenerada no mesmo registro ou ignorada. O envio persiste texto final humano com chave idempotente; sugestao antiga e rejeitada quando chega novo inbound. Resposta manual funciona sem provider.
