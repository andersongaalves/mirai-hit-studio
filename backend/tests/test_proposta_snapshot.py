"""Roadmap 3.0, 5.05: catalog services in proposals and frozen economic snapshots."""
import unittest

import test_bootstrap_database as isolated
from test_proposta_comercial import SETUP as COMMERCIAL_SETUP

SETUP = COMMERCIAL_SETUP + '''
from models import ServicoEtapaModel, ServicoModel
from services import proposta_snapshot_service as snapshots

def seed_service(db, service_id=1, weights=(('Briefing', '0', True), ('Rough Mix', '20', False),
                                            ('Mixagem', '50', False), ('Masterizacao', '30', False))):
    db.add(ServicoModel(id=service_id, nome='Plano Start', subtitulo='', valor_base=1000, categoria='Mix',
                        aplica_desconto=False, parametros='',
                        estrutura_servico='{"intro":"","sections":[],"benefits":[]}'))
    db.flush()
    for ordem, (nome, peso, administrativa) in enumerate(weights, start=1):
        db.add(ServicoEtapaModel(servico_id=service_id, ordem=ordem, nome=nome, descricao='',
                                 peso_percentual=Decimal(peso), prazo_dias=3 if not administrativa else None,
                                 unidade='faixa' if not administrativa else '', revisoes_incluidas=None,
                                 depende_da_anterior=ordem > 2, administrativa=administrativa))
    db.commit()

CATALOG_ITEMS = [
    {'descricao': 'Plano Start', 'quantidade': 1, 'valor_unitario': '1000.00', 'desconto': '200.00', 'servico_id': 1},
    {'descricao': 'Taxa avulsa', 'quantidade': 1, 'valor_unitario': '50.00'},
]
'''


class PropostaSnapshotTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_distribution_is_exact_and_deterministic(self):
        self.run_case('''
assert snapshots.distribuir_centavos(100000, [2000, 5000, 3000]) == [20000, 50000, 30000]
assert snapshots.distribuir_centavos(80000, [2000, 5000, 3000]) == [16000, 40000, 24000]
assert snapshots.distribuir_centavos(1, [3333, 3333, 3334]) == [0, 0, 1]
assert snapshots.distribuir_centavos(100, [0, 3333, 3333, 3334]) == [0, 33, 33, 34]
assert snapshots.distribuir_centavos(1, [5000, 5000]) == [1, 0]
import random
rng = random.Random(505)
for _ in range(2000):
    size = rng.randint(1, 8)
    cuts = sorted(rng.randint(0, 10000) for _ in range(size - 1))
    weights = [b - a for a, b in zip([0] + cuts, cuts + [10000])]
    total = rng.randint(0, 10 ** 8)
    parts = snapshots.distribuir_centavos(total, weights)
    assert sum(parts) == total and all(part >= 0 for part in parts)
    assert all(part == 0 for part, weight in zip(parts, weights) if weight == 0)
for invalid in [(100, [5000, 4999]), (-1, [10000]), (100, [-1, 10001])]:
    try:
        snapshots.distribuir_centavos(*invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(invalid)
''')

    def test_catalog_items_freeze_on_send_and_catalog_edits_never_rewrite(self):
        self.run_case('''
with Session(engine) as db:
    seed_service(db)
    p = service.criar_por_orcamento(db, 1)
    assert p.snapshot_economico is None and p.itens[0].servico_id is None
    assert 'servico_id' not in db.get(PropostaModel, p.id).itens_json[0]
    try:
        service.atualizar(db, p.id, PropostaUpdate(itens=[
            {'descricao': 'X', 'quantidade': 1, 'valor_unitario': '1.00', 'servico_id': 99}]))
    except service.PropostaInvalida as error:
        assert 'catalogo' in str(error)
    else:
        raise AssertionError('unknown catalog service accepted')
    assert service.buscar(db, p.id) == p
    p = service.atualizar(db, p.id, PropostaUpdate(itens=CATALOG_ITEMS))
    assert p.itens[0].servico_id == 1 and p.itens[1].servico_id is None
    assert p.totais.total == Decimal('850.00') and p.snapshot_economico is None

    with patch.object(resend.Emails, 'send', return_value={'id': 'synthetic-message'}):
        sent = commercial.enviar(db, p.id)
    snap = sent.snapshot_economico
    assert snap.origem == 'envio' and snap.moeda == 'BRL' and snap.proposta_versao == sent.versao
    assert (snap.subtotal, snap.desconto, snap.total) == (Decimal('1050.00'), Decimal('200.00'), Decimal('850.00'))
    catalog_line, free_line = snap.itens
    assert catalog_line.servico_nome == 'Plano Start' and catalog_line.preco_catalogo == Decimal('1000.00')
    assert catalog_line.valor_unitario == Decimal('1000.00') and catalog_line.valor_contratado == Decimal('800.00')
    assert [(stage.nome, stage.peso_percentual, stage.valor) for stage in catalog_line.etapas] == [
        ('Briefing', Decimal('0.00'), Decimal('0.00')),
        ('Rough Mix', Decimal('20.00'), Decimal('160.00')),
        ('Mixagem', Decimal('50.00'), Decimal('400.00')),
        ('Masterizacao', Decimal('30.00'), Decimal('240.00')),
    ]
    assert catalog_line.etapas[0].administrativa and catalog_line.etapas[2].depende_da_anterior
    assert free_line.servico_id is None and free_line.etapas == [] and not free_line.catalogo_disponivel
    assert free_line.valor_contratado == Decimal('50.00')
    stored = db.get(PropostaModel, p.id)
    assert stored.snapshot_congelado_em is not None and stored.snapshot_economico['origem'] == 'envio'

    # Catalog edits after sending (price, weights, stage removal) never touch the contract.
    servico = db.get(ServicoModel, 1)
    servico.valor_base = 2000
    servico.etapas[1].peso_percentual = Decimal('40')
    servico.etapas[2].peso_percentual = Decimal('30')
    db.delete(servico.etapas[0])
    db.commit()
    approved = commercial.aprovar(db, p.id)
    assert approved.status == 'aceita' and approved.snapshot_economico == snap
    assert service.buscar(db, p.id).snapshot_economico == snap
    assert snapshots.congelar(db, db.get(PropostaModel, p.id), origem='aceite', estrito=False) is False
''')

    def test_send_is_blocked_when_the_catalog_is_unusable(self):
        self.run_case('''
with Session(engine) as db:
    seed_service(db)
    seed_service(db, 2, weights=(('Unica', '50', False),))
    removed = service.atualizar(db, service.criar_por_orcamento(db, 1).id, PropostaUpdate(itens=CATALOG_ITEMS))
    broken = service.atualizar(db, service.criar_por_orcamento(db, 2).id, PropostaUpdate(itens=[
        {'descricao': 'Servico com pesos invalidos', 'quantidade': 1, 'valor_unitario': '100.00', 'servico_id': 2}]))
    db.delete(db.get(ServicoModel, 1))
    db.commit()
    with patch.object(resend.Emails, 'send', return_value={'id': 'synthetic-message'}) as send:
        for proposal, expected in [(removed, 'removido'), (broken, '100%')]:
            try:
                commercial.enviar(db, proposal.id)
            except service.PropostaConflito as error:
                assert expected in str(error), str(error)
            else:
                raise AssertionError('unusable catalog sent')
            current = service.buscar(db, proposal.id)
            assert current.status == 'rascunho' and current.snapshot_economico is None
        assert send.call_count == 0
    assert db.get(OrcamentoModel, 1).status == 'novo'
''')

    def test_pre_505_sent_proposal_gets_lenient_snapshot_on_acceptance(self):
        self.run_case('''
from datetime import datetime, timezone
with Session(engine) as db:
    seed_service(db)
    p = service.atualizar(db, service.criar_por_orcamento(db, 1).id, PropostaUpdate(itens=CATALOG_ITEMS))
    # Simulates a proposal sent before 5.05: no snapshot, and its service removed since.
    model = db.get(PropostaModel, p.id)
    model.status = 'enviada'
    model.enviada_em = datetime.now(timezone.utc)
    db.get(OrcamentoModel, 1).status = 'proposta_enviada'
    db.delete(db.get(ServicoModel, 1))
    db.commit()
    approved = commercial.aprovar(db, p.id)
    snap = approved.snapshot_economico
    assert approved.status == 'aceita' and snap.origem == 'aceite' and snap.total == Decimal('850.00')
    assert snap.itens[0].servico_id == 1 and not snap.itens[0].catalogo_disponivel and snap.itens[0].etapas == []
''')


if __name__ == "__main__":
    unittest.main()
