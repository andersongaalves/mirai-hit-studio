# Mirai Hit Studio - Technical Taxonomy

## 1. Principios

- Nao duplicar dados sem necessidade.
- Evitar enums rigidos no banco quando a taxonomia precisa evoluir.
- Usar JSON somente quando houver estrutura e validacao explicitas.
- Separar classificacao comercial de apresentacao visual.
- Separar dado historico de configuracao atual.
- Nao reescrever dados originais de orcamento ou proposta.
- Preservar snapshots nos pontos em que mudancas futuras alterariam o sentido historico.
- Preferir evolucao aditiva e compativel com registros existentes.
- Backend valida slugs e permanece fonte autoritativa.

## 2. Servico

O modelo atual guarda nome, subtitulo, valor base, categoria, desconto, parametros e estrutura visual. `categoria` hoje organiza `avulso` e `combo`; nao representa vertical, segmento ou nivel comercial.

| Metadado | Classificacao | Recomendacao | Motivo |
|---|---|---|---|
| `vertical` | A. Persistir no servico | String validada, inicialmente nullable | E classificacao primaria para catalogo, jornadas e analytics |
| `segmentos` | A. Persistir no servico | Lista JSON tipada de slugs, inicialmente vazia | Um servico pode atender varios segmentos sem tabela prematura |
| `pricing_mode` | A. Persistir no servico | String validada: `fixed`, `starting_at`, `custom` | Altera exibicao de preco, CTA e futuro checkout |
| `commercial_level` | A. Persistir no servico | String validada: `entry`, `launch`, `premium`, `custom` | Permite organizar oferta e funil sem confundir com categoria |
| `cta_type` | B. Derivar | Derivar de `pricing_mode`, com ajuste de copy na camada de apresentacao | Evita texto livre redundante |
| `custom_service` | B. Derivar | `pricing_mode == custom` | Booleano duplicaria a mesma regra |
| `active` | A. Persistir no servico | Booleano `ativo`, default compativel `true` | Disponibilidade e retirada de catalogo precisam de controle |
| Publicacao independente | E. Adiar | Inicialmente, visibilidade publica acompanha `ativo` | Criar workflow editorial agora seria prematuro |
| Relacao com case | C/E. Portfolio e adiar | Usar taxonomia compartilhada primeiro | Vinculo explicito nao e necessario para filtros iniciais |

`estrutura_servico` continua exclusiva para conteudo de apresentacao; taxonomia funcional nao deve ser inserida nesse JSON. `categoria` deve permanecer durante a transicao para nao quebrar a UI atual.

## 3. Vertical e segmento

`vertical` e uma classificacao primaria unica. Recomenda-se `String` com validacao por conjunto canonico na aplicacao: `artists`, `creators`, `media_games`. Nao usar enum nativo do PostgreSQL: adicionar ou renomear valores seria mais custoso. Um enum Python ou constantes centrais podem validar API e regras sem tornar o banco rigido.

Um servico pode atender varios segmentos. Na primeira evolucao, usar uma lista JSON estritamente validada de strings canonicas. Isso e menor que uma relacao N:N, funciona com a metadata JSON ja usada pelo projeto e atende catalogo de pequeno porte. Nao usar texto separado por virgulas.

Se segmentos ganharem administracao propria, atributos, traducao ou consultas relacionais intensas, migrar depois para tabelas `segmentos` e associacao. Nao ha justificativa atual para isso.

No orcamento/lead, guardar apenas a vertical e o segmento principal escolhidos no momento da conversao. Eles sao historicos e nao devem mudar quando o servico for reclassificado.

## 4. Nivel comercial

`commercial_level` deve ser persistido no servico porque organiza catalogo, ordem de oferta, analytics e futuras experiencias comerciais. Deve ser opcional durante backfill e obrigatorio para novos servicos apos classificacao do catalogo.

Ele deve aparecer na API administrativa e publica quando o frontend passar a consumi-lo. Inicialmente nao altera preco, pagamento ou permissao; e classificacao comercial com impacto de apresentacao e medicao. Regras financeiras nao devem depender apenas desse campo.

## 5. Pricing mode

`pricing_mode` merece persistencia porque muda comportamento funcional:

| Modo | `valor_base` | Exibicao e fluxo esperado |
|---|---|---|
| `fixed` | Preco fechado publicado | Pode seguir para contratacao quando houver checkout compativel |
| `starting_at` | Valor inicial publicado | Exibe "a partir de" e exige briefing/orcamento antes do valor final |
| `custom` | Nao e preco contratavel | Valor pode ficar nulo no futuro; fluxo segue para briefing e proposta |

Na primeira migration, `valor_base` deve continuar existente e compativel. Registros antigos recebem `fixed` somente apos verificacao comercial; nao se deve inferir que todo preco atual e realmente fechado. Permitir `valor_base` nulo para `custom` pode ser uma etapa posterior, pois hoje model/schema/calculadora exigem numero.

CTA padrao derivado: `fixed` -> contratar/comecar projeto; `starting_at` -> solicitar orcamento; `custom` -> falar sobre o projeto. A copy exata pertence ao site e pode variar sem migration.

