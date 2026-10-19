"""Stage payouts in a disposable database; no live payment or transfer."""
import inspect
import textwrap
import unittest

import test_bootstrap_database as isolated
from test_carteira_creditos import EXTRA
from test_credito_alocacao import ALLOC
from test_proposta_snapshot import SETUP


def preparar_repasse_sintetico(db, *, producer_id, client_id, service_id, actor_id):
    from datetime import datetime, timezone

    from models import OrcamentoModel, ProducaoModel, PropostaModel, UsuarioModel
    from schemas.proposta import PropostaUpdate
    from services import (
        financial_service,
        producao_etapa_service,
        producao_liberacao_service,
        proposta_service,
        proposta_snapshot_service,
    )
    from sqlalchemy import select

    budget = OrcamentoModel(nome_cliente="Sintetico repasse", email="synthetic@example.invalid", servico="Mix", cliente_id=client_id)
    db.add(budget)
    db.commit()
    response = proposta_service.criar_por_orcamento(db, budget.id)
    proposta_service.atualizar(db, response.id, PropostaUpdate(politica_pagamento="integral", produtor_id=producer_id,
        itens=[{"descricao": "Mix", "quantidade": 1, "valor_unitario": "50000000.00", "servico_id": service_id}]))
    model = db.get(PropostaModel, response.id)
    proposta_snapshot_service.congelar(db, model, origem="envio", estrito=True)
    model.status = "aceita"
    model.enviada_em = model.aprovada_em = datetime.now(timezone.utc)
    budget.status = "aprovado"
    db.flush()
    charge = financial_service.criar_para_proposta(db, model, cliente_id=client_id)
    financial_service.registrar_pagamento(db, charge.id, tipo="integral", valor="50000000.00", status="aprovado")
    producao_liberacao_service.avaliar_liberacao_producao(db, charge.id)
    db.commit()
    production = db.scalar(select(ProducaoModel).where(ProducaoModel.orcamento_id == budget.id))
    production.status = "em_producao"
    db.commit()
    stage = producao_etapa_service._etapas(db, production.id)[0]
    for status in ("em_andamento", "concluida"):
        producao_etapa_service.atualizar(db, production, stage.id, papel="admin", usuario=db.get(UsuarioModel, actor_id), status=status)
    production.status = "finalizado"
    db.commit()
    return production.id, stage.id, charge.id


PAYOUTS = inspect.getsource(preparar_repasse_sintetico) + '''
from models import (ProducaoEtapaModel,RepasseEtapaModel,RepasseEtapaPagamentoModel,RepasseProdutorModel)
from schemas.repasse_etapa import RepasseEtapaPagamento
from services import repasse_etapa_service as payouts, producao_etapa_service as stages, repasse_produtor_service as legacy

def producer(db):
    user=UsuarioModel(username='stage-producer',role='produtor',is_admin=False,ativo=True,password_hash='synthetic-only')
    db.add(user)
    db.commit()
    return user

def normal(db,owner,partial=False):
    proposal=service.criar_por_orcamento(db,1)
    service.atualizar(db,proposal.id,PropostaUpdate(finalidade='producao',produtor_id=owner.id,
        politica_pagamento='entrada_50_50' if partial else 'integral',
        itens=[{'descricao':'Plano','quantidade':1,'valor_unitario':'1000.00','servico_id':1}]))
    with patch.object(resend.Emails,'send',return_value={'id':'synthetic-only'}):
        commercial.enviar(db,proposal.id)
    commercial.aprovar(db,proposal.id)
    charge=financial.buscar_por_proposta(db,proposal.id)
    payment=pay(db,charge,'500.00' if partial else '1000.00',kind='entrada' if partial else 'integral')
    return crud_producao.buscar_por_orcamento(db,1),charge,payment

def finish(db,production):
    production.status='em_producao'
    db.commit()
    for row in stages._etapas(db,production.id):
        for status in ('em_andamento','concluida'):
            stages.atualizar(db,production,row.id,papel='admin',usuario=db.get(UsuarioModel,1),status=status)
    production.status='finalizado'
    db.commit()

def rejected(operation):
    try: operation()
    except (payouts.RepasseEtapaConflito,legacy.RepasseError,stages.EtapaConflito,stages.EtapaNaoEncontrada): return
    raise AssertionError('unsafe payout operation accepted')
'''


class RepasseEtapasTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + EXTRA + ALLOC + PAYOUTS + textwrap.dedent(source))

    def test_normal_contract_requires_completion_settlement_and_preserves_executor(self):
        self.run_case('''
            with Session(engine) as db:
                owner=producer(db)
                production,charge,payment=normal(db,owner,partial=True)
                rejected(lambda: payouts.emitir(db,production.id,actor=db.get(UsuarioModel,1)))
                finish(db,production)
                assert {r['estado'] for r in payouts.listar(db,production.id)}=={'bloqueado'}
                rejected(lambda: payouts.emitir(db,production.id,actor=db.get(UsuarioModel,1)))
                pay(db,charge,'500.00',kind='saldo')
                result=payouts.emitir(db,production.id,actor=db.get(UsuarioModel,1))
                records=db.scalars(select(RepasseEtapaModel)).all()
                assert len(records)==3
                assert [r.produtor_centavos for r in records]==[16000,40000,24000]
                assert sum(r.mirai_centavos for r in records)==20000
                assert all(r.produtor_id==owner.id for r in records)
                payouts.emitir(db,production.id,actor=db.get(UsuarioModel,1))
                assert db.scalar(select(func.count()).select_from(RepasseEtapaModel))==3
                rejected(lambda: legacy.define(db,production_id=production.id,amount=Decimal('800'),actor=db.get(UsuarioModel,1)))
                stage=db.get(ProducaoEtapaModel,records[0].etapa_id)
                rejected(lambda: stages.atualizar(db,production,stage.id,papel='admin',usuario=db.get(UsuarioModel,1),status='em_andamento'))
                assert payouts.listar_produtor(db,999)==[]
                assert len(payouts.listar_produtor(db,owner.id))==4
                from alembic import command
                from scripts.bootstrap_database import migration_config
                try: command.downgrade(migration_config(),'b3d5f7a9c014')
                except RuntimeError as error:
                    assert str(error)=='stage_payout_history_prevents_downgrade'
                else: raise AssertionError('issued payout history removed by downgrade')
                assert db.scalar(select(func.count()).select_from(RepasseEtapaModel))==3
        ''')

    def test_postgresql_scenario_arrangement_is_also_executed_locally(self):
        self.run_case('''
            with Session(engine) as db:
                owner=producer(db)
                seed_service(db,2,weights=(('Execucao','100',False),))
                production_id,stage_id,charge_id=preparar_repasse_sintetico(db,
                    producer_id=owner.id,client_id=1,service_id=2,actor_id=1)
                result=payouts.emitir(db,production_id,actor=db.get(UsuarioModel,1))
                assert len(result)==1
                row=result[0]
                assert row['etapa_id']==stage_id
                assert (row['bruto_centavos'],row['produtor_centavos'],row['mirai_centavos'])==(5000000000,4000000000,1000000000)
                assert db.scalar(select(func.count()).select_from(PagamentoModel).where(PagamentoModel.cobranca_id==charge_id))==1
        ''')

    def test_payment_registration_is_immutable_idempotent_and_held_after_refund(self):
        self.run_case('''
            with Session(engine) as db:
                owner=producer(db)
                production,charge,payment=normal(db,owner)
                finish(db,production)
                payouts.emitir(db,production.id,actor=db.get(UsuarioModel,1))
                record=db.scalar(select(RepasseEtapaModel))
                request=RepasseEtapaPagamento(referencia='TRANSFERENCIA-SINTETICA',idempotency_key=uuid4())
                for _ in range(2): payouts.pagar(db,production.id,record.id,request,actor=db.get(UsuarioModel,1))
                assert db.scalar(select(func.count()).select_from(RepasseEtapaPagamentoModel))==1
                rejected(lambda: payouts.pagar(db,999,record.id,request,actor=db.get(UsuarioModel,1)))
                rejected(lambda: payouts.pagar(db,production.id,record.id,
                    RepasseEtapaPagamento(referencia='DIVERGENTE',idempotency_key=uuid4()),actor=db.get(UsuarioModel,1)))
                records=db.scalars(select(RepasseEtapaModel)).all()
                rejected(lambda: payouts.pagar(db,production.id,records[1].id,request,actor=db.get(UsuarioModel,1)))
                payment.status='reembolsado'
                financial.sincronizar_status(charge)
                db.commit()
                rows=payouts.listar_produtor(db,owner.id)
                paid=[r for r in rows if r['estado']=='pago']
                assert len(paid)==1 and paid[0]['bloqueio']
                assert all(r['estado']=='bloqueado' for r in rows if r['id']!=record.id)
                rejected(lambda: payouts.pagar(db,production.id,records[1].id,
                    RepasseEtapaPagamento(referencia='NAO-PAGAR',idempotency_key=uuid4()),actor=db.get(UsuarioModel,1)))
                record.produtor_centavos=1
                try: db.commit()
                except ValueError: db.rollback()
                else: raise AssertionError('issued economic obligation overwritten')
                transfer=db.scalar(select(RepasseEtapaPagamentoModel))
                db.delete(transfer)
                try: db.commit()
                except ValueError: db.rollback()
                else: raise AssertionError('transfer history erased')
        ''')

    def test_credit_splitting_across_productions_conserves_source_80_20(self):
        self.run_case('''
            with Session(engine) as db:
                owner=producer(db)
                db.get(ServicoModel,1).credito_servico={'unidade':'canal','quantidade':'3'}
                db.commit()
                proposal,charge=contract(db,itens=[{'descricao':'Tres unidades','servico_id':1,
                    'quantidade':1,'valor_unitario':'0.03'}])
                pay(db,charge,'0.03')
                lot=db.scalar(select(CreditoLoteModel))
                assert db.scalar(select(func.count()).select_from(RepasseEtapaModel))==0
                allocations_created=[]
                for target in (2,3,4):
                    production=operation(db,target)
                    production.produtor_id=owner.id
                    db.commit()
                    item=reserve(db,production,lot,'1')
                    allocations_created.append(item['id'])
                    production.status='em_producao'
                    db.commit()
                    move(db,production,item,'consumo')
                    finish(db,production)
                    payouts.emitir(db,production.id,actor=db.get(UsuarioModel,1))
                records=db.scalars(select(RepasseEtapaModel)).all()
                assert len(records)==3
                assert sum(r.bruto_centavos for r in records)==3
                assert sum(r.produtor_centavos for r in records)==2
                assert sum(r.mirai_centavos for r in records)==1
                assert sum(db.get(CreditoAlocacaoModel,i).produtor_centavos for i in allocations_created)==2
                assert db.scalar(select(func.count()).select_from(PagamentoModel))==1
        ''')

    def test_return_restores_producer_pool_and_missing_legacy_basis_blocks_consumption(self):
        self.run_case('''
            with Session(engine) as db:
                proposal,charge=contract(db)
                pay(db,charge)
                lot=db.scalar(select(CreditoLoteModel))
                production=operation(db)
                item=reserve(db,production,lot,'5')
                original=db.get(CreditoAlocacaoModel,item['id']).produtor_centavos
                move(db,production,item,'devolucao')
                replacement=reserve(db,production,lot,'5')
                assert db.get(CreditoAlocacaoModel,replacement['id']).produtor_centavos==original
                # Reproduce a pre-5.13 immutable record without mutating real history.
                from sqlalchemy import text
                db.execute(text('UPDATE credito_alocacoes SET produtor_centavos=NULL WHERE id=:id'),{'id':replacement['id']})
                db.commit()
                db.expire_all()
                production.status='em_producao'
                db.commit()
                try: move(db,production,replacement,'consumo')
                except allocations.AlocacaoConflito: pass
                else: raise AssertionError('legacy missing payout basis consumed without reconciliation')
                assert allocations.listar(db,production.id)[1]['estado']=='reservada'
        ''')

    def test_divergent_stage_or_legacy_obligation_fails_closed(self):
        self.run_case('''
            with Session(engine) as db:
                owner=producer(db)
                production,charge,payment=normal(db,owner)
                finish(db,production)
                stage=db.scalar(select(ProducaoEtapaModel).where(ProducaoEtapaModel.valor>0))
                original=stage.valor
                stage.valor=Decimal('999')
                db.commit()
                rejected(lambda: payouts.emitir(db,production.id,actor=db.get(UsuarioModel,1)))
                stage.valor=original
                db.add(RepasseProdutorModel(producao_id=production.id,produtor_id=owner.id,
                    valor_combinado=Decimal('800'),moeda='BRL',status='definido'))
                db.commit()
                rejected(lambda: payouts.emitir(db,production.id,actor=db.get(UsuarioModel,1)))
                assert db.scalar(select(func.count()).select_from(RepasseEtapaModel))==0
        ''')
