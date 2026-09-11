# Auditoria do Mirai Hit Studio
Data: 11/09/2026. Escopo: código local, estrutura, contratos, comportamento isolado do frontend e verificações públicas de produção.

## Parecer
O projeto ainda não está pronto para encerrar o desenvolvimento ou ser considerado pronto para produção. A arquitetura modular existente é aproveitável; não há justificativa para trocar HTML/CSS/JavaScript vanilla ou reescrever o sistema.

Os maiores bloqueios são autenticação insegura, integração incompleta do model de propostas, ausência do fluxo persistente de propostas e perda de informações na solicitação do cliente. O site publicado funciona nas páginas verificadas, mas apresenta desempenho abaixo da meta e problemas de acessibilidade e SEO técnico.

Esta etapa não implementa correções. As alterações preexistentes do usuário foram preservadas. O único arquivo de projeto criado nesta auditoria é este relatório.

## 1. Escopo e limites das evidências
- Inventário de 93 arquivos no frontend, incluindo 69 módulos JavaScript.
- Leitura das páginas, componentes, estilos, módulos públicos e administrativos, routers, CRUDs, schemas, models, serviços, templates de e-mail e das sete migrations.
- Sintaxe de 55 arquivos Python verificada por AST, sem executar scripts de administração.
- Sintaxe e ligação dos imports/exports dos 69 módulos JavaScript verificadas.
- Testes do ORM, autenticação, contratos e migration inicial com configuração sintética e SQLite em memória. Nenhum banco real foi alterado ou consultado.
- Testes de navegador em Edge/Playwright com arquivos locais e respostas de API sintéticas. Nenhum pedido, e-mail ou alteração administrativa real foi enviado.
- Checagens em 320, 414, 768, 1440 e 2560 px; interação com calculadora, login, configuração e propostas; inspeção visual do editor em celular.
- Requisições públicas GET e OPTIONS para verificar URLs, cabeçalhos, health e CORS.
- Lighthouse 13.4.1 nas três páginas públicas publicadas, uma execução mobile por página, Chrome headless, rede simulada e redução de CPU de 4x.
- Não foi feita auditoria autenticada de produção, leitura de logs reais, varredura completa do histórico Git, inspeção de permissões do Supabase ou teste de restauração de backup.
- Não foi consultado CrUX/Search Console. Os números de laboratório não são métricas reais de campo nem certificação de conformidade.
- O código local contém alterações ainda não commitadas. Resultados locais e resultados do deploy devem ser tratados separadamente.

## 2. Módulos e estado atual
| Área | Estado encontrado | Pendência e prioridade |
| --- | --- | --- |
| Home | Página, marca, carrossel de destaques, componentes e newsletter | Desempenho, headings, estabilidade visual e acessibilidade. ALTO. |
| Serviços públicos | Seleção e conteúdo dentro da calculadora; não há página exclusiva de serviços | Corrigir segurança do renderer e contratos. Página própria somente se houver conteúdo editorial útil. ALTO. |
| Portfólio público | Listagem e filtros por categoria | Imagens, HTML não escapado, títulos e carregamento. ALTO. |
| Orçamento público | Calculadora em três passos e POST de solicitação | Não envia os detalhes digitados; validação e prevenção de duplicações incompletas. ALTO. |
| Contato | Instagram, newsletter e solicitação de orçamento | Newsletter não é formulário de contato. Definir canal efetivo de contato; não inventar localização. MÉDIO. |
| Dashboard | Menu de cinco áreas, sem indicadores operacionais | Inicialização após login quebrada; indicadores devem refletir dados reais. ALTO. |
| Serviços admin | CRUD, parâmetros e builder modular | Validação de estrutura, XSS no builder, responsividade. ALTO. |
| Orçamentos / CRM | Listagem, busca, filtro, produtor, notas e mudanças de status | Fluxo não protegido no backend; filtro desatualizado; aprovação usa orçamento original. ALTO. |
| Propostas | Editor local em seis abas e model incompleto | Sem persistência, API funcional, PDF, QR, envio ou aceite integrado. CRÍTICO para ORM; ALTO para completar o produto. |
| Produção | Listagem, status, checklist e prazo | Sem edição persistente de observações ou criação de etapas pela UI; validações frágeis. ALTO. |
| Projetos | CRUD de portfólio | Não é a entidade de execução comercial. Preservar distinção entre Projeto de portfólio e Produção. MÉDIO. |
| Clientes | Dados presentes nos orçamentos e produções | Não existe módulo. Começar com consulta consolidada e histórico, sem copiar dados indiscriminadamente. MÉDIO. |
| Usuários | Model, listagem protegida e script CLI de criação | Não existe gestão de usuários no painel nem autorização por papel. ALTO. |
| Newsletter | Cadastro e boas-vindas | Sem listagem administrativa, descadastro, consentimento registrado ou campanhas. MÉDIO. |
| Comunicação | Templates de confirmação/notificação e Resend | Sem histórico confiável de entrega, reenvio ou proposta anexada. ALTO. |
| Financeiro | Estimativas e campos locais de pagamento na proposta | Não existe controle de recebimentos. Link/QR não comprova pagamento. MÉDIO. |
| Calendário | Apenas prazo em produção | Pode começar como visão dos prazos existentes, sem entidade duplicada. MÉDIO. |
| Configurações | Tabela de custos | Contrato de desconto quebrado; limites não validados. ALTO. |
| Logs | Prints e arquivo de logger praticamente vazio | Remover dados sensíveis e registrar eventos úteis com controle de acesso. CRÍTICO/ALTO. |
| Backup | Serviço vazio e importação de JSON no startup | Não há backup/restauração operacional verificável no projeto. ALTO. |

Não criar módulos vazios para preencher o menu. Clientes, calendário e indicadores podem inicialmente ser projeções dos dados existentes. Financeiro exige um modelo real de recebimentos antes de ser apresentado como funcional.

## 3. Achados críticos
### C01 — Credenciais e tokens nos logs
**CRÍTICO — confirmado no código.**
Em `backend/core/dependencies.py:13` são impressos tokens; em `:20`, payloads; em `:27`, a chave secreta em caso de erro JWT.
Impacto: logs podem permitir reutilização de sessão e, se a chave tiver sido exposta, assinatura de novos tokens.
Correção: retirar logs sensíveis, sanitizar registros e verificar exposição no ambiente. Se essa versão foi executada e o segredo entrou em logs, rotacionar a chave e invalidar sessões por procedimento controlado. Não foi afirmado que um terceiro acessou esses logs.

