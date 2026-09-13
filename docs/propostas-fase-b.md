# Propostas: Fase B

Integracao somente do frontend. Backend, banco, autenticacao e fases anteriores
nao foram alterados ou revalidados nesta execucao.

## Fluxos

- Abrir: GET /propostas/orcamento/{id}; somente em 404, POST idempotente
  /orcamentos/{id}/proposta. Loading visivel, response mapeada e dirty=false.
- Consultar por ID: GET /propostas/{id}, disponivel no adaptador HTTP.
- Salvar: allowlist do mapper -> PATCH /propostas/{id} -> response -> state.
  Saving bloqueia edicao, troca de aba, fechamento e novo envio. Sucesso atualiza
  numero/versao/status/totais do backend e limpa dirty. Erro preserva os inputs,
  dirty e dados locais para tentar novamente.
- Fechar com dirty exige confirmacao; cancelar mantem o editor. Confirmar descarta
  apenas a copia local. Nenhuma proposta persistida e excluida.
- Reabrir consulta a API novamente. Respostas de contextos encerrados/trocados
  sao ignoradas; cliques repetidos para o mesmo carregamento nao duplicam chamadas.
  Se o POST ja estiver em andamento ao fechar, o backend pode concluir a criacao
  idempotente; o frontend nao tenta reverter a proposta persistida.

## Contrato e interface

O helper authFetch existente e reutilizado, sem outra implementacao de token/fetch.
O mapper permanece desacoplado do transporte; o payload contem somente produtor_id,
objeto, descricao, itens, pagamentos e condicoes. Nao envia snapshot, numero,
status, versao, timestamps, PDF, subtotais ou totais autoritativos.

Cliente e preview usam exclusivamente cliente_snapshot. Numero, status e versao
sao recebidos do backend e readonly. Fora de rascunho, o editor permite consulta,
mas bloqueia edicao, coerentemente com o contrato existente.

Dirty compara o payload editavel com a ultima response. Render, abertura e troca
de aba nao alteram dirty. Editar e retornar exatamente ao valor salvo limpa dirty.
Dados de UI ficam separados dos dados persistidos.

Adicionar/remover itens produz alteracao estrutural; digitar atualiza somente
state, subtotal/total visuais e estado do botao. Os inputs nao sao reconstruidos.
Valores numericos digitados permanecem como strings no payload para evitar
conversao prematura e permitir erro de validacao para campo numerico vazio.
Totais recebidos sao usados apos carregar/salvar; estimativas locais durante a
edicao nao sobrescrevem totais autoritativos.

Os tres links correspondem a integral/parcial_1/parcial_2 na lista pagamentos.
O terceiro respeita o checkbox habilitado; tipos adicionais recebidos sao
preservados. URLs invalidas/valores invalidos sao tratados pelos erros da API.

Campos sem contrato (prestador, entrada, prazo, validade, PIX avulso, Mercado Pago
avulso, observacoes de pagamento) estao readonly, identificados como locais.
Nao foram inventadas colunas nem prometido salvamento desses campos. O destino
persistido deles depende de decisao de contrato antes de inclui-los no documento.
Condicoes comerciais permanecem editaveis e persistentes.

Gerar PDF continua desabilitado. Nenhum QR e gerado nem simulado. Preview continua
HTML local nesta fase; template definitivo e PDF pertencem a Fase C.
Abrir/salvar nao altera o status do orcamento.

## Testes

```sh
node frontend/tests/proposta_contracts.mjs
node frontend/tests/proposta_editor.cjs
```

O segundo comando requer Playwright via NODE_PATH e Edge headless, ou outro
canal em BROWSER_CHANNEL. Todas as requisicoes sao interceptadas; nenhuma e
encaminhada a producao. O teste cobre criacao/consulta/reabertura, PATCH e
double-submit, falha com preservacao de dados, snapshot/numero readonly,
itens, pagamentos/parcial 2, foco, confirmacao de fechamento, bloqueio de
edicao fora de rascunho e descarte de respostas atrasadas.

Os testes verificam integracao HTTP do frontend com responses sinteticas;
nao constituem um novo teste de banco ou backend. Sem commits/push/deploy.
