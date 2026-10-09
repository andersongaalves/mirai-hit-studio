# Inventario de componentes - Fase 3.9

## Foundations

| Grupo | Estado atual | Acao Fase 4 |
| --- | --- | --- |
| Cores | tokens no codigo; duas variantes de roxo no Figma | definir paleta canonica e semantica |
| Tipografia | codigo e Figma divergem parcialmente | validar manual e criar estilos por funcao |
| Espacamento | escala 4-64 px no codigo | espelhar como variables |
| Raios | tokens 4/8 px, literais adicionais | reduzir a escala e eliminar excecoes |
| Elevacao | sombras e glow reduzidos | limitar a estados funcionais |
| Grid | layouts responsivos por pagina | definir public, portal e admin grids |
| Motion | transicao rapida e reduced motion | catalogar feedback, nao decoracao |

## Componentes comprovados

| Componente | Variantes necessarias | Onde existe |
| --- | --- | --- |
| Logo | principal, horizontal, lettering, icone, mono, inverse | Figma + assets |
| Header publico | desktop, mobile fechado/aberto, link ativo | codigo; Figma sem Entrar |
| Footer publico | desktop/mobile, links institucionais | codigo; Figma simplificado |
| Botao | primary, outline/quiet, small, loading, disabled | Figma parcial + codigo |
| Campo | text, email, senha, moeda, textarea, erro, disabled | formularios |
| Select | simples, multiplo, busca, inativo legado | Admin/portfolio |
| Status badge | sucesso, aviso, perigo, neutro, processamento | portais/Admin |
| Feedback | loading, vazio, erro, confirmacao, toast | todos ambientes |
| Auth shell | acesso, cadastro, ativacao, recovery, reset | paginas publicas |
| Portal shell | Cliente/Produtor, desktop/mobile | portais |
| Portal nav | dashboard, lista, detalhe, financeiro | portais |
| Metric | valor, rotulo, vazio | portais/Admin |
| Filter bar | busca, status, produtor, periodo, limpar | Admin/portais |
| Data table/list | desktop, mobile row, loading, vazio | Admin/portais |
| File row | material, previa, entrega, comprovante | Admin/portais |
| Upload | idle, progress, validation error, provider error | Admin/portais |
| Audio player | loading, ready, error, comparison A/B | portfolio/portais |
| Proposal summary | enviada, aceita, recusada, expirada | Cliente/Admin |
| Payment summary | integral, entrada, saldo, pending, recusado | checkout/Cliente |
| Checkout method | Pix, cartao, selected, unavailable | checkout |
| Modal/detail | create, edit, read-only, destructive confirm | Admin |
| Sidebar | expanded, compact/mobile, role-scoped | Admin/portais |
| Pagination | default, disabled, loading | Admin |

## Componentes Figma existentes

- `Action / Primary`
- `Action / Quiet`
- logos oficiais e suas variantes
- header da landing como frame, nao como biblioteca completa

## Gaps da biblioteca

1. Inputs e validacao.
2. Navegacao autenticada.
3. Tabelas, filtros e paginacao.
4. Estados financeiros e operacionais.
5. Arquivos, upload e audio.
6. Dialogos e confirmacoes.
7. Empty/loading/error states.
8. Variantes tablet e desktop compacto.

## Regra de implementacao futura

Criar componentes somente quando representarem comportamento existente. Variantes
devem usar tokens e auto-layout; layouts de Admin devem priorizar leitura e acao,
sem cards aninhados ou ornamentacao de landing.