### C02 — ORM não consegue resolver PropostaModel
**CRÍTICO — reproduzido isoladamente.**
`backend/models/orcamento.py:51` declara relationship para `PropostaModel`, mas `backend/models/__init__.py` não registra esse model. Ao importar diretamente `backend/models/proposta.py:7`, ocorre `ModuleNotFoundError: No module named 'enums'`; o enum existente está em `models/enums/proposta.py`.
`configure_mappers()` e `startup_database()` falham com `InvalidRequestError`. Importar FastAPI ou responder health não garante que as consultas ORM funcionem.
Correção: acertar import, registro e metadata; preparar a migration da entidade antes de implantar. Não habilitar criação automática de tabelas como substituto de migration.

### C03 — Histórico de migrations não inicializa banco vazio
**CRÍTICO para instalação reproduzível — reproduzido isoladamente.**
A primeira revision, `b59e3f99f562`, já executa ALTER na tabela `servicos`; nenhuma das sete revisions cria as tabelas iniciais. O teste no banco vazio falhou por ausência de `servicos`.
Além disso, `backend/main.py:18` executa `create_all` no import, concorrendo com a responsabilidade do Alembic.
Correção: documentar/reconstruir um bootstrap ou baseline versionado separado para bancos novos, preservando as revisions já aplicadas. Uma migration nova no final da cadeia, sozinha, não corrige o replay desde um banco vazio. Conferir o estado do banco existente antes de qualquer stamp ou mudança de estratégia.

## 4. Segurança e contratos
| ID | Prioridade | Evidência / impacto | Correção proposta |
| --- | --- | --- | --- |
| S01 | ALTO | `core/dependencies.py` devolve apenas `sub`, sem buscar usuário, validar papel ou exigir tipo access. Tokens sintéticos assinados com usuário inexistente, sem subject e do tipo refresh foram aceitos pela dependência. | Validar claims obrigatórias e tipo, buscar usuário ativo e aplicar permissões. Unificar algoritmo com `core/security.py`, que fixa HS256 enquanto a dependência usa settings. |
| S02 | ALTO | `is_admin` e `role` existem, mas não protegem operações. Usuários não administrativos com token válido recebem o mesmo acesso. | Matriz simples de permissões; validar também acesso por produtor se esse isolamento for adotado. Não tratar IDs sequenciais como vulnerabilidade por si só. |
| S03 | ALTO | `service_renderer.js`, `ui.js`, `portfolio_ui.js`, `builder_dom.js` e `builder_preview.js` interpolam dados em HTML/atributos. O renderer executou um evento HTML sintético no teste. | Texto via DOM/textContent ou escape centralizado; validar URLs por protocolo; nenhuma execução de HTML vindo de campos livres. |
| S04 | ALTO | JWT em localStorage amplia o impacto de XSS. Logout oculta o admin, mas não limpa os estados nem fecha modais que estão fora de `admin-area`. | Corrigir XSS, encerrar contexto visual/dados no logout e definir ciclo de sessão. Migração para cookies exige avaliar CSRF, domínio e CORS, não apenas trocar o armazenamento. |
| S05 | ALTO | Login, orçamento e newsletter não possuem limitação de requisições no código. Solicitações enviam e-mails síncronos. | Limites no ponto de entrada e aplicação conforme infraestrutura, limites de payload, proteção contra repetição e abuso. Verificar regras externas antes de duplicá-las. |
| S06 | ALTO | Schema de orçamento aceita nome/serviço vazios, total negativo e URL `javascript:`; produtor não é validado explicitamente. | Comprimentos, formatos, números finitos e não negativos, URLs HTTP(S), referência válida de serviço/produtor e erros coerentes. |
| S07 | ALTO | Preço e seleção de parâmetros são calculados só no frontend. O backend grava `valor_total` informado. | Preservar solicitação e valor informado como origem; calcular/validar estimativa no backend com parâmetros estruturados. Proposta deve ter seus próprios totais autoritativos. |
| S08 | ALTO | Serviços guardam JSON como string sem schema. JSON sintaticamente válido como `null` quebra renderer; listas/itens inválidos quebram builder. | Validar a estrutura tipada na API e normalizar dados legados; renderização defensiva. |
| S09 | MÉDIO | Sem CSP, HSTS ou proteção contra framing nos cabeçalhos das páginas públicas amostradas; há `nosniff` e gzip no frontend. | Definir cabeçalhos no deploy, testar CSP inicialmente em report-only e remover handlers inline gradualmente. Evitar bloquear o próprio admin/preview. |
| S10 | MÉDIO | Senha sem limites no schema; bcrypt 5 pode rejeitar entradas acima do limite em bytes; criação CLI usa senha como argumento. | Política e validação em bytes, tratamento de falhas sem 500 e leitura de senha sem expô-la em argumento de processo. |
| S11 | MÉDIO | Settings de backup, refresh e outras opções não têm fluxo implementado; faltam observabilidade e health de prontidão. | Separar liveness de readiness; validar configuração e documentar recursos efetivamente suportados. |

Pontos positivos: consultas examinadas usam SQLAlchemy e filtros parametrizados; não foi encontrada SQL dinâmica baseada em entrada de usuário. Schemas de usuário não retornam hash de senha. Jinja dos e-mails habilita autoescape. CORS publicado permitiu os dois domínios Mirai testados e rejeitou `https://audit.invalid`. Não há endpoint de upload implementado para auditar. Não foi demonstrada vulnerabilidade de mass assignment arbitrário: os payloads atuais passam por schemas, embora estes tenham validação insuficiente.