## 6. CRM, cliente e lead

Implementado em F.2: `ClienteModel` e a identidade comercial viva, com nome, email, telefone, observacoes e estado ativo. `OrcamentoModel` continua sendo o lead/oportunidade e possui `cliente_id` nullable, mantendo nome, email e WhatsApp originais como snapshot do pedido. Propostas permanecem independentes.

O matching automatico usa email normalizado e telefone quando nao houver conflito. Nome isolado nunca identifica ou une clientes. Identificadores conflitantes preservam o novo orcamento com vinculo nulo para revisao, sem criar merge ambiguo.

| Campo CRM | Classificacao | Local recomendado |
|---|---|---|
| Origem/source | Necessario em F0.3/F.2 | Lead/orcamento, nao cliente |
| Vertical e segmento | Necessarios em F.2 | Lead/orcamento; perfil do cliente pode ser derivado |
| Status comercial | Necessario em F.2 | Oportunidade/orcamento; status geral do cliente somente se houver regra clara |
| Cliente recorrente | Derivavel | Contagem de producoes/pagamentos confirmados |
| Ultimo contato | Necessario em F.2 | Derivar de interacao quando existir; campo temporario apenas se indispensavel |
| Observacoes | Necessario em F.2 | Cliente para contexto duradouro; orcamento para contexto da oportunidade |
| Valor potencial | Derivavel/por oportunidade | Proposta ativa ou valor estimado do orcamento |
| Responsavel | Necessario em F.2 | Oportunidade hoje; cliente pode ter responsavel principal opcional |

Uma entidade completa de atividades/contatos pode ser adiada ate haver inbox ou IA. Nao criar CRM generico nesta fundacao.

## 7. Orcamento

Persistir no orcamento:

- `vertical`: snapshot da jornada escolhida.
- `segmento`: segmento principal informado ou classificado.
- `lead_source`: origem comercial normalizada, definida pelo backend.
- `servico_id` nullable: referencia ao catalogo quando houver selecao real.
- Nome textual do servico e briefing atuais: permanecem como dados historicos.

UTMs, referrer e landing page pertencem a atribuicao do lead. Devem ser capturados pelo frontend/analytics, validados e registrados pelo backend, nunca aceitos como autoridade comercial. O formato e consentimento serao definidos em F0.3.

Quando vertical/segmento vierem do servico, o backend deve copia-los no momento da criacao. Se o usuario escolher outro contexto no briefing, guardar a escolha explicitamente. Reclassificar o servico no futuro nao altera orcamentos antigos.

## 8. Proposta

A proposta nao deve consultar dinamicamente a taxonomia atual do servico para representar o passado. Ao criar a proposta, seu `cliente_snapshot` deve incluir a classificacao do orcamento: vertical, segmento, servico selecionado e modalidade de preco vigente, quando disponiveis.

Nao sao necessarias novas colunas de taxonomia na proposta inicialmente. O snapshot JSON existente e adequado porque ja e um documento historico validado. Numero, status, itens, totais e transicoes permanecem controlados pelo backend.

## 9. Producao

Producao precisa operacionalmente de cliente, servico, status, responsavel, prazo e etapas, que ja existem. Vertical e segmento podem ser obtidos pelo orcamento/proposta vinculados e nao devem ser duplicados agora.

Se consultas operacionais futuras mostrarem custo real de joins ou necessidade de snapshot independente, a decisao pode ser revista. Performance hipotetica nao justifica colunas nesta fase.

## 10. Projeto e portfolio

Projeto e case/conteudo, nao execucao comercial. Para filtros e prova social verificavel, recomenda-se futuramente persistir:

- `vertical`: string validada.
- `segmentos`: lista JSON tipada de slugs.
- `case_type`: `client_case`, `demo`, `concept_project` ou `study`.

`client_case` deve ser usado somente quando houver trabalho real publicavel. Os demais tipos deixam clara a natureza de demos e estudos. `categoria` atual permanece durante a transicao e pode continuar descrevendo genero ou formato ate G.5 definir seu destino.

## 11. Relacao servico e case

Nao criar FK, N:N ou lista de IDs agora. Para o primeiro catalogo, servico e case compartilham vertical/segmento e o site pode selecionar exemplos por essa taxonomia.

Uma relacao explicita so se justifica se houver curadoria manual por servico, ordem especifica ou cases que nao possam ser selecionados corretamente por taxonomia. Se essa necessidade aparecer, preferir N:N; uma FK direta limitaria um case a um servico e lista de IDs criaria integridade fraca.

## 12. Analytics e atribuicao

`utm_source`, `utm_medium`, `utm_campaign`, `referrer` e `landing_page` nao pertencem ao servico nem ao cliente. Sao contexto de aquisicao do lead/evento e devem ser ligados ao orcamento ou a uma futura entidade de atribuicao.

F0.3 deve definir eventos, persistencia, consentimento, retencao e normalizacao. O backend deve registrar valores aceitos com limites; o frontend apenas coleta o contexto permitido.

## 13. Matriz de decisao

