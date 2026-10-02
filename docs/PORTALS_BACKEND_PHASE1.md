# Portais Mirai - Backend Fase 1

Status: **BLOCKED parcial**.

O backend do Portal do Produtor foi preparado com isolamento por identidade. O Portal do
Cliente nao foi exposto porque o schema atual nao possui associacao autenticavel entre
`usuarios` e `clientes`. Nenhuma tabela ou migration foi criada.

## Reutilizacao confirmada

| Recurso | Estado | Uso nesta fase |
| --- | --- | --- |
| Usuarios/JWT | Existe | Login, expiracao, usuario ativo e papel foram reutilizados. |
| Produtores | Existe | O papel `produtor` e o proprio `usuarios.id` identificam o produtor. |
| Clientes | Existe | Entidade comercial autoritativa, sem identidade de login associada. |
| Producoes | Existe | `producoes.produtor_id` define ownership do produtor. |
| Cliente da producao | Adaptavel | `producao -> orcamento -> cliente_id` identifica o cliente comercial. |
| Status/prazo | Existe | Os mesmos campos de Producao sao projetados no portal. |
| Admin | Existe | Rotas operacionais permanecem administrativas. |
| Financeiro do cliente | Existe | Cobrancas e pagamentos continuam restritos ao Admin. |
| Repasse do produtor | Ausente | Nao existe entidade com semantica de valor devido/pago ao produtor. |
| Arquivos privados da producao | Ausente | Storage existe para PDF de proposta e audio publico, sem metadados de anexos da producao. |
| Auditoria | Existe | Fluxos administrativos existentes continuam usando audit logs. |

`projetos` representa o Portfolio publico e nao foi tratado como historico privado de
producoes.

## API do produtor

- `GET /portal/produtor/producoes`
- `GET /portal/produtor/producoes/{producao_id}`

As consultas usam exclusivamente o ID do usuario autenticado. Nao aceitam `producer_id`
ou `client_id` do browser. Recursos de outro produtor e IDs inexistentes retornam a mesma
resposta `404`, reduzindo enumeracao. A resposta inclui somente identificacao operacional,
servico, status, etapas e prazo; email, observacoes administrativas e dados financeiros
nao sao expostos.

Reatribuicao tem efeito imediato porque ownership e consultado no banco em cada request.
O produtor anterior perde acesso mesmo com token ainda valido. A Inbox de IA e os modulos
de clientes, usuarios, orcamentos, propostas, producoes administrativas, dashboard,
checkout administrativo e financeiro permanecem exclusivos de Admin.

## Bloqueio do cliente

`UsuarioModel` nao possui `cliente_id`, email verificado ou outra associacao persistente
com `ClienteModel`. Comparar um email informado pelo browser ou pelo token com
`clientes.email` nao seria prova de identidade e criaria risco de IDOR. Por isso, esta fase
nao publica rotas `/portal/cliente`.

Menor proposta estrutural para avaliacao posterior:

1. adicionar `usuarios.cliente_id` nullable, unico e com FK para `clientes.id`;
2. aceitar o papel `cliente` mantendo `ativo` como revogacao global e JWT com expiracao;
3. provisionar o vinculo por Admin; se houver onboarding por email, persistir verificacao
   segura e de uso unico em vez de inferir identidade pelo endereco informado;
4. aplicar ownership por esse vinculo em toda listagem, detalhe, financeiro e arquivo.

Essa proposta exige migration e aprovacao antes da implementacao.

## Lacunas deliberadamente nao simuladas

- **Arquivos:** nao ha relacao persistida entre Producao e objetos privados. PDFs de
  propostas nao representam materiais, previas ou entregas; audio do Portfolio e publico.
  Nenhuma rota de arquivo foi criada.
- **Repasse:** cobranca e pagamento representam recebimento do cliente, nao obrigacao com
  o produtor. Nenhum saldo de produtor foi calculado.
- **Historico do cliente:** producoes finalizadas podem formar o historico quando houver
  identidade de cliente segura; nenhuma tabela paralela e necessaria.

## Resultado de seguranca

- autenticacao obrigatoria no portal do produtor;
- autorizacao e ownership no backend;
- Admin recusado nas rotas do produtor e produtor recusado nas rotas administrativas;
- tokens invalidos/expirados recusados;
- projecao sem campos administrativos e financeiros;
- zero novas tabelas;
- zero migrations;
- nenhuma alteracao de Mercado Pago, Storage, frontend ou fluxo publico.

Conclusao: a parte independente e segura do produtor esta pronta. A Fase 1 permanece
**BLOCKED** ate a aprovacao do vinculo persistente Usuario-Cliente; anexos privados e
repasse tambem precisam de modelagem propria antes de serem expostos.
