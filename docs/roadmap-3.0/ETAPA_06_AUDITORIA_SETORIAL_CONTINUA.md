# Mirai Hit Studio 3.0 - Etapa 06: Auditoria setorial continua

## 1. Checkpoint de retomada

> Esta secao deve ser lida e atualizada por qualquer IA antes de trabalhar nesta etapa.

| Campo | Estado atual |
| --- | --- |
| Status global | Auditoria em andamento |
| Fase atual | 6.1 - Diagnostico setorial |
| Setor atual | S02 - Identidade e acesso (DIAGNOSTICADO) |
| Ultima acao concluida | Diagnostico S02 entregue em `auditoria/S02_IDENTIDADE_ACESSO.md` (15 achados: 1 P1, 6 P2, 8 P3) |
| Proxima acao | Iniciar diagnostico S06 - Checkout e pagamentos. Correcoes do S02 aguardam autorizacao (ordem sugerida: AUD6-S02-001 e 002) |
| Ultimo SHA analisado | `18caa5b` (main; sem mudanca de codigo desde `8a7ac44`) |
| Ultima atualizacao | 24/10/2026 |
| Bloqueios | Correcoes do S02 dependem de autorizacao; 004, 006, 007 e 015 dependem de decisao |

### Regra de atualizacao obrigatoria

No inicio de cada sessao:

1. Atualizar `Status global`, `Fase atual`, `Setor atual`, `Proxima acao`, SHA e data.
2. Adicionar uma linha no historico com status `INICIADO`.
3. Confirmar se houve mudanca na `main` desde o ultimo SHA analisado.

Ao parar ou concluir:

1. Registrar a ultima acao realmente concluida.
2. Registrar a proxima acao concreta, sem termos vagos como "continuar".
3. Marcar o setor como `PAUSADO`, `DIAGNOSTICADO`, `EM CORRECAO` ou `VALIDADO`.
4. Adicionar uma linha no historico com achados, PRs, testes e bloqueios.
5. Nunca marcar como concluido algo que depende de CI, homologacao ou decisao humana.

## 2. Objetivo

Auditar os 12 setores mapeados da Mirai de forma repetivel, encontrando defeitos,
riscos e oportunidades de simplificacao. Cada setor deve produzir diagnostico antes de
qualquer implementacao. Correcoes, migrations, merge e deploy sao atividades separadas.

A auditoria deve responder, para cada fluxo:

- O que esta quebrado?
- O que esta confuso, excessivo ou no lugar errado?
- O que expoe informacao indevida?
- O que pode ser removido, simplificado ou centralizado?
- O que vale implementar?
- Onde uma orientacao contextual ou tutorial e necessario?
- Quais testes faltam para provar o comportamento?

## 3. Status permitidos

| Status | Significado |
| --- | --- |
| NAO INICIADO | Nenhuma evidencia coletada no setor |
| INICIADO | Escopo e baseline registrados; diagnostico em execucao |
| PAUSADO | Trabalho interrompido com proxima acao registrada |
| DIAGNOSTICADO | Achados documentados; nenhuma correcao implicita |
| EM CORRECAO | Correcao autorizada e isolada em branch/PR |
| EM VALIDACAO | Testes ou CI em andamento |
| VALIDADO | Criterios do setor atendidos e riscos residuais registrados |
| BLOQUEADO | Impedimento objetivo registrado; exige decisao ou acesso |

## 4. Matriz obrigatoria de auditoria

### 4.1 Bugs funcionais

- Botoes, links, filtros ou formularios inoperantes.
- Falhas silenciosas, estados desatualizados e dados duplicados.
- Fluxos sem saida ou quebrados por voltar, recarregar ou expirar sessao.
- Divergencias entre frontend, backend, banco e providers.
- Concorrencia, repeticao e idempotencia incorretas.

### 4.2 Bugs visuais e responsividade

