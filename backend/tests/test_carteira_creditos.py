"""Service credits: real contracts and private ledger, disposable DB, no real payments."""

import textwrap
import unittest

import test_bootstrap_database as isolated
from test_proposta_snapshot import SETUP

EXTRA = '''
from models import ClienteModel, CreditoLoteModel, CreditoLancamentoModel, PagamentoModel
from services import carteira_creditos_service as wallet, financial_service as financial
from services import producao_liberacao_service as release
from schemas.credito_servico import CreditoServico
from pydantic import ValidationError
config.settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
with Session(engine) as db:
    seed_service(db)
    db.get(ServicoModel,1).credito_servico = {'unidade':'canal','quantidade':'10'}
    db.add_all([ClienteModel(id=1,nome='Cliente A'),ClienteModel(id=2,nome='Cliente B')])
    db.flush()
    for budget_id in range(1,5):
        db.get(OrcamentoModel,budget_id).cliente_id = 1
    db.commit()

def contract(db, budget_id=1, **changes):
    proposal = service.criar_por_orcamento(db,budget_id)
    data = {'finalidade':'creditos','politica_pagamento':'integral','itens':[
        {'descricao':'Mix', 'quantidade':2, 'valor_unitario':'500.00','servico_id':1}]}
    data.update(changes)
    proposal = service.atualizar(db,proposal.id,PropostaUpdate(**data))
    with patch.object(resend.Emails,'send',return_value={'id':'synthetic-only'}):
        commercial.enviar(db,proposal.id)
    commercial.aprovar(db,proposal.id)
    return db.get(PropostaModel,proposal.id), financial.buscar_por_proposta(db,proposal.id)

def pay(db, charge, amount='1000.00', status='aprovado', kind='integral'):
    p = financial.registrar_pagamento(db,charge.id,tipo=kind,valor=amount,status=status)
    release.avaliar_liberacao_producao(db,charge.id)
    db.commit()
    return p
'''


class CarteiraCreditosTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + EXTRA + textwrap.dedent(source))

    def test_downgrade_preserves_unpaid_credit_proposal_without_ledger(self):
        self.run_case('''
            import importlib
            migration=importlib.import_module('migrations.versions.f9b1d3e5a780_carteira_creditos')
            with Session(engine) as db:
                proposal=service.criar_por_orcamento(db,1)
                service.atualizar(db,proposal.id,PropostaUpdate(finalidade='creditos'))
            with engine.connect() as connection, patch.object(migration.op,'get_bind',return_value=connection), \\
                 patch.object(migration.op,'drop_table',side_effect=AssertionError('destructive DDL reached')):
                try: migration.downgrade()
                except RuntimeError as error:
                    assert str(error)=='credit_contract_history_prevents_downgrade'
                else: raise AssertionError('unpaid credit proposal removed')
            with Session(engine) as db:
                assert db.get(PropostaModel,proposal.id).finalidade=='creditos'
                assert db.scalar(select(func.count()).select_from(CreditoLoteModel))==0
                assert db.scalar(select(func.count()).select_from(PagamentoModel))==0
        ''')

    def test_downgrade_preserves_settled_credit_acquisition(self):
        self.run_case('''
            import importlib
            migration=importlib.import_module('migrations.versions.f9b1d3e5a780_carteira_creditos')
            with Session(engine) as db:
                proposal,charge=contract(db)
                pay(db,charge)
            with engine.connect() as connection, patch.object(migration.op,'get_bind',return_value=connection), \\
                 patch.object(migration.op,'drop_table',side_effect=AssertionError('destructive DDL reached')):
                try: migration.downgrade()
                except RuntimeError as error:
                    assert str(error)=='credit_acquisition_history_prevents_downgrade'
                else: raise AssertionError('acquisition ledger removed')
            with Session(engine) as db:
                assert db.scalar(select(func.count()).select_from(CreditoLoteModel))==1
                assert db.scalar(select(func.count()).select_from(CreditoLancamentoModel))==1
                assert db.scalar(select(func.count()).select_from(PagamentoModel))==1
                assert wallet.carteira(db,1)['saldos'][0]['disponivel']=='20.000'
        ''')

    def test_settled_acquisition_replays_and_catalog_changes(self):
        self.run_case('''
            with Session(engine) as db:
                proposal, charge = contract(db)
                assert proposal.finalidade == 'creditos'
                assert wallet.carteira(db,1) == {'saldos':[], 'lotes':[]}
                assert proposal.contrato_creditos['itens'][0]['quantidade'] == '20'
                html = documents.preview(db,proposal.id)
                assert '20 canal' in html and 'iniciada ap' not in html
                # Economic and unit terms survive later catalog changes.
                db.get(ServicoModel,1).credito_servico = {'unidade':'hora','quantidade':'3'}
                db.get(ServicoModel,1).valor_base = 2000
                db.commit()
                pay(db,charge)
                for _ in range(3):
                    release.avaliar_liberacao_producao(db,charge.id)
                    db.commit()
                assert db.scalar(select(func.count()).select_from(CreditoLoteModel)) == 1
                assert db.scalar(select(func.count()).select_from(CreditoLancamentoModel)) == 1
                assert db.scalar(select(func.count()).select_from(PagamentoModel)) == 1
                assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 0
                balance = wallet.carteira(db,1)
                assert balance['saldos'][0]['disponivel'] == '20.000'
                assert balance['saldos'][0]['unidade'] == 'canal'
                assert not any('expir' in key for key in balance['lotes'][0])
                assert wallet.carteira(db,2) == {'saldos':[], 'lotes':[]}
                lot = db.scalar(select(CreditoLoteModel))
                assert lot.valor_centavos == 100000
                lot.quantidade = Decimal('999')
                try:
                    db.commit()
                except ValueError as error:
                    assert str(error) == 'credit_record_is_immutable'
                    db.rollback()
                else:
                    raise AssertionError('lot mutated')
        ''')

    def test_partial_pending_reconciliation_and_refund_hold(self):
        self.run_case('''
            with Session(engine) as db:
                proposal, charge = contract(db)
                first = pay(db,charge,'500.00',kind='entrada')
                assert wallet.carteira(db,1)['lotes'] == []
                second = pay(db,charge,'500.00',status='pendente',kind='saldo')
                assert wallet.carteira(db,1)['lotes'] == []
                second.status = 'aprovado'
                second.reconciliation_status = 'required'
                db.commit()
                release.avaliar_liberacao_producao(db,charge.id)
                db.commit()
                assert wallet.carteira(db,1)['lotes'] == []
                second.reconciliation_status = None
                financial.sincronizar_status(charge)
                release.avaliar_liberacao_producao(db,charge.id)
                db.commit()
                assert wallet.carteira(db,1)['saldos'][0]['disponivel'] == '20.000'
                first.reconciliation_status = 'conflict'
                db.commit()
                assert wallet.carteira(db,1)['saldos'][0]['bloqueado'] == '20.000'
                first.reconciliation_status = None
                first.status = 'reembolsado'
                financial.sincronizar_status(charge)
                db.commit()
                assert wallet.carteira(db,1)['saldos'][0]['disponivel'] == '0'
                assert db.scalar(select(func.count()).select_from(CreditoLancamentoModel)) == 1
                assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 0
        ''')

    def test_bad_units_missing_catalog_and_legacy_mode_fail_closed(self):
        self.run_case('''
            for bad in [{'unidade':'dinheiro','quantidade':'1'}, {'unidade':'faixa','quantidade':'1.5'},
                        {'unidade':'hora','quantidade':'NaN'}, {'unidade':'hora','quantidade':'0'},
                        {'unidade':'canal','quantidade':'1','extra':True}]:
                try:
                    CreditoServico.model_validate(bad)
                except ValidationError:
                    pass
                else:
                    raise AssertionError('invalid service credit accepted')
            with Session(engine) as db:
                for identifier, changes in [(1,{'politica_pagamento':'entrada_50_50'}),
                     (2,{'itens':[{'descricao':'Manual','quantidade':1,'valor_unitario':100}]}),
                     (3,{'itens':[{'descricao':'Gratis','quantidade':1,'valor_unitario':0,'servico_id':1}]})]:
                    try:
                        contract(db,identifier,**changes)
                    except service.PropostaInvalida:
                        db.rollback()
                    else:
                        raise AssertionError('invalid credit contract sent')
                proposal, charge = contract(db,4)
                config.settings.COMMERCIAL_PIPELINE_V2_ENABLED = False
                try:
                    commercial.aprovar(db,proposal.id)
                except service.PropostaConflito:
                    pass
                else:
                    raise AssertionError('credit accepted in legacy mode')
                assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 0
                assert db.scalar(select(func.count()).select_from(CreditoLoteModel)) == 0
        ''')

    def test_draft_pdf_freezes_units_and_edit_clears_only_new_contract(self):
        self.run_case('''
            with Session(engine) as db:
                proposal = service.criar_por_orcamento(db,1)
                service.atualizar(db,proposal.id,PropostaUpdate(finalidade='creditos',politica_pagamento='integral',
                    itens=[{'descricao':'Mix','quantidade':1,'valor_unitario':100,'servico_id':1}]))
                preview = documents.preview(db,proposal.id)
                stored = db.get(PropostaModel,proposal.id)
                assert stored.snapshot_economico is None and stored.contrato_creditos is None
                assert '10 canal' in preview
                generated = documents.gerar_documento(db,proposal.id)
                old_pdf = documents.obter_documento(db,proposal.id)[0]
                assert generated.contrato_creditos.itens[0].quantidade == Decimal('10')
                db.get(ServicoModel,1).credito_servico = {'unidade':'canal','quantidade':'12'}
                db.commit()
                assert documents.obter_documento(db,proposal.id)[0] == old_pdf
                updated = service.atualizar(db,proposal.id,PropostaUpdate(descricao='Escopo revisado'))
                assert updated.snapshot_economico is None and updated.contrato_creditos is None
                assert updated.pdf_path is None
                regenerated = documents.gerar_documento(db,proposal.id)
                assert regenerated.contrato_creditos.itens[0].quantidade == Decimal('12')
        ''')

    def test_additive_migration_roundtrip_preserves_legacy_rows(self):
        self.run_case('''
            from alembic import command
            from scripts.bootstrap_database import migration_config
            from sqlalchemy import inspect, text
            with Session(engine) as db:
                proposal = service.criar_por_orcamento(db,1)
                assert proposal.finalidade == 'producao' and proposal.contrato_creditos is None
            command.downgrade(migration_config(), 'e8a0c2d4f679')
            assert 'credito_lotes' not in inspect(engine).get_table_names()
            assert 'finalidade' not in {c['name'] for c in inspect(engine).get_columns('propostas')}
            with engine.connect() as connection:
                assert connection.execute(text('SELECT count(*) FROM propostas')).scalar_one() == 1
                assert connection.execute(text('SELECT count(*) FROM usuarios')).scalar_one() == 1
                assert connection.execute(text('SELECT nome FROM servicos')).scalar_one() == 'Plano Start'
            command.upgrade(migration_config(),'head')
            with engine.connect() as connection:
                assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'e1a3c5d7f9b2'
            with Session(engine) as db:
                old = db.get(PropostaModel,proposal.id)
                assert old.finalidade == 'producao' and old.contrato_creditos is None
                assert db.scalar(select(func.count()).select_from(CreditoLoteModel)) == 0
        ''')

    def test_combo_preserves_component_units_and_economic_origin(self):
        self.run_case('''
            from models import ComboModel, ComboItemModel
            with Session(engine) as db:
                seed_service(db,service_id=2)
                second = db.get(ServicoModel,2)
                second.nome, second.valor_base = 'Master', 500
                second.credito_servico = {'unidade':'faixa','quantidade':'1'}
                combo = ComboModel(nome='Mix e master',preco_base=1500,
                    itens=[ComboItemModel(servico_id=1,ordem=1),ComboItemModel(servico_id=2,ordem=2)])
                db.add(combo)
                db.commit()
                proposal, charge = contract(db,itens=[{'descricao':'Combo','quantidade':2,'valor_unitario':'500',
                                                     'combo_id':combo.id}])
                pay(db,charge)
                lots = db.scalars(select(CreditoLoteModel).order_by(CreditoLoteModel.componente)).all()
                assert len(lots) == 2
                assert [(l.unidade,l.quantidade) for l in lots] == [('canal',Decimal('20')),('faixa',Decimal('2'))]
                assert [l.valor_centavos for l in lots] == [66667,33333]
                assert sum(l.valor_centavos for l in lots) == 100000
                assert db.scalar(select(func.count()).select_from(PagamentoModel)) == 1
                assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 0
        ''')

    def test_frozen_owner_cannot_be_reassigned_and_acquisition_rolls_back(self):
        self.run_case('''
            from models import CreditoContratoItemModel
            with Session(engine) as db:
                proposal, charge = contract(db)
                before = db.scalar(select(CreditoContratoItemModel))
                assert before.cliente_id == 1
                # Frozen ownership is independent of mutable budget associations.
                db.get(OrcamentoModel,proposal.orcamento_id).cliente_id = 2
                charge.cliente_id = 2
                db.commit()
                try:
                    pay(db,charge)
                except financial.FinanceiroConflito:
                    db.rollback()
                else:
                    raise AssertionError('credits transferred across clients')
                assert db.scalar(select(func.count()).select_from(PagamentoModel)) == 0
                assert db.scalar(select(func.count()).select_from(CreditoLoteModel)) == 0
                db.get(OrcamentoModel,proposal.orcamento_id).cliente_id = 1
                charge.cliente_id = 1
                db.commit()
                # Grant and the financial confirmation share the caller transaction.
                original_flush = db.flush
                def failing_flush(*args, **kwargs):
                    if any(isinstance(row,CreditoLancamentoModel) for row in db.new):
                        raise SQLAlchemyError('synthetic ledger failure')
                    return original_flush(*args, **kwargs)
                with patch.object(db,'flush',side_effect=failing_flush):
                    try:
                        pay(db,charge)
                    except SQLAlchemyError:
                        db.rollback()
                    else:
                        raise AssertionError('partial financial commit accepted')
                assert db.scalar(select(func.count()).select_from(CreditoLoteModel)) == 0
                assert db.scalar(select(func.count()).select_from(PagamentoModel)) == 0
                pay(db,charge)
                assert db.scalar(select(func.count()).select_from(CreditoLoteModel)) == 1
        ''')

    def test_zero_value_component_is_preserved_and_financial_mismatch_is_held(self):
        self.run_case('''
            from models import ComboModel, ComboItemModel
            with Session(engine) as db:
                seed_service(db,service_id=2)
                second = db.get(ServicoModel,2)
                second.nome, second.valor_base = 'Bonus', 0
                second.credito_servico = {'unidade':'faixa','quantidade':'1'}
                combo = ComboModel(nome='Mix e bonus',preco_base=1000,
                    itens=[ComboItemModel(servico_id=1,ordem=1),ComboItemModel(servico_id=2,ordem=2)])
                db.add(combo)
                db.commit()
                proposal, charge = contract(db,itens=[{'descricao':'Combo','quantidade':1,'valor_unitario':'1000',
                                                     'combo_id':combo.id}])
                charge.moeda = 'USD'
                assert wallet.financiamento_valido(charge) is False
                db.rollback()
                assert db.scalar(select(func.count()).select_from(CreditoLoteModel)) == 0
                payment = pay(db,charge)
                charge.valor_total = Decimal('999')
                try:
                    with db.no_autoflush:
                        wallet.creditar_cobranca_bloqueada(db,charge)
                except financial.FinanceiroConflito:
                    db.rollback()
                else:
                    raise AssertionError('charge identity mismatch accepted')
                assert db.scalar(select(func.count()).select_from(CreditoLoteModel)) == 2
                charge.valor_total = Decimal('1000')
                release.avaliar_liberacao_producao(db,charge.id)
                db.commit()
                lots = db.scalars(select(CreditoLoteModel).order_by(CreditoLoteModel.componente)).all()
                assert [(l.valor_centavos,l.unidade) for l in lots] == [(100000,'canal'),(0,'faixa')]
                payment.reconciliation_status = 'conflict'
                db.commit()
                assert all(s['disponivel'] == '0' for s in wallet.carteira(db,1)['saldos'])
                assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 0
        ''')


if __name__ == "__main__":
    unittest.main()
