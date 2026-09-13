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
