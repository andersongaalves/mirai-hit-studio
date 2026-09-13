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
