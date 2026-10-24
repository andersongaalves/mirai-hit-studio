# Auditoria setorial - S07 Portal do Cliente

Status do setor: **DIAGNOSTICADO**. Mudancas derivadas: [Etapa 07](../ETAPA_07_APLICACAO_AUDITORIA.md).

## 1. Baseline

| Campo | Valor |
| --- | --- |
| SHA | `18caa5b` (main) |
| Data | 24/10/2026 |
| Ambiente | Leitura estatica; `portal_cliente.cjs` verde com capturas 390/1440 px (API simulada); `beat_preview`, `portal_notifications` verdes |
| Limitacoes | Sem conta real de cliente; telas Creditos e Explorar avaliadas por codigo |

## 2. Inventario

- Rotas `/portal/cliente`: solicitacoes, propostas (lista, detalhe, PDF, aceitar, recusar),
  checkout por proposta, producoes (lista, historico, detalhe, etapas, mensagens, cotas,
  financeiro, arquivos e envio), conteudo de arquivo, creditos, beats (catalogo,
  adquiridos, arquivos, solicitar licenca), notificacoes.
- Frontend: `portal-cliente.html`, `js/cliente/{index,ui,api,request,utils}.js`, modulos
  compartilhados (mensagens, etapas, cotas, notificacoes, fila de envios).
- Menu: Dashboard, Propostas, Projetos, Creditos, Explorar.

## 3. Fluxos

- Proposta -> aceite -> pagamento -> projeto -> previas/mensagens -> entrega (5.14).
- Solicitar producao (servico + titulo + descricao) -> analise do Admin.
- Explorar beats -> solicitar licenca -> checkout -> arquivos adquiridos.
- Envio de material em segundo plano ("Envios").

## 4. Achados

| ID | Sev. | Categoria | Achado | Status |
| --- | --- | --- | --- | --- |
| AUD6-S07-001 | P2 | 4.8 / 4.3 | Detalhe do projeto e uma pagina unica muito longa no celular (~3.800 px): pagamento fica no fim, embora a pendencia apareca no topo | Aberto |
| AUD6-S07-002 | P3 | 4.5 | Catalogo do cliente recebe campos internos do beat (`produtor_id`, `status`, `ativo`, `motivo_rejeicao`) | Aberto |
| AUD6-S07-003 | P3 | 4.2 | Botao flutuante "Envios" sobrepoe a borda dos cards no celular | Aberto |
| AUD6-S07-004 | P3 | 4.3 | Campos vazios exibidos como conteudo ("Vencimento: Nao informado") | Aberto |
| AUD6-S07-005 | P3 | 4.2 / 4.9 | Todos os itens do menu usam o mesmo icone generico | Aberto |
| AUD6-S07-006 | P3 | 4.6 | Solicitacao de producao sem limite por cliente (so idempotencia por pedido) | Aberto |
| AUD6-S07-007 | P3 | 4.4 | Mensagens do backend sem acentos e com jargao ("Situacao financeira requer conciliacao") | Aberto |

### AUD6-S07-001 - Detalhe do projeto longo demais (P2)

- Evidencia: captura 390 px do detalhe com previas, entregas, materiais, formulario de
  envio, mensagens e pagamento empilhados; "Pagamento pendente" no topo e o botao de
  pagamento so no fim.
- Impacto: o cliente precisa rolar muito para a acao principal (pagar, aprovar previa,
  responder).
- Recomendacao: secoes com ancoras ou abas (Visao geral, Arquivos, Mensagens, Pagamento) e
  CTA da pendencia principal no topo, com link para a secao.

### P3

- **002**: `beat_service._response` e usado para todos os papeis; criar resposta publica
  sem campos de moderacao e ids internos.
- **003**: o botao "Envios" fica fixo sobre o conteudo; reservar espaco ou mover para o
  cabecalho/menu da conta.
- **004**: ocultar linhas sem valor ou usar texto util ("Sem vencimento definido").
- **005**: icones distintos (ou nenhum) por item de menu.
- **006**: limite simples por cliente/dia, com mensagem clara.
- **007**: tabela de mensagens amigaveis no frontend para 409/503 (ver S06-005).

## 5-7. Corrigir, centralizar, implementar

- Centralizar: perfil do cliente e "Minhas compras" no menu da conta (Etapa 06, 5.3);
  pendencias (pagar, revisar previa, responder) num bloco unico do dashboard.
- Candidatas: checklist do primeiro projeto; historico de downloads.

## 8-10. Tutoriais, linguagem, links

- Tutoriais: "Entender proposta, entrada, saldo e quitacao"; "Revisar previa e enviar
  referencias"; "Comprar licenca de beat".
- Links: notificacao -> secao exata do projeto (mensagem, arquivo, pagamento).

## 11. Lacunas de teste

- Detalhe com muitas secoes em 390 px (navegacao por secao); catalogo sem campos internos.

## 12. Dependencias

- S02 (menu da conta, nome exibido), S06 (mensagens de pagamento), S08 (fila de envios
  compartilhada), S11 (notificacoes).

## 13. Criterios de validacao

001 resolvido com inspecao 390/1440 px; 002 com teste de contrato; P3 revisados.
