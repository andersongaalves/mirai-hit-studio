# Backlog da Fase 4

## P0 - antes de desenhar telas

Nenhum P0 visual foi confirmado nesta auditoria.

## P1 - foundations e cobertura

### DS-01 Canonizar marca

Decidir com o manual oficial: ciano, roxo, fundo, neutros e familias tipograficas.

Aceite:
- uma fonte canonica documentada;
- tokens Figma correspondem a `variables.css` ou possuem plano de migracao;
- contraste AA para texto e controles essenciais.

### DS-02 Biblioteca basica

Criar botao, campo, select, badge, feedback, modal, tabela/lista, filtro, sidebar,
arquivo/upload e audio com estados reais.

Aceite:
- auto-layout e variables;
- foco, disabled, loading e erro;
- variantes 390, 768/1024 e 1440 quando estruturais.

### DS-03 Sincronizar navegacao publica

Atualizar header/footer do Figma para incluir `Entrar`, `Area de acesso` e links
atuais sem competir com `Comecar projeto`.

### UX-01 Autenticacao completa

Projetar acesso, cadastro, ativacao, recovery e reset com erro, rate limit, sucesso
e redirecionamento seguro.

### UX-02 Proposta e checkout do Cliente

Projetar lista/detalhe, PDF, aceite/recusa, integral, 50/50, Pix, cartao, pending,
recusado e retorno ao Portal.

## P1 - ambientes operacionais

### UX-03 Portal Cliente

Dashboard, propostas, projetos, detalhe, andamento, financeiro, materiais, previas e
entregas. Priorizar proxima acao e estado real.

### UX-04 Portal Produtor

Dashboard, producoes, detalhe, transicoes permitidas, arquivos e recebimentos.

### UX-05 Admin foundation

Shell, navegacao, filtros, tabelas, detalhe e modais. Validar primeiro em dashboard,
propostas, producoes e financeiro antes de propagar aos demais modulos.

## P2 - jornadas publicas

### UX-06 Landing e verticais

Sincronizar o Figma com o site sem remover a marca central e o espaco negativo.
Preservar clareza, performance e CTA.

### UX-07 Portfolio

Catalogo, filtros, cards, audio e A/B com loading, erro e teclado.

### UX-08 Orcamento

Stepper, selecao de servico, dados, resumo e confirmacao em mobile/desktop.

## P2 - responsividade e acessibilidade

### QA-01 Matriz responsiva

Validar 320, 390, 768, 1024 e 1440 sem overflow, conteudo oculto ou acoes
inacessiveis.

### QA-02 Interacao acessivel

Documentar ordem de foco, Escape, menu, dialogo, mensagens por campo, `aria-live`,
reduced motion, audio por teclado e contraste.

## P3 - acabamento

1. Motion discreto para transicao e feedback.
2. Iconografia consistente.
3. Regras de imagem publica e placeholders.
4. Polimento de microcopy e estados vazios.

## Ordem recomendada

1. DS-01 e DS-02.
2. DS-03 e UX-01.
3. UX-02, UX-03 e UX-04.
4. UX-05 por modulos prioritarios.
5. UX-06, UX-07 e UX-08.
6. QA-01, QA-02 e P3.

Nao iniciar implementacao antes de aprovar foundations e os fluxos P1 no Figma.