## 5. Fluxo comercial e funcionalidades incompletas
| ID | Prioridade | Problema confirmado | Arquivos principais |
| --- | --- | --- | --- |
| F01 | ALTO | Pedido enviado com `detalhes: ""`, descartando descrição e escolhas. Reproduzido após preencher o campo de descrição. A mensagem chama orçamento de proposta enviada. | `frontend/js/modules/orcamento.js:34`, `ui.js`, schemas/serviço de orçamento. |
| F02 | ALTO | Formulário usa `cfg_desconto`; API exige `desconto`. Campo fica vazio ao carregar e o payload é inválido, gerando 422 no schema. | `admin/configuracoes.js:14`, `admin.html:439`, `schemas/config.py`. |
| F03 | ALTO | Login novo mostra painel sem carregar listas. No teste havia zero serviços após login e dois após recarregar. | `admin/auth.js`, `admin/index.js:45`, `admin/dashboard.js`. |
| F04 | ALTO | Propostas sempre são criadas em memória a partir do orçamento; fechar apaga rascunho sem confirmação. Salvar/PDF estão disabled. | `propostas/propostas.js:104`, `:117`, `admin.html:791`. |
| F05 | ALTO | API frontend aponta para `/propostas/orcamento/{id}`, mas não há router, schemas, CRUD ou serviço backend de propostas. | `proposta_api.js`, `backend/main.py`. |
| F06 | ALTO | Itens e entrada re-renderizam a aba no input e perdem foco. Componentes chamam setters do state diretamente, contrariando input → controller → state → render. | `proposta_itens.js:61`, `proposta_pagamento.js`, `proposta_form.js`, `proposta_condicoes.js`. |
| F07 | ALTO | Model e frontend divergem: `itens_json`/itens, lista `pagamentos_json`/objeto pagamento, `produtor_id`/texto responsável. Snapshot não é usado na UI. Template e notas internas da proposta não existem no model. | `models/proposta.py`, `proposta_state.js`, `proposta_utils.js`, `proposta_cliente.js`. |
| F08 | ALTO | Endpoint legado registra envio e caminho de PDF fictício, sem gerar documento nem enviar e-mail. | `routers/orcamentos.py:147`, `crud_orcamento.py:78`. |
| F09 | ALTO | PATCH de orçamento aceita qualquer status do enum, sem validar transição ou proposta. Aprovação cria produção a partir do orçamento, sem proposta aceita. | `crud_orcamento.py:61`, `crud_producao.py:40`. |
| F10 | ALTO | Aprovação faz consulta prévia e depende de UNIQUE, mas não trata concorrência nem retorno idempotente em conflito. Commits estão divididos entre CRUDs. | `crud_producao.py:64`, `crud_orcamento.py:72`, `models/producao.py`. |
| F11 | MÉDIO | Filtro CRM ainda oferece recusado e omite proposta_enviada. Modal tenta preencher `orc_status`/`orc_produtor`, ausentes no HTML; resposta só tem produtor_id. | `admin.html:532`, `orcamentos_modal.js`, `orcamentos_utils.js`. |
| F12 | ALTO | Produção aceita qualquer string de status e JSON livre em etapas. Modal usa JSON.parse sem proteção. Observações são editáveis, mas não há ação de salvar. Não há UI para adicionar etapas. | `schemas/producao.py`, `producoes_modal.js`, `admin.html`. |
| F13 | MÉDIO | Prazo não pode ser limpo pelo contrato; datetime-local não normaliza fuso. Atualização de prazo não redesenha lista e etapas falhadas não são revertidas na UI. | `schemas/producao.py`, `producoes_modal.js`, `producoes.js`. |
| F14 | MÉDIO | Exclusão de projeto mostra sucesso sem checar response.ok. Botões de envio/salvar não têm bloqueio consistente contra cliques repetidos. | `admin/projetos.js`, módulos de orçamento/newsletter/serviços. |
| F15 | MÉDIO | Trocar para serviço sem parâmetros deixa formulário anterior. Badges de desconto usam o mesmo ID nos cards e no resultado; foram observados três IDs iguais. | `ui.js`, `modules/calculator.js`, `calculadora.html`. |
| F16 | ALTO | E-mail ocorre depois do commit e falhas são convertidas em None. Resposta HTTP não representa entrega, não existe fila persistida/reenvio. | `services/email_service.py`, routers de orçamento/newsletter. |
| F17 | ALTO | Excluir orçamento pode conflitar com FK de produção; relacionamento de proposta configura delete-orphan, podendo apagar o documento associado quando integrado. | `routers/orcamentos.py`, models de orçamento/produção/proposta. |
| F18 | MÉDIO | Newsletter não possui descadastro, histórico de consentimento nem tratamento de corrida de cadastro duplicado. | `routers/newsletter.py`, `models/newsletter.py`, footer e templates. |

Os campos legados de proposta continuam referenciados em model, schema, CRUD e router de orçamento. Não podem ser removidos agora. O fluxo novo deve assumir a responsabilidade antes de uma migration de limpeza, com reconciliação de registros legados: a flag antiga não prova que houve envio de e-mail.

## 6. Arquitetura e dívida técnica
- **ALTO:** lógica de transição, criação de produção e commits misturam negócio/persistência em CRUD. Routers de config, projetos, serviços e newsletter acessam o ORM diretamente.
- **ALTO:** ainda não existe uma unidade transacional para aprovar proposta, atualizar orçamento e criar produção.
- **MÉDIO:** callbacks são usados em orçamentos/serviços, mas produção faz imports circulares entre controller, UI e modal. Padronizar pelo fluxo já existente de callbacks.
- **MÉDIO:** `frontend/js/ui.js` concentra templates da calculadora, serviços, requisição/render de portfólio, componentes compartilhados, efeitos e eventos.
- **MÉDIO:** `frontend/js/admin/projetos.js` reúne estado, API, criação de DOM, formulário e ações. Extrair gradualmente para pasta própria, mantendo entrypoint compatível enquanto houver consumidores.
- **MÉDIO:** três wrappers repetem `handleResponse`; helpers DOM e modal se repetem. Consolidar somente interfaces comprovadamente comuns, sem criar abstrações genéricas excessivas.
- **MÉDIO:** formatação de capa de YouTube está duplicada em `ui.js` e `portfolio_ui.js`, com fallback para PNG inexistente.
- **MÉDIO:** `main.js` espera nav/footer antes dos módulos de página; erro de um módulo pode impedir os seguintes. Isolar carregamentos e estados de erro.
- **MÉDIO:** dashboard carrega todos os dados mesmo sem abrir áreas; listagens retornam tudo, sem paginação; busca re-renderiza toda a lista em cada tecla.
- **MÉDIO:** model de Projeto redeclara link_audio/link_capa; schema de Produção redeclara created_at/updated_at.
- **BAIXO:** espaçamento e comentários narrativos inflam o tamanho de vários arquivos; compactar apenas os trechos alterados.
- **BAIXO:** README descreve SQLite, pasta front e pasta alembic em desacordo com a organização atual.

Arquivos maiores: `admin.html` 863 linhas; `calculator.css` 565; `admin.css` 380; `components.css` 346; `ui.js` 299; `admin/projetos.js` 236. Quantidade de linhas sozinha não justifica dividir arquivos; responsabilidade e testabilidade são os critérios.

