# Auditoria Figma - Fase 3.9

## Resultado

- FASE 3.9: PASS
- Base: `2d83c8047c76614264cee2d4804fbf13a6740fc7`
- Branch: `phase/3.9-figma-audit`
- Figma original: acessivel e nao alterado

A auditoria foi concluida com cobertura integral das telas comprovadas no codigo e
cobertura parcial no Figma. O arquivo de design possui landing desktop/mobile,
acoes basicas e identidade; nao possui Admin, Portais, autenticacao, orcamento ou
checkout. Essa ausencia e um achado de planejamento, nao uma tela presumida.

## Evidencia Figma

Arquivo: `PwJK2S7yBPk97vG5vIrcaR`.

- Pagina `01 - Landing`: frames 1440 e 390, alem de Actions.
- Pagina `03 - Identidade`: logos principal, horizontal, lettering, simbolo, icone
  e monocromatica.
- Componentes de interface: apenas `Action / Primary` e `Action / Quiet`.
- Nao foram encontrados frames dos ambientes autenticados.

Tipografia medida no Figma:

- Landing: Carlito, Manrope, Michroma, Oxanium e Rajdhani.
- Identidade: Manrope e Michroma.
- Codigo: Ethnocentric, Oxanium, Rajdhani e Calibri.

Paleta medida:

- Landing: `#06101F`, `#00D5ED`, `#D430EF` e neutros.
- Identidade: `#06101F`, `#00D5ED`, `#B413F0` e neutros.

A variacao do roxo e a divergencia entre familias tipograficas precisam de uma
decisao canonica na abertura da Fase 4. Nao foram corrigidas nesta auditoria.

## Achados priorizados

### P1 - cobertura Figma incompleta

Admin, Cliente, Produtor, acesso, cadastro, ativacao, recovery, orcamento e checkout
nao possuem telas no arquivo auditado. Isso impede validar hierarquia, estados e
responsividade em uma fonte visual compartilhada antes da implementacao.

Recomendacao: criar foundations e componentes primeiro; entao documentar cada fluxo
em 390, 768/1024 quando estruturalmente relevante, e 1440.

### P1 - fonte visual desatualizada em relacao a navegacao publica

O Figma da landing nao inclui `Entrar`. O header atual inclui a acao secundaria e o
footer inclui `Area de acesso`, alem de uma navegacao institucional mais completa.

Recomendacao: sincronizar os componentes de header/footer na Fase 4 sem remover o
CTA principal `Comecar projeto`.

### P1 - Admin concentra alta densidade em um unico documento

O Admin contem dashboard, servicos, portfolio, configuracoes financeiras,
orcamentos, clientes, producoes, Inbox, usuarios, newsletter, financeiro e
auditoria, com muitos modais no mesmo HTML. A funcionalidade e ampla, mas falta uma
especificacao visual de densidade, estados e navegacao responsiva.

Recomendacao: projetar shell, tabela, filtros, detalhe lateral/modal e estados antes
de redesenhar modulos individuais.

### P2 - tokens visuais parcialmente normalizados

O codigo possui aliases semanticos, escala de espacamento, tipografia e raios. Ainda
existem valores literais de raio 4, 6, 8, 12 e 14 px espalhados, enquanto
`radius-lg` e igual a `radius-md`. Isso dificulta consistencia sem constituir erro
funcional.

Recomendacao: consolidar tokens no Figma e mapear para `variables.css` antes de
alterar componentes.

### P2 - estilos de Cliente dependem semanticamente do Produtor

Os dois portais reutilizam o shell e componentes, o que e positivo, mas classes
`producer-*` tambem nomeiam estruturas do Cliente e telas de autenticacao.

Recomendacao: no redesign, definir componentes neutros (`portal-shell`, `auth-card`,
`metric`, `file-row`) mantendo a implementacao atual ate uma refatoracao autorizada.

### P2 - breakpoints nao possuem paridade Figma

O codigo contempla 390, 600/720/767, 900, 1024 e desktop; o Figma oferece apenas
390 e 1440. Tablet e desktop compacto sao especialmente relevantes para tabelas,
sidebars, filtros e checkout.

Recomendacao: produzir variantes estruturais de 768 e 1024 para componentes densos.

### P2 - estados de produto nao estao catalogados visualmente

O frontend possui loading, vazio, erro, 401/403/404, pending, aprovado, recusado,
revisao, arquivos privados e feedback de formularios. Esses estados nao aparecem
como componentes/variantes no Figma.

Recomendacao: incluir estados e mensagens reais, sem inventar funcoes inexistentes.

## Avaliacao por jornada

### Publica

A landing no Figma tem hierarquia clara, marca forte, CTA unico e boa versao mobile.
O site atual expandiu navegacao, portfolio e acesso. A Fase 4 deve preservar o espaco
negativo da marca, mas sincronizar conteudo e componentes reais.

### Autenticacao

As telas existem e reutilizam um shell funcional. Faltam no Figma estados de
credencial invalida, rate limit, convite, ativacao, recuperacao e proximo destino.

### Cliente

O produto oferece visao geral, propostas, aceite/recusa, PDF, checkout, projetos,
financeiro, arquivos e entregas. A prioridade e reduzir mudancas de contexto entre
proposta, pagamento e projeto sem ocultar estados financeiros.

### Produtor

O produto oferece dashboard, producoes, detalhe, status, arquivos e recebimentos.
A prioridade e apresentar prazo, proxima acao e estado de entrega antes de metricas
decorativas.

### Admin

O Admin e ferramenta operacional: precisa densidade controlada, filtros persistentes,
comparacao, acoes previsiveis e modais com hierarquia curta. Evitar composicao de
landing, cards decorativos e headings superdimensionados.

## Acessibilidade e responsividade

Pontos positivos comprovados: skip link, landmarks, labels, `aria-live`, dialogos,
menu mobile e breakpoints dedicados. A Fase 4 deve especificar foco, teclado,
contraste, reduced motion, erro por campo, estados vazios e overflow de tabelas.

## Limites

- Nao houve alteracao no Figma ou frontend.
- Nao foram inventadas telas ausentes.
- Nao foi feita validacao visual autenticada com dados reais.
- O manual oficial deve decidir a paleta e tipografia canonicas antes das foundations.

## LeanDev

Leitura limitada ao Figma fornecido, rotas HTML, componentes compartilhados, tokens,
CSS de paginas e JS de roteamento. Buscas localizaram estruturas antes das leituras.
Nao houve auditoria de backend, `.codex/lean-dev`, redesign ou refatoracao.
