"""Roadmap 3.0, 5.08: catalog combos and the two-level economic distribution."""
import unittest

import test_bootstrap_database as isolated
from test_proposta_snapshot import SETUP as SNAPSHOT_SETUP

SETUP = SNAPSHOT_SETUP + '''
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from core.security import create_access_token
from database import get_db
from models import ComboModel, ProducaoEtapaModel
from routers.combos import router as combos_router
from routers.servicos import router as servicos_router
from services import producao_etapa_service as stages

def add_service(db, service_id, nome, preco, weights):
    db.add(ServicoModel(id=service_id, nome=nome, subtitulo='', valor_base=preco, categoria='Audio',
                        aplica_desconto=False, parametros='',
                        estrutura_servico='{"intro":"","sections":[],"benefits":[]}'))
    db.flush()
    for ordem, (etapa, peso) in enumerate(weights, start=1):
        db.add(ServicoEtapaModel(servico_id=service_id, ordem=ordem, nome=etapa, descricao='',
                                 peso_percentual=Decimal(peso), prazo_dias=2, unidade='faixa',
                                 revisoes_incluidas=None, depende_da_anterior=ordem > 1, administrativa=False))
    db.commit()

with Session(engine) as db:
    seed_service(db)  # 1: Plano Start, R$ 1000, Briefing 0 / Rough 20 / Mixagem 50 / Masterizacao 30
    add_service(db, 2, 'Master', 500, [('Master final', '100')])
    add_service(db, 3, 'Vocal', 0, [])
    db.add_all([
        UsuarioModel(id=6, username='admin', password_hash='unused', role='admin', is_admin=True, ativo=True),
        UsuarioModel(id=7, username='producer', password_hash='unused', role='produtor', is_admin=False, ativo=True),
    ])
    db.commit()

app = FastAPI()
app.include_router(combos_router)
app.include_router(servicos_router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
api = TestClient(app)
def bearer(username):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': username, 'av': 0})}
ADMIN = bearer('admin')

def create_combo(**body):
    payload = {'nome': 'Combo Mix e Master', 'descricao': 'Mix completo com master', 'preco_base': '1350.00',
               'servicos': [1, 2]}
    payload.update(body)
    return api.post('/combos', headers=ADMIN, json=payload)
'''


class ComboTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_catalog_crud_validation_and_service_guard(self):
        self.run_case('''
created = create_combo()
assert created.status_code == 201, created.text
combo = created.json()
assert combo['preco_base'] == '1350.00' and combo['soma_servicos'] == '1500.00' and combo['ativo'] is True
assert [(item['servico_id'], item['nome'], item['etapas']) for item in combo['servicos']] == [
    (1, 'Plano Start', 4), (2, 'Master', 1)]
for invalid in [{'servicos': [1]}, {'servicos': [1, 1]}, {'servicos': [1, 99]}, {'preco_base': '-1'},
                {'nome': 'x'}, {'extra': True}]:
    assert create_combo(**invalid).status_code == 422, invalid
assert api.get('/combos', headers=bearer('producer')).status_code == 403
assert api.get('/combos').status_code == 401
updated = api.put(f"/combos/{combo['id']}", headers=ADMIN,
                  json={'nome': 'Combo trio', 'preco_base': '1400.00', 'ativo': False, 'servicos': [2, 1, 3]})
assert updated.status_code == 200, updated.text
assert [item['servico_id'] for item in updated.json()['servicos']] == [2, 1, 3]
assert updated.json()['ativo'] is False and updated.json()['nome'] == 'Combo trio'
assert api.put('/combos/999', headers=ADMIN, json={'nome': 'Nada aqui', 'preco_base': '1', 'servicos': [1, 2]}).status_code == 404
# A service inside a combo cannot be deleted.
assert api.delete('/servicos/3', headers=ADMIN).status_code == 409
with Session(engine) as db:
    assert db.get(ServicoModel, 3) is not None
    actions = [event.action for event in db.query(AuditLogModel)]
    assert actions.count('combo.created') == 1 and actions.count('combo.updated') == 1
''')

    def test_two_level_distribution_freezes_and_instantiates_with_origin(self):
        self.run_case('''
combo_id = create_combo().json()['id']
with Session(engine) as db:
    proposal = service.criar_por_orcamento(db, 1)
    try:
        PropostaUpdate(itens=[{'descricao': 'X', 'quantidade': 1, 'valor_unitario': '1', 'servico_id': 1, 'combo_id': combo_id}])
    except ValidationError:
        pass
    else:
        raise AssertionError('service and combo accepted together')
    try:
        service.atualizar(db, proposal.id, PropostaUpdate(itens=[
            {'descricao': 'X', 'quantidade': 1, 'valor_unitario': '1', 'combo_id': 999}]))
    except service.PropostaInvalida as error:
        assert 'Combo' in str(error)
    else:
        raise AssertionError('unknown combo accepted')
    proposal = service.atualizar(db, proposal.id, PropostaUpdate(itens=[
        {'descricao': 'Combo Mix e Master', 'quantidade': 1, 'valor_unitario': '1350.00', 'desconto': '150.00',
         'combo_id': combo_id}]))
    assert proposal.itens[0].combo_id == combo_id and proposal.totais.total == Decimal('1200.00')
    with patch.object(resend.Emails, 'send', return_value={'id': 'combo-message'}):
        sent = commercial.enviar(db, proposal.id)
    line = sent.snapshot_economico.itens[0]
    assert line.combo_nome == 'Combo Mix e Master' and line.preco_catalogo == Decimal('1350.00')
    assert line.valor_contratado == Decimal('1200.00')
    # Level 1: by catalog price (1000 : 500). Level 2: by stage weight inside each service.
    assert [(c.servico_nome, c.preco_catalogo, c.valor_alocado) for c in line.componentes] == [
        ('Plano Start', Decimal('1000.00'), Decimal('800.00')), ('Master', Decimal('500.00'), Decimal('400.00'))]
    assert [(e.servico_nome, e.nome, e.valor, e.componente_indice) for e in line.etapas] == [
        ('Plano Start', 'Briefing', Decimal('0.00'), 1),
        ('Plano Start', 'Rough Mix', Decimal('160.00'), 1),
        ('Plano Start', 'Mixagem', Decimal('400.00'), 1),
        ('Plano Start', 'Masterizacao', Decimal('240.00'), 1),
        ('Master', 'Master final', Decimal('400.00'), 2),
    ]
    assert sum(e.valor for e in line.etapas) == line.valor_contratado
    # Catalog edits after sending never reach the contract.
    edited = api.put(f'/combos/{combo_id}', headers=ADMIN, json={'nome': 'Outro', 'preco_base': '9.00', 'servicos': [2, 3]})
    assert edited.status_code == 200
    approved = commercial.aprovar(db, proposal.id)
    assert approved.snapshot_economico == sent.snapshot_economico
    production = crud_producao.buscar_por_orcamento(db, 1)
    created = stages._etapas(db, production.id)
    assert [(s.servico_id, s.item_descricao, s.nome, s.valor, s.depende_da_anterior) for s in created] == [
        (1, 'Combo Mix e Master — Plano Start', 'Briefing', Decimal('0.00'), False),
        (1, 'Combo Mix e Master — Plano Start', 'Rough Mix', Decimal('160.00'), False),
        (1, 'Combo Mix e Master — Plano Start', 'Mixagem', Decimal('400.00'), True),
        (1, 'Combo Mix e Master — Plano Start', 'Masterizacao', Decimal('240.00'), True),
        (2, 'Combo Mix e Master — Master', 'Master final', Decimal('400.00'), False),
    ]
    assert sum(s.valor for s in created) == Decimal('1200.00')
''')

    def test_rounding_free_components_inactive_and_blocked_send(self):
        self.run_case('''
with Session(engine) as db:
    add_service(db, 4, 'Edicao', 100, [('Edicao', '100')])
    add_service(db, 5, 'Afinacao', 100, [('Afinacao', '100')])
    add_service(db, 6, 'Mixagem', 100, [('Mix', '100')])
even = create_combo(nome='Trio igual', preco_base='300.00', servicos=[4, 5, 6]).json()['id']
free = create_combo(nome='Com gratuito', preco_base='0.00', servicos=[3, 4]).json()['id']
inactive = create_combo(nome='Inativo', ativo=False).json()['id']
with Session(engine) as db:
    # Equal prices and R$ 100,00: the extra cent goes to the first component, sum stays exact.
    p = service.atualizar(db, service.criar_por_orcamento(db, 1).id, PropostaUpdate(itens=[
        {'descricao': 'Trio', 'quantidade': 1, 'valor_unitario': '100.00', 'combo_id': even},
        {'descricao': 'Gratuito', 'quantidade': 1, 'valor_unitario': '50.00', 'combo_id': free}]))
    with patch.object(resend.Emails, 'send', return_value={'id': 'm'}):
        snap = commercial.enviar(db, p.id).snapshot_economico
    assert [c.valor_alocado for c in snap.itens[0].componentes] == [Decimal('33.34'), Decimal('33.33'), Decimal('33.33')]
    assert [e.valor for e in snap.itens[0].etapas] == [Decimal('33.34'), Decimal('33.33'), Decimal('33.33')]
    # A R$ 0 service (no stages) gets no share; the priced one gets the whole value.
    assert [(c.servico_nome, c.valor_alocado) for c in snap.itens[1].componentes] == [
        ('Vocal', Decimal('0.00')), ('Edicao', Decimal('50.00'))]
    assert snap.total == Decimal('150.00')
    try:
        service.atualizar(db, service.criar_por_orcamento(db, 2).id, PropostaUpdate(itens=[
            {'descricao': 'Inativo', 'quantidade': 1, 'valor_unitario': '10.00', 'combo_id': inactive}]))
    except service.PropostaInvalida:
        pass
    else:
        raise AssertionError('inactive combo accepted in a draft')
    # Combo emptied of stages-valid services after the draft: send is blocked.
    blocked = service.atualizar(db, service.criar_por_orcamento(db, 3).id, PropostaUpdate(itens=[
        {'descricao': 'Trio', 'quantidade': 1, 'valor_unitario': '90.00', 'combo_id': even}]))
    db.query(ServicoEtapaModel).filter(ServicoEtapaModel.servico_id == 5).update({'peso_percentual': Decimal('50')})
    db.commit()
    with patch.object(resend.Emails, 'send', return_value={'id': 'm2'}) as send:
        try:
            commercial.enviar(db, blocked.id)
        except service.PropostaConflito as error:
            assert 'Afinacao' in str(error) and '100%' in str(error)
        else:
            raise AssertionError('invalid component weights sent')
        assert send.call_count == 0
''')


if __name__ == "__main__":
    unittest.main()
