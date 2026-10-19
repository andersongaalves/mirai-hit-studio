"""Service rights conserved in disposable databases, never a live financial operation."""
import textwrap
import unittest

import test_bootstrap_database as isolated
from test_carteira_creditos import EXTRA
from test_proposta_snapshot import SETUP

ALLOC = '''
from uuid import uuid4
from models import CreditoAlocacaoModel, CreditoMovimentoModel
from schemas.credito_alocacao import ReservaCreditos, MovimentoCreditos
from services import credito_alocacao_service as allocations
from services import portal_cliente_service

def operation(db, budget_id=2, cliente_id=1):
    budget=db.get(OrcamentoModel,budget_id)
    budget.cliente_id=cliente_id
    production=ProducaoModel(titulo='Uso sintetico',cliente='Cliente sintetico',servico='Mix',
        orcamento_id=budget_id,status='aguardando_inicio')
    db.add(production)
    db.commit()
    return production

def reserve(db, production, lot, quantity='5', key=None):
    return allocations.reservar(db,production.id,ReservaCreditos(lote_id=lot.id,quantidade=quantity,
        motivo='Alocacao sintetica',idempotency_key=key or uuid4()),actor=db.get(UsuarioModel,1))

def move(db, production, item, kind, key=None):
    return allocations.movimentar(db,production.id,item['id'],MovimentoCreditos(tipo=kind,
        motivo='Movimento sintetico',idempotency_key=key or uuid4()),actor=db.get(UsuarioModel,1))
'''


class CreditoAlocacaoTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + EXTRA + ALLOC + textwrap.dedent(source))

    def test_downgrade_preserves_returned_reservations_and_movements(self):
        self.run_case('''
            import importlib
            migration=importlib.import_module('migrations.versions.a1c3e5f7b902_credito_alocacao')
            with Session(engine) as db:
                proposal,charge=contract(db)
                pay(db,charge)
                production=operation(db)
                first=reserve(db,production,db.scalar(select(CreditoLoteModel)))
                move(db,production,first,'devolucao')
            with engine.connect() as connection, patch.object(migration.op,'get_bind',return_value=connection), \\
                 patch.object(migration.op,'drop_table',side_effect=AssertionError('destructive DDL reached')):
                try: migration.downgrade()
                except RuntimeError as error:
                    assert str(error)=='credit_allocation_history_prevents_downgrade'
                else: raise AssertionError('returned allocation history removed')
            with Session(engine) as db:
                assert db.scalar(select(func.count()).select_from(CreditoAlocacaoModel))==1
                assert db.scalar(select(func.count()).select_from(CreditoMovimentoModel))==2
                assert db.scalar(select(func.count()).select_from(PagamentoModel))==1
                assert Decimal(wallet.carteira(db,1)['saldos'][0]['disponivel'])==20
        ''')

    def test_reserve_consume_and_return_preserve_units_and_history(self):
        self.run_case('''
            with Session(engine) as db:
                proposal, charge=contract(db)
                pay(db,charge)
                lot=db.scalar(select(CreditoLoteModel))
                production=operation(db)
                first=reserve(db,production,lot)
                assert first['estado']=='reservada' and first['valor_centavos']==25000
                balance=wallet.carteira(db,1)['saldos'][0]
                assert Decimal(balance['disponivel'])==15 and Decimal(balance['reservado'])==5
                assert portal_cliente_service.entrega_bloqueada(db,production)
                second=reserve(db,production,lot,'3')
                move(db,production,second,'devolucao')
                production.status='em_producao'
                db.commit()
                consumed=move(db,production,first,'consumo')
                assert consumed['estado']=='consumida'
                balance=wallet.carteira(db,1)['saldos'][0]
                assert Decimal(balance['disponivel'])==15 and Decimal(balance['consumido'])==5
                assert not portal_cliente_service.entrega_bloqueada(db,production)
                production.status='finalizado'
                db.commit()
                assert Decimal(wallet.carteira(db,1)['saldos'][0]['disponivel'])==15
                assert db.scalar(select(func.count()).select_from(CreditoMovimentoModel))==4
                assert db.scalar(select(func.count()).select_from(PagamentoModel))==1
        ''')

    def test_replays_conflicts_overallocation_and_authorization(self):
        self.run_case('''
            with Session(engine) as db:
                proposal, charge=contract(db)
                pay(db,charge)
                lot=db.scalar(select(CreditoLoteModel))
                production=operation(db)
                key=uuid4()
                first=reserve(db,production,lot,'15',key)
                assert reserve(db,production,lot,'15.000',key)['id']==first['id']
                for qty,k in [('1',key),('6',uuid4()),('0.5',uuid4())]:
                    try: reserve(db,production,lot,qty,k)
                    except (allocations.AlocacaoConflito,allocations.AlocacaoInvalida): pass
                    else: raise AssertionError('invalid reservation accepted')
                other=operation(db,3,2)
                try: reserve(db,other,lot,'1')
                except allocations.AlocacaoConflito: pass
                else: raise AssertionError('cross-client allocation accepted')
                assert db.scalar(select(func.count()).select_from(CreditoAlocacaoModel))==1
                assert Decimal(wallet.carteira(db,1)['saldos'][0]['disponivel'])==5
                try: service.criar_por_orcamento(db,production.orcamento_id)
                except service.PropostaConflito: pass
                else: raise AssertionError('duplicate economic charge created')
                actor=db.get(UsuarioModel,1)
                actor.is_admin=False
                actor.role='produtor'
                db.commit()
                try: reserve(db,production,lot,'1')
                except allocations.AlocacaoConflito: pass
                else: raise AssertionError('producer moved credits')
        ''')

    def test_refund_holds_units_and_reversal_is_append_only(self):
        self.run_case('''
            with Session(engine) as db:
                proposal, charge=contract(db)
                payment=pay(db,charge)
                lot=db.scalar(select(CreditoLoteModel))
                production=operation(db)
                first=reserve(db,production,lot)
                production.status='em_producao'
                db.commit()
                payment.reconciliation_status='conflict'
                db.commit()
                try: move(db,production,first,'consumo')
                except allocations.AlocacaoConflito: pass
                else: raise AssertionError('held credits consumed')
                assert portal_cliente_service.entrega_bloqueada(db,production)
                payment.reconciliation_status=None
                db.commit()
                key=uuid4()
                move(db,production,first,'consumo',key)
                assert move(db,production,first,'consumo',key)['estado']=='consumida'
                payment.status='reembolsado'
                financial.sincronizar_status(charge)
                production.status='aguardando_inicio'
                db.commit()
                move(db,production,first,'estorno')
                balance=wallet.carteira(db,1)['saldos'][0]
                assert Decimal(balance['disponivel'])==0 and Decimal(balance['bloqueado'])==20
                assert portal_cliente_service.entrega_bloqueada(db,production)
                assert db.scalar(select(func.count()).select_from(CreditoMovimentoModel))==3
                stored=db.scalar(select(CreditoMovimentoModel))
                stored.tipo='consumo'
                try: db.commit()
                except ValueError as error:
                    assert str(error)=='credit_record_is_immutable'
                    db.rollback()
                else: raise AssertionError('movement overwritten')
        ''')

    def test_fractional_hours_conserve_every_cent(self):
        self.run_case('''
            with Session(engine) as db:
                db.get(ServicoModel,1).credito_servico={'unidade':'hora','quantidade':'0.003'}
                db.commit()
                proposal, charge=contract(db,itens=[{'descricao':'Sessao','quantidade':1,'valor_unitario':'0.01','servico_id':1}])
                pay(db,charge,'0.01')
                lot=db.scalar(select(CreditoLoteModel))
                production=operation(db)
                a=reserve(db,production,lot,'0.001')
                b=reserve(db,production,lot,'0.001')
                c=reserve(db,production,lot,'0.001')
                assert [a['valor_centavos'],b['valor_centavos'],c['valor_centavos']]==[0,0,1]
                move(db,production,c,'devolucao')
                d=reserve(db,production,lot,'0.001')
                assert d['valor_centavos']==1
                assert allocations.uso_lote(db,lot.id)['valor_usado']==1
                assert Decimal(wallet.carteira(db,1)['saldos'][0]['disponivel'])==0
        ''')

    def test_failed_ledger_flush_rolls_back_reservation_and_audit(self):
        self.run_case('''
            with Session(engine) as db:
                proposal, charge=contract(db)
                pay(db,charge)
                lot=db.scalar(select(CreditoLoteModel))
                production=operation(db)
                original_flush=db.flush
                def broken_flush(*args,**kwargs):
                    if any(isinstance(row,CreditoMovimentoModel) for row in db.new):
                        raise SQLAlchemyError('synthetic movement failure')
                    return original_flush(*args,**kwargs)
                with patch.object(db,'flush',side_effect=broken_flush):
                    try: reserve(db,production,lot)
                    except SQLAlchemyError: pass
                    else: raise AssertionError('partial allocation committed')
                assert db.scalar(select(func.count()).select_from(CreditoAlocacaoModel))==0
                assert db.scalar(select(func.count()).select_from(CreditoMovimentoModel))==0
                assert Decimal(wallet.carteira(db,1)['saldos'][0]['disponivel'])==20
                assert db.scalar(select(func.count()).select_from(PagamentoModel))==1
        ''')

    def test_existing_contract_work_and_legacy_payout_are_not_repriced(self):
        self.run_case('''
            from services import repasse_produtor_service as payouts
            with Session(engine) as db:
                proposal, charge=contract(db)
                pay(db,charge)
                lot=db.scalar(select(CreditoLoteModel))
                production=operation(db)
                data=allocations.contexto(db,production.id)
                assert data['pode_reservar'] and len(data['lotes'])==1 and data['alocacoes']==[]
                config.settings.COMMERCIAL_PIPELINE_V2_ENABLED=False
                try: reserve(db,production,lot)
                except allocations.AlocacaoConflito: pass
                else: raise AssertionError('credits mutated with V2 off')
                config.settings.COMMERCIAL_PIPELINE_V2_ENABLED=True
                reserve(db,production,lot)
                try: payouts.define(db,production_id=production.id,amount=Decimal('100'),actor=db.get(UsuarioModel,1))
                except payouts.RepasseConflict: db.rollback()
                else: raise AssertionError('duplicate payout origin accepted')
                billed=operation(db,3)
                service.criar_por_orcamento(db,billed.orcamento_id)
                assert not allocations.contexto(db,billed.id)['pode_reservar']
                try: reserve(db,billed,lot)
                except allocations.AlocacaoConflito: pass
                else: raise AssertionError('commercial contract repriced using credits')
                assert db.scalar(select(func.count()).select_from(CreditoAlocacaoModel))==1
        ''')

    def test_creation_reserves_atomically_and_does_not_create_another_charge(self):
        self.run_case('''
            from schemas.credito_alocacao import NovaProducaoCreditos
            with Session(engine) as db:
                proposal, charge=contract(db)
                pay(db,charge)
                lot=db.scalar(select(CreditoLoteModel))
                producer=UsuarioModel(username='synthetic-producer',password_hash='not-a-real-secret',
                    role='produtor',is_admin=False,ativo=True)
                db.add(producer)
                db.commit()
                values={'lote_id':lot.id,'quantidade':'5','motivo':'Uso contratado',
                        'titulo':'Nova faixa','produtor_id':producer.id,'idempotency_key':uuid4()}
                request=NovaProducaoCreditos(**values)
                first=allocations.criar_producao(db,1,request,actor=db.get(UsuarioModel,1))
                second=allocations.criar_producao(db,1,request,actor=db.get(UsuarioModel,1))
                assert first['producao_id']==second['producao_id']
                assert db.scalar(select(func.count()).select_from(ProducaoModel))==1
                assert db.scalar(select(func.count()).select_from(CobrancaModel))==1
                assert db.scalar(select(func.count()).select_from(PropostaModel))==1
                assert db.scalar(select(func.count()).select_from(CreditoMovimentoModel))==1
                assert Decimal(wallet.carteira(db,1)['saldos'][0]['disponivel'])==15
                assert db.get(ProducaoModel,first['producao_id']).produtor_id==producer.id
                try:
                    allocations.criar_producao(db,1,NovaProducaoCreditos(**{**values,'titulo':'Outra faixa'}),actor=db.get(UsuarioModel,1))
                except allocations.AlocacaoConflito: pass
                else: raise AssertionError('idempotency key reused with different title')
                before=db.scalar(select(func.count()).select_from(OrcamentoModel))
                try:
                    allocations.criar_producao(db,1,NovaProducaoCreditos(**{**values,'quantidade':'16',
                        'idempotency_key':uuid4()}),actor=db.get(UsuarioModel,1))
                except allocations.AlocacaoConflito: pass
                else: raise AssertionError('production created without enough credits')
                assert db.scalar(select(func.count()).select_from(OrcamentoModel))==before
                assert db.scalar(select(func.count()).select_from(ProducaoModel))==1
        ''')


if __name__ == '__main__':
    unittest.main()
