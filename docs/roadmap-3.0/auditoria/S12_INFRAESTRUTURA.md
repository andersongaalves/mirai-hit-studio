# Auditoria setorial - S12 Infraestrutura

Status do setor: **DIAGNOSTICADO**. Mudancas derivadas: [Etapa 07](../ETAPA_07_APLICACAO_AUDITORIA.md).

## 1. Baseline

| Campo | Valor |
| --- | --- |
| SHA | `18caa5b` (main) |
| Data | 24/10/2026 |
| Ambiente | Leitura dos workflows (`.github/workflows`), `main.py`, `core/`, `_headers`; historico de execucoes do CI desta semana |
| Limitacoes | Sem leitura das variaveis do Render nem das regras de protecao de branch |

## 2. Inventario

Release protegido (gate de integracao, evidencia de storage, dry-run, publish), backups e
restore drill, Storage (R2/Cloudinary/Supabase), worker de tag no processo web, limitador
de requisicoes em SQLite local, CSP em Report-Only, Cloudflare Pages + Render.

## 4. Achados

| ID | Sev. | Categoria | Achado | Status |
| --- | --- | --- | --- | --- |
| AUD6-S12-001 | P2 | 4.12 | Cobertura de CI: ~26 de 63 suites de navegador e ~25 de 96 arquivos Python nao rodam em nenhum workflow; duas ja quebraram sem alerta (`flows.cjs`, `public_accessibility.cjs`) | Aberto |
| AUD6-S12-002 | P2 | 4.10 | Worker de tag (ffmpeg) roda dentro do processo web, disputando CPU/memoria com a API | Aberto |
| AUD6-S12-003 | P2 | 4.6 | Limitador de requisicoes em SQLite local: zera a cada deploy/instancia (ver S02-009, S03-002) | Aberto |
| AUD6-S12-004 | P2 | 4.6 | CSP so em Report-Only (ver S02-007) | Aberto |
| AUD6-S12-005 | P3 | 4.10 | Passo "Run isolated browser auth regression" do Portals E2E falha de forma intermitente (visto em `c05d947` e no PR #69; passa ao reexecutar) | Aberto |
| AUD6-S12-006 | P3 | 4.12 | Branches descartaveis ficam no repositorio (ex.: `audit/s02-probes`); o proxy desta sessao nao permite apagar | Aberto |
| AUD6-S12-007 | P3 | 4.12 | README descreve a v1 (AUD-S12-005 da Etapa 03, ainda aberto) | Aberto |

### AUD6-S12-001 - Cobertura de CI (P2)

- Evidencia: comparacao entre `frontend/tests/*` e `backend/tests/test_*.py` e as chamadas
  nos workflows (inclui glob `test_proposta_*.py` e suites chamadas por testes Python).
  Fora do CI, entre outros: `acesso`, `security`, `dashboard`, `financeiro_admin`,
  `clientes`, `auditoria`, `public_accessibility`, `seo_*`, `ai_*` (navegador) e
  `test_usuarios`, `test_audit_logs`, `test_clientes`, `test_dashboard`,
  `test_financeiro_admin`, `test_newsletter`, `test_ai_*` (Python). O PR #96 inclui
  `test_usuarios` e `test_audit_logs`.
- Recomendacao: job dedicado "suites restantes" (paralelo, sem bloquear o release no
  inicio) e corrigir as duas suites quebradas; depois tornar obrigatorio.

### AUD6-S12-002 - Worker no processo web (P2)

- Evidencia: `main.py` inicia `process_previews` no startup (`AUDIO_TAG_WORKER_ENABLED`
  padrao `True`), consultando a fila a cada 5 s e executando ffmpeg via `asyncio.to_thread`.
- Recomendacao: servico/worker separado no Render (ou cron) e desligar no web.

### P3

- **005**: investigar a instabilidade (provavel corrida de tempo) e estabilizar.
- **006**: apagar a branch pela interface do GitHub; politica de limpeza de branches.
- **007**: atualizar o README.

## 5-13. Resumo

- Candidatas: saude interna, historico de releases, alertas, runbooks restritos.
- Dependencias: todos os setores (CI), S02 (CSP/limitador), S08 (worker).
- Validacao: 001 com job no CI e suites verdes; 002 com worker separado.