- Elementos cortados, desalinhados, sobrepostos ou fora do container.
- Texto que ultrapassa cards, botoes ou modais.
- Espacos vazios, secoes sem conteudo e dimensoes desproporcionais.
- Estado ativo/selecionado ausente ou incorreto.
- Imagens distorcidas, recortes ruins e layout quebrado por viewport.
- Mudanca de layout durante carregamento.

### 4.3 Excesso de informacao ou opcoes

- Texto, metrica ou campo sem utilidade para a decisao atual.
- Informacao tecnica apresentada a usuarios nao tecnicos.
- Opcoes duplicadas, equivalentes ou avancadas cedo demais.
- Secoes vazias exibidas como conteudo real.
- Acoes raras ocupando o mesmo peso da acao principal.

### 4.4 Linguagem e comunicacao

- Titulos, labels, botoes e mensagens ambiguos.
- Termos diferentes para o mesmo conceito.
- Linguagem tecnica, acusatoria, insegura ou pouco humana.
- Mensagem de erro sem causa segura nem proximo passo.
- Portugues, pontuacao, capitalizacao e consistencia por papel.

### 4.5 Vazamento de informacoes internas

- IDs, stack traces, chaves de objetos, buckets e providers.
- URLs assinadas, tokens ou referencias reconstruiveis.
- Margens, comissoes e regras internas expostas indevidamente.
- Dados de outro cliente ou produtor.
- Campos de API alem do necessario para a tela.

### 4.6 Seguranca e autorizacao

- Isolamento entre clientes, produtores e administradores.
- Acesso direto por URL ou ID.
- Download e preview sem ownership.
- Sessao expirada, revogada ou reutilizada.
- Upload malicioso, extensao falsa e tamanho excessivo.
- Operacao duplicada ou sem trilha de auditoria.

### 4.7 Integridade financeira

- Valor cadastrado, exibido, congelado e cobrado divergentes.
- Desconto ou promocao no dominio errado.
- Pagamento parcial, integral, externo, cancelado ou reembolsado.
- Webhook atrasado, repetido ou concorrente.
- Arquivo ou producao liberado sem quitacao valida.
- Repasse calculado ou liberado incorretamente.

### 4.8 Experiencia e eficiencia

- Passos e campos desnecessarios.
- Informacao que pode ser preenchida automaticamente.
- Operacao longa que deveria continuar em segundo plano.
- Falta de progresso, retry seguro ou recuperacao.
- Busca, filtro, ordenacao e estados vazios.
- Primeira utilizacao e descoberta de recursos.

### 4.9 Acessibilidade

- Teclado, ordem de foco e fechamento por `Esc`.
- Labels, `aria-live`, contraste e texto alternativo.
- Acao compreensivel sem depender apenas de cor.
- Movimento reduzido e componentes dinamicos anunciados.

### 4.10 Performance e confiabilidade

- Chamadas repetidas, consultas N+1 e payload excessivo.
- Imagens, audio e uploads sem limites adequados.
- Tela principal bloqueada por dado secundario.
- Cache incorreto e comportamento em conexao lenta.

### 4.11 Observabilidade e suporte

- Logs sanitizados e correlacao por request ID.
- Diferenciacao entre erro do usuario, sistema e provider.
- Eventos financeiros e administrativos auditaveis.
- Diagnostico possivel sem consulta manual ao banco.

### 4.12 Manutencao tecnica

- Regra de negocio duplicada ou calculada no frontend.
- Contratos inconsistentes e componentes repetidos.
- Teste fragil, ausente ou que nao reproduz a producao.
- Documentacao e comportamento divergentes.
- Arquivo sem setor responsavel definido.

## 5. Centralizacao e navegacao

Cada setor deve identificar informacoes e funcoes espalhadas que podem ser reunidas sem
criar telas gigantes ou misturar papeis.

### 5.1 Menu central da conta

O nome no canto superior direito dos portais e candidato a abrir um menu acessivel com:

