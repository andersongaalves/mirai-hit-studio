"""Etapa 07, APL-S03-01 (AUD6-S03-001): the public budget price comes from the catalog."""
import unittest

import test_bootstrap_database as isolated

SETUP = r'''
from decimal import Decimal
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from database import get_db
from models import OrcamentoModel
from models.combo import ComboItemModel, ComboModel
from models.config import ConfigModel
from models.servico import ServicoModel
from routers.orcamentos import router
from services import proposta_service
from services.email_service import EmailService
bootstrap(engine)
app = FastAPI()
app.include_router(router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
with Session(engine) as db:
    db.add(ConfigModel(id=1, desconto=10, val_extra_duracao=0.10, val_extra_pessoa=20, val_extra_canal_voz=5,
        val_extra_canal_inst=5, val_extra_melodia=10, val_inst_hibrido=40, val_inst_gravado=100,
        val_lease_desconto=50, val_extra_revisao=30, val_prazo_urgente=40, val_prazo_express=80))
    db.add(ServicoModel(id=12, nome='Trilha custom', valor_base=500, categoria='avulso', aplica_desconto=True,
        parametros='descricao,duracao,guia,prazo'))
    db.add(ServicoModel(id=13, nome='Mix', valor_base=300, categoria='avulso', aplica_desconto=False,
        parametros='canais_voz,inst_aberto,revisoes'))
    db.add(ServicoModel(id=14, nome='Combo legado', valor_base=10, categoria='combo', parametros=''))
    db.flush()
    combo = ComboModel(id=5, nome='Mix + Master', preco_base=Decimal('700.00'), ativo=True, aplica_desconto=False, destaques=[])
    db.add(combo); db.flush()
    db.add(ComboItemModel(combo_id=5, servico_id=13, ordem=1))
    db.add(ComboModel(id=6, nome='Inativo', preco_base=Decimal('1.00'), ativo=False, destaques=[]))
    db.commit()
def post(http, **extra):
    payload = dict(nome_cliente='Visitante', email='lead@example.com', servico='Qualquer', detalhes='Briefing')
    payload.update(extra)
    return http.post('/orcamentos', json=payload)
'''


class OrcamentoPrecoTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_server_recalculates_and_ignores_the_browser_total(self):
        self.run_case(r'''
with TestClient(app) as http, patch.object(EmailService, 'enviar'):
    # (500 + 30 s * 0.10 + urgente 40) * 0.9 = 488.70
    tampered = post(http, valor_total=1, selecao={'servico_id': 12, 'parametros': {'duracao': '210', 'prazo': 'urgente'}})
    assert tampered.status_code == 200, tampered.text
    body = tampered.json()
    assert body['valor_total'] == 488.70 and body['servico'] == 'Trilha custom'
    assert 'Estimativa exibida no site: R$ 1.00' in body['detalhes'] and 'R$ 488.70' in body['detalhes']

    honest = post(http, email='honest@example.com', valor_total=488.7, selecao={'servico_id': 12, 'parametros': {'duracao': 210, 'prazo': 'urgente'}})
    assert honest.json()['valor_total'] == 488.70 and honest.json()['detalhes'] == 'Briefing'

    # (300 + 2 extra voice channels * 5 + 3 stems * 5 + 2 extra revisions * 30) = 385, no discount.
    mix = post(http, email='mix@example.com', valor_total=385, selecao={'servico_id': 13, 'parametros': {
        'canais_voz': '7', 'inst_aberto': 'sim', 'canais_inst': '3', 'revisoes': '3'}})
    assert mix.json()['valor_total'] == 385.0

    combo = post(http, email='combo@example.com', valor_total=700, selecao={'combo_id': 5, 'parametros': {}})
    assert combo.json()['valor_total'] == 700.0 and combo.json()['servico'] == 'Mix + Master'

    # Without a verifiable selection the browser value never becomes a price.
    legacy = post(http, email='legacy@example.com', valor_total=50)
    assert legacy.status_code == 200 and legacy.json()['valor_total'] is None
    assert 'sem seleção verificável: R$ 50.00' in legacy.json()['detalhes']

    for bad in ({'servico_id': 999}, {'servico_id': 14}, {'combo_id': 6},
                {'servico_id': 12, 'parametros': {'duracao': '999999'}},
                {'servico_id': 12, 'parametros': {'prazo': 'ontem'}},
                {'servico_id': 12, 'parametros': {'senha': 'x'}}):
        response = post(http, email='bad@example.com', valor_total=1, selecao=bad)
        assert response.status_code == 422, (bad, response.text)
        assert 'Recarregue a página' in response.json()['detail']
    for malformed in ({'servico_id': 12, 'combo_id': 5}, {}, {'servico_id': '12'}):
        assert post(http, email='bad@example.com', selecao=malformed).status_code == 422

with Session(engine) as db:
    budget = db.query(OrcamentoModel).filter_by(email='lead@example.com').one()
    proposal = proposta_service.criar_por_orcamento(db, budget.id)
    assert proposal.itens[0].valor_unitario == Decimal('488.70')
    legacy = db.query(OrcamentoModel).filter_by(email='legacy@example.com').one()
    assert proposta_service.criar_por_orcamento(db, legacy.id).itens[0].valor_unitario == Decimal('0')
''')

    def test_retry_with_the_same_selection_reuses_the_budget(self):
        self.run_case(r'''
from uuid import uuid4
headers = {'Idempotency-Key': str(uuid4())}
payload = dict(nome_cliente='Visitante', email='retry@example.com', servico='Qualquer', valor_total=450,
               selecao={'servico_id': 12, 'parametros': {'duracao': '180'}})
with TestClient(app) as http, patch.object(EmailService, 'enviar'):
    first = http.post('/orcamentos', json=payload, headers=headers)
    retry = http.post('/orcamentos', json=payload, headers=headers)
    assert first.status_code == retry.status_code == 200, retry.text
    assert first.json()['id'] == retry.json()['id']
    assert 'selecao' not in retry.json()
with Session(engine) as db:
    assert db.query(OrcamentoModel).filter_by(email='retry@example.com').count() == 1
''')


if __name__ == "__main__":
    unittest.main()
