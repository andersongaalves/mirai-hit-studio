# Mirai Hit Studio 3.0 - Etapa 03: Auditoria tecnica

- Versao auditada: `main` `a37c82b` (PR #25), mais as branches abertas
  `feat/segregacao-testes-dashboards-20261014` (PR #26, rascunho) e
  `feat/producer-preview-auto-client` (sem PR).
- Data: 14/10/2026.
- Metodo: leitura estatica por setor, inventario de autorizacao das 143 rotas,
  execucao das 40 suites Playwright do frontend (sem PostgreSQL) e consulta ao historico
  de CI. Nenhum banco, provider ou ambiente de producao foi acessado.
- Limite: as suites Python nao rodaram neste ambiente (PyPI indisponivel). O CI do
  GitHub estava verde em `a37c82b` e no PR #26 (`ddda9ad`).

Severidades conforme o roadmap: P0 critica, P1 alta, P2 media, P3 baixa.
Status: **Corrigido** = tratado na branch `fix/roadmap-3-0-etapas-02-04`;
**Aberto** = exige decisao, ambiente ou fase posterior.

## Resumo

| ID | Setor | Sev. | Achado | Status |
| --- | --- | --- | --- | --- |
| AUD-S12-001 | S12/S02 | P3 | Rate limit por IP: IP real confirmado nos logs; resta testar `X-Forwarded-For` forjado | Rebaixado (P1 -> P3) |
| AUD-S06-001 | S06 | P2 | Assinatura do webhook Mercado Pago so aceita `data.id` no caso original; a documentacao atual exige minusculas | Corrigido |
| AUD-S12-002 | S12/S07/S08 | P2 | CORS nao expoe `Content-Disposition`; downloads cross-origin saem como "arquivo" | Corrigido |
| AUD-S07-001 | S07 | P2 | Falha do financeiro impede abrir o projeto (Promise.all) | Corrigido |
| AUD-S08-002 | S08 | P2 | Falha de repasses impede carregar todo o portal do produtor | Corrigido |
| AUD-S07-003 | S07 | P2 | Seletor de substituicao oferece versoes ja substituidas (409) | Corrigido |
| AUD-S08-001 | S08 | P2 | Seletor do produtor ignora o tipo e oferece versoes antigas (404/409) | Corrigido |
| AUD-S07-002 | S07/S08 | P2 | Lista de projetos fica em memoria sem atualizacao | Corrigido (parcial) |
| AUD-S08-003 | S08 | P3 | Status salvo e reportado como erro se a lista de arquivos falhar | Corrigido |
| AUD-S07-004 | S07/S08 | P3 | `URL.revokeObjectURL` sincrono pode cancelar downloads | Corrigido |
| AUD-S12-003 | S12 | P2 | CI cobre 4 de 40 suites de frontend; 3 suites quebraram sem alerta | Parcial |
| AUD-S12-004 | S12/S06 | P2 | Preview Netlify 19 aponta para a API de producao | Aberto (PR #20) |
| AUD-S05-001 | S07/S05 | P2 | Previas do produtor nascem invisiveis ao cliente | Corrigido (decisao: visiveis) |
| AUD-S01-001 | S01 | P3 | `portfolio.html` perdeu o rotulo de estudo e os links para as verticais (SEO H2) | Corrigido (rotulo "Estudo") |
| AUD-S02-001 | S02 | P3 | Login revela existencia de usuario por tempo de resposta | Aberto |
| AUD-S08-004 | S08 | P3 | Produtor pode versionar previa/entrega oculta para ele | Aberto |
| AUD-S09-001 | S09 | P3 | `PUT /config` retorna 500 se a linha `id=1` nao existir | Aberto |
| AUD-S12-005 | S12 | P3 | README descreve a v1 (SQLite, `front/`) | Aberto |
| AUD-S09-002 | S09 | P3 | Editor de servicos (builder legado) estoura a largura em telas de 390px | Aberto |

AUD-S12-001 foi rebaixado apos leitura dos logs do Render (14/10): o Uvicorn registra o IP
publico de cada visitante, entao o limite nao agrupa todos os usuarios.

## Fichas

### AUD-S12-001 - Rate limit pode tratar todos os clientes como um IP
- Arquivos: `backend/core/http_security.py`, `routers/ai_chat.py`, `routers/client_access.py`.
- Evidencia: a chave e `request.client.host`. O start command e
  `uvicorn main:app --host 0.0.0.0 --port $PORT`; o Uvicorn so confia em
  `X-Forwarded-For` vindo de `FORWARDED_ALLOW_IPS` (padrao `127.0.0.1`). Atras do balanceador
  do Render, todos os pedidos chegariam com o IP do proxy.
- Impacto: limite global de 5 orcamentos a cada 10 min e 10 logins por minuto para todo o
  site. `docs/seguranca-fase-e.md` ja lista a confirmacao como pendente.
- Plano minimo: verificar o IP observado em producao; configurar
  `FORWARDED_ALLOW_IPS` para a faixa do proxy (nunca `*` sem acesso direto bloqueado) ou
  ler o cabecalho confiavel do Render. Teste de regressao com dois IPs.

### AUD-S06-001 - Manifest da assinatura Mercado Pago
- Arquivo: `backend/services/mercado_pago_webhook_service.py`.
- Evidencia: o guia de notificacoes de Orders diz para converter `data.id` alfanumerico
  para minusculas antes de montar `id:[data.id_url];request-id:...;ts:...;`. O codigo usava
  o caso original. Ids de Orders sao maiusculos (`ORD...`). A validacao I.4 usou o
  simulador, que assinou o caso original.
- Impacto: entregas reais poderiam receber 401, deixando a confirmacao de Pix dependente
  de polling.
- Correcao: aceita os dois manifests com o mesmo segredo, em comparacao constante. O HMAC
  continua obrigatorio.
- Teste: `test_signature_accepts_documented_lowercase_manifest_for_uppercase_order_id`.

### AUD-S12-002 - Nome do arquivo no download
- Arquivo: `backend/main.py`.
- Evidencia: o frontend (`miraihitstudio.com.br`) chama `mirai-hit-studio.onrender.com`;
  `expose_headers=["X-Request-ID"]`. `Content-Disposition` nao e safelisted, entao
  `response.headers.get("content-disposition")` volta `null` e os portais caem em
  `"arquivo"`/`proposta-{id}.pdf`. As suites Playwright nao detectam porque o mock nao
  aplica CORS.
- Correcao: expor `Content-Disposition`. Teste: `tests/test_http_cors_contract.py`.

### AUD-S07-001 / AUD-S08-002 - Falha secundaria bloqueando telas
- Arquivos: `frontend/js/cliente/index.js` (`openDetail`), `frontend/js/produtor/index.js`
  (`enterPortal`).
- Evidencia: `Promise.all` com o financeiro (cliente) e os repasses (produtor). Qualquer
  falha descartava os dados principais e redirecionava ou mostrava o portal vazio.
- Correcao: chamadas secundarias isoladas, com aviso proprio e ultimo valor conhecido.
- Testes: cenarios `failFinance` e `failPayouts` em `portal_cliente.cjs` e
  `portal_produtor.cjs` (vermelhos no codigo anterior, verdes na correcao).

### AUD-S07-003 / AUD-S08-001 - Seletor de versoes
- Arquivos: `frontend/js/cliente/ui.js`, `frontend/js/produtor/ui.js`;
  regra em `producao_arquivo_service._version`.
- Evidencia: o backend recusa substituir uma versao ja substituida (409) e exige mesmo
  tipo (404). A UI listava todas as versoes; no produtor, tambem de outro tipo.
- Correcao: somente a versao mais recente de cada grupo, filtrada pelo tipo escolhido.

### AUD-S07-002 - Projetos em memoria
- Arquivo: `frontend/js/cliente/index.js`.
- Evidencia: `productions` era carregado apenas no login.
- Correcao: o detalhe atualiza o item na lista; ao voltar para a aba, dashboard e lista
  recarregam em segundo plano. Polling continuo ou eventos ficam para a fase 5.03.

### AUD-S12-003 - Cobertura de CI do frontend
- Evidencia: o Storage Integration Gate roda `portfolio_admin`, `portal_produtor`,
  `portal_cliente` e `checkout`. No baseline, 34/40 suites passaram localmente. Causas:
  - Ambiente: `checkout` (falta `qrcode`), `performance_h3` (recurso externo),
    `proposta_documento` (layout gerado pelo backend).
  - Drift corrigido: `home_artists` (esperava o seletor do placeholder de carregamento) e
    `client_signup` (asserção sem esperar a resposta). `client_signup` entrou no gate.
  - Aberto: `seo_content_h2` (AUD-S01-001).
- Proximo passo: job de frontend dedicado com as demais suites.

### AUD-S12-004 - Preview apontando para producao
- Arquivo: `frontend/js/config.js` (`deploy-preview-19--miraihitstudio.netlify.app` ->
  `PROD_API`).
- Impacto: cadastros e pagamentos de teste entram no banco real, exatamente o tipo de
  registro que a Etapa 01 precisa classificar. O PR #20 (rascunho) trata isso.

### AUD-S05-001 - Visibilidade de previas
- `portal_produtor.enviar_arquivo` grava `visible_to_client=False`; o cliente so ve a
  previa apos acao do admin. A branch `feat/producer-preview-auto-client` muda para
  `tipo == "previa"`. E decisao de produto (fase 5.10 trata politicas por servico).

### Demais (P3)
- AUD-S01-001: `seo_content_h2.cjs` exige "Study" em `portfolio.html`; o rotulo hoje so
  aparece via JS (`portfolio_ui.js`).
- AUD-S02-001: `/auth/login` nao executa bcrypt quando o usuario nao existe.
- AUD-S08-004: `_version` nao checa `visivel_produtor` do arquivo substituido.
- AUD-S09-001: `update_config` nao trata `config is None`.
- AUD-S12-005: README desatualizado.

## Inventario de autorizacao

143 rotas. Publicas por desenho: login, cadastro/recuperacao/ativacao, checkout por token,
newsletter, `POST /orcamentos`, leitura de `/projetos`, `/servicos`, `/config` e
segmentos publicos, webhooks assinados. Todas as rotas de portal usam `require_client`,
`require_producer` ou `require_admin` com ownership no servico. Nenhuma rota
administrativa publica foi encontrada.

## Relacao com a Etapa 01

O PR #26 substitui a remocao fisica por classificacao reversivel (`is_test`) e mantem o
Pix real de R$ 5 no historico. Isso atende as restricoes do roadmap (sem TRUNCATE, sem
apagar Storage, conciliacao preservada). Antes de aplicar: decidir se a Etapa 01 fica
como classificacao ou se a limpeza DB-08 continua prevista; recalcular o manifesto
(DB-01/DB-02), pois a migration usa IDs fixos.
