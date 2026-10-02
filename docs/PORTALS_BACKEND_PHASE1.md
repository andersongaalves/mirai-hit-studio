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
| Repasse do produtor | Ausente | Nao existe entidade com semantica de valor devido/pago ao produtor. |
| Arquivos privados da producao | Ausente | Storage existe para PDF de proposta e audio publico, sem metadados de anexos da producao. |
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

## Lacunas deliberadamente nao simuladas

- **Arquivos:** nao ha relacao persistida entre Producao e objetos privados. PDFs de
  propostas nao representam materiais, previas ou entregas; audio do Portfolio e publico.
  Nenhuma rota de arquivo foi criada.
- **Repasse:** cobranca e pagamento representam recebimento do cliente, nao obrigacao com
  o produtor. Nenhum saldo de produtor foi calculado.

## Resultado de seguranca

- autenticacao obrigatoria nos dois portais;
- autorizacao e ownership no backend;
- isolamento mutuo entre Admin, Produtor e Cliente;
- tokens invalidos/expirados recusados;
- projecoes sem campos administrativos ou financeiros internos;
- zero novas tabelas;
- uma migration incremental;
- nenhuma alteracao de Mercado Pago, Storage, frontend ou fluxo publico.

Conclusao: o backend minimo dos Portais do Produtor e do Cliente esta pronto. Anexos
privados de Producao e repasses ao produtor permanecem dependencias explicitas das fases
seguintes e nao foram simulados com JSON, audit logs ou dados financeiros do cliente.
