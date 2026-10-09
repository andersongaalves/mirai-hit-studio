# Mapa de navegacao - Fase 3.9

## Publico

```text
Home /
|- Artistas /artists
|- Criadores /creators
|- Media & Games /media-games
|- Portfolio /portfolio
|- Orcamento /orcamento
|- Acesso /acesso
   |- Cadastro /cadastro
   |- Ativacao /ativar
   |- Recuperar senha /recuperar-senha
   `- Redefinir senha /redefinir-senha

Checkout legado /checkout/<referencia-opaca>
Checkout autenticado /checkout?proposta=<id-autorizado>
```

O header conduz a `Entrar` como acao secundaria e preserva `Comecar projeto` como
CTA primario.

## Cliente

```text
/cliente
|- /cliente/propostas
|  `- /cliente/propostas/{id}
|     |- aceitar/recusar
|     |- baixar PDF
|     `- pagamento autorizado
`- /cliente/projetos
   `- /cliente/projetos/{id}
      |- andamento e prazo
      |- financeiro permitido
      `- arquivos/entregas autorizados
```

Identidade e ownership derivam da sessao. Nao desenhar seletores de cliente ou IDs
editaveis.

## Produtor

```text
/produtor
|- /produtor/producoes
|  `- /produtor/producoes/{id}
|     |- status permitido
|     `- arquivos autorizados
`- /produtor/financeiro
   `- recebimento/comprovante autorizado
```

## Admin

```text
/admin
|- Dashboard
|- Servicos
|- Portfolio
|- Configuracoes/custos
|- Orcamentos e propostas
|- Clientes
|- Producoes
|- Inbox IA
|- Financeiro
|- Usuarios
|- Newsletter
`- Auditoria
```

As secoes respeitam permissao; a Fase 4 nao deve mostrar modulos restritos apenas
para desabilita-los visualmente.

## Transicoes criticas

1. Orcamento publico -> Admin -> proposta.
2. Proposta enviada -> convite/login -> proposta autenticada.
3. Aceite -> checkout -> estado financeiro -> Producao.
4. Producao -> Cliente e Produtor com visoes filtradas.
5. Arquivo -> classificacao/visibilidade -> download autorizado.

## Regras UX

- Preservar `next` local seguro apos login/ativacao.
- Voltar de detalhe para a lista correspondente, mantendo filtros quando possivel.
- Diferenciar proposta, pagamento e Producao sem criar estados visuais ficticios.
- Exibir 401/403/404 de forma segura, sem revelar recurso alheio.