- Meu perfil.
- Configuracoes.
- Notificacoes.
- Seguranca e senha.
- Ajuda.
- Sair.

O menu deve funcionar por teclado, fechar ao clicar fora ou usar `Esc`, e exibir somente
opcoes permitidas para o papel autenticado.

### 5.2 Perfil e configuracoes do produtor

Centralizar, quando fizer sentido:

- Nome de exibicao, contato, biografia e especialidades.
- Tag de audio, intervalo e volume.
- Preferencias de notificacao e upload.
- Dados de repasse.
- Portfolio, beats enviados e historico de processamento.

Avaliar mover a aba isolada `Minha tag` para esta area, preservando acesso rapido quando
a configuracao estiver incompleta.

### 5.3 Perfil e configuracoes do cliente

- Nome, contato, nome artistico ou empresa.
- Senha, seguranca e preferencias de comunicacao.
- Dados reutilizados em propostas e documentos.
- Solicitacoes, creditos, compras e arquivos adquiridos.

`Minhas compras` deve aparecer somente quando houver conteudo e pode ter acesso pela
conta e por `Explorar`, sem duplicar os dados.

### 5.4 Paginas centrais no Admin

Cliente:

- Cadastro, orcamentos, propostas, producoes, arquivos, pagamentos, creditos,
  solicitacoes, comunicacao e auditoria.

Produtor:

- Perfil, especialidades, producoes, etapas, portfolio, beats, tag, repasses, arquivos e
  auditoria.

### 5.5 Links contextuais

Quando autorizado, nomes e referencias devem abrir a entidade correspondente:

- Cliente -> perfil administrativo do cliente.
- Produtor -> perfil do produtor.
- Proposta -> detalhe e versao.
- Producao -> operacao e arquivos.
- Cobranca -> historico financeiro.
- Beat -> revisao ou catalogo.
- Arquivo -> producao e versao de origem.

Nenhum link contextual pode ampliar autorizacao ou expor uma entidade por ID.

## 6. Tutoriais e ajuda contextual

### 6.1 Quando exigir orientacao

- Fluxo com mais de tres passos importantes.
- Termo tecnico ou financeiro inevitavel.
- Acao irreversivel ou de alto impacto.
- Upload com formato, limite ou processamento especifico.
- Opcoes parecidas com consequencias diferentes.
- Primeiro uso sem dados existentes.
- Erro recorrente observado em suporte ou testes.

### 6.2 Formatos permitidos

- Introducao curta e opcional no primeiro acesso.
- Tooltip para um termo, nao para explicar uma tela inteira.
- Painel lateral de ajuda.
- Exemplo de preenchimento.
- Checklist de configuracao.
- Tutorial reabrivel pelo menu `Ajuda`.

Tutoriais nunca devem bloquear tarefas, reaparecer em toda visita, substituir labels
claros ou revelar regras internas. A conclusao deve ser persistida por usuario.

### 6.3 Tutoriais candidatos

- Solicitar uma producao e acompanhar a analise.
- Entender proposta, entrada, saldo e quitacao.
- Pagar por Pix ou cartao e retomar tentativa pendente.
- Revisar previa e enviar referencias.
- Comprar licenca de beat e entender arquivos liberados.
- Enviar previa como produtor.
- Cadastrar/testar tag e publicar beat.
- Registrar pagamento externo no Admin.
- Liberar ou ocultar arquivos.
- Revisar portfolio e catalogo de beats.

## 7. Entregas obrigatorias por setor

Cada diagnostico deve conter:

1. Baseline: SHA, data, ambiente e limitacoes.
2. Inventario: telas, rotas, servicos, tabelas e providers.
3. Fluxos principais, alternativos e de erro.
4. Achados priorizados com evidencia sanitizada.
5. O que corrigir, remover e simplificar.
6. O que centralizar.
7. Implementacoes candidatas.
8. Tutoriais ou ajuda contextual necessarios.
9. Melhorias de linguagem.
10. Links contextuais e opcoes que devem ficar ocultas ate serem relevantes.
11. Lacunas de teste.
12. Dependencias entre setores.
13. Riscos residuais e criterios para validacao.

