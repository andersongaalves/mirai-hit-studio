# Propostas: Fase D

## Escopo entregue

Envio autenticado, transicoes comerciais, aprovacao idempotente e criacao de producao. As Fases A/B/C foram preservadas. Sem migration, novos estados, campos de model, pagamento, webhook, envio real em testes, commit ou deploy.

## Arquivos

Criados:
- `backend/services/proposta_comercial_service.py`
- `backend/templates/email_proposta.html`
- `backend/tests/test_proposta_comercial.py`
- `frontend/tests/proposta_comercial.cjs`
- `docs/propostas-fase-d.md`

Alterados nesta fase, preservando as modificacoes locais anteriores:
- `backend/services/proposta_documento_service.py`: geracao reutilizavel sem commit interno.
- `backend/services/email_service.py`: metodo especifico para enviar proposta com anexo e chave idempotente; metodos anteriores preservados.
- `backend/crud/crud_producao.py`: consulta por orcamento e criacao sem commit.
- `backend/crud/crud_orcamento.py`: protecao contra transicoes comerciais fora do editor.
- `backend/routers/propostas.py`: endpoints e erro de envio controlado.
- `backend/routers/orcamentos.py`: protecao do caminho legado de envio/status.
- `backend/tests/test_proposta_router.py`: expectativa do endpoint de aprovacao agora existente.
- `frontend/admin.html`: botoes Enviar/Aprovar.
- `frontend/css/pages/admin.css`: quebra dos botoes no espaco disponivel.
- `frontend/js/admin/propostas/proposta_api.js`
- `frontend/js/admin/propostas/proposta_state.js`
- `frontend/js/admin/propostas/propostas.js`
- `frontend/js/admin/orcamentos/orcamentos.js`
- `frontend/js/admin/producoes/producoes.js`

## Envio

`POST /propostas/{proposta_id}/enviar` usa a autenticacao ja existente e retorna `PropostaResponse`.

O servico bloqueia primeiro o orcamento, depois a proposta (mesma ordem da criacao), e atualiza as instancias carregadas. Aceita `rascunho` ou `pronta`; nao cria transicao automatica para `pronta`. Orcamento deve estar `novo` ou `em_analise`. `enviada` retorna o estado existente sem novo e-mail. `aceita`, `recusada` e `cancelada` nao podem ser enviadas por essa acao.

O destinatario vem exclusivamente de `cliente_snapshot.cliente.email`, validado antes do envio. Corpo Jinja com autoescape: nome, numero, resumo e total Decimal recalculado no backend. PDF anexado em base64; nao e enviado link que dependeria do login administrativo.

O arquivo atual e reutilizado quando a chave corresponde ao ID/versao, ha `gerada_em`, e o PDF pode ser lido e validado. Arquivo ausente/corrompido/referencia antiga provoca geracao pela implementacao da Fase C sem commit intermediario. A resposta do provedor deve conter ID de mensagem nao vazio. Isso representa aceite pelo provedor, nao confirmacao de entrega na caixa postal.

Somente depois desse aceite: proposta `enviada`, `enviada_em` UTC e orcamento `proposta_enviada`, confirmados em um commit. Sem mudanca de versao ou de campos legados. Falhas retornam mensagem controlada, rollback e evento `proposal_send_failed`; sucesso registra `proposal_sent`. Snapshot, PDF, enderecos e credenciais nao sao registrados.

## Idempotencia e limite transacional do envio

