# Portais Mirai - Backend Fase 1

Status: **PASS**.

Os Portais do Produtor e do Cliente usam os mesmos registros operacionais do Admin, com
autenticacao JWT existente e ownership consultado no banco em cada requisicao. A Fase 1.1
adicionou somente o vinculo autenticavel necessario entre `usuarios` e `clientes`.

## Reutilizacao confirmada

| Recurso | Estado | Uso nesta fase |
| --- | --- | --- |
| Usuarios/JWT | Existe | Login, expiracao, usuario ativo e papel foram reutilizados. |
| Produtores | Existe | O papel `produtor` e o proprio `usuarios.id` identificam o produtor. |
| Clientes | Existe | Entidade comercial autoritativa vinculada a uma conta provisionada pelo Admin. |
| Producoes | Existe | `producoes.produtor_id` define o produtor; `orcamento.cliente_id` define o cliente. |
| Status/prazo | Existe | Os mesmos campos de Producao sao projetados nos portais. |
| Admin | Existe | Rotas operacionais permanecem administrativas. |
| Financeiro do cliente | Existe | Projecao read-only limitada a cobrancas e pagamentos do proprio cliente. |
| Repasse do produtor | Implementado na Fase 2 | Obrigacao manual, unica por Producao, com produtor preservado como snapshot. |
| Arquivos privados da producao | Implementado na Fase 2 | Metadados versionados e objetos opacos em bucket privado dedicado. |
| Auditoria | Existe | O provisionamento reutiliza o gerenciamento administrativo auditado de Usuarios. |

`projetos` representa o Portfolio publico e nao foi tratado como historico privado de
producoes.

## API do produtor

- `GET /portal/produtor/producoes`
- `GET /portal/produtor/producoes/{producao_id}`

As consultas usam exclusivamente o ID do usuario autenticado. Nao aceitam `producer_id`
ou `client_id` do browser. Recursos de outro produtor e IDs inexistentes retornam a mesma
resposta `404`. Email, observacoes administrativas e dados financeiros nao sao expostos.

Reatribuicao tem efeito imediato porque ownership e consultado no banco em cada request.
O produtor anterior perde acesso mesmo com token ainda valido.

## Identidade e API do cliente

`usuarios.cliente_id` e nullable para manter contas Admin e Produtor existentes, possui FK
para `clientes.id` e e unico quando preenchido. A constraint de papel exige que apenas
usuarios com papel `cliente` tenham o vinculo e que toda conta cliente tenha exatamente um
cliente associado. Nenhuma tabela nova foi criada.

O provisionamento usa as rotas administrativas existentes de Usuarios. Nao existe signup
publico nem associacao automatica por nome ou email. O cliente nao pode alterar o proprio
vinculo. Desativacao, mudanca de papel ou troca do cliente associado tem efeito na proxima
requisicao porque o backend recarrega o usuario e o `cliente_id` atual do banco; o
identificador nao e confiado ao JWT nem ao browser.

Endpoints read-only:

- `GET /portal/cliente/producoes`
- `GET /portal/cliente/producoes/historico`
- `GET /portal/cliente/producoes/{producao_id}`
- `GET /portal/cliente/producoes/{producao_id}/financeiro`

O ownership segue `producao -> orcamento -> cliente_id`. Um ID inexistente e um ID de
outro cliente produzem a mesma resposta `404`. A projecao omite observacoes internas,
produtor, dados pessoais, referencias do provider e conciliacao. O historico reutiliza os
status reais `finalizado` e `entregue`; nenhuma tabela ou maquina de estados foi duplicada.

## Migration

`d3b8e1f4a720` adiciona `usuarios.cliente_id`, FK com exclusao restrita, UNIQUE e check de
coerencia entre papel e vinculo. A coluna e nullable e preserva contas Admin e Produtor.
Upgrade, downgrade de uma revision e novo upgrade sao validados em banco descartavel.

## Fase 2 - Portal do Produtor

A Fase 2 adiciona exatamente as duas estruturas autorizadas pela lacuna comprovada na
Fase 1. A migration incremental `24ef7f883a03`, descendente de `d3b8e1f4a720`, cria:

- `producao_arquivos`: arquivos privados de uma Producao, tipo controlado, autoria,
  MIME, tamanho, SHA-256, chave opaca unica, grupo/numero de versao, substituicao sem
  sobrescrita, visibilidade separada para produtor e cliente e timestamps;
- `repasses_produtor`: uma obrigacao por Producao, produtor persistido como snapshot,
  `Numeric(12,2)`, BRL, estados `definido`, `liberado` e `pago`, datas coerentes,
  referencia opcional e comprovante referenciado em `producao_arquivos`.

