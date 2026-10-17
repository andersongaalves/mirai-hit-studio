"""Roadmap 5.17: non-stacking, temporal promotions and immutable contract prices."""
import unittest

import test_bootstrap_database as isolated
from test_entrega_final import SETUP as API_SETUP
from test_proposta_snapshot import SETUP as SNAPSHOT_SETUP


class PromocoesTests(unittest.TestCase):
    def test_percentages_dates_and_largest_discount(self):
        isolated.BootstrapTests().run_case(SNAPSHOT_SETUP + '''
from datetime import datetime, timedelta, timezone
from pydantic import ValidationError
from schemas.promocao import Promocao
from services import promocao_service as promotions
now = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)
for data in ({'percentual': '0'}, {'percentual': '100'}, {'percentual': '100.01'}, {'percentual': 'NaN'},
             {'percentual': '10.001'}, {'percentual': '20', 'inicio': '2026-10-17T12:00:00'},
             {'percentual': '20', 'inicio': now, 'fim': now}):
    try:
        Promocao.model_validate(data)
        raise AssertionError('invalid promotion accepted')
    except ValidationError:
        pass
with Session(engine) as db:
    seed_service(db)
    model = db.get(ServicoModel, 1)
    model.aplica_desconto = True
    def set_promotion(**extra):
        model.promocao = Promocao(ativa=True, percentual='20', inicio=now, fim=now + timedelta(hours=1),
                                 **extra).model_dump(mode='json')
    set_promotion()
    assert promotions.preco(model, Decimal('10'), agora=now)['preco_vigente'] == Decimal('800.00')
    assert promotions.preco(model, Decimal('30'), agora=now)['preco_vigente'] == Decimal('700.00')
    assert promotions.preco(model, Decimal('20'), agora=now)['preco_vigente'] == Decimal('800.00')
    assert promotions.preco(model, Decimal('10'), agora=now - timedelta(seconds=1))['preco_vigente'] == Decimal('900.00')
    assert promotions.preco(model, Decimal('10'), agora=now + timedelta(hours=1))['preco_vigente'] == Decimal('900.00')
    model.aplica_desconto = False
    assert promotions.preco(model, Decimal('30'), agora=now)['preco_vigente'] == Decimal('800.00')
    model.promocao['ativa'] = False
    assert promotions.preco(model, Decimal('30'), agora=now)['preco_vigente'] == Decimal('1000.00')
    model.promocao = {'ativa': True, 'percentual': '99.99'}
    assert promotions.preco(model, agora=now)['preco_vigente'] == Decimal('0.10')
    model.valor_base = 10.01
    model.promocao = {'ativa': True, 'percentual': '50'}
    assert promotions.preco(model, agora=now)['preco_vigente'] == Decimal('5.01')
''')

    def test_contract_freezes_price_and_promotion_context(self):
        isolated.BootstrapTests().run_case(SNAPSHOT_SETUP + '''
import copy
from models import PropostaModel
from models.config import ConfigModel
with Session(engine) as db:
    seed_service(db)
    model = db.get(ServicoModel, 1)
    model.aplica_desconto = True
    model.promocao = {'ativa': True, 'percentual': '25', 'inicio': None, 'fim': None}
    db.add(ConfigModel(desconto=10))
    db.commit()
    p = service.atualizar(db, service.criar_por_orcamento(db, 1).id, PropostaUpdate(itens=[
        {'descricao': 'Plano em promocao', 'quantidade': 1, 'valor_unitario': '750.00', 'servico_id': 1}]))
    with patch.object(resend.Emails, 'send', return_value={'id': 'synthetic'}):
        commercial.enviar(db, p.id)
    p = db.get(PropostaModel, p.id)
    original = copy.deepcopy(p.snapshot_economico)
    line = original['itens'][0]
    assert Decimal(original['total']) == Decimal('750.00')
    assert Decimal(line['preco_catalogo_vigente']['preco_vigente']) == Decimal('750.00')
    assert Decimal(line['preco_catalogo_vigente']['desconto_percentual']) == Decimal('25')
    assert sum(Decimal(stage['valor']) for stage in line['etapas']) == Decimal('750.00')
    model.promocao = None
    model.valor_base = 2000
    db.commit()
    assert snapshots.congelar(db, p, origem='aceite', estrito=False) is False
    assert p.snapshot_economico == original
''')

    def test_admin_only_and_older_editors_preserve_promotions(self):
        isolated.BootstrapTests().run_case(API_SETUP + '''
from routers.servicos import router as services_router
from routers.combos import router as combos_router, public_router
app.include_router(services_router)
app.include_router(combos_router)
app.include_router(public_router)
payload = {'nome': 'Plano promocional', 'subtitulo': '', 'valor_base': 100, 'aplica_desconto': True,
           'parametros': '', 'estrutura_servico': '{}', 'promocao': {'ativa': True, 'percentual': '20'}}
assert api.put('/servicos/1', headers=bearer('producer-a'), json=payload).status_code == 403
response = api.put('/servicos/1', headers=ADMIN, json=payload)
assert response.status_code == 200, response.text
assert response.json()['preco_catalogo']['preco_vigente'] == '80.00'
assert api.put('/servicos/1', headers=ADMIN, json={**payload, 'valor_base': 0.01,
    'promocao': {'ativa': True, 'percentual': '90'}}).status_code == 422
payload.pop('promocao')
payload['valor_base'] = 0
assert api.put('/servicos/1', headers=ADMIN, json=payload).status_code == 422
assert api.get('/servicos').json()[0]['valor_base'] == 100
payload['valor_base'] = 100
response = api.put('/servicos/1', headers=ADMIN, json=payload)
assert response.status_code == 200 and response.json()['promocao']['ativa'] is True
with Session(engine) as db:
    seed_service(db, service_id=2)
combo = {'nome': 'Combo promocional', 'preco_base': '500.00', 'servicos': [1, 2],
         'promocao': {'ativa': True, 'percentual': '30'}}
response = api.post('/combos', headers=ADMIN, json=combo)
assert response.status_code == 201, response.text
assert response.json()['preco_catalogo']['preco_vigente'] == '350.00'
combo_id = response.json()['id']
assert api.put(f'/combos/{combo_id}', headers=ADMIN, json={**combo, 'preco_base': '0.01',
    'promocao': {'ativa': True, 'percentual': '90'}}).status_code == 422
combo.pop('promocao')
combo['preco_base'] = '0.00'
assert api.put(f'/combos/{combo_id}', headers=ADMIN, json=combo).status_code == 422
assert api.get('/catalogo/combos').json()[0]['preco_catalogo']['preco_vigente'] == '350.00'
payload['promocao'] = {'ativa': True, 'percentual': '101'}
assert api.put('/servicos/1', headers=ADMIN, json=payload).status_code == 422
payload['promocao'] = None
assert api.put('/servicos/1', headers=ADMIN, json=payload).json()['promocao'] is None
assert api.get('/servicos').json()[0]['promocao'] is None
with Session(engine) as db:
    events = db.query(AuditLogModel).filter_by(action='catalog.promotion_changed', entity_type='service', entity_id='1').all()
    assert len(events) == 2 and all(event.actor_user_id == 6 for event in events)
    assert events[0].metadata_json['new_promotion_percent'] == '20'
    assert events[1].metadata_json['new_promotion_percent'] is None
''')

    def test_additive_migration_roundtrip(self):
        isolated.BootstrapTests().run_case('''
from alembic import command
head = bootstrap(engine)
assert head == 'f1a3c5e7b902'
with engine.begin() as connection:
    connection.exec_driver_sql("INSERT INTO servicos (id, nome, subtitulo, valor_base, estrutura_servico) VALUES (1, 'Sintetico', '', 100, '{}')")
command.downgrade(migration_config(), 'e8a0c2d4f659')
assert 'promocao' not in {c['name'] for c in inspect(engine).get_columns('servicos')}
command.upgrade(migration_config(), head)
for table in ('servicos', 'combos'):
    assert 'promocao' in {c['name'] for c in inspect(engine).get_columns(table)}
with engine.connect() as connection:
    assert connection.exec_driver_sql('SELECT valor_base, promocao FROM servicos WHERE id=1').one() == (100, None)
''')
