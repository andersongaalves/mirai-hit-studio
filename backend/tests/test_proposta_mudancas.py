"""AUD6-S05-002: version comparison is pure and stable."""
import unittest

from core import proposta_mudancas as m


def proposta(itens, total, **extra):
    return {"versao": 2, "enviada_em": "2026-10-01T12:00:00+00:00", "itens": itens, "totais": {"total": total},
            "objeto": "Single", "descricao": "Uma faixa", "condicoes": "Prazo: 10 dias", "politica_pagamento": "integral",
            **extra}


class PropostaMudancasTests(unittest.TestCase):
    def test_no_previous_version_or_no_change(self):
        atual = proposta([{"descricao": "Mix", "quantidade": "1", "valor_unitario": "500", "desconto": "0"}], "500")
        self.assertIsNone(m.comparar(None, atual))
        self.assertIsNone(m.comparar(m.foto(atual), dict(atual, descricao="Uma  faixa")))  # spacing only

    def test_added_removed_changed_total_and_texts(self):
        antes = proposta([
            {"descricao": "Mixagem", "quantidade": "1", "valor_unitario": "500", "desconto": "0", "servico_id": 3},
            {"descricao": "Master", "quantidade": "1", "valor_unitario": "200", "desconto": "0"},
        ], "700")
        depois = proposta([
            {"descricao": "Mixagem e ajustes", "quantidade": "1", "valor_unitario": "600", "desconto": "50", "servico_id": 3},
            {"descricao": "Beat", "quantidade": "1", "valor_unitario": "300", "desconto": "0", "beat_id": 9, "licenca_beat": "lease"},
        ], "850.00", condicoes="Prazo: 15 dias", versao=3)
        result = m.comparar(m.foto(antes), depois)
        self.assertEqual(result["versao_anterior"], 2)
        self.assertEqual([(i["tipo"], i["descricao"]) for i in result["itens"]],
                         [("alterado", "Mixagem e ajustes"), ("adicionado", "Beat"), ("removido", "Master")])
        self.assertEqual(result["itens"][0]["antes"]["valor_unitario"], "500")
        self.assertEqual(result["itens"][0]["depois"]["desconto"], "50")
        self.assertEqual(result["total"], {"antes": "700", "depois": "850.00"})
        self.assertEqual(result["campos_alterados"], ["condicoes"])

    def test_bad_numbers_do_not_break(self):
        antes = m.foto(proposta([{"descricao": "X", "quantidade": None, "valor_unitario": "abc"}], None))
        self.assertIsNone(m.comparar(antes, proposta([{"descricao": "x", "quantidade": "0", "valor_unitario": "0", "desconto": "0"}], "0")))


if __name__ == "__main__":
    unittest.main()
