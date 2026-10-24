# Auditoria setorial - S05 Propostas comerciais

Status do setor: **DIAGNOSTICADO**. Mudancas derivadas: [Etapa 07](../ETAPA_07_APLICACAO_AUDITORIA.md).

## 1. Baseline

| Campo | Valor |
| --- | --- |
| SHA | `18caa5b` (main) |
| Data | 24/10/2026 |
| Ambiente | Leitura estatica; `proposta_editor`, `proposta_catalogo`, `proposta_comercial`, `public_contracting` verdes |
| Limitacoes | `proposta_documento.cjs` depende de layout gerado pelo backend (nao roda isolado) |

## 2. Inventario

- Admin: criar a partir do orcamento, editar (nova versao), enviar, aprovar, PDF, acesso do
  cliente (convite/reenvio/revogacao).
- Cliente: listar, detalhar, baixar PDF, aceitar/recusar por versao, checkout.
- Compra de beat: proposta criada e aceita automaticamente.
- Snapshot economico congelado no envio (5.05); politicas e cotas congeladas.

## 3. Fluxos

Rascunho -> enviada -> aceita (cliente) ou aprovada (Admin) -> cobranca -> producao.
Nova versao invalida aceite de versao anterior (conflito de versao).

## 4. Achados

| ID | Sev. | Categoria | Achado | Status |
| --- | --- | --- | --- | --- |
| AUD6-S05-001 | P2 | 4.7 / 4.12 | Validade de 10 dias consta no PDF, mas aceite e pagamento continuam possiveis indefinidamente com o preco congelado | Aberto (decisao anterior: so texto) |
| AUD6-S05-002 | P3 | 4.8 | Sem comparacao entre versoes nem destaque do que mudou para o cliente | Aberto |
| AUD6-S05-003 | P3 | 4.12 / S12 | `proposta_documento.cjs` nao roda isolado nem no CI | Aberto |

### AUD6-S05-001 - Validade sem efeito (P2)

- Evidencia: `templates/proposta.html` declara "validade de 10 (dez) dias corridos";
  `aceitar_cliente` e o checkout nao verificam data de envio.
- Impacto: proposta antiga com promocao vencida ou preco desatualizado pode ser aceita e
  paga meses depois. Em 15/10 o responsavel decidiu manter a validade so como texto; o
  achado registra o risco para nova decisao.
- Recomendacao (decisao): bloquear aceite apos a validade com status "expirada" e acao
  "reenviar com valores atuais", ou retirar a frase do PDF.

### P3

- **002**: linha do tempo e diff de itens/valores entre versoes.
- **003**: tornar o teste autossuficiente e inclui-lo no CI.

## 5-13. Resumo

- Centralizar: documentos da proposta (PDF, versoes, aceite) na pagina do cliente (S09).
- Tutorial: "Entender proposta, entrada, saldo e quitacao".
- Lacunas de teste: aceite apos validade (se aplicada).
- Dependencias: S06 (checkout), S03 (origem do orcamento), S09.
- Validacao: decisao de 001 registrada e implementada.
