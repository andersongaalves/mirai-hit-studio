# Storage 3.8E - ciclo de vida e retencao

## Resultado

FASE 3.8E: BLOCKED para exclusao automatica.

O inventario read-only e o planejador de retencao foram implementados. A
ferramenta opera somente em `--dry-run`, retorna contagens sanitizadas e sempre
informa zero exclusoes. Nenhuma migration foi criada.

## Classificacao

| Categoria | Regra segura atual |
|---|---|
| Materiais e referencias ativos | Preservar |
| Previas ativas | Preservar |
| Versoes substituidas de material/referencia/previa | Revisar ate prazo ser aprovado |
| Entregas finais, inclusive substituidas | Preservar |
| Comprovantes | Preservar como registro financeiro |
| PDFs de propostas enviados | Preservar como documento comercial imutavel |
| Imagens e audios publicos referenciados | Preservar |
| Objetos remotos sem referencia | Nao avaliados: providers nao oferecem listagem no contrato atual |

## Exclusao segura planejada

Uma futura execucao destrutiva deve validar referencia, ausencia de vinculo
protegido, prazo aprovado e estado remoto, registrar auditoria e tratar banco e
provider de modo retomavel. Versoes finais e comprovantes nao entram em limpeza
automatica. A origem nao deve ser removida no mesmo passo da primeira copia.

## Decisoes pendentes

O negocio precisa aprovar prazos separados para materiais, referencias,
previas e versoes substituidas. O CTRL tambem precisa aprovar extensoes de
inventario paginado por provider antes que objetos orfaos possam ser provados.
Sem essas duas decisoes, habilitar exclusao automatica seria inseguro.

Nenhuma politica de lifecycle de R2, Supabase ou Cloudinary foi alterada e
nenhum objeto real foi listado ou removido.
