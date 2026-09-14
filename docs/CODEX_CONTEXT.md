# Mirai Hit Studio - Codex Context

## Stack

- Frontend: HTML, CSS e JavaScript vanilla modular.
- Backend: FastAPI.
- ORM: SQLAlchemy.
- Banco: PostgreSQL/Supabase.
- Migrations: Alembic.
- Frontend deploy: Cloudflare Pages.
- Backend deploy: Render.
- E-mail: Resend.
- Pagamentos planejados: Mercado Pago.
- IA futura: chat do site e e-mail.
- Git: branch `main`.

## Arquitetura relevante

Dominios principais: servicos, orcamentos, propostas, producoes, projetos/portfolio, usuarios, newsletter e configuracoes.

Projeto representa conteudo e portfolio. Producao representa a execucao comercial de um servico contratado.

## Fases concluidas

- A: backend persistente de propostas.
- B: editor real de propostas.
- C: HTML, PDF, QR e documento.
- D: envio, aprovacao e producao.
- E: hardening de seguranca.

Decisoes importantes dessas fases estao preservadas nos documentos `propostas-fase-*.md` e `seguranca-fase-e.md`.

## Propostas

- Proposta e entidade independente do orcamento.
- O snapshot do cliente/orcamento e preservado.
- Numero, status e versao sao controlados pelo backend.
- O PDF deriva de uma fonte HTML unica.
- Alteracao relevante invalida o PDF anterior.
- A aprovacao cria Producao de forma idempotente.
- A aprovacao nao cria Projeto.
- Campos legados so devem ser removidos quando nao houver referencias.

## Producoes

- Etapas sao uma lista flexivel de nome/feito; nao existe fluxo rigido por vertical.
- Prazo proximo significa ate 3 dias. Producoes `finalizado` ou `entregue` nunca aparecem como atrasadas.
- Cliente e origem comercial continuam derivaveis dos snapshots para registros legados.

## Clientes / CRM

- Cliente existe como entidade comercial viva; `orcamento.cliente_id` e nullable e registros legados continuam validos.
- Orcamentos e propostas preservam seus snapshots. Matching automatico e conservador por email/telefone e nunca usa apenas o nome.

## Banco e migrations

- Alembic e responsavel pelo schema.
- `Base.metadata.create_all()` nao roda no startup normal.
- Existe bootstrap seguro e explicito para banco realmente vazio.
- Migrations historicas nunca devem ser editadas.
- Mudancas futuras devem usar migration nova.
- Migrations devem ser testadas em PostgreSQL descartavel antes de producao.
- Nunca testar operacoes destrutivas em banco real.

## Seguranca

- Rotas administrativas exigem autenticacao e autorizacao apropriadas.
- Nunca registrar token, senha, `SECRET_KEY` ou payload sensivel.
- JWT continua com limitacoes conhecidas documentadas na Fase E.
- CSP ainda possui limitacoes conhecidas e esta em modo compatibilidade/report-only.
- Rate limiting local pode nao ser distribuido entre instancias.
- Frontend nunca e fonte autoritativa para pagamento ou status critico.
- Conteudo vindo de usuario ou API deve ser tratado contra XSS.
- O backend e a fonte de verdade para regras comerciais e financeiras.

## Analytics

- A camada `frontend/js/analytics.js` centraliza eventos e consentimento.
- GA4 existente so carrega apos aceite de analytics; eventos nao incluem PII.
- Conversoes comerciais dependem de confirmacao do backend/webhook.
- Atribuicao de lead aguarda contrato e persistencia futura em F0.3/F.2.

## Mirai Hit Studio 2.0

Posicionamento: "Producao musical e audio para artistas, criadores e projetos digitais."

Slogan: "Criando o som do futuro."

Verticais:

1. Artists: rap, trap, drill, funk, geek music, producao, beat/instrumental, vocal production, mix e master.
2. Creators: temas, intro/outro, musica original, sound branding e trilha para conteudo.
3. Media & Games: soundtrack, loops, stingers, menu music, sound design e audiovisual.

Geek Music e especialidade transversal, nao limitacao da marca.

Direcao visual: music-tech, premium e futurista. Evitar neon gratuito, glitch excessivo e estetica gamer generica. Manter `#111827`, `#00D4FF`, `#B22AF0`, `#F9FAFB`, identidade futurista e referencias japonesas/geek como assinatura secundaria.

Design: tokens CSS semanticos complementam as variaveis legadas; foco visivel e reduced motion sao obrigatorios para componentes novos. Provas sociais devem ser verificaveis e rotuladas como case, demo, concept project ou study.

Admin UX: J0 define shell compartilhado, header, filtros, badges, estados e modal acessivel como fundacao vanilla. Componentes visuais nao absorvem regras de dominio; J0.3 aplica a fundacao primeiro em Producoes.

Dashboard: `/dashboard` e autenticado, agrega indicadores operacionais no backend e nao representa receita ou analytics publico.

Usuarios internos: gerenciamento exclusivo de administradores, papeis `admin`/`produtor` e desativacao sem exclusao para preservar historico. Contas inativas nao autenticam nem permanecem validas em sessoes existentes.

Newsletter: inscricao publica exige opt-in explicito e permanece separada de e-mail transacional. Cancelamento usa token opaco, campanhas sao manuais e exclusivas de administradores, e entregas registram apenas o resultado sanitizado do provedor.

Auditoria: acoes administrativas criticas geram `AuditLog` estruturado, imutavel pela API e separado de logs tecnicos. Metadata usa allowlist e nunca armazena credenciais ou payload completo.

Backup/restore: operacao exclusiva de infraestrutura por `pg_dump`/`pg_restore`, fora do frontend. Restore de producao exige confirmacao e opt-in explicitos; dumps e storage de arquivos possuem politicas separadas.

## IA planejada

Canais: chat proprio do site e e-mail. Nao havera WhatsApp.

Dois modos: autonomo para tarefas seguras e copiloto para atendente.

A IA pode responder FAQ, consultar servicos/precos publicados, coletar briefing, qualificar lead, resumir conversas e registrar informacoes estruturadas.

A IA nao pode negociar desconto especial, fechar projeto personalizado, confirmar pagamento manualmente, marcar pagamento como aprovado sem fonte financeira, emitir reembolso ou executar acao administrativa sensivel sem autorizacao.

## Pagamentos planejados

Mercado Pago sera o gateway inicial.

Fluxo: proposta/contratacao -> cobranca -> Mercado Pago -> webhook -> backend -> atualizacao financeira -> producao.

O futuro modelo deve suportar pagamento integral, parcial 1, parcial 2, Pix e cartao. O backend e o webhook/provedor serao a fonte de verdade.

## Politica de desenvolvimento

- Trabalhar em tarefas pequenas e fechadas.
- Ler somente arquivos relevantes para cada subfase.
- Usar testes focados durante subfases.
- Fazer regressao ampla apenas nos checkpoints.
- Nao criar funcionalidades especulativas ou modulos vazios.
- Preservar compatibilidade com as fases anteriores.
- Mudancas de banco exigem migration nova.
- Evitar refatoracoes amplas sem necessidade comprovada.

## Politica Git

- Preferir um commit funcional por subfase.
- Push somente em checkpoints do roadmap ou por instrucao explicita.
- Antes de commit: testes focados, `git diff --check` e revisao dos arquivos staged.
- Evitar `git add .` quando houver alteracoes alheias.
- Nunca usar `reset --hard`, `clean`, `restore` ou `checkout` para organizar trabalho local.
- Nunca fazer deploy automaticamente.