### Ficha de achado

| Campo | Conteudo |
| --- | --- |
| ID | `AUD6-Sxx-NNN` |
| Setor principal | S01-S12 |
| Setores impactados | Lista |
| Categoria | Secao 4, 5 ou 6 |
| Severidade | P0-P3 |
| Evidencia | Passos, tela, rota ou teste; sem segredo |
| Impacto | Usuario, operacao, financeiro ou seguranca |
| Causa provavel | Hipotese sustentada por evidencia |
| Recomendacao | Menor solucao coerente |
| Implementacao candidata | Opcional; sem implementacao implicita |
| Teste necessario | Regressao focada |
| Dependencias | Setores, dados ou decisao |
| Status | Aberto, aceito, descartado, corrigido ou validado |

### Severidade

- P0: perda de dados, acesso indevido, vazamento ou risco financeiro critico.
- P1: fluxo principal bloqueado ou resultado incorreto sem alternativa segura.
- P2: atrito relevante, inconsistiencia ou falha com alternativa.
- P3: melhoria visual, textual, de descoberta ou conveniencia.

## 8. Ordem e progresso setorial

S12 acompanha transversalmente todas as auditorias, embora sua auditoria isolada seja a
ultima.

| Ordem | Setor | Foco adicional | Status | Inicio | Ultima atualizacao | Documento de achados |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | S02 - Identidade e acesso | Conta, sessao, papeis e menu central | DIAGNOSTICADO | 24/10/2026 | 24/10/2026 | [S02](auditoria/S02_IDENTIDADE_ACESSO.md) |
| 2 | S06 - Checkout e pagamentos | Valores, idempotencia, Pix, cartao e webhook | NAO INICIADO | - | - | - |
| 3 | S10 - Financeiro | Conciliacao, externos, saldos e repasses | NAO INICIADO | - | - | - |
| 4 | S07 - Portal do Cliente | Projetos, explorar, compras e perfil | NAO INICIADO | - | - | - |
| 5 | S08 - Portal do Produtor | Producoes, uploads, tag, beats e perfil | NAO INICIADO | - | - | - |
| 6 | S09 - Administracao operacional | Entidades centrais, tarefas e excecoes | NAO INICIADO | - | - | - |
| 7 | S05 - Propostas comerciais | Versoes, documentos, aceite e congelamento | NAO INICIADO | - | - | - |
| 8 | S03 - Orcamentos | Calculadora, combos, resumo e rascunho | NAO INICIADO | - | - | - |
| 9 | S04 - Catalogo de servicos | Servicos, combos, beats e promocoes | NAO INICIADO | - | - | - |
| 10 | S01 - Institucional | Conteudo, portfolio, SEO e conversao | NAO INICIADO | - | - | - |
| 11 | S11 - IA e comunicacao | Assistente, e-mail, notificacoes e consentimento | NAO INICIADO | - | - | - |
| 12 | S12 - Infraestrutura | Release, Storage, backup, logs e recuperacao | NAO INICIADO | - | - | - |

## 9. Implementacoes candidatas por setor

Estas ideias devem ser avaliadas, nao implementadas automaticamente.