O bucket privado padrao e `producao-arquivos` (configuravel por
`PRODUCAO_STORAGE_BUCKET`). O backend usa a credencial privilegiada somente no servidor,
valida ownership antes de acessar o objeto e entrega o conteudo por streaming autenticado.
Nem a credencial nem `object_key` sao retornadas ao browser. Upload usa chave nova e
`upsert=false`; falha do banco depois do upload executa compensacao no Storage.

O Portal do Produtor reutiliza o login JWT e oferece dashboard, lista/detalhe, transicoes
operacionais permitidas, arquivos visiveis, envio de previa/entrega e recebimentos
read-only. O Admin gerencia arquivos/visibilidade e define, libera, registra ou corrige o
repasse com auditoria. Reatribuicao da Producao revoga os arquivos pelo ownership atual,
mas nao transfere o repasse historico: consultas financeiras usam `produtor_id` gravado no
acordo.

Endpoints adicionados ao portal:

- `PATCH /portal/produtor/producoes/{id}/status`
- `GET|POST /portal/produtor/producoes/{id}/arquivos`
- `GET /portal/produtor/arquivos/{id}/conteudo`
- `GET /portal/produtor/repasses`
- `GET /portal/produtor/repasses/{id}/comprovante`

As mutacoes administrativas ficam sob `/producoes/{id}/arquivos` e
`/producoes/{id}/repasse`, protegidas por `require_admin`. Pagamentos do cliente,
Mercado Pago e checkout nao foram alterados. Repasse continua manual via Pix: nao ha
split, Pix Out, parcelas, estorno ou transferencia automatica.

A migration passou por bootstrap, downgrade, upgrade, constraints, RLS e smoke de app em
PostgreSQL 17.11 descartavel. O cluster, fixtures e binarios temporarios foram removidos.

## Fase 3 - Portal do Cliente

O Portal do Cliente reutiliza a identidade `Usuario -> Cliente`, as Producoes existentes,
o financeiro comercial e `producao_arquivos`. Nenhuma tabela ou migration foi criada; a
head permanece `24ef7f883a03`.

Rotas da interface, compativeis com Clean URLs:

- `/cliente`
- `/cliente/projetos`
- `/cliente/projetos/{id}`

Endpoints de arquivos adicionados ao portal:

- `GET|POST /portal/cliente/producoes/{id}/arquivos`
- `GET /portal/cliente/arquivos/{id}/conteudo`

O dashboard e a lista usam somente status, prazos e datas existentes. Producoes
`finalizado` e `entregue` formam o historico, sem duplicar registros. O detalhe apresenta
etapas derivadas da maquina de estados atual, materiais, referencias, previas, entregas e
financeiro do proprio cliente. Cobrancas pendentes reutilizam o checkout existente;
Mercado Pago, webhooks e a semantica de Pagamento nao foram alterados.

Uploads do cliente aceitam apenas `material` e `referencia`, preservam versoes imutaveis e
so permitem substituir um arquivo anteriormente enviado pela mesma conta. Listagem,
streaming e download exigem ownership atual e visibilidade para cliente. `object_key` e
identificadores internos de autoria nao chegam ao browser. Arquivos `comprovante`, usados
no repasse ao produtor, sao excluidos da projecao e nao podem ser tornados visiveis ao
cliente.

Solicitacao textual de revisao nao foi implementada: nao existe entidade persistente
adequada para comentario, decisao e limite contratado. A interface exibe o status real de
revisao e as previas liberadas, mas nao simula a solicitacao em audit log ou observacoes.
Esse recurso depende de aprovacao estrutural futura.

## Lacunas atuais

- **Revisoes do cliente:** falta persistencia de solicitacoes, comentarios e limites.
- **Data de conclusao:** Producao nao possui campo dedicado; o portal nao rotula
  `updated_at` como data de conclusao.

## Resultado de seguranca

- autenticacao obrigatoria nos dois portais;
- autorizacao e ownership no backend;
- isolamento mutuo entre Admin, Produtor e Cliente;
- tokens invalidos/expirados recusados;
- sessoes de Admin, Produtor e Cliente isoladas no navegador, com logout e falhas 401
  restritos ao perfil afetado;
- access token JWT com duracao definida por `ACCESS_TOKEN_EXPIRE_MINUTES` (60 minutos no
  exemplo de ambiente); o frontend nao implementa renovacao por refresh token;
- projecoes sem campos administrativos ou financeiros internos;
- zero novas tabelas ou migrations na Fase 3;
- comprovantes e repasses do produtor nunca sao expostos ao cliente;
- nenhuma alteracao de Mercado Pago, configuracao do bucket ou fluxo publico;
- frontend novo restrito ao Portal do Cliente, sem alterar a landing.

Conclusao: o backend dos dois portais permanece compartilhado com o Admin e a Fase 2 do
Produtor passou a representar arquivos privados e repasses sem reutilizar entidades com
semantica incorreta. A Fase 3 entrega a interface funcional do Cliente sobre esses mesmos
registros, com isolamento por ownership e sem iniciar o design definitivo da Fase 4.
