"""Browser payloads checked against real schemas/routes on disposable SQLite."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_bootstrap_database as bootstrap_tests


class PublicAdminContracts(unittest.TestCase):
    def test_browser_payloads_and_backend_roundtrip(self):
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(prefix="mirai-contracts-") as directory:
            output = Path(directory) / "payloads.json"
            result = subprocess.run(
                ["node", str(root / "frontend/tests/flows.cjs")],
                env={**os.environ, "PAYLOAD_OUTPUT": str(output)},
                capture_output=True, text=True, timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payloads = json.loads(output.read_text(encoding="utf-8"))
        bootstrap_tests.BootstrapTests().run_case(f"""
            from sqlalchemy.orm import Session
            from pydantic import ValidationError
            from schemas.orcamento import OrcamentoCreate, OrcamentoResponse
            from schemas.config import ConfigResponse
            from routers.orcamentos import criar_orcamento
            from routers.config import get_config, update_config
            from services.email_service import EmailService
            from models import ConfigModel, OrcamentoModel
            bootstrap(engine)
            with Session(engine) as db, patch.object(EmailService, 'enviar') as send:
                for payload in {payloads!r}:
                    created = criar_orcamento(OrcamentoCreate.model_validate(payload), db)
                    identifier = created.id
                    db.expire_all()
                    saved = db.get(OrcamentoModel, identifier)
                    response = OrcamentoResponse.model_validate(saved)
                    assert response.detalhes == payload['detalhes']
                    assert response.valor_total == payload['valor_total']
                    assert response.servico == payload['servico']
                    if payload['detalhes']:
                        for call in send.call_args_list[-2:]:
                            assert payload['detalhes'] in call.kwargs['html']
                assert send.call_count == 8
                db.add(ConfigModel(id=1))
                db.commit()
                initial = ConfigResponse.model_validate(get_config(db)).model_dump()
                assert initial['desconto'] == 10
                for value in [0, 15, -1, 101]:
                    data = ConfigResponse.model_validate({{**initial, 'desconto': value}})
                    update_config(data, db, user=object())
                    db.expire_all()
                    assert ConfigResponse.model_validate(get_config(db)).desconto == value
                for value in ['', None, float('nan'), float('inf')]:
                    try:
                        ConfigResponse.model_validate({{**initial, 'desconto': value}})
                    except ValidationError:
                        pass
                    else:
                        raise AssertionError('invalid config accepted')
        """)


if __name__ == '__main__':
    unittest.main()