A proposta fica bloqueada durante a operacao no PostgreSQL. Uma repeticao apos sucesso ve `enviada` e nao chama o provedor. Resend recebe a chave estavel `proposal/{id}/v{versao}/{created_at}`. A [idempotencia do Resend dura 24 horas](https://resend.com/docs/dashboard/emails/idempotency-keys).

Nao existe transacao atomica entre PostgreSQL e o servico de e-mail. Se o provedor aceitar e o commit falhar, o banco faz rollback, mas o e-mail nao pode ser desfeito. A API informa explicitamente que o aceite ocorreu sem registro local confirmado. Timeout tambem pode ter resultado incerto. Nesses casos, verificar o provedor e conciliar antes de repetir, especialmente apos 24 horas.

Se houve rollback da geracao, uma nova renderizacao pode produzir bytes PDF diferentes; o provedor pode rejeitar a mesma chave com payload diferente, em vez de reenviar. Nao ha retry automatico nem promessa de entrega exatamente uma vez em falha distribuida. Uma futura outbox persistente, com payload/ID do provedor e conciliacao, e o ajuste recomendado para eliminar essa dependencia operacional; nao foi criada migration para isso nesta fase.

## Aprovacao e producao

`POST /propostas/{proposta_id}/aprovar` retorna `PropostaResponse`. Exige proposta `enviada` com `enviada_em` e orcamento `proposta_enviada`. A confirmacao no painel e um registro administrativo do aceite do cliente, nao um link publico de aprovacao.

Uma unica transacao cria a producao, marca proposta `aceita`, preenche `aprovada_em` UTC e marca orcamento `aprovado`. Falhas no flush/commit revertem todos esses dados. Logs depois do commit: `proposal_approved` e `production_created`. Versao e PDF nao mudam.

Repeticao com proposta ja aceita retorna seu estado sem nova producao. O vinculo suficiente ja existe: `PropostaModel.orcamento_id` e 1:1 e `ProducaoModel.orcamento_id` possui UNIQUE. O bloqueio de linha serializa aprovacoes pelo servico, e a restricao UNIQUE tambem impede duplicacao por outros escritores. Nao foi necessaria migration ou nova coluna.

Se existir producao antes da aprovacao, ou proposta aceita sem producao, retorna 409 para conciliacao. Nao sobrescreve producao preexistente nem tenta reparar dados silenciosamente.

Mapeamento para campos reais:
- `titulo`: objeto da proposta, limitado a 150 caracteres; objeto completo preservado nas observacoes.
- `cliente` / `servico`: snapshot congelado; limites de 120/100 caracteres verificados.
- `produtor_id` / `orcamento_id`: proposta persistida.
- `observacoes`: numero, versao, objeto, descricao, itens, descontos, total calculado e condicoes da proposta.
- `status`: `aguardando_inicio`; `etapas`: `[]`; sem inventar prazo de entrega.

Nenhum campo legado de proposta do orcamento e usado como fonte. Nenhum Projeto de portfolio e criado.

## CRM e caminhos legados

O editor usa um estado de operacao que bloqueia double-submit, edicao, geracao simultanea e fechamento durante envio/aprovacao. Dirty impede ambas as acoes. Cada acao exige confirmacao e usa a resposta real para atualizar o estado; erros preservam os dados locais. Respostas posteriores a logout sao descartadas pelo contexto existente.

Um evento do controller solicita nova leitura da lista de orcamentos; apos aceite, solicita tambem a lista de producoes. Nao atribui status localmente nem cria producao ficticia. Os listeners sao registrados uma vez por modulo, nao em cada abertura. Falha na leitura do CRM nao reexecuta a acao comercial.

O botao antigo Aprovar e as selecoes comerciais de status abrem o editor. O endpoint legado `/orcamentos/{id}/enviar-proposta`, que antes apenas inventava uma referencia de PDF, agora retorna 409 orientando o uso do fluxo real. PATCH direto de status comercial tambem retorna 409; status de orcamento com proposta finalizada fica protegido contra regressao. Isso e uma mudanca intencional de comportamento para impedir bypass; campos legados permanecem intactos. Registros antigos incoerentes exigem conciliacao, nao conversao automatica.

## Validacao

Na raiz do repositorio, com dependencias locais:

```powershell
backend/venv/Scripts/python.exe -B -m unittest discover -s backend/tests -p test_proposta_comercial.py -v
node frontend/tests/proposta_comercial.cjs
```

Playwright deve estar resolvivel pelo Node; Edge e o navegador padrao dos testes. Nenhum servidor real precisa ser iniciado: as requisicoes do navegador sao interceptadas localmente. Os testes backend usam SQLite descartavel e mock do Resend, com rede externa bloqueada.

Seis testes backend cobrem envio, snapshot/anexo, PDF ausente/corrompido/reutilizado, resposta invalida do provedor, falha de e-mail, falha de commit, repeticoes, transicoes, aprovacao, producao unica, rollback de producao, guarda UNIQUE e endpoints HTTP. A consulta com bloqueio foi compilada para PostgreSQL; concorrencia real em PostgreSQL nao foi executada.

Teste frontend cobre dirty, botoes, confirmacoes aceitas/canceladas, erros, double-submit, state/CRM atualizados e producao disponivel. Foram observadas exatamente duas recargas de orcamentos (envio e aprovacao) e uma de producoes (aprovacao), sem listeners/chamadas duplicados.

Regressao: suites anteriores de persistencia, router, HTML/QR/PDF, editor e contratos executadas. Nenhuma regressao encontrada nesses testes. A diferenca de timezone do SQLite foi normalizada apenas nas comparacoes dos testes; o codigo continua usando UTC e campos timezone-aware no PostgreSQL.

## Pendencias para Fase E

- Outbox/conciliacao duravel para falhas entre provedor e commit; nao prometer exactly-once distribuido.
- Validacao em PostgreSQL descartavel concorrente e homologacao do Resend com destinatario de teste autorizado.
- Storage persistente, empacotamento do logo/template e limites de runtime continuam conforme Fase C. Envio depende do PDF estar acessivel nesse storage.
- Planejar tratamento de registros comerciais legados incoerentes sem sobrescrever dados existentes.
- Nenhum webhook, financeiro, autorizacao nova, reenvio, aprovacao publica ou Fase E foi implementado.