| Setor | Candidatas |
| --- | --- |
| S01 | Busca/filtros do portfolio; comparacao integrada; CTA contextual; ajuda para iniciar projeto |
| S02 | Menu da conta; sessoes ativas; senha; privacidade; primeiro acesso guiado |
| S03 | Resumo fixo; rascunho; recomendacao de combos; ajuda dos adicionais |
| S04 | Card unico; detalhe do item; central de promocoes; explicacao de licencas |
| S05 | Linha do tempo; comparar versoes; destacar mudancas; centralizar documentos |
| S06 | Resumo financeiro; recuperar pendencia; historico de tentativas; ajuda de liberacao |
| S07 | Perfil central; Explorar; compras; downloads; checklist do primeiro projeto |
| S08 | Perfil/tag central; central de uploads; checklist; historico de processamento |
| S09 | Paginas centrais; busca global; tarefas pendentes; filtros salvos; links entre entidades |
| S10 | Visao por cliente/producao; fila de conciliacao; registro guiado de pagamento externo |
| S11 | Central de notificacoes; canais; templates; historico por entidade; revisao humana |
| S12 | Saude interna; historico de releases; evidencias/backups; alertas; runbooks restritos |

## 10. Metodo de execucao

Para cada setor:

1. Registrar baseline e marcar `INICIADO`.
2. Ler apenas instrucoes, codigo e contratos do setor e integracoes diretas.
3. Inventariar telas, rotas, dados e fluxos.
4. Executar testes existentes e inspecao visual desktop/mobile quando aplicavel.
5. Testar autorizacao, estados vazios, erro, espera e repeticao.
6. Registrar achados sem corrigir durante o diagnostico.
7. Classificar prioridade, centralizacao, implementacao e tutorial.
8. Entregar diagnostico e marcar `DIAGNOSTICADO`.
9. Solicitar decisao antes de mudanca estrutural, migration ou producao.
10. Atualizar checkpoint e historico ao parar.

Nao misturar correcoes de setores diferentes em uma PR. Integracoes podem ser lidas, mas
uma falha externa deve ser registrada no setor responsavel.

## 11. Criterio de validacao de um setor

Um setor so pode ser `VALIDADO` quando:

- Inventario e fluxos estao documentados.
- P0 e P1 foram resolvidos ou formalmente bloqueados.
- P2 aceitos tem plano e responsavel.
- Testes focados passam.
- Autorizacao e isolamento foram verificados.
- Interface foi inspecionada nos viewports relevantes.
- Linguagem, estados vazios, carregamento e erros foram revisados.
- Riscos financeiros e de dados foram registrados.
- Checkpoint aponta para o proximo setor ou acao concreta.

## 12. Historico de sessoes

Adicionar novas linhas no topo da tabela.

| Data | Setor/fase | Status | SHA | Resultado | Proxima acao |
| --- | --- | --- | --- | --- | --- |
| 24/10/2026 | S02 - Identidade e acesso | DIAGNOSTICADO | `18caa5b` | 15 achados (1 P1, 6 P2, 8 P3). P1: sessao de conta renomeada autentica a nova conta com o mesmo login. 8 suites de navegador verdes; sondagens de backend no CI (branch descartavel `audit/s02-probes`); consultas agregadas somente leitura. Sem correcao, migration ou deploy | Iniciar S06; aguardar autorizacao para corrigir AUD6-S02-001/002 |
| 24/10/2026 | S02 - Identidade e acesso | INICIADO | `18caa5b` | Baseline registrado; diagnostico em execucao | Inventariar rotas, telas e sessoes do S02 |
| 24/10/2026 | 6.0 - Preparacao | CONCLUIDO | `8a7ac44318d5b172ff9df75ca35159b571febd3c` | Roadmap, matriz, centralizacao, tutoriais e ordem definidos; nenhuma auditoria executada | Iniciar diagnostico S02 |

## 13. Restricoes permanentes

- Diagnostico nao autoriza correcao, migration, exclusao, merge ou deploy.
- Nao expor tokens, credenciais, dados pessoais ou referencias completas de objetos.
- Nao usar producao para testes destrutivos.
- Nao presumir que registro desconhecido e teste.
- Nao enfraquecer autorizacao, auditoria ou garantias financeiras.
- Preservar alteracoes nao relacionadas.
- Parar no checkpoint quando a proxima acao depender de decisao humana.
