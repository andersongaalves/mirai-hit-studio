import json
from pathlib import Path
import subprocess
import unittest
import test_bootstrap_database as isolated


class PropostaContracts(unittest.TestCase):
    def test_contracts_without_database(self):
        root = Path(__file__).resolve().parents[2]
        fixture = json.loads((root / 'frontend/tests/fixtures/proposta.json').read_text())
        result = subprocess.run(['node', str(root / 'frontend/tests/proposta_contracts.mjs'), '--json'],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        isolated.BootstrapTests().run_case(f'''
            from decimal import Decimal
            from pydantic import ValidationError
            from sqlalchemy.orm import configure_mappers
            from models import PropostaModel
            from schemas.proposta import PropostaCreate, PropostaUpdate, PropostaResponse
            from models.enums.proposta import PropostaStatus
            fixture = {fixture!r}
            with patch.object(engine, 'connect', side_effect=AssertionError('database forbidden')):
                configure_mappers()
                assert PropostaCreate().model_dump() == {{}}
                assert PropostaUpdate().model_dump(exclude_unset=True) == {{}}
                assert PropostaUpdate(produtor_id=None).model_dump(exclude_unset=True) == {{'produtor_id': None}}
                assert PropostaUpdate(descricao='').model_dump(exclude_unset=True) == {{'descricao': ''}}
                valid = PropostaUpdate.model_validate({payload!r})
                assert isinstance(valid.itens[0].valor_unitario, Decimal)
                for field in ['id', 'orcamento_id', 'numero', 'versao', 'status', 'cliente_snapshot',
                              'pdf_path', 'gerada_em', 'enviada_em', 'aprovada_em', 'created_at',
                              'updated_at', 'totais', 'pagamento', 'itens_json']:
                    for schema in [PropostaCreate, PropostaUpdate]:
                        try:
                            schema.model_validate({{field: None}})
                        except ValidationError:
                            pass
                        else:
                            raise AssertionError(field)
                invalid = [{{'objeto': None}}, {{'itens': None}}, {{'objeto': 'x' * 201}},
                           {{'produtor_id': -1}}, {{'produtor_id': True}}, {{'produtor_id': 1.5}}]
                item = {{'descricao': 'Mix', 'quantidade': 1, 'valor_unitario': '150.00'}}
                for field, value in [('quantidade', 0), ('quantidade', -1), ('valor_unitario', -1),
                                     ('valor_unitario', 'NaN'), ('desconto', -1), ('subtotal', 150)]:
                    invalid.append({{'itens': [{{**item, field: value}}]}})
                payment = {{'tipo': 'integral', 'titulo': 'Completo', 'url': '', 'habilitado': False}}
                for url in ['javascript:alert(1)', 'ftp://example.com', 'not-a-url']:
                    invalid.append({{'pagamentos': [{{**payment, 'url': url}}]}})
                invalid.extend([{{'pagamentos': [{{**payment, 'habilitado': True}}]}},
                                {{'pagamentos': [payment, payment]}},
                                {{'pagamentos': [{{**payment, 'tipo': ''}}]}}])
                for data in invalid:
                    try:
                        PropostaUpdate.model_validate(data)
                    except ValidationError:
                        pass
                    else:
                        raise AssertionError(data)
                for url in ['http://example.com', 'https://example.com/pay']:
                    PropostaUpdate(pagamentos=[{{**payment, 'url': url, 'habilitado': True}}])
                response = PropostaResponse.model_validate(fixture)
                assert response.cliente_snapshot.orcamento.id == 42
                assert response.model_dump(mode='json')['itens'][0]['valor_unitario'] == '150.00'
                for status in PropostaStatus:
                    PropostaResponse.model_validate({{**fixture, 'status': status.value}})
                try:
                    PropostaResponse.model_validate({{**fixture, 'status': 'aprovado'}})
                except ValidationError:
                    pass
                else:
                    raise AssertionError('invalid status accepted')
                storage = dict(fixture)
                for public, column in [('itens', 'itens_json'), ('pagamentos', 'pagamentos_json'), ('totais', 'totais_json')]:
                    storage[column] = storage.pop(public)
                model = PropostaModel(**storage)
                assert PropostaResponse.from_orm_model(model) == response
                model.totais_json = {{}}
                assert PropostaResponse.from_orm_model(model).totais is None
        ''')


if __name__ == '__main__':
    unittest.main()
