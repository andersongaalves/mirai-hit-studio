"""Roadmap 5.16: public cards get a complete estimate, not internal stage data."""
import unittest

import test_bootstrap_database as isolated
from test_proposta_snapshot import SETUP as SNAPSHOT_SETUP


class CatalogoPrazoTests(unittest.TestCase):
    def test_service_and_combo_public_estimates(self):
        isolated.BootstrapTests().run_case(SNAPSHOT_SETUP + '''
from models import ComboItemModel, ComboModel
from routers.servicos import _resposta_servico
from schemas.combo import ComboResponse
from services import catalogo_service, combo_service

with Session(engine) as db:
    seed_service(db)
    seed_service(db, service_id=2)
    first = db.get(ServicoModel, 1)
    second = db.get(ServicoModel, 2)
    assert catalogo_service.prazo_estimado([]) is None
    for stage in first.etapas:
        stage.prazo_dias = 2
    for stage in second.etapas:
        stage.prazo_dias = 1
    public = _resposta_servico(first).model_dump()
    assert public['prazo_estimado_dias'] == 8
    assert not {'etapas', 'cotas_arquivos', 'politicas', 'peso_percentual'} & public.keys()
    combo = ComboModel(nome='Sintético', descricao='', preco_base=100, ativo=True,
                       subtitulo='', aplica_desconto=False, destaques=[])
    db.add(combo)
    db.flush()
    combo.itens = [ComboItemModel(servico_id=1, ordem=1), ComboItemModel(servico_id=2, ordem=2)]
    db.flush()
    response = ComboResponse.model_validate(combo_service.serializar(combo)).model_dump()
    assert response['prazo_estimado_dias'] == 12
    assert all(isinstance(row['etapas'], int) for row in response['servicos'])
    assert all('peso_percentual' not in row for row in response['servicos'])
    first.etapas[0].prazo_dias = None
    assert _resposta_servico(first).prazo_estimado_dias is None
    assert combo_service.serializar(combo)['prazo_estimado_dias'] is None
    first.etapas[0].prazo_dias = 0
    assert _resposta_servico(first).prazo_estimado_dias == 6
''')
