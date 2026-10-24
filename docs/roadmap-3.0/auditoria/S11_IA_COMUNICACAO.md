# Auditoria setorial - S11 IA e comunicacao

Status do setor: **DIAGNOSTICADO**. Mudancas derivadas: [Etapa 07](../ETAPA_07_APLICACAO_AUDITORIA.md).

## 1. Baseline

| Campo | Valor |
| --- | --- |
| SHA | `18caa5b` (main) |
| Data | 24/10/2026 |
| Ambiente | Suites `ai_chat`, `ai_inbox`, `portal_notifications`, `newsletter_admin`, `newsletter_public`, `analytics` verdes; e-mails revisados no PR #55 |
| Limitacoes | Provider de IA e Resend nao chamados; suites Python de IA nao rodam localmente nem no CI |

## 2. Inventario

Chat do site (consentimento, handoff), Inbox IA do Admin (copiloto), e-mails transacionais
(Resend + webhook), newsletter (campanhas, descadastro), notificacoes dos portais (5.18).

## 4. Achados

| ID | Sev. | Categoria | Achado | Status |
| --- | --- | --- | --- | --- |
| AUD6-S11-001 | P2 | 4.11 / 5.4 | Notificacoes existem so para cliente e produtor (`papel IN ('cliente','produtor')`); o Admin nao recebe avisos de eventos que exigem acao | Aberto |
| AUD6-S11-002 | P3 | 4.11 | Eventos sem notificacao: aprovacao/rejeicao de beat (S04-002), falha de tag (S08-002), proposta de portfolio do produtor, solicitacao de producao do cliente | Aberto |
| AUD6-S11-003 | P2 | 4.12 / S12 | 12 arquivos de teste Python de IA (guardrails, inbox, e-mail, provider) nao rodam em nenhum workflow | Aberto |

### Detalhes

- **001**: estender o modelo (papel `admin`) ou alimentar a lista de pendencias do
  dashboard (S09-001) com os mesmos eventos.
- **002**: adicionar os eventos ao `portal_notificacao_service`, com texto fixo.
- **003**: incluir as suites de IA no CI (sem chamar providers reais).

## 5-13. Resumo

- Centralizar: central de notificacoes por papel e preferencias de canal (Etapa 06, 9).
- Dependencias: S04, S08, S09, S12.
- Validacao: 001 e 002 entregues; suites de IA no CI.
