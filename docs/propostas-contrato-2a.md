# Propostas: contrato 2A

Somente contratos. Nenhuma rota, acao de persistencia, PDF ou envio foi implementado.
Models, colunas e migrations permanecem intactos. Pydantic v2.

## Contrato publico

`PropostaCreate` aceita somente `{}`. O futuro comando obtera o orcamento da
URL/contexto autorizado, nunca de um campo enviado no body. Snapshot, numero,
status, versao e defaults serao construidos pelo backend.

`PropostaUpdate` aceita PATCH parcial com apenas:
`produtor_id`, `objeto`, `descricao`, `itens`, `pagamentos`, `condicoes`.
Campo ausente significa preservar; use `model_dump(exclude_unset=True)`.
Somente `produtor_id` aceita null explicito, para remover atribuicao.
Listas vazias e textos vazios sao aceitos para rascunhos. Objeto: ate 200 caracteres.
A permissao e existencia do produtor serao verificadas no futuro service.
Campos extras sao rejeitados, inclusive em objetos aninhados.

Item: `{descricao, quantidade, valor_unitario, desconto}`.
Quantidade positiva; valores financeiros nao negativos e finitos, em Decimal.
Desconto e absoluto por linha, conforme o editor existente, nao percentual.
IDs locais e subtotais nao fazem parte do input nem do item de response.
Regras de arredondamento e desconto superior ao valor da linha ficam para o service;
o calculo visual existente limita subtotal a zero, sem constituir regra autoritativa.

Pagamento: `{tipo, titulo, url, habilitado}`; lista extensivel com tipos unicos no PATCH.
Editor atual apresenta integral, parcial_1 e parcial_2. Tipos adicionais recebidos
sao preservados pelo mapper. URL nao vazia deve ser HTTP/HTTPS, inclusive quando
desabilitada; pagamento habilitado exige URL. Rascunhos locais iniciam todos
desabilitados. Preencher os dois primeiros links os habilita; o terceiro utiliza
o checkbox existente. Habilitar o terceiro sem URL produz payload invalido,
a ser apresentado como erro de validacao na futura integracao.

Totais de response: `{subtotal, desconto, total}` em Decimal, ou null quando
ainda nao calculados. Nenhum total e aceito no PATCH. O futuro service sera a
autoridade e recalculara os valores antes de gravar. O schema nao calcula nem
atesta consistencia aritmetica de dados recebidos. JSON serializa Decimal como string.

Snapshot de response:
`{cliente: {nome, email, whatsapp}, orcamento: {id, servico, detalhes, valor_total, link_guia}}`.
Contatos/detalhes historicos sao preservados sem nova validacao comercial.
O backend criara o snapshot; o editor recebe uma copia para exibicao readonly.

`PropostaResponse` contem os seis campos editaveis mais:
`id`, `orcamento_id`, `numero`, `versao`, `status`, `cliente_snapshot`, `totais`,
`pdf_path`, `gerada_em`, `enviada_em`, `aprovada_em`, `created_at`, `updated_at`.
Esses campos adicionais sao server-owned. Datas seguem a nulabilidade do model.
Status: rascunho, pronta, enviada, aceita, recusada, cancelada. Nenhuma transicao
ou PATCH generico de status foi criado.

## Mapeamento ORM e frontend

`PropostaResponse.from_orm_model(model)` mapeia explicitamente:
`itens_json -> itens`, `pagamentos_json -> pagamentos`, `totais_json -> totais`.
Um `totais_json = {}` vira null, nao um total zero inventado. JSON interno precisa
conter a estrutura documentada; formato legado divergente falhara explicitamente.
`PropostaResponse.model_validate()` valida o contrato publico, nao nomes de colunas.
O futuro service devera fazer o mapeamento inverso e serializar Decimal para JSON;
nao deve passar `model_dump()` diretamente ao construtor ORM.

`mapResponseToState()` copia campos conhecidos sem compartilhar objetos com a response.
`setProposta()` aplica o mapper, deriva a exibicao do cliente a partir do snapshot,
reinicia campos locais e mantem dirty=false. Edicoes do usuario marcam dirty=true.
Numero, status e snapshot nao podem ser alterados pelos mutadores genericos.

`state.proposta` contem dados do contrato. Flags dirty/aba/carregando/salvando e
`state.orcamento` sao contexto da UI. `state.ui.locais` guarda prestador, entrada,
prazo, validade, PIX, Mercado Pago e observacoes de pagamento: nao existem colunas
ou contrato persistido para esses campos. Permanecem locais e identificados nos
rotulos; nao sao prometidos como salvos. Data e readonly, derivada de created_at.
Produtor responsavel deixou de ser texto livre e usa produtor_id.

`getEditorProposta()` adapta esses dados para as abas antigas, mantendo sua estrutura
visual. `state.ui.totaisVisuais` guarda total/restante estimados sem sobrescrever
os totais autoritativos recebidos. Preview respeita habilitado em toda a lista.
O rascunho aberto a partir do orcamento continua exclusivamente local; nao simula
um snapshot oficial, numero, status ou datas criados pelo servidor.

`buildPropostaPayload()` usa allowlist e elimina numero, orcamento_id, snapshot,
status, timestamps, totais, subtotal, ID local, restante e demais campos locais.
`getPropostaPayload()` delega ao mapper; nao exige acoplamento da API ao state.
`proposta_api.js` expoe somente os adaptadores nesta fase: foram removidas chamadas
especulativas a endpoints inexistentes. Nao ha GET/POST/PATCH de propostas ativo.

## Testes e proxima fase

Na raiz: `node frontend/tests/proposta_contracts.mjs`.
Em backend: `python -B -m unittest discover -s tests -p test_proposta_contracts.py -v`.
Backend roda em subprocesso com settings sinteticos e conexao bloqueada; utiliza
instancia ORM transiente, sem banco nem create_all. O payload gerado pelo teste JS
e validado pelo schema Python. Snapshot, enums, PATCH, readonly, Decimal, URL,
campos extras, totais derivados, pagamentos e dirty possuem verificacoes focadas.

Proxima fase, apenas mediante autorizacao: defaults/snapshot/numero no backend,
recalculo monetario, validacao de produtor, mapeamento de gravacao e integracao.
Antes de oferecer salvar, decidir o destino dos campos locais ainda sem contrato.
