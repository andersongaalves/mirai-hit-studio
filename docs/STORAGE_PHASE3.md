# Storage da Fase 3

Base de trabalho: `2d83c8047c76614264cee2d4804fbf13a6740fc7`.

## 3.8B - R2 privado

Status tecnico: **PASS para revisao do CTRL**. Nao houve merge, deploy, criacao de
bucket ou acesso ao R2 real.

O fluxo de `producao_arquivos` passou a resolver o provider pelo Storage Core da
3.8A. Materiais, referencias e previas usam `production_temp`; entregas e
comprovantes usam `production_final`. Ambos apontam para R2 pela configuracao
padrao, mas podem usar o fake em testes. As referencias persistidas sao opacas e
provider-neutral, sem nome de cliente ou nome original do arquivo.

Objetos Supabase antigos continuam legiveis: uma chave historica sem esquema e
interpretada pelo bridge legado conforme o tipo persistido. O banco nao precisou
de coluna nova, backfill ou migration.

O backend continua sendo a autoridade de ownership e visibilidade. Nenhuma URL,
credencial ou `object_key` e enviada nos schemas dos Portais. Downloads passam
pelo backend e agora conferem o SHA-256 do conteudo com o hash persistido antes
de responder. Divergencia falha fechada e gera somente IDs tecnicos no log.

### Falhas e compensacao

- Upload e imutavel; o adapter R2 envia `If-None-Match: *`.
- Falha antes da persistencia nao cria linha no banco.
- Falha de banco apos upload tenta remover apenas o novo objeto.
- Versao anterior nao e apagada ao ser substituida logicamente.
- Falha de compensacao e registrada sem credenciais ou chave privada.
- Objeto ausente, hash divergente e indisponibilidade retornam erro sanitizado.
- Reconciliacao de orfaos e retencao pertencem a 3.8E; nenhuma exclusao
  automatica foi ativada nesta fase.

### Evidencias

- Core R2: upload, leitura, `HEAD`, exclusao, assinatura curta, MIME, tamanho,
  assinatura de conteudo, conflito e erros sanitizados com transporte fake.
- Fluxos de Producao: ownership Admin/Produtor/Cliente, visibilidade, historico,
  substituicao, comprovante privado e compensacao de Storage/banco.
- Integracao nova: selecao de escopo, referencia opaca, leitura legada e
  verificacao de integridade no download.

O R2 real permanece **nao validado** nesta branch. Sua validacao requer
credenciais server-only, buckets privados preexistentes e autorizacao especifica;
nao deve ser confundida com o resultado do fake S3-compatível.

### Rollout pendente

1. Revisar a branch isolada e o CI PostgreSQL 17.
2. Confirmar os dois buckets R2 privados e as variaveis server-only.
3. Executar smoke controlado sem dados comerciais reais.
4. Manter origem Supabase disponivel para referencias historicas.
5. Integrar somente apos aprovacao do CTRL; nao remover objetos legados.
