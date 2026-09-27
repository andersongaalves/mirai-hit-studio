# Mirai Hit Studio - PostgreSQL Validation I.1

## Escopo e seguranca

A validacao foi executada em 27/09/2026 no PostgreSQL existente da Mirai, classificado como banco remoto ativo/potencialmente produtivo. O host foi identificado apenas pelo marcador anonimizado `ec0cb1a676`; nenhuma URL, credencial ou nome de role foi registrado.

Regras aplicadas:

- suite opt-in por `MIRAI_I1_DATABASE_URL` e confirmacao `MIRAI_I1_ALLOW_EXISTING_DATABASE=I1_NON_DESTRUCTIVE_ONLY`;
- nenhuma operacao global de `DROP`, `TRUNCATE`, bootstrap ou downgrade;
- fixtures com prefixo unico `i1_test_<uuid>` e e-mail reservado em `example.com`;
- providers OpenAI/Groq, Resend e Mercado Pago desabilitados ou substituidos por fakes;
- transacoes curtas, `lock_timeout` local e duas sessions independentes nos cenarios concorrentes;
- cleanup filtrado exclusivamente por IDs e prefixos da execucao;
- hash interno de todos os registros de `usuarios` antes/depois da suite.

O banco e compatível com Supabase. A documentacao atual confirma que owner e roles com `BYPASSRLS` ignoram policies; grants e RLS sao controles complementares:

- https://supabase.com/docs/guides/database/postgres/row-level-security
- https://supabase.com/docs/guides/api/securing-your-api

## Ambiente observado

- PostgreSQL: `17.6`, Linux x86_64.
- Banco atual: `postgres`.
- Isolation level: `read committed`.
- Em recovery: nao.
- Alembic antes: `f2a8c4e6d901`.
- Alembic depois: `f2a8c4e6d901`.
- Heads: uma unica head, `f2a8c4e6d901`.
- `alembic upgrade head`: sucesso, sem migration pendente.
- Application role: nao-superuser, owner das tabelas e `BYPASSRLS`.

## Validado em PostgreSQL real

### Schema e migrations

- Todas as tabelas criticas financeiras e de IA existem.
- Comparacao SQLAlchemy metadata x banco: zero diferencas.
- Nenhuma migration nova foi necessaria.
- Migrations historicas nao foram alteradas.
- Tipos financeiros `Numeric(12, 2)` confirmados em `cobrancas.valor_total` e `pagamentos.valor`.
- Foreign keys, checks, uniques e indices foram inspecionados no catalogo PostgreSQL.
- Uniques criticos confirmados: uma cobranca por proposta, order/idempotency de pagamento, deduplicacao de webhook, inbound/reply de IA e root de thread de e-mail.
- Indices criticos confirmados para status financeiro, reconciliacao, webhook, conversa, historico e mensagens pendentes.

### Financeiro

- `Decimal('199.99')` persistiu e retornou como `Decimal`, sem conversao para float.
- Split 50/50 confirmado como `99.99 + 100.00`.
- `UNIQUE(proposta_id)` rejeitou segunda cobranca para a mesma proposta.
- `UNIQUE(provider_idempotency_key)` rejeitou tentativa duplicada.
- Rollback forcado nao deixou pagamento parcial persistido.
- `SELECT ... FOR UPDATE` foi comprovado com duas sessions; a segunda recebeu SQLSTATE `55P03` sob `lock_timeout=750ms`.
- Dois pagamentos aprovados concorrentes de `60.00` sobre cobranca de `100.00` resultaram em um aprovado e um conflito; nao houve overpayment.
- A chamada fake ao provider ocorre antes da aquisicao do row lock de reconciliacao; nenhum provider externo foi chamado dentro de lock longo.

### Webhook e reconciliacao

- Duas deliveries simultaneas do mesmo evento produziram um unico `provider_webhook_event`.
- A reconciliacao convergiu para um pagamento aprovado e uma cobranca paga.
- O segundo processamento foi reconhecido como duplicado/estado inalterado.
- Provider Mercado Pago substituido por fake deterministico.

### IA, e-mail e briefing

