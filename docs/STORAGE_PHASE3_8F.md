# Storage 3.8F - migracao de arquivos legados

## Resultado

FASE 3.8F: PASS para ferramenta e simulacao descartavel.

MIGRACAO REAL: PENDENTE DE AUTORIZACAO CTRL.

A ferramenta cobre o caminho comprovado de arquivos privados de Producao:
Supabase Storage legado para os buckets R2 configurados pelo Storage Core.
Nenhuma migration de banco foi criada.

## Fluxo

1. Inventario sanitizado por provider e tipo, sem imprimir referencias.
2. Leitura do objeto de origem.
3. Verificacao do tamanho e SHA-256 persistidos.
4. Copia para chave R2 deterministica e opaca.
5. Leitura e `stat` do destino.
6. Nova verificacao de tamanho e SHA-256.
7. Lock da linha e atualizacao atomica da referencia.
8. Audit log tecnico `storage.production_file_migrated`.

A origem nunca e apagada pela ferramenta. Retry usa a mesma chave de destino;
se ela ja existe, seu conteudo precisa conferir antes da referencia ser
atualizada. Falha de provider, hash, tamanho ou metadata interrompe o item.

O modo de copia exige simultaneamente `--confirm-copy` e
`STORAGE_MIGRATION_WRITE_ENABLED=true`, alem de PostgreSQL. Os lotes sao
limitados a 500 registros.

## Escopo dos legados

- Arquivos privados de Producao: ferramenta implementada e simulada.
- Audio de Portfolio: permanece no Supabase; compatibilidade lazy pertence a
  3.8D, sem copia necessaria.
- Imagens do Portfolio: URLs historicas sao preservadas; importar URLs externas
  automaticamente criaria risco de SSRF e exige inventario/revisao 3.8C.
- PDFs de propostas: ja possuem Storage duravel e imutavel; nenhum novo destino
  foi aprovado.

## Validacao e rollout

Os testes descartaveis cobrem copia, verificacao, retry, conflito divergente e
preservacao da origem. Nenhuma credencial, bucket ou arquivo real foi usado.

Antes de executar em producao: revisar o inventario, confirmar backup e restore,
validar configuracoes R2, executar lote minimo, conferir leitura pela aplicacao,
monitorar e somente depois ampliar lotes. A desativacao ou limpeza do Supabase
legado deve ser uma etapa posterior e separadamente autorizada.