## 7. Banco e migrations
- **CRÍTICO:** baseline ausente e efeitos de schema no import, conforme C03.
- **ALTO:** proposta não participa da metadata Alembic e não possui migration.
- **ALTO:** valores monetários existentes usam Float. No novo documento comercial usar Decimal/Numeric, precisão e arredondamento definidos no backend; JSON monetário com representação decimal estável.
- **ALTO:** versionamento precisa distinguir revisão comercial de controle de concorrência. UNIQUE em orçamento_id permite uma proposta raiz por orçamento, mas não guarda versões históricas sozinho.
- **ALTO:** preservar snapshot de cliente/orçamento ao criar documento. Reabrir proposta não deve substituir snapshot por dados atuais.
- **ALTO:** remover documento em cascata ao excluir orçamento não é uma política apropriada para registros comerciais enviados/aceitos; definir arquivamento e restrições.
- **MÉDIO:** produtor_id recebe FK sem validação de existência/papel; conflitos podem virar 500.
- **MÉDIO:** vários status são strings sem constraint; campos de data/status importantes aceitam NULL em alguns models; defaults Python não protegem inserções externas.
- **MÉDIO:** criar índices para consultas reais de status, produtor, datas e paginação; decidir por EXPLAIN e volume, evitando índices sem uso.
- **MÉDIO:** nomes de constraints e estratégia de downgrade merecem revisão: migration CRM cria/remove FK com nome None. Não modificar arquivo histórico; planejar migração corretiva e política de rollback.
- **ALTO:** startup restaura dados de arquivos de backup implicitamente, se presentes. Pode reintroduzir serviços/projetos excluídos e disputar execução entre workers. Restauração deve ser operação explícita.
- **Pendente:** comparar models com schema, constraints e alembic_version do PostgreSQL real em procedimento somente leitura. Testes SQLite não validam semântica JSONB, locks e concorrência PostgreSQL.

## 8. API: inventário e consumidores
| Endpoints existentes | Consumidor no repositório | Estado |
| --- | --- | --- |
| POST /auth/login | admin/auth.js | Usado; falta robustez de sessão/permissões. |
| GET /config | calculadora e admin/configuracoes.js | Usado. |
| PUT /config | admin/configuracoes.js | Usado com payload incompatível. |
| GET /servicos | calculadora e admin/servicos | Usado. |
| POST /servicos; PUT/DELETE /servicos/{id} | admin/servicos | Usados; validação insuficiente. |
| GET /projetos | home, portfólio e admin/projetos.js | Usado; listagem integral. |
| POST /projetos; PUT/DELETE /projetos/{id} | admin/projetos.js | Usados. |
| POST /orcamentos | modules/orcamento.js | Usado; detalhes perdidos. |
| GET /orcamentos; DELETE /orcamentos/{id} | admin/orcamentos | Usados; sem paginação/política de retenção completa. |
| PATCH /orcamentos/{id}/status, /produtor, /observacoes | admin/orcamentos | Usados; transições e relacionamentos precisam validação. |
| POST /orcamentos/{id}/enviar-proposta | Wrapper exportado em orcamentos_api.js, sem chamada ativa encontrada | Legado perigoso; não presumir que não há consumidor externo. |
| GET /usuarios | Seleção de produtor no CRM | Usado; não é módulo de gestão de usuários. |
| GET /producoes | admin/producoes | Usado. |
| POST /producoes | Nenhum consumidor frontend encontrado | Manter até decidir criação manual e verificar uso externo. |
| PATCH /producoes/{id}/status, /etapas, /prazo | admin/producoes | Usados. |
| POST /newsletter | modules/newsletter.js | Usado. |
| GET /; GET /health | Sem consumidor frontend necessário | Operacionais; não considerar mortos. |
| /docs, /redoc, /openapi.json | Documentação automática | Definir exposição por ambiente; não substitui autenticação. |
| GET/POST /propostas/orcamento/{id} | Apenas funções frontend ainda desconectadas | Endpoints inexistentes no backend. |

Padronizar schemas Create/Update/Response, erros estruturados e status HTTP. Usar 201 para criação, definir 204 ou resposta para exclusão, 401 para sessão inválida, 403 para permissão insuficiente, 404 para recurso ausente e 409 para versão/transição conflitante. O formato de erro precisa ser interpretado uma única vez pelo cliente HTTP, incluindo os detalhes de validação 422.

## 9. Acessibilidade e responsividade
- **ALTO:** cards de serviço escondem o input radio com display:none; títulos de accordion são div com onclick. Não há operação equivalente adequada pelo teclado.
- **ALTO:** menu principal só abre por hover. Focar o botão por teclado não abriu os links no teste.
- **ALTO:** não existem estilos gerais de `.modal`/`.modal-content`. Editor renderiza como bloco estático no fluxo da página; nenhum gerenciamento de foco, Escape, retorno de foco ou bloqueio de fundo.
- **ALTO:** itens de proposta excedem viewport em 320, 414 e 768 px. Builder reserva 420 px à direita sem breakpoint. Dashboard e formulários têm grades rígidas.
- **MÉDIO:** newsletter sai da tela em 320 px; notificações têm largura fixa de 340 px mais margem lateral.
- **MÉDIO:** labels frequentemente não usam for/id nem envolvem o input. Inputs de login, newsletter, cliente e proposta precisam nomes acessíveis consistentes.
- **MÉDIO:** cards de navegação do dashboard são div clicáveis; controles com símbolos precisam nomes acessíveis.
- **MÉDIO:** notificações não têm região live; erros de formulário não se associam ao campo nem preservam um fluxo de correção claro.
- **MÉDIO:** sem tratamento de prefers-reduced-motion; partículas e efeitos permanecem ativos.
- **MÉDIO:** Lighthouse confirmou contraste insuficiente: links do footer aproximadamente 2,56:1 e copyright 1,51:1 sobre o fundo medido.
- **MÉDIO:** alterações de abas não têm semântica/teclado de tabs; usar botões e regiões corretamente, com ARIA apenas onde necessário.

A correção anterior da altura dos cards de serviços está presente: o limite de 500 px foi removido. Isso não resolve os problemas independentes de modais, tabelas e grids administrativos.

## 10. SEO técnico e site público
Pontos presentes: títulos e descriptions específicos nas três páginas, idioma pt-BR, viewport, canonical, Open Graph, Twitter Cards, robots, sitemap e JSON-LD. A home já possui logo WebP com dimensões explícitas e preload.

