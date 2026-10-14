# Classificacao comercial e contas de teste

## Fonte autoritativa

`orcamentos.is_test` classifica cada cadeia comercial. Proposta, cobranca,
pagamentos, producao e repasses herdam a classificacao por relacionamento,
sem duplicar campos nem modificar valores, status, documentos ou arquivos.
Novas versoes da proposta conservam o mesmo orcamento.

`usuarios.is_test` identifica contas de cliente/produtor. Para uma conta de
cliente, a classificacao especifica de `clientes.is_test` acompanha a conta.
Isso nao reclassifica orcamentos existentes. Um cliente com operacoes mistas
continua no painel oficial quando possui orcamento real; os totais comerciais
de clientes contam somente as operacoes do ambiente selecionado.

## Admin

- `GET/PATCH /propostas/{id}/classificacao`: administrador autenticado;
  payload `is_test` booleano estrito e, quando houver pagamentos,
  `confirmar_historico_financeiro=true`.
- `PATCH /usuarios/{id}/classificacao`: contas de cliente/produtor;
  administradores, Yonda e contas relacionadas a cadeias protegidas bloqueadas.
- Listagens: `ambiente=real|teste|todos` para orcamentos, producoes, clientes,
  cobrancas e resumo financeiro. O padrao comercial e `real`.
- O checkbox do editor restaura o estado confirmado antes de abrir o modal.
  Nenhum PATCH ocorre sem confirmacao explicita. Erros preservam o estado
  anterior. Listas e dashboard sao atualizados sem recarregar a pagina.
- Toda alteracao efetiva registra ator, data, classificacao anterior/nova e
  confirmacao financeira. Repeticoes identicas nao criam nova auditoria.

## Preservacao financeira

O Pix historico de R$ 5 (pagamento 84/cobranca 73/proposta 72) pode ser
classificado como teste comercial, mas continua no financeiro com filtro
`todos`/`teste`, nos detalhes e na conciliacao. Nao ha cancelamento, estorno,
reembolso, simulacao, migracao de arquivos nem reescrita de PDFs.
O resumo filtrado comercial nao substitui relatorio contabil completo.

Reversao comercial TESTE -> REAL e bloqueada quando existe tentativa de
pagamento, independentemente do seu status ou ambiente externo. A reversao
de conta com pagamentos associados tambem exige conciliacao futura. Sem
historico financeiro, a reversao pode ser confirmada normalmente.

Uma cadeia de teste nao cria novas Orders (publica ou autenticada). A reserva
e o envio validam o orcamento no backend. O envio conserva os locks existentes
de pagamento/cobranca ate confirmar o registro do provedor; classificacao
espera o lock da cobranca antes de bloquear orcamento/proposta. Uma Order
preexistente continua recebendo webhooks e conciliacao normalmente.

## Migration e validacao

Migration existente `d8a7b1c9e240`, sobre `a7d3e5f9c210` (fase 5.02): flags em clientes,
orcamentos e usuarios. Backfill comercial exige os pares de IDs e vinculos
inventariados; bloqueia identidade Yonda e descendentes protegidos. Clientes
com qualquer orcamento real nao sao marcados automaticamente. Produtores
e administradores nao recebem backfill. Downgrade remove somente flags/indexes,
perdendo classificacoes, mas conserva pagamentos, arquivos e auditorias.

Testes locais usam SQLite descartavel e Playwright com respostas sinteticas.
O Storage Integration Gate existente valida a migration e concorrencia em
PostgreSQL 17 descartavel, com timeout controlado. Nao executar a migration
em producao nem publicar sem autorizacao separada.
