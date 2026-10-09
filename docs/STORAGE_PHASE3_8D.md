# Storage 3.8D - audio publico do Portfolio

## Resultado

FASE 3.8D: PASS para implementacao e validacao descartavel.

Os audios demonstrativos do Portfolio continuam no bucket publico
`portfolio-audio` do Supabase, mas o fluxo ativo agora resolve o provider pelo
Storage Core. Nenhuma service role e enviada ao navegador e nenhuma migration
foi criada.

## Compatibilidade

- Novos uploads persistem uma referencia opaca com provider e bucket.
- Chaves historicas `projects/{id}/{slot}-{uuid}.mp3` continuam legiveis e
  removiveis sem backfill.
- Antes e Depois permanecem imutaveis por versao; a nova versao e gravada no
  banco antes da limpeza da anterior.
- Falha no commit compensa o objeto novo.
- Falha de limpeza preserva a referencia ativa e gera log sanitizado.
- O player publico continua usando URL publica do Supabase, `controls` e
  `preload=metadata`.

## Limites

O contrato atual aceita somente MP3 de ate 30 MB. MIME, assinatura, tamanho,
projeto e slot sao validados no backend. Duracao nao e extraida porque o modelo
nao possui esse metadado e a interface atual nao o utiliza.

Os testes usam transporte HTTP simulado; Range Requests, cache e reproducao em
um bucket Supabase real permanecem como smoke de rollout. Nenhum objeto real foi
criado, alterado ou removido e nenhum deploy foi realizado.