Problemas:
- **ALTO:** URLs inexistentes retornam home com HTTP 200. Confirmado com manifest, PNG inexistente e caminho de auditoria. Isso mascara 404 e produz recursos com MIME incorreto.
- **MÉDIO:** `site.webmanifest` é referenciado, mas não existe no frontend; em produção retorna HTML e gera erro no console.
- **MÉDIO:** `img/logo-principal.png` não existe. É usado como fallback e em dados estruturados. O recurso real principal é WebP.
- **MÉDIO:** home prefere domínio sem www; outras páginas, sitemap e JSON-LD alternam www. Ambos os hosts responderam 200 sem redirecionamento entre eles.
- **MÉDIO:** canonical aponta para URLs sem extensão, sitemap usa .html e OG do portfólio usa .html. As URLs amigáveis testadas funcionam, mas as referências precisam convergir.
- **MÉDIO:** navbar usa H1. Com ela carregada, home tem dois H1 e portfólio tem H1 adicional por card. Calculadora só tem H1 da navbar, não do conteúdo principal.
- **MÉDIO:** saltos de heading e ausência de landmark main na calculadora.
- **MÉDIO:** admin não possui noindex; robots permite tudo. Noindex não é controle de acesso, e bloquear crawler não substitui autenticação.
- **MÉDIO:** serviços e portfólio dependem de JS/API; prever conteúdo inicial útil e estado de falha. Não criar páginas com texto repetido apenas para segmentar palavras-chave.
- **BAIXO:** links do footer usam barras invertidas e caminhos relativos ao contexto de inserção. Normalizar para URLs coerentes.
- **BAIXO:** datas de sitemap são estáticas e precisam refletir alterações relevantes.
- **BAIXO:** referências genéricas nos e-mails, como link para YouTube sem canal e CTA de portfólio apontando para home.

Proposta SEO: uma identidade única por @id para Organization/WebSite; Service apenas para serviços reais; BreadcrumbList quando houver hierarquia navegável. Reavaliar ProfessionalService/LocalBusiness sem inventar endereço ou presença física. Brasil aparece explicitamente como área atendida; cidade/bairro só devem entrar com confirmação do negócio. Linguagem natural sobre produção musical, mixagem, masterização, instrumentais, beats, rap e universo geek.

A documentação do Google orienta manter sinais de canonicalização consistentes; nota 100 no Lighthouse não valida todo o SEO nem garante ranking. Referência: [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls).

## 11. Desempenho e Core Web Vitals
### Baseline de produção
Lighthouse mobile, uma execução por URL em 11/09/2026, sem alterações entre medições. Não são médias nem dados de usuários reais.

| Página | Performance | Accessibility | Best Practices | SEO | LCP | TBT | CLS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Home | 50 | 90 | 96 | 100 | 3,9 s | 3.800 ms | 0,109 |
| Calculadora | 70 | 90 | 96 | 100 | 3,8 s | 250 ms | 0,112 |
| Portfólio | 45 | 90 | 73 | 100 | 9,4 s | 140 ms | 0,425 |

