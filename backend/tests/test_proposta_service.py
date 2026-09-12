"""Phase A persistence tests, always in a subprocess with disposable SQLite."""
import unittest
import test_bootstrap_database as isolated

SETUP = '''
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from models import OrcamentoModel, PropostaModel, UsuarioModel, ProducaoModel
from models.enums.proposta import PropostaStatus
from schemas.proposta import PropostaUpdate, PropostaItem
from services import proposta_service as service
from crud import crud_proposta
@event.listens_for(engine, 'connect')
def enable_foreign_keys(connection, record):
    connection.execute('PRAGMA foreign_keys=ON')
bootstrap(engine)
with Session(engine) as db:
    db.add(UsuarioModel(id=1, username='test-admin', password_hash='not-a-real-hash'))
    db.commit()
    for identifier in range(1, 5):
        db.add(OrcamentoModel(id=identifier, nome_cliente='Cliente Teste',
            email='teste@example.com', servico='Mixagem', valor_total=150.25,
            detalhes='Pedido original', link_guia='https://example.com/guia', produtor_id=1))
    db.commit()
'''


class PropostaPersistenceTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_create_edit_snapshot_and_reload(self):
        self.run_case('''
with Session(engine) as db:
    created = service.criar_por_orcamento(db, 1)
    assert created.numero == 'MHS-000001' and created.versao == 1
    assert created.status == PropostaStatus.RASCUNHO
    assert created.produtor_id == 1 and created.totais.total == Decimal('150.25')
    assert len(created.pagamentos) == 3 and not any(p.habilitado for p in created.pagamentos)
    assert service.criar_por_orcamento(db, 1).model_dump() == created.model_dump()
    assert db.scalar(select(func.count()).select_from(PropostaModel)) == 1
    original = db.get(OrcamentoModel, 1)
    original.detalhes = 'Alteracao posterior do orcamento'
    db.commit()
    assert service.criar_por_orcamento(db, 1).cliente_snapshot.orcamento.detalhes == 'Pedido original'
    patch_data = PropostaUpdate(objeto='Novo escopo', descricao='Comercial', produtor_id=None,
        itens=[{'descricao': 'Mix', 'quantidade': '2', 'valor_unitario': '99.90', 'desconto': '10.00'}],
        pagamentos=[{'tipo': 'integral', 'titulo': 'Completo', 'url': 'https://example.com/pay', 'habilitado': True}],
        condicoes='Novas condicoes')
    edited = service.atualizar(db, created.id, patch_data)
    assert edited.totais.model_dump() == {'subtotal': Decimal('199.80'), 'desconto': Decimal('10.00'), 'total': Decimal('189.80')}
    assert edited.numero == created.numero and edited.versao == 2
    assert edited.cliente_snapshot == created.cliente_snapshot
    assert edited.produtor_id is None
    assert service.atualizar(db, created.id, patch_data).versao == 2
    assert service.atualizar(db, created.id, PropostaUpdate()).versao == 2
with Session(engine) as db:
    loaded = service.buscar(db, created.id)
    assert loaded == edited
    assert service.buscar_por_orcamento(db, 1) == loaded
    original = db.get(OrcamentoModel, 1)
    assert original.valor_total == 150.25 and original.produtor_id == 1
    assert original.status == 'novo' and original.detalhes == 'Alteracao posterior do orcamento'
    assert not original.proposta_enviada
    assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 0
    assert db.get(PropostaModel, created.id).itens_json[0]['valor_unitario'] == '99.90'
    empty = service.atualizar(db, created.id, PropostaUpdate(itens=[], pagamentos=[], descricao=''))
    assert empty.totais.total == Decimal('0.00') and empty.versao == 3
''')

    def test_missing_producer_invalid_source_and_status(self):
        self.run_case('''
with Session(engine) as db:
    for action in [lambda: service.criar_por_orcamento(db, 999), lambda: service.buscar(db, 999),
                   lambda: service.buscar_por_orcamento(db, 999),
                   lambda: service.atualizar(db, 999, PropostaUpdate())]:
        try:
            action()
        except service.PropostaNaoEncontrada:
            pass
        else:
            raise AssertionError('missing record accepted')
    created = service.criar_por_orcamento(db, 1)
    try:
        service.atualizar(db, created.id, PropostaUpdate(produtor_id=999, descricao='must rollback'))
    except service.PropostaInvalida:
        pass
    else:
        raise AssertionError('unknown producer accepted')
    assert service.buscar(db, created.id) == created
    for status in PropostaStatus:
        if status == PropostaStatus.RASCUNHO:
            continue
        model = db.get(PropostaModel, created.id)
        model.status = status.value
        db.commit()
        try:
            service.atualizar(db, created.id, PropostaUpdate(descricao='forbidden'))
        except service.PropostaConflito:
            pass
        else:
            raise AssertionError(status)
        assert service.buscar(db, created.id).versao == 1
    budget = db.get(OrcamentoModel, 2)
    budget.valor_total = -5
    db.commit()
    try:
        service.criar_por_orcamento(db, 2)
    except service.PropostaInvalida:
        pass
    else:
        raise AssertionError('negative source accepted')
    assert crud_proposta.buscar_por_orcamento(db, 2) is None
''')

    def test_decimal_rounding_and_no_negative_totals(self):
        self.run_case('''
items = [PropostaItem(descricao='A', quantidade=3, valor_unitario='0.10'),
         PropostaItem(descricao='B', quantidade='0.5', valor_unitario='0.01'),
         PropostaItem(descricao='C', quantidade=1, valor_unitario='10.00', desconto='20.00')]
totals = service.calcular_totais(items)
assert totals.subtotal == Decimal('10.31')
assert totals.desconto == Decimal('10.00') and totals.total == Decimal('0.31')
try:
    service.calcular_totais([PropostaItem(descricao='Too large', quantidade=1, valor_unitario='1e100')])
except service.PropostaInvalida:
    pass
else:
    raise AssertionError('unrepresentable amount accepted')
''')

    def test_atomic_rollback_and_unique_collision(self):
        self.run_case('''
with Session(engine) as db:
    with patch.object(db, 'commit', side_effect=SQLAlchemyError('synthetic failure')):
        try:
            service.criar_por_orcamento(db, 1)
        except SQLAlchemyError:
            pass
        else:
            raise AssertionError('commit failure hidden')
    assert crud_proposta.buscar_por_orcamento(db, 1) is None
    created = service.criar_por_orcamento(db, 1)
    with patch.object(db, 'commit', side_effect=SQLAlchemyError('synthetic failure')):
        try:
            service.atualizar(db, created.id, PropostaUpdate(descricao='must rollback'))
        except SQLAlchemyError:
            pass
    assert service.buscar(db, created.id) == created
    existing = db.get(PropostaModel, created.id)
    existing.numero = 'MHS-000002'
    db.commit()
    try:
        service.criar_por_orcamento(db, 2)
    except service.PropostaConflito:
        pass
    else:
        raise AssertionError('number collision accepted')
    assert crud_proposta.buscar_por_orcamento(db, 2) is None
    assert db.scalar(select(func.count()).select_from(PropostaModel)) == 1
''')

    def test_concurrent_creation_unique_fallback(self):
        self.run_case('''
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, local
barrier = Barrier(4)
thread = local()
original_lookup = crud_proposta.buscar_por_orcamento
def lookup(db, identifier):
    value = original_lookup(db, identifier)
    if not getattr(thread, 'checked', False):
        thread.checked = True
        barrier.wait(timeout=10)
    return value
def create(identifier):
    with Session(engine) as db:
        return service.criar_por_orcamento(db, identifier)
with patch.object(crud_proposta, 'buscar_por_orcamento', side_effect=lookup):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(create, [1, 1, 1, 1]))
assert len({result.id for result in results}) == 1
with ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(create, [2, 3, 4]))
assert len({result.numero for result in results}) == 3
with Session(engine) as db:
    assert db.scalar(select(func.count()).select_from(PropostaModel)) == 4
''')


if __name__ == '__main__':
    unittest.main()