- Duas persistencias concorrentes do mesmo inbound produziram uma unica mensagem logica.
- Dois workers disputando o mesmo claim tiveram um unico vencedor.
- Lease expirado foi recuperado por novo claim; completion do token antigo foi rejeitada.
- Mensagem concluida nao foi processada novamente.
- Resposta tardia apos handoff foi rejeitada e nao criou outbound.
- Delivery concorrente de e-mail convergiu por retry idempotente para uma conversa, um inbound, uma resposta logica e um envio fake.
- Dois submits concorrentes do mesmo briefing criaram um unico cliente sintetico e um unico orcamento.
- Nenhuma chamada OpenAI, Groq ou Resend foi feita.

### RLS e roles

RLS real esta habilitada em:

- `ai_conversations`;
- `ai_messages`;
- `ai_email_threads`;
- `ai_briefings`;
- `ai_usage_events`.

Estado observado:

- `relrowsecurity=true` nas cinco tabelas;
- `relforcerowsecurity=false` nas cinco tabelas;
- nenhuma policy explicita em `pg_policies`;
- roles publicas sao protegidas pela combinacao de grants revogados e deny-all do RLS sem policy;
- role temporaria `NOLOGIN NOBYPASSRLS`, com `SELECT` explicitamente concedido, nao enxergou a fixture sintetica;
- role temporaria, grants e membership foram removidos no cleanup;
- application role atual e owner e possui `BYPASSRLS`, portanto o backend nao e limitado pelo RLS.

O `BYPASSRLS` e deliberadamente apenas documentado nesta fase. Revisar separacao de privilegios e threat model em I.4 antes de qualquer troca de role; nao alterar a role da aplicacao diretamente em producao.

## Usuarios protegidos

O modelo possui uma unica tabela autoritativa de autenticacao, `usuarios`, com `role`, `is_admin`, `ativo` e `password_hash`. Referencias existem em propostas, orcamentos, producoes, campanhas, auditoria e conversas de IA.

A suite nao cria, atualiza nem remove usuarios. Um digest interno com contagem e conteudo de todas as linhas foi comparado no inicio e no fim de cada execucao e permaneceu identico. O digest e os hashes de senha nunca sao exibidos.

Antes de futura operacao estrutural, confirmar no painel do provider a politica de backup gerenciado. Como alternativa operacional, exportar logicamente `usuarios` e tabelas dependentes com `pg_dump` para armazenamento privado e criptografado. Restore drill permanece reservado para I.6 e exige banco descartavel.

## Execucoes

- Suite completa: 7 testes, aprovada.
- Concorrencia financeira, webhook, AI lease/inbound e e-mail/briefing: 5 repeticoes aprovadas.
- Sessions simultaneas por disputa: 2.
- Fixtures remanescentes apos cleanup: 0.
- Roles temporarias remanescentes: 0.
- Novo warning observado: configuracao Pydantic v1-style em `schemas/servico.py`; nao pertence a I.1.

Comando seguro da suite:

```powershell
$env:MIRAI_I1_DATABASE_URL = '<URL explicitamente revisada>'
$env:MIRAI_I1_ALLOW_EXISTING_DATABASE = 'I1_NON_DESTRUCTIVE_ONLY'
python -m unittest tests.test_postgres_i1 -v
```

Sem as duas variaveis, todos os testes PostgreSQL sao ignorados.

## Pendente por exigir banco descartavel

- Clean bootstrap nao validado por ausencia de PostgreSQL descartavel.
- Fluxo banco vazio -> `Base.metadata.create_all()` -> Alembic stamp/head nao foi executado.
- Downgrade destrutivo, inclusive de migrations recentes, nao foi executado.
- Restore drill nao foi executado.

Esses itens devem ser retomados em I.6 ou assim que existir PostgreSQL descartavel. Nao podem ser simulados destruindo o banco ativo.

## Riscos e proximas fases

### I.4

- confirmar backups gerenciados e retencao no provider;
- revisar a application role owner/BYPASSRLS e documentar o modelo de privilegios;
- validar configuracao da Data API, grants e schemas expostos;
- alinhar a minor version PostgreSQL planejada pelo provider.

### I.5

- manter a suite I.1 fora da regressao comum, exigindo opt-in;
- repetir schema drift, RLS e concorrencia no ambiente de release;
- tratar o warning Pydantic apenas em fase apropriada.

### I.6

- executar clean bootstrap em banco descartavel;
- validar downgrade recente suportado quando fizer sentido;
- executar backup/restore drill completo fora do banco ativo.
