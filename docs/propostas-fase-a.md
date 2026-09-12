# Propostas: Fase A

## Estado verificado

O repositorio estava limpo no inicio desta fase. As correcoes C01-C03 e F01-F03,
o bootstrap e os contratos 2A ja estavam versionados. A auditoria antiga foi
usada como referencia, nao como descricao literal do codigo atual.
O editor continuava local, sem chamadas HTTP de propostas; CRUD, service e
router de propostas ainda nao existiam. Campos legados permanecem referenciados
pelo fluxo antigo de orcamentos e nao foram removidos.

## Arquivos e responsabilidades

- `backend/crud/crud_proposta.py`: consultas, locks, add/flush; sem commit.
- `backend/services/proposta_service.py`: defaults, snapshot, numero, calculos,
  edicao de rascunho e propriedade da transacao, com commit/rollback.
- `backend/routers/propostas.py`: validacao HTTP e traducao de erros.
- `backend/main.py`: registro do router, sem inicializacao de schema.
- `backend/tests/test_proposta_service.py`: persistencia, Decimal, concorrencia e falhas.
- `backend/tests/test_proposta_router.py`: requisicoes ASGI sem rede e contrato HTTP.

Schemas, models, migrations, frontend e autenticacao nao foram alterados.
O contrato descrito em `propostas-contrato-2a.md` foi preservado. Este documento
atualiza especificamente o estado do backend, que agora tem persistencia.

## Endpoints

| Metodo | Caminho | Resultado |
| --- | --- | --- |
| POST | `/orcamentos/{orcamento_id}/proposta` | Cria ou retorna a proposta existente; 200 em ambos os casos. Body vazio ou `{}`. |
| GET | `/propostas/{proposta_id}` | Retorna a proposta completa. |
| GET | `/propostas/orcamento/{orcamento_id}` | Localiza a proposta vinculada; 404 se ausente. |
| PATCH | `/propostas/{proposta_id}` | Edita somente rascunhos, recalcula e retorna a proposta. |

IDs de caminho devem ser positivos. Todos os endpoints usam a dependencia
`get_current_user` existente. Erros: 404 para ausencia; 422 para input/referencia
invalida; 409 para conflitos ou edicao fora de rascunho; 503 para indisponibilidade
de persistencia. Erros de banco nao retornam SQL ou credenciais; log generico
`proposta_database_failed`. Nenhum endpoint de documento/envio/aprovacao foi criado.

## Criacao e concorrencia

O service bloqueia a linha do orcamento via SELECT FOR UPDATE no PostgreSQL.
Depois verifica a proposta existente. Repetir a criacao nao muda numero, versao,
snapshot, itens ou estado, inclusive quando o orcamento foi alterado posteriormente.

A numeracao e `MHS-{orcamento_id:06d}`: usa uma PK ja alocada pelo banco, nao
`max(id)+1`. O numero identifica o vinculo 1:1, nao a ordem de criacao da proposta;
pode conter lacunas e mais de seis digitos. UNIQUE de numero e orcamento_id ja
existem na migration. Nao foi criada uma sequence ou migration adicional.
Propostas existentes mantem seus numeros. Uma colisao com numeracao legada em
outro vinculo gera 409; o service nao renumera registros automaticamente.

UNIQUE e a ultima protecao para escritores que nao usam o lock. Em conflito,
a transacao e revertida e a proposta concorrente do mesmo orcamento e consultada.
Sem proposta desse orcamento, o conflito e retornado sem ocultar o problema.
SQLite nao implementa o lock de linha PostgreSQL; o teste concorrente cobre a
restricao UNIQUE e a recuperacao, nao comprova o comportamento do PostgreSQL.

O snapshot congela cliente e solicitacao usando o schema 2A. O produtor e copiado
quando presente e precisa existir. Sem valor estimado, o primeiro item tem valor
zero, mas o snapshot preserva null. Valor estimado negativo/nao finito impede a
criacao, sem modificar o orcamento. Sao criados um item, condicoes padrao e tres
pagamentos desabilitados, status rascunho e versao 1.

