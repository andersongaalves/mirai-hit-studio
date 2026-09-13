# Mirai Hit Studio - Commercial Architecture

## 1. Posicionamento

Mirai Hit Studio e uma produtora de audio contemporanea para artistas, criadores e projetos digitais.

**Descritor:** Producao musical e audio para artistas, criadores e projetos digitais.

**Slogan:** Criando o som do futuro.

**Promessa:** Som com identidade. Tecnica com proposito. Entrega pronta para competir no ambiente digital.

A Mirai nao deve ser apresentada como "estudio de rap geek". Geek Music permanece especialidade e assinatura cultural, sem excluir artistas, criadores ou projetos fora do universo geek/anime.

## 2. Verticais

### Artists

Prioridade principal.

**Publicos:** rap, trap, drill, funk, geek music e artistas independentes compativeis.

**Necessidades:** lancar singles, elevar qualidade sonora, construir identidade, manter producao recorrente e obter acabamento profissional.

**Ofertas possiveis:** instrumental/beat, producao musical, vocal production, mixagem, masterizacao, mix + master, producao completa de single e projetos/EP sob orcamento.

Esta e a arquitetura comercial desejada; ela nao afirma que todas as ofertas ja existem no banco.

### Creators

Prioridade de expansao comercial e B2B criativo.

**Publicos:** YouTubers, streamers, influenciadores, canais, marcas e projetos digitais compativeis.

**Ofertas:** tema original, intro/outro, trilha original, sound branding, stingers, pacote de audio e musica para campanha ou conteudo.

Creator nao deve ser combinado automaticamente com Artist: as dores, briefing, entrega e decisor podem ser diferentes.

### Media & Games

Prioridade premium e de crescimento.

**Publicos:** jogos indie, animacao, audiovisual e projetos interativos.

**Ofertas:** soundtrack, loops, stingers, menu music, ambient, sound design e trilha audiovisual.

Essa vertical depende de portfolio especifico. A Mirai nao deve alegar experiencia ou clientes inexistentes; materiais iniciais devem ser identificados como Demo, Concept Project ou Study.

## 3. Verticais, segmentos e especialidades

Vertical organiza a necessidade comercial. Segmento ou especialidade descreve o contexto do cliente ou do projeto. Os dois conceitos nao sao equivalentes.

Verticais canonicas recomendadas:

- `artists`
- `creators`
- `media_games`

Segmentos canonicos iniciais recomendados:

- `rap`, `trap`, `drill`, `funk`, `geek_music`, `pop_indie`
- `youtube`, `streaming`, `content_creator`, `brand`
- `games`, `animation`, `audiovisual`, `other`

Exemplos: `artists` + `trap`; `artists` + `geek_music`; `creators` + `youtube`; `media_games` + `games`.

Esses slugs sao uma convencao comercial, nao enums ou tabelas de banco nesta fase.

## 4. Arquitetura de oferta

Servico e nivel comercial sao conceitos distintos. O mesmo servico pode aparecer em mais de um nivel dependendo do escopo.

| Nivel | Papel | Exemplos conceituais |
|---|---|---|
| `entry` | Servico pontual, menor barreira | mixagem, masterizacao, instrumental simples |
| `launch` | Pacote orientado ao lancamento | beat + mix/master, single completo |
| `premium` | Direcao e acompanhamento maiores | producao completa, vocal production, direcao artistica/sonora |
| `custom` | Escopo dependente de briefing | creators, sound branding, games, soundtrack, EP, audiovisual |

Os niveis nao impõem preco nesta fase.

## 5. Estrategia de preco

Principios:

- Nao competir apenas por preco.
- Preservar servicos de entrada acessiveis.
- Criar caminho para tickets maiores.
- Usar "a partir de" quando fizer sentido.
- Tratar projetos complexos como orcamento personalizado.
- Nao elevar precos automaticamente nesta fase.
- Nao usar benchmarks externos como preco interno inventado.
- Diferenciar preco publicado de preco negociado quando necessario.

Modalidades conceituais:

- `fixed`: preco definido para escopo padronizado.
- `starting_at`: valor inicial, sujeito ao briefing ou opcoes.
- `custom`: valor definido pela proposta apos briefing.

## 6. CTA por tipo de oferta

Servicos simples e padronizados usam "Contratar" ou "Comecar projeto" quando houver checkout compativel.

Servicos que exigem levantamento usam "Solicitar orcamento".

Projetos premium ou custom usam "Falar sobre o projeto" ou texto equivalente.

Esses CTAs sao diretrizes comerciais; nao devem ser implementados nesta fase.

## 7. Jornadas comerciais

**Artist:** entrada -> servico -> portfolio -> briefing -> orcamento/proposta -> pagamento -> producao.

**Creator:** entrada -> solucao -> exemplos -> briefing -> proposta -> pagamento -> execucao.

**Media & Games:** entrada -> capabilities -> demos/cases -> briefing -> contato humano -> proposta custom -> pagamento -> execucao.

## 8. Limites e regras de marca

Evitar: percepcao exclusivamente geek, promessa de sucesso garantido, "garantimos hit", linguagem infantilizada, excesso de jargao gamer, prova social falsa, falso cliente/case, escassez falsa e descontos artificiais.

Priorizar: identidade sonora, acabamento, direcao, processo, clareza, confianca, qualidade percebida e profissionalismo.

## 9. Estado atual e estado desejado

| Conceito | Existe hoje? | Estado desejado | Precisa mudanca tecnica? |
|---|---|---|---|
| Vertical | Nao | `artists`, `creators`, `media_games` | Provavelmente, apos F0.2 |
| Segmento | Nao | Slugs comerciais independentes da vertical | Provavelmente, apos F0.2 |
| Categoria | Sim, livre e usada como `avulso`/`combo` na UI | Manter compatibilidade; separar de vertical/nivel | Sim, se novos conceitos forem persistidos |
| Modalidade de preco | Nao | `fixed`, `starting_at`, `custom` | Provavelmente, apos F0.2 |
| Oferta/pacote | Parcial: servico e categoria, sem entidade propria | Pacotes compostos sem confundir com servico base | Avaliar em F0.2 |
| Servico custom | Parcial: orcamento suporta briefing, sem classificacao comercial | Fluxo custom orientado por briefing/proposta | Pode iniciar sem schema novo |
| CTA | Nao persistido; fluxo atual e orcamento | CTA guiado por tipo de oferta | Pode iniciar no frontend quando G comecar |
| Portfolio/case relacionado | Projeto existe, sem vinculo a servico/vertical | Cases filtraveis e declaracoes verificaveis | Avaliar em F0.2/G.5 |

Hoje, `ServicoModel` possui `nome`, `subtitulo`, `valor_base`, `categoria`, `aplica_desconto`, `parametros` e `estrutura_servico`. A categoria atende ao agrupamento atual da interface e nao deve ser reinterpretada como vertical sem uma migracao planejada.

## 10. Diretriz de evolucao

Nao introduzir tabela por vertical, segmento ou nivel apenas por classificacao. F0.2 deve decidir quais metadados realmente precisam persistir para CRM, proposta, analytics e site; campos ou configuracao leve podem ser suficientes para a primeira etapa. Nenhum framework, CMS, microservico ou reescrita e pressuposto por este documento.
