# Mirai Hit Studio 3.0 - Etapa 01: Inventario (DB-01) e classificacao (DB-02)

- Data: 14/10/2026, consulta somente leitura ao PostgreSQL de producao (Supabase,
  PostgreSQL 17.6), autorizada pelo responsavel.
- Revisao Alembic em producao: `c5f2a7d9e184`.
- **Aplicada em producao em 14/10/2026 ~07:48 (BRT)** junto com a 5.02: Alembic
  `c5f2a7d9e184` -> `a7d3e5f9c210` -> `d8a7b1c9e240`. Resultado conferido: orcamentos
  234, 237, 239, 240 -> teste; 238 (Yonda) real; clientes 90-93 e contas 45-47 -> teste;
  5 pagamentos, soma R$ 126,50, inalterados.
- Incidente: o release publicou o backend ~3 min antes das migrations (o release
  protegido nao migra o banco). Nenhuma requisicao de usuario atingiu rotas afetadas
  nesse intervalo, segundo os logs do Render.
- Decisao do responsavel: **por enquanto, marcar como teste basta**. A remocao fisica
  (DB-08) fica fora de escopo. A classificacao e feita pela migration `d8a7b1c9e240` do
  PR #26.

## DB-01 - Contagens atuais

| Entidade | Total | Observacao |
| --- | --- | --- |
| usuarios | 8 | 1 admin, 3 produtores, 4 contas de cliente |
| clientes | 5 | ids 90-94 |
| orcamentos | 5 | ids 234, 237, 238, 239, 240 |
| propostas | 5 | ids 67, 70, 71, 72, 73 |
| cobrancas | 5 | ids 68, 71, 72, 73, 74 |
| pagamentos | 5 | ids 81-85 |
| producoes | 4 | ids 45-48 |
| producao_arquivos | 7 | producoes 46 e 47 |
| repasses_produtor | 1 | producao 47, status `definido` |
| cliente_acessos | 4 | clientes 91, 92, 93, 94 |
| servicos / projetos | 7 / 19 | catalogo e portfolio preservados |
| ai_conversations | 14 | fora do escopo da classificacao comercial |

## DB-02 - Resultado esperado da migration `d8a7b1c9e240` sobre os dados atuais

Simulacao feita por leitura, aplicando as condicoes da migration linha a linha:

| Cadeia (orcamento -> proposta -> cobranca -> pagamentos -> producao) | Cliente | Classificacao |
| --- | --- | --- |
| 234 -> 67 -> 68 (pendente) -> - -> 45 | 90 | **teste** |
| 237 -> 70 -> 71 (pendente) -> 81 cancelado, 82 pendente R$ 0,50 -> - | 93 | **teste** |
| 239 -> 71 -> 72 (paga) -> 83 aprovado R$ 60 -> 46 | 93 | **teste** |
| 240 -> 72 -> 73 (parcial) -> 84 aprovado R$ 5 (Pix real) -> 47 | 93 | **teste** |
| 238 -> 73 -> 74 (paga) -> 85 aprovado R$ 60 -> 48 | 94 (Yonda) | **real (protegida)** |

- Clientes 90, 91, 92 e 93 -> teste; cliente 94 (Yonda) permanece real.
- Contas de cliente 45, 46, 47 -> teste; conta 48 (Yonda), admin e produtores intactos.
- Nenhum valor, status, pagamento, arquivo, repasse ou PDF e alterado; o Pix de R$ 5
  (pagamento 84) continua na conciliacao com o filtro `teste`/`todos`.

Os IDs fixos da migration conferem com o banco atual. Apos a aplicacao, o painel oficial
mostrara somente a cadeia de Yonda.

## Pontos de atencao antes de aplicar

1. **Pix pendente fora de Yonda:** pagamento 82 (R$ 0,50, cobranca 71) continua
   `pendente`. A migration nao o cancela; webhooks e conciliacao seguem funcionando.
2. **Producao 45 atribuida ao usuario 1 (admin)** como produtor. Nao afeta a
   classificacao, mas vale corrigir a atribuicao no Admin.
3. **Repasse 1 (producao 47) esta `definido`** em uma cadeia de teste. Nao deve ser
   pago.
4. Aplicar a migration exige backup recente com restore testado (DB-05) e o fluxo de
   release protegido; nao foi executada nesta etapa.
5. A migration agora vem depois da 5.02: `c5f2a7d9e184` -> `a7d3e5f9c210` ->
   `d8a7b1c9e240`. Um `alembic upgrade head` aplica as duas, nessa ordem.