## PATCH e valores

Allowlist inalterada: produtor_id, objeto, descricao, itens, pagamentos, condicoes.
Campos ausentes sao preservados; null explicito somente em produtor_id. Snapshot,
numero, status, timestamps e totais nao sao input. JSON usa nomes publicos no
contrato e mapeamento explicito para as colunas `*_json` na persistencia.

A proposta e bloqueada durante a edicao. Alteracoes efetivas incrementam versao;
repetir o mesmo PATCH persistido nao incrementa novamente. Decimal com
representacao textual diferente pode ser tratado como alteracao do item JSON.
Recalculo tambem pode corrigir totais antigos divergentes. Referencias locais de
PDF e gerada_em sao invalidadas quando ha alteracao, sem gerar/remover arquivos.
Somente rascunho pode ser editado nesta fase; revisao de documento enviado e
transicoes de estado dependem das fases seguintes.

Calculo autoritativo com Decimal, contexto de precisao 64 e ROUND_HALF_UP:
1. Bruto por linha = quantidade * valor_unitario, arredondado em centavos.
2. Desconto absoluto por linha arredondado em centavos e limitado ao bruto.
3. Subtotal = soma dos brutos; desconto = soma dos descontos efetivos;
   total = subtotal - desconto.

O limite de desconto reproduz o piso zero ja usado no editor. O item conserva o
desconto solicitado; os totais mostram o abatimento efetivo. Valores fora da
capacidade de calculo geram 422. Nao ha float nos novos calculos; os valores
Decimal sao serializados em strings dentro do JSON. Preview visual do frontend
ainda nao aplica a politica monetaria do backend: alinhar na Fase B.

## Verificacao local

Em `backend/`, usando o venv:

```sh
python -B -m unittest discover -s tests -p "test_proposta*.py" -v
```

Os testes novos usam settings sinteticos e SQLite temporario com foreign keys
habilitadas. O schema descartavel e preparado pelo bootstrap explicito existente,
nao pelo FastAPI. Requisicoes ASGI exercitam FastAPI sem servidor externo;
rede e envio de e-mail ficam bloqueados. Validam criar, repetir, consultar,
editar, recarregar em outra sessao, snapshot independente, Decimal, PATCH
readonly, produtor, status, rollback, colisao, concorrencia e erros HTTP.
Tambem compilam locks para o dialeto PostgreSQL, sem conectar a ele.

Suite geral: `python -B -m unittest discover -s tests -v`.
O teste publico/admin requer Node e Playwright disponivel por NODE_PATH, com
Edge headless (ou BROWSER_CHANNEL configurado). Nao le .env nem usa banco real.

## Limites e proximas fases

- Sem frontend integrado, PDF, QR, envio, aprovacao ou criacao de producao nesta fase.
- Campos locais do editor (prazo, validade, entrada, prestador, PIX etc.) continuam
  sem contrato persistido. Resolver antes de prometer salvamento completo na Fase B.
- S01/S02 continuam pendentes: a dependencia atual nao valida usuario real/tipo
  access/permissoes. Os endpoints nao devem ser considerados prontos para producao
  enquanto a Fase E nao concluir esses controles.
- Concorrencia e migrations em PostgreSQL descartavel ainda precisam ser testadas
  na Fase I. Nenhuma migration foi executada em banco real nesta fase.
- O service deve receber sessao exclusiva da requisicao, sem gravacoes externas
  pendentes. E dono da transacao; nao deve ser chamado de outra unidade de escrita.
- Edicoes simultaneas sao serializadas por lock; nao ha If-Match/controle otimista
  por versao. Para o mesmo campo, prevalece a ultima escrita confirmada.
- Exclusao de orcamento ainda usa o cascade existente; endpoints legados de envio
  e aprovacao continuam fora deste fluxo. Revisar nas fases D/E, sem remocao antecipada.
- Sem commits, staging ou deploy automaticos. A Fase B requer nova autorizacao.
