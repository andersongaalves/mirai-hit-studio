# Auditoria setorial - S09 Administracao operacional

Status do setor: **DIAGNOSTICADO**. Mudancas derivadas: [Etapa 07](../ETAPA_07_APLICACAO_AUDITORIA.md).

## 1. Baseline

| Campo | Valor |
| --- | --- |
| SHA | `18caa5b` (main) |
| Data | 24/10/2026 |
| Ambiente | Leitura estatica; suites `dashboard` (com capturas), `producoes`, `clientes`, `auditoria`, `newsletter_admin`, `production_stages_admin`, `portal_settings_admin`, `usuarios`, `admin_foundation` verdes |
| Limitacoes | Sem dados reais; volume de producoes pequeno |

## 2. Inventario

- Menu do Admin (13 itens): Dashboard, Inbox IA, Producoes, Clientes, Propostas e
  Orcamentos, Financeiro, Servicos, Portfolio, Beats, Configuracoes, Usuarios, Newsletter,
  Auditoria.
- Dashboard: `GET /dashboard` (metricas, pipeline, atencao, atividade recente).
- Modal de producao concentra operacao, etapas, arquivos, mensagens, cotas, politicas,
  creditos e repasse.

## 3. Fluxos

- Entrar -> dashboard -> abrir secao -> modal da entidade.
- Pendencias reais hoje espalhadas: solicitacoes de producao, beats em revisao, projetos de
  portfolio propostos, previas com falha de tag, cobrancas a conciliar, propostas sem
  resposta, producoes atrasadas.

## 4. Achados

| ID | Sev. | Categoria | Achado | Status |
| --- | --- | --- | --- | --- |
| AUD6-S09-001 | P2 | 5.4 / 4.8 | "Requer atencao" so mostra producoes atrasadas e propostas sem resposta; demais pendencias exigem visitar cada secao | Aberto |
| AUD6-S09-002 | P2 | 5.4 / 5.5 | Nao ha pagina central de cliente ou produtor nem links entre entidades (cliente -> propostas, producoes, cobrancas, creditos) | Aberto |
| AUD6-S09-003 | P3 | 4.3 | Dashboard repete os mesmos numeros em tres blocos (metricas, atencao e pipeline) | Aberto |
| AUD6-S09-004 | P3 | 4.10 | Ao entrar, o Admin carrega servicos, portfolio e configuracoes junto com o dashboard; uma falha gera alertas de secoes que o usuario nem abriu | Aberto |
| AUD6-S09-005 | P3 | 4.4 | Textos sem acento no dashboard ("Orcamentos em aberto", "Producoes ativas", "VER PRODUCOES") e mensagens cruas da API em alertas ("Not found") | Aberto |
| AUD6-S09-006 | P3 | 4.8 | Sem busca global (cliente, proposta, producao, cobranca) | Aberto |
| AUD6-S09-007 | P3 | 4.6 | `PUT /config` retorna 500 se a linha `id=1` nao existir (AUD-S09-001 da Etapa 03, ainda aberto) | Aberto |

### AUD6-S09-001 - Pendencias incompletas (P2)

- Evidencia: `dashboard_service` monta `attention` apenas com `producoes_atrasadas` e
  `propostas_aguardando_decisao`.
- Recomendacao: lista de tarefas com contagem e link para: solicitacoes de producao,
  beats em revisao, portfolio em revisao, previas com falha de tag (S08-002), cobrancas a
  conciliar (S10-003), entregas aguardando aprovacao.

### AUD6-S09-002 - Paginas centrais e links (P2)

- Evidencia: cada modulo lista sua entidade isoladamente; nomes de cliente e produtor sao
  texto simples.
- Recomendacao: pagina de cliente e de produtor (Etapa 06, 5.4) e links contextuais (5.5),
  sem ampliar autorizacao.

### P3

- **003**: manter um bloco de pipeline e um de pendencias.
- **004**: carregar cada secao ao abrir (os carregadores por secao ja existem).
- **005**: revisar textos e mapear erros para mensagens humanas.
- **006**: busca por nome/numero com resultados agrupados.
- **007**: tratar ausencia da configuracao com criacao ou 404 claro.

## 5-7. Corrigir, centralizar, implementar

- Centralizar: pendencias (001), paginas de cliente/produtor (002).
- Candidatas: busca global; filtros salvos.

## 8-10. Tutoriais, linguagem, links

- Tutoriais: "Liberar ou ocultar arquivos", "Revisar portfolio e catalogo de beats".
- Links: em todas as tabelas, cliente/produtor/proposta/producao/cobranca clicaveis.

## 11. Lacunas de teste

- Dashboard com todas as pendencias; carregamento sob demanda; links contextuais.

## 12. Dependencias

- S02 (usuarios), S06/S10 (conciliacao), S08 (tag), S04 (beats), S01 (portfolio).

## 13. Criterios de validacao

001 e 002 entregues e inspecionados; textos revisados.
