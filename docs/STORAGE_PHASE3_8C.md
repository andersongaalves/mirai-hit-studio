# Storage 3.8C - imagens publicas do Portfolio

## Resultado

FASE 3.8C: PASS para implementacao e validacao descartavel.

O upload administrativo de capas do Portfolio usa o escopo `public_image` do
Storage Core e o provider Cloudinary configurado no backend. Nenhuma credencial
e enviada ao navegador e nenhuma migration foi criada.

## Contrato

- Upload restrito a Admin, com limite de 10 MB.
- JPEG, PNG, WebP e AVIF passam por validacao de MIME e assinatura.
- O identificador publico e opaco e gerado no backend.
- A URL de entrega aplica `f_auto`, `q_auto`, limite de largura de 1600 px e
  preserva o cache publico do provider.
- Substituicao grava a nova URL antes de remover o objeto anterior.
- Falha no commit compensa o upload novo.
- Remocao e exclusao do projeto eliminam apenas objetos reconhecidos como
  pertencentes ao Cloudinary configurado.
- URLs externas e historicas permanecem intactas.

## Evidencias

Os testes usam um adapter em memoria e transporte HTTP simulado. Foram
validados upload, autorizacao, tipo/conteudo, chave opaca, substituicao,
compensacao, remocao, compatibilidade com URL historica e fluxo do Admin.

A integracao com uma conta Cloudinary real nao foi executada nesta fase. Nenhum
asset real foi criado, alterado ou removido, e nenhum deploy foi realizado.

## Rollout pendente

Antes de integrar e publicar, o CTRL deve revisar a branch, confirmar as
variaveis `CLOUDINARY_*` no ambiente e autorizar um smoke administrativo com um
asset descartavel. A migracao de imagens historicas pertence a Fase 3.8F.
