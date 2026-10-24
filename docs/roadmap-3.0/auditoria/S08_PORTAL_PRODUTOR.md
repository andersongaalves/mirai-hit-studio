# Auditoria setorial - S08 Portal do Produtor

Status do setor: **DIAGNOSTICADO**. Mudancas derivadas: [Etapa 07](../ETAPA_07_APLICACAO_AUDITORIA.md).

## 1. Baseline

| Campo | Valor |
| --- | --- |
| SHA | `18caa5b` (main) |
| Data | 24/10/2026 |
| Ambiente | Leitura estatica; `portal_produtor.cjs` verde com capturas 390/1440 px; `audio_tags`, `beat_preview`, `stage_payouts` verdes |
| Limitacoes | Processamento real de tag (ffmpeg) nao executado; sem conta real |

## 2. Inventario

- Rotas `/portal/produtor`: producoes (lista, detalhe, status), arquivos (lista, envio,
  conteudo), repasses e comprovante; beats (meus, catalogo, configuracao, envio); tag de
  audio (perfil, envio, configuracao); portfolio do produtor (5.20); notificacoes.
- Menu: Dashboard, Producoes, Financeiro, Portfolio, Minha tag, Catalogo, Beats.
- Worker de tag: tarefa assincrona no processo web, consulta a fila a cada 5 s e usa
  ffmpeg; falha marca `erro`; Admin pode reprocessar.

## 3. Fluxos

- Producao atribuida -> etapas (iniciar, enviar para revisao) -> previa (com tag
  automatica) -> entrega -> repasse por etapa.
- Beat: enviar (MP3/WAV/multitrack, capa) -> revisao do Admin -> catalogo.
- Portfolio: propor projeto -> aprovacao do Admin -> creditos.

## 4. Achados

| ID | Sev. | Categoria | Achado | Status |
| --- | --- | --- | --- | --- |
| AUD6-S08-001 | P2 | 4.3 / 4.4 | Menu com "Catalogo" e "Beats" separados e "Minha tag" isolada; funcoes do mesmo tema espalhadas | Aberto |
| AUD6-S08-002 | P2 | 4.11 | Falha da tag na previa nao avisa o Admin; o produtor so ve "Solicite revisao ao estudio" | Aberto |
| AUD6-S08-003 | P3 | 4.4 / 4.2 | Envio de arquivo do produtor usa o seletor nativo em ingles ("Choose File"), diferente do cliente | Aberto |
| AUD6-S08-004 | P3 | 4.2 | Botao "Envios" sobrepoe cards no celular (mesmo componente do S07) | Aberto |
| AUD6-S08-005 | P3 | 4.8 | "Enviar para revisao" fica solto abaixo das etapas, sem indicar qual etapa | Aberto |
| AUD6-S08-006 | P3 | 4.4 | Saudacao e cabecalho usam o login ("Ola, producer-a") | Aberto (ver S02-011) |
| AUD6-S08-007 | P3 | 4.6 | Produtor pode versionar previa/entrega oculta para ele (AUD-S08-004 da Etapa 03, ainda aberto) | Aberto |

### AUD6-S08-001 - Navegacao do produtor (P2)

- Evidencia: menu com sete itens; "Catalogo" (beats publicados por todos) e "Beats" (meus
  beats) sao o mesmo dominio em dois lugares; "Minha tag" e configuracao de perfil.
- Recomendacao: "Beats" com abas (Meus beats, Catalogo); tag e preferencias no perfil do
  produtor (Etapa 06, 5.2), com aviso rapido no dashboard quando a tag estiver incompleta.

### AUD6-S08-002 - Falha de tag silenciosa (P2)

- Evidencia: `audio_tag_service.processar_um` marca `erro` e registra log; a rota
  `/admin/audio-tag/previas/{id}/reprocessar` existe, mas nao ha notificacao ou fila
  visivel ao Admin.
- Impacto: previa fica sem versao com tag; cliente pode ficar sem previa ate alguem notar.
- Recomendacao: notificacao/pendencia no dashboard do Admin com acao "Reprocessar".

### P3

- **003**: reutilizar o seletor estilizado do portal do cliente.
- **004**: mesmo ajuste de S07-003.
- **005**: botao dentro da etapa em andamento, com o nome da etapa.
- **007**: `producao_arquivo_service._version` nao verifica `visivel_produtor` do arquivo
  substituido.

## 5-7. Corrigir, centralizar, implementar

- Centralizar: perfil do produtor (nome de exibicao, tag, especialidades, dados de
  repasse) e "Beats" unico.
- Candidatas: central de uploads com historico de processamento; checklist do produtor.

## 8-10. Tutoriais, linguagem, links

- Tutoriais: "Enviar previa", "Cadastrar/testar tag e publicar beat".
- Links: notificacao -> etapa/arquivo; repasse -> producao.

## 11. Lacunas de teste

- Falha de tag gerando pendencia ao Admin; seletor de arquivo em portugues.

## 12. Dependencias

- S02 (perfil e menu), S07 (fila de envios), S09 (pendencias do Admin), S12 (worker).

## 13. Criterios de validacao

001 e 002 entregues; inspecao 390/1440 px; testes focados.