| Conceito | Entidade recomendada | Persistir? | Tipo sugerido | Implementacao | Motivo |
|---|---|---|---|---|---|
| Vertical do catalogo | Servico | Sim | String validada | F.2 | Classificacao primaria e comportamento de jornada |
| Segmentos do catalogo | Servico | Sim | JSON tipado de slugs | F.2 | Relacao multipla sem normalizacao prematura |
| `pricing_mode` | Servico | Sim | String validada | F3/G | Afeta preco, CTA e checkout |
| `commercial_level` | Servico | Sim | String validada | G | Organiza oferta e analytics |
| `cta_type` | Nenhuma | Nao, derivar | Regra de apresentacao | G | Evita duplicacao textual |
| `lead_source` | Orcamento/lead | Sim | String validada | F0.3/F.2 | Origem pertence a oportunidade |
| UTM/referrer/landing | Atribuicao do lead | Sim, conforme politica | Campos limitados ou estrutura dedicada | F0.3 | Contexto de aquisicao, nao catalogo |
| Cliente | Cliente | Sim | Nova entidade + FK nullable | F.2 | Unifica relacionamento recorrente sem apagar snapshots |
| `case_type` | Projeto | Sim | String validada | G.5 | Distingue cliente, demo, conceito e estudo |
| Taxonomia do case | Projeto | Sim | Vertical + JSON tipado | G.5 | Habilita filtros e prova social correta |
| Taxonomia historica | Orcamento/snapshot da proposta | Sim | Strings copiadas e snapshot JSON | F.2/G | Preserva contexto da conversao |
| Taxonomia na producao | Producao | Nao inicialmente | Derivada por vinculo | Adiar | Evita duplicacao sem necessidade |
| Relacao servico-case | Associacao N:N futura | Nao agora | N:N somente se necessario | Adiar | Taxonomia compartilhada cobre o primeiro uso |
| Publicacao separada | Servico | Nao agora | Estado editorial futuro | Adiar | `ativo` basta inicialmente |

## 14. Plano de migracao futura

### Obrigatorio

Migration 1, catalogo e historico comercial, quando a implementacao for autorizada:

1. Adicionar ao servico `vertical`, `segmentos_json`, `pricing_mode`, `commercial_level` como nullable/default seguro e `ativo` com default `true`.
2. Adicionar ao orcamento `servico_id`, `vertical`, `segmento` e `lead_source` como nullable.
3. Adicionar ao projeto `vertical`, `segmentos_json` e `case_type` como nullable/default seguro.
4. Publicar codigo que leia campos ausentes/nulos com fallback para o comportamento atual.
5. Classificar e fazer backfill dos registros existentes com revisao humana; nao inferir modalidade de preco apenas por `valor_base`.
6. Tornar obrigatorios somente os campos de novos registros que estiverem comercialmente classificados.

Todos os passos sao aditivos e podem ser implantados sem downtime se codigo antigo ignorar as novas colunas e codigo novo aceitar nulos.

Migration 2, CRM em F.2:

1. Criar `clientes` com identidade e contato canonicos, observacoes, status opcional, responsavel opcional e timestamps.
2. Adicionar `orcamentos.cliente_id` nullable com FK e indice.
3. Fazer backfill conservador; e-mail pode ajudar na correspondencia, mas conflitos exigem revisao.
4. Preservar para sempre os campos de contato existentes no orcamento como snapshot da solicitacao.
5. Passar novas solicitacoes a vincular/criar cliente de forma idempotente.

Migration 3, atribuicao em F0.3, somente se a politica exigir persistencia propria: adicionar campos limitados ao orcamento ou criar registro de atribuicao. Deve ser decidida depois de consentimento e retencao.

### Nice to have

- Tabelas de segmentos e N:N se a taxonomia ganhar administracao propria.
- Relacao N:N entre servico e case para curadoria manual.
- Estado editorial separado de `ativo`.
- Entidade de interacoes do CRM para contato, inbox e IA.
- `valor_base` nullable para servicos `custom`, coordenado com calculadora e checkout.

## 15. Recomendacao final

1. Adicionar futuramente ao servico: `vertical`, `segmentos_json`, `pricing_mode`, `commercial_level` e `ativo`.
2. Nao adicionar: CTA textual, `custom_service`, atribuicao/UTM, dados de case ou taxonomia visual dentro de `estrutura_servico`.
3. Cliente deve virar entidade propria em F.2, com vinculo nullable e snapshots atuais preservados.
4. Orcamento deve guardar vertical e segmento como contexto historico, alem de `servico_id` opcional.
5. Projeto/portfolio precisa de vertical, segmentos e tipo de case para filtros e honestidade da prova social.
6. Relacao explicita servico-case nao e necessaria agora.
7. Recomenda-se duas migrations estruturais principais: taxonomia comercial e CRM. Uma terceira de atribuicao depende da decisao de F0.3.
8. A menor mudanca estrutural capaz de suportar a Mirai 2.0 e adicionar metadados validados ao Servico, snapshots de classificacao no Orcamento/Proposta e taxonomia minima no Projeto, sem novas tabelas de classificacao.