INP não foi medido. Lighthouse de navegação usa TBT como diagnóstico de bloqueio, não como equivalente de INP. As metas de campo são LCP ≤ 2,5 s, INP ≤ 200 ms e CLS ≤ 0,1 no percentil 75, separando mobile/desktop. Referência: [Web Vitals](https://web.dev/articles/vitals).

O SEO 100 não elimina os achados manuais. A nota de acessibilidade também não cobre adequadamente os fluxos administrativos, abas e controles não exercitados nessa navegação.

### Gargalos e prioridades
- **ALTO:** home apresentou 7,5 s de trabalho na thread principal; gtag respondeu por cerca de 2,1 s de execução no teste. Rever carregamento e configuração de analytics sem remover medição às cegas.
- **ALTO:** portfólio teve LCP de 9,4 s e CLS de 0,425. A imagem de LCP é descoberta após JS/API. Reservar espaço para filtros/cards e priorizar somente a imagem inicialmente visível.
- **ALTO:** inserção assíncrona de navegação/conteúdo desloca layout. O maior shift da home envolveu main.container. Reservar dimensões e tornar cabeçalho inicial previsível.
- **MÉDIO:** main.css carrega CSS de todas as páginas, inclusive admin, e importa portfolio.css duas vezes. Há cadeia adicional de Google Fonts.
- **MÉDIO:** Ethnocentric TTF não declara font-display. Preferir WOFF2 e revisão de uso/pesos; fonte local tem apenas cerca de 61 KiB, não é o maior arquivo.
- **MÉDIO:** favicon local tem 743.997 bytes; banner social 2.106.693; logo principal WebP 182.528; logo P&B 479.365. Redimensionar por uso. O banner social é metadado, não deve ser contado automaticamente como custo de renderização da página.
- **MÉDIO:** imagens dinâmicas não têm política de lazy/decoding/dimensões consistente. Imagens acima da dobra devem continuar eager; lazy apenas fora da área crítica.
- **MÉDIO:** carrossel triplica o HTML e elementos focáveis. O cache pode reutilizar imagens, mas isso não elimina custo de DOM/render/acessibilidade.
- **MÉDIO:** lista pública/admin sem paginação; orçamento envia dois e-mails síncronos antes de responder.
- **MÉDIO:** efeitos de mouse consultam DOM e alteram estilo em cada evento; usar referência estável e requestAnimationFrame quando necessário.
- **MÉDIO:** CSS duplicado/obsoleto e seletores globais causam colisões. .btn-small, .hidden e estilos de builder se repetem; animations.css não é importado apesar de classes referenciadas.
- **MÉDIO:** portfólio publicado usa ao menos um recurso de Google Drive que dispara fluxo de cookies de terceiros; revisar URLs de capa para garantir que sejam imagens, não páginas de compartilhamento.
- **BAIXO:** minificação/build não está configurado no repositório; adicionar etapa simples e reproduzível apenas após medir ganho. Não introduzir framework para isso.

Frontend publicado já retorna gzip e cache com revalidação para HTML; não há motivo para afirmar que compressão inexiste. Política de cache de assets versionados pode ser melhorada sem aplicar cache público a API privada ou documentos comerciais.

Objetivo posterior: Performance ≥90, Accessibility ≥90, Best Practices ≥90, SEO ≥95, com meta maior quando sustentável. Não há garantia de nota: reavaliar com várias execuções controladas após cada grupo de otimizações.

## 12. Código sem uso, duplicado e obsoleto
Candidatos, não autorização de remoção automática:
| Prioridade | Arquivo/símbolo | Evidência e decisão |
| --- | --- | --- |
| MÉDIO | crud_config.py, crud_projeto.py, crud_servico.py | Sem import consumidor encontrado; models não importados geram 16 ocorrências F821. Aproveitar ao retirar persistência dos routers ou remover após migração das responsabilidades. |
| BAIXO | core/constants.py | Enum antigo com recusado e sem proposta_enviada, sem consumidor encontrado. Consolidar com core/enums.py. |
| BAIXO | schemas/token.py; create_refresh_token; decode_token | Sem fluxo ativo encontrado. Decidir estratégia de sessão antes de manter/remover. |
| BAIXO | frontend/js/admin/ui.js | Sem import consumidor encontrado; repete helpers. Aproveitar para componente compartilhado de modal ou remover após conferência de consumidores externos. |
| BAIXO | builder_serializer.js | Arquivo vazio. Serialização está em builder.js; não criar duplicação apenas por nome de arquivo. |
| BAIXO | backend/services/backup_service.py | Vazio; não conta como backup implementado. Preencher com integração operacional justificada ou remover placeholder. |
| BAIXO | backend/tests/test_auth.py | Vazio; deve virar teste real. |
| BAIXO | backend/utils/logger.py | Apenas comentário; deve receber logging estruturado se mantido. |
| BAIXO | dashboard.voltarDashboard, atualizarTudo | Sem chamadas encontradas. |
| BAIXO | builder.obterState; orcamentos_utils.STATUS_OPTIONS | Sem chamadas encontradas; STATUS_OPTIONS pode resolver a duplicação do filtro. |
| BAIXO | wrappers de status em orcamentos_api.js | Controller usa atualizarStatus diretamente; revisar todos antes de simplificar. |
| BAIXO | proposta_api e getPropostaPayload | Desconectados, mas necessários à integração prevista; não apagar por ausência atual de consumidores. |
| BAIXO | helpers dom.on, validation.email, format.date/datetime/percent | Não usados ou sem fluxo ativo identificado. Consolidar uso antes de remover. |
| BAIXO | animations.css | Não carregado, mas suas classes são referenciadas. Corrigir intenção ou retirar classes/arquivo em conjunto. |
| BAIXO | info-title/info-desc em calculadora.html | Painel oculto sem atualização encontrada; descrição migrou para os cards. |
| BAIXO | prod.filtro no state | Não há UI/aplicação correspondente. Implementar se útil ou eliminar estado ocioso. |
| BAIXO | email_cliente.html | Repete valor e data; corrigir template pontualmente. |

Ruff encontrou 43 diagnósticos F: 16 nomes indefinidos nos CRUDs ociosos, dois imports sem uso evidentes e os demais associados a registros/reexports de models/schemas. Imports em __init__ e env.py podem ser necessários por efeitos de registro: não aplicar --fix indiscriminadamente.

Não existe teste suficiente para garantir remoção de todo CSS aparentemente sem uso. Classes dinâmicas, estados ocultos e integrações externas devem ser considerados. Nenhum arquivo foi removido.

## 13. Arquitetura proposta para conclusão
### Contrato central
Orçamento guarda solicitação original e metadados do CRM separados. Proposta possui identidade própria e snapshot; produção representa execução. Projeto de portfólio continua separado e não deve ser publicado automaticamente ao aprovar uma proposta.

Fluxo:
1. Cliente envia orçamento completo → novo.
2. Comercial inicia análise → em_analise.
3. Backend cria/retorna proposta vinculada, com número estável e snapshot.
4. Editor carrega dados; input dispara controller; controller chama state; render atualiza somente o necessário.
5. Salvar rascunho valida, calcula e persiste no backend; resposta normalizada atualiza state.
6. Preparar gera revisão validada/pronta.
7. Mesmos dados salvos e mesmo template produzem HTML de visualização e PDF.
8. Envio controlado no backend registra tentativa, confirmação do provedor e enviada_em; só então proposta enviada e orçamento proposta_enviada.
9. Aceite marca proposta aceita/aprovada_em, orçamento aprovado e cria uma produção, em transação idempotente.
10. Arquivar preserva histórico e documentos.

### Backend
- Routers: parsing HTTP, autenticação/autorização, schemas e resposta.
- Services: regras, transições, totais e fronteira transacional.
- CRUD: consultas/add/flush; sem commits ocultos em operações compostas.
- Models/schemas: contratos explícitos, constraints e serialização.
- Uma proposta raiz por orçamento é compatível com o modelo atual. Revisões enviadas precisam ser preservadas; propor tabela de revisões/snapshots, com unicidade proposta_id + versão, para não sobrescrever o documento comercial já enviado.
- Numeração por sequência/identidade do banco e UNIQUE, nunca MAX+1 ou contador frontend. Formato MHS-000001, estável entre edições; versão é separada.
- Controle de concorrência por revisão esperada/lock_version; conflito retorna 409 em vez de sobrescrever edição alheia.
- Pagamentos em lista JSON tipada: id/tipo, rótulo, valor, URL e habilitado. Completo, parcial_1 e parcial_2 são opções iniciais; parcial_2 começa desabilitado.
- PIX/texto e URLs são dados comerciais, não comprovação de pagamento. Valores de entrada/restante devem obedecer às regras do backend.
- QR gerado localmente pelo backend a partir de URL validada, sem buscar conteúdo remoto do link.
- Snapshot/revisão salva alimenta um único template; resposta HTML pode ser exibida em iframe isolado. Não injetar HTML de documento diretamente no DOM do admin.
- PDF associado à revisão e hash dos dados/template; alterações invalidam artefato anterior para novos envios, preservando histórico.
- Envio requer registro persistido de tentativa e chave idempotente. Não existe transação atômica comum entre PostgreSQL e e-mail: tratar falhas e reconciliação explicitamente.
- Aceite transacional com constraint única e tratamento de corrida; nenhum retry pode duplicar produção.
- PDF em storage privado persistente, acesso autorizado/temporário. Disco local do Render é efêmero por padrão; avaliar Supabase Storage privado já alinhado à stack. Referência: [Render Persistent Disks](https://render.com/docs/disks).

### Frontend
Preservar admin/propostas e seus arquivos. Componentes recebem dados e callbacks; nenhum componente altera state diretamente. Controller coordena operações, state guarda proposta normalizada, API encapsula HTTP, modal cuida de foco/abertura/fechamento e preview somente apresenta o documento backend.

Manter cálculos locais apenas como feedback provisório. Totais persistidos, número, QR, transições e aprovação são responsabilidade do backend. Fechamento, navegação e logout precisam tratar dirty state; nenhuma atualização deve substituir o input ativo durante a digitação.

## 14. Arquivos a alterar e criar
### Alterações previstas
| Prioridade | Arquivos/grupos existentes | Responsabilidade da mudança |
| --- | --- | --- |
| CRÍTICO | backend/core/dependencies.py, core/security.py | Remover vazamentos, validar sessão e permissões. |
| CRÍTICO | backend/models/__init__.py, models/proposta.py, models/orcamento.py, migrations/env.py, main.py | Integrar model/metadata e organizar inicialização. |
| ALTO | backend/routers/orcamentos.py, crud/crud_orcamento.py, crud/crud_producao.py, schemas/orcamento.py, schemas/producao.py | Transições, aprovação transacional, pedido completo, validações. |
| ALTO | backend/routers/config.py, projetos.py, servicos.py, newsletter.py; CRUDs e schemas correspondentes | Routers finos, contratos e erros. |
| ALTO | backend/services/email_service.py, startup_service.py | Entrega rastreável, restauração explícita e startup previsível. |
| ALTO | frontend/js/modules/orcamento.js, calculator.js; frontend/js/calculator.js, ui.js | Solicitação original, estimativa, erros e responsabilidades. |
| ALTO | frontend/js/admin/auth.js, index.js, dashboard.js, configuracoes.js | Inicialização, logout e contrato de configuração. |
| ALTO | frontend/js/admin/propostas/*.js | Estado por controller, persistência, ações e preview único. |
| ALTO | frontend/js/admin/orcamentos/*.js, producoes/*.js | Integração do fluxo e consistência visual/estado. |
| ALTO | frontend/js/modules/service_renderer.js, portfolio_ui.js, admin/builder/*.js | Renderização segura e controles acessíveis. |
| ALTO | frontend/admin.html, css/pages/admin.css, css/layout.css, css/notifications.css | Modais, grids, mobile, foco e mensagens. |
| MÉDIO | frontend/index.html, calculadora.html, portfolio.html, components/nav.html, footer.html | Semântica, SEO, navegação, recursos e formulários. |
| MÉDIO | frontend/css/main.css, variables.css, base.css, components.css, pages/*.css | Escopo por página, duplicações, fontes, CLS. |
| MÉDIO | frontend/assets/*, frontend/img/*, frontend/fonts/* | Otimização por finalidade, preservando identidade visual. |
| MÉDIO | backend/requirements.txt, tests/test_auth.py, README.md, backend/README.md | Dependências verificáveis, testes e operação. |

### Arquivos novos propostos por fase
| Prioridade | Arquivo/grupo | Responsabilidade |
| --- | --- | --- |
| ALTO | backend/schemas/proposta.py | Contratos tipados de itens, pagamentos, snapshot, rascunho e resposta. |
| ALTO | backend/routers/propostas.py | Endpoints do editor e ações do documento. |
| ALTO | backend/crud/crud_proposta.py | Persistência e consultas, sem orquestração de negócio. |
| ALTO | backend/services/proposta_service.py | Criação, numeração, totais, transições, versão e aceite. |
| ALTO | backend/services/orcamento_service.py | Recebimento, estimativa e metadados CRM preservando origem. |
| ALTO | backend/services/pdf_service.py | Renderizar HTML e PDF com a mesma entrada/template, isolando engine. |
| ALTO | backend/services/qr_code_service.py | Gerar QR de URL validada. |
| ALTO | backend/services/storage_service.py | Armazenar/obter documentos privados e seus metadados. |
| ALTO | backend/models/proposta_versao.py | Preservar revisões/snapshots enviados. |
| ALTO | backend/models/envio.py e serviço de envio correspondente | Tentativas, idempotência, resultado e retry persistido. |
| ALTO | backend/templates/proposta.html e proposta.css | Única composição visual do documento. Logo P&B disponível ao backend como asset controlado. |
| ALTO | Novas revisions em backend/migrations/versions/ | Propostas/revisões/envios e constraints corretivas, sem editar histórico. IDs só serão definidos ao gerar revisions. |
| ALTO | backend/tests/conftest.py, test_propostas.py, test_orcamentos.py, test_producao.py, test_pdf.py | Isolamento, contratos, fluxo, concorrência e documentos. |
| MÉDIO | frontend/js/utils/http.js, frontend/js/utils/safe_dom.js | HTTP e segurança de texto/URLs compartilhados onde houver consumidores reais. |
| MÉDIO | frontend/js/admin/components/modal.js | Comportamento acessível de modal comum. |
| MÉDIO | frontend/js/admin/projetos/ e separações pontuais de UI pública | API/state/form/render separados, mantendo compatibilidade durante a extração. |
| MÉDIO | frontend/404.html, frontend/_headers, frontend/_redirects | Erros reais, política de segurança/cache e canonicalização conforme Cloudflare Pages. |
| MÉDIO | frontend/site.webmanifest | Criar somente se houver finalidade; caso contrário remover referência. |
| MÉDIO | tests/frontend/ e configuração de ferramentas de desenvolvimento | Testes de navegador/lint reproduzíveis, sem framework de UI. |
| MÉDIO | Documentação de deploy, baseline/bootstrap e restauração; pipeline CI | Preparação/validação de deploy; nome de arquivo ajustado ao mecanismo efetivamente utilizado. |

Para clientes/calendário/dashboard, criar arquivos de consulta/render apenas na fase operacional, com uso real dos dados já existentes. Gestão de usuários, newsletter e recebimentos ganha models/endpoints somente junto das funcionalidades concretas. Não antecipar dezenas de arquivos vazios.

## 15. Plano em fases
Cada fase entrega mudanças pequenas, verificação, arquivos afetados e pendências. Não avançar com testes da fase falhando.

### Fase 0 — Estabilização e segurança [CRÍTICO]
Retirar vazamentos; corrigir imports/registro de models; verificar startup sem improvisar schema; autenticação/autorização e validação mínima; bloquear o falso envio de proposta enquanto o fluxo real não existir.
Validar: import, configure_mappers, startup isolado, tokens inválidos/sem subject/refresh, usuário sem permissão e nenhum segredo em logs.
Impacto: tokens incorretos antes aceitos passam a falhar; corrigir permissões pode limitar acessos existentes. Rotação de chave invalida sessões e é operação de ambiente.

### Fase 1 — Contratos e solicitações existentes [ALTO]
Corrigir inicialização do admin, desconto, envio de detalhes e parâmetros, duplicação de pedidos, filtro CRM, feedback de erros e validação de serviços/URLs.
Validar: login sem reload, GET/PUT config, fluxo completo de solicitação com detalhes preservados, cliques repetidos e respostas 401/403/409/422.
Impacto: alterações aditivas no payload; manter leitura compatível de dados antigos.

### Fase 2 — Arquitetura persistente de propostas [ALTO]
Fechar schemas, migrations novas, número do banco, snapshot, revisão, pagamentos extensíveis, totais Decimal e endpoints de criar/carregar/salvar rascunho.
Validar: PostgreSQL descartável, migration em cópia do esquema existente, numeração concorrente, rollback, payload inválido, snapshot imutável e controle de versão.
Impacto: novas tabelas e contratos. Nenhum campo legado removido.

### Fase 3 — Interface e estado do editor [ALTO]
Consolidar modal acessível, abas, grids e campos; em seguida padronizar input → controller → state → render. Corrigir foco, dirty state, fechamento, itens e pagamentos sem re-render destrutivo.
Validar: teclado, foco, edição contínua, adicionar/remover itens, troca de aba, parcial 2 desabilitado e cinco viewports.
Impacto: mudanças visuais preservando logo/identidade e estrutura modular.

### Fase 4 — Integração do editor com a API [ALTO]
Conectar criar/carregar/salvar; tratar carregamento, reabertura, erros de rede, sessão e conflito 409; substituir rascunho local por resposta autoritativa.
Validar: salvar/reabrir sem perda, editar em duas sessões, falha de rede preserva rascunho, cliente original não muda.
Impacto: salvar torna-se operação real; dados comerciais sensíveis ficam restritos a usuários autorizados.

### Fase 5 — HTML definitivo, preview e PDF [ALTO]
Criar template backend único, QR, storage, preview autenticado e PDF por revisão; incluir logo P&B, número, snapshot, itens, totais, condições, prazos, pagamentos, validade e aceite.
Validar: render de documentos curtos/longos, quebras de página, acentos, URLs longas, leitura de QR, fonte/imagem no Render e acesso privado.
Impacto: nova dependência de renderização isolada; confirmar suporte no deploy antes de escolher engine. Não manter layout duplicado frontend/backend.

### Fase 6 — Envio, aprovação e produção [ALTO]
Implementar pronta → enviada com registro persistido e confirmação do provedor; aprovar com transação/idempotência; gerar produção com escopo da proposta aceita; completar observações, etapas e prazos.
Validar: falha e timeout de e-mail, retry sem duplicação, aceite concorrente, rollback e ausência de publicação automática no portfólio.
Impacto: efeitos externos reais. Usar provedor fake nos testes; envio real apenas para destinatário explicitamente autorizado.

### Fase 7 — Administração operacional útil [MÉDIO; permissões ALTO]
Dashboard com indicadores reais; histórico de clientes; usuários/permissões; newsletter com descadastro; comunicação; calendário de prazos; recebimentos e saldo se registrados; logs auditáveis e backup/restauração.
Validar: matriz de acesso, isolamento de dados, consistência de histórico, filtros, conciliação de recebimentos e ensaio de restauração.
Impacto: expandir o painel por funcionalidade concluída, sem prometer módulos que só exibem placeholders.

### Fase 8 — Site público, acessibilidade, performance e SEO [ALTO/MÉDIO]
Corrigir 404/manifest/canonical, navegação/semântica, imagens/fontes e conteúdo inicial; reduzir dependências críticas, trabalho de render e deslocamentos; limitar escopo de CSS/JS.
Validar: links/recursos, cinco viewports, navegação por teclado, contraste, metadados/JSON-LD e Lighthouse antes/depois.
Impacto: redirects exigem escolha de domínio canônico; caches/headers precisam preservar login, API e documentos privados.

### Fase 9 — Limpeza e preparação de produção [ALTO; limpeza cosmética BAIXO]
Remover código comprovadamente sem consumidores; revisar dependências, build/deploy, checks CI, monitoramento e documentação. Remover legado de proposta somente após reconciliação e verificação completa das referências.
Validar: cadeia de migrations/baseline, regressão integral, restauração, fluxo comercial ponta a ponta, status HTTP, screenshots e medições repetidas.
Impacto: exclusões e migrations destrutivas terão inventário e plano de recuperação antes de serem executadas.

## 16. Resultado das validações desta auditoria
| Verificação | Resultado |
| --- | --- |
| Sintaxe Python | 55 arquivos sem erro de sintaxe. |
| Sintaxe e ligação ES Modules | 69 módulos sem erro sintático, import relativo ausente ou export solicitado inexistente. |
| Ruff, regras F | 43 diagnósticos; triagem descrita na seção 12. |
| Registro ORM / startup | Falhou ao resolver PropostaModel. |
| Import direto da proposta | Falhou por import de enums inexistente. |
| FastAPI/OpenAPI isolados | Import e geração de OpenAPI funcionaram; isso não valida startup/consultas. |
| Alembic | Sete revisions e uma head d1bdcc7920ab; migration inicial falhou em banco vazio. |
| Autenticação sintética | Dependência aceitou casos que deveria rejeitar. |
| Configuração | Payload real do frontend falha no schema pela ausência de desconto. |
| Orçamento | Schema aceita dados inválidos; navegador reproduziu perda de detalhes e campos antigos após troca de serviço. |
| Login admin | Listas não carregam no primeiro login; carregam após reload com sessão. |
| Propostas | Foco perdido no input, overflow mobile/tablet, salvar desabilitado e rascunho apagado no fechamento. |
| XSS local controlado | Execução de evento HTML no renderer confirmada; nenhum payload salvo em banco. |
| Navegação pública local | Sem pageerror JavaScript nos fluxos testados com fixtures; falha de menu por teclado e cortes no footer confirmados. |
| Produção pública | Páginas e /health responderam 200; URLs inexistentes retornaram HTML 200. |
| CORS publicado | Domínios Mirai aceitos; origem de auditoria inválida rejeitada. |
| Lighthouse | Baseline de três páginas concluído, sem runtime error/warnings. |
| Testes existentes | test_auth.py vazio; pytest/httpx não estão instalados no venv examinado. |
| CRUD/PDF/envio/aceite de propostas | Não executáveis como fluxo integrado: implementação ausente e ORM bloqueado. |
| PostgreSQL real / restore / CrUX | Não executados; pendentes. |

Relatórios brutos Lighthouse desta sessão estão na pasta temporária do usuário: mirai-audit-lighthouse-home.json, mirai-audit-lighthouse-calculadora.json e mirai-audit-lighthouse-portfolio.json. Screenshots de auditoria também ficaram fora do repositório.

## 17. Critérios para declarar conclusão futura
- Todos os bloqueios críticos corrigidos e verificados.
- Solicitação original preservada; proposta independente salva, visualizada, gerada, enviada e aceita.
- Totais, número, QR, transições e criação de produção controlados pelo backend.
- Concorrência e idempotência validadas em PostgreSQL, inclusive falhas entre banco, storage e e-mail.
- Regras de acesso e validação de entrada testadas; nenhum segredo em logs/frontend.
- Páginas e fluxos administrativos utilizáveis por teclado e em telas pequenas.
- URLs, metadados, recursos e documentos sem falsos 200/404 mascarados.
- Metas Lighthouse verificadas em execuções repetidas, com ressalva de variação de rede/dispositivo; acompanhamento de métricas de campo posteriormente.
- Migrations/deploy reproduzíveis e restauração demonstrada.
- Relatório de encerramento com funcionalidades concluídas e pendentes, migrations/endpoints/arquivos alterados, resultados de testes, segurança, SEO e desempenho.

Nesta auditoria não foram concluídas novas funcionalidades, criadas migrations, alterados endpoints nem corrigidas vulnerabilidades. O produto permanece no estado examinado; este documento define o trabalho necessário para encerrá-lo com segurança.

