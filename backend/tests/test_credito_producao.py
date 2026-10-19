"""Frozen operational rules for credit-funded work; disposable DB and no providers."""
import textwrap
import unittest

import test_bootstrap_database as isolated
from test_carteira_creditos import EXTRA
from test_credito_alocacao import ALLOC
from test_proposta_snapshot import SETUP

OPS = '''
from sqlalchemy import delete
from models import (CreditoEtapaModel,ProducaoEtapaModel,ProducaoEtapaAtribuicaoModel,
    ServicoCotaArquivoModel,ServicoPoliticaModel,ProducaoCotaArquivoModel,ProducaoPoliticaModel)
from services import producao_etapa_service as stages, cota_arquivo_service as quotas, politica_service as policies
from crud import crud_producao

def seeded_quota(db):
    db.add(ServicoCotaArquivoModel(servico_id=1,tipo='previa',max_arquivos=2,max_versoes=2,
        max_tamanho_mb=5,max_total_mb=50,formatos=['audio/mpeg']))
    db.add(ServicoPoliticaModel(servico_id=1,dados={'cliente_ve_etapas':False}))
    db.commit()

def list_stages(db,production):
    return stages.listar(db,production,papel='admin',usuario=db.get(UsuarioModel,1))['etapas']
'''


class CreditoProducaoTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + EXTRA + ALLOC + OPS + textwrap.dedent(source))

    def test_reserved_stages_use_frozen_rules_and_exact_economic_parcel(self):
        self.run_case('''
            with Session(engine) as db:
                seeded_quota(db)
                proposal,charge=contract(db)
                pay(db,charge)
                lot=db.scalar(select(CreditoLoteModel))
                production=operation(db)
                # Catalog edits must not rewrite the already purchased operational contract.
                db.scalar(select(ServicoCotaArquivoModel)).max_arquivos=99
                db.get(ServicoPoliticaModel,1).dados={'cliente_ve_etapas':True}
                db.commit()
                first=reserve(db,production,lot,'5')
                rows=db.scalars(select(ProducaoEtapaModel).order_by(ProducaoEtapaModel.ordem)).all()
                assert len(rows)==4
                assert [s.valor for s in rows]==[Decimal('0'),Decimal('50'),Decimal('125'),Decimal('75')]
                assert sum(s.valor for s in rows)==Decimal('250')
                assert all(s.proposta_id==proposal.id for s in rows)
                assert len(db.scalars(select(CreditoEtapaModel)).all())==4
                assert len(db.scalars(select(ProducaoEtapaAtribuicaoModel)).all())==4
                assert all(s['acoes']==[] and s['bloqueio_creditos'] for s in list_stages(db,production))
                assert db.scalar(select(ProducaoCotaArquivoModel)).max_arquivos==2
                assert policies.vigentes(db,production.id)['cliente_ve_etapas'] is False
                reserve(db,production,lot,'5')
                # Two halves of the same plan are grouped before applying the existing ceiling.
                assert db.scalar(select(ProducaoCotaArquivoModel)).max_arquivos==2
                assert len(db.scalars(select(ProducaoEtapaModel)).all())==8
                assert db.scalar(select(func.count()).select_from(PagamentoModel))==1
        ''')

    def test_work_requires_consumption_and_started_work_cannot_be_reversed(self):
        self.run_case('''
            with Session(engine) as db:
                proposal,charge=contract(db)
                payment=pay(db,charge)
                lot=db.scalar(select(CreditoLoteModel))
                production=operation(db)
                allocation=reserve(db,production,lot)
                stage=db.scalar(select(ProducaoEtapaModel).order_by(ProducaoEtapaModel.ordem))
                try:
                    stages.atualizar(db,production,stage.id,papel='admin',usuario=db.get(UsuarioModel,1),
                        status='em_andamento',status_atual='pendente')
                except stages.EtapaConflito: pass
                else: raise AssertionError('unconsumed rights started work')
                production.status='em_producao'
                db.commit()
                move(db,production,allocation,'consumo')
                quotas.verificar(db,production.id,tipo='previa',mime_type='audio/mpeg',tamanho=10,nova_versao=None)
                assert 'em_andamento' in list_stages(db,production)[0]['acoes']
                stages.atualizar(db,production,stage.id,papel='admin',usuario=db.get(UsuarioModel,1),
                    status='em_andamento',status_atual='pendente')
                production.status='aguardando_inicio'
                db.commit()
                try: move(db,production,allocation,'estorno')
                except allocations.AlocacaoConflito: pass
                else: raise AssertionError('executed work reversed without reconciliation')
                payment.reconciliation_status='conflict'
                db.commit()
                assert all(row['acoes']==[] for row in list_stages(db,production))
                assert allocations.listar(db,production.id)[0]['estado']=='consumida'
        ''')

    def test_return_preserves_history_and_removes_stage_only_producer_access(self):
        self.run_case('''
            with Session(engine) as db:
                proposal,charge=contract(db)
                pay(db,charge)
                lot=db.scalar(select(CreditoLoteModel))
                production=operation(db)
                item=reserve(db,production,lot)
                producer=UsuarioModel(username='stage-only',password_hash='synthetic-only',role='produtor',ativo=True,is_admin=False)
                db.add(producer)
                db.flush()
                stage=db.scalar(select(ProducaoEtapaModel))
                stage.responsavel_usuario_id=producer.id
                db.commit()
                assert crud_producao.buscar_por_produtor(db,production.id,producer.id) is not None
                from services import portal_notificacao_service as notices
                from models import PortalNotificacaoModel
                notices.emitir_producao(db,production,'etapa_concluida','credit-before-return',clientes=False,produtores=True)
                db.commit()
                assert db.query(PortalNotificacaoModel).filter_by(usuario_id=producer.id,chave_evento='credit-before-return').count()==1
                move(db,production,item,'devolucao')
                assert list_stages(db,production)==[]
                assert crud_producao.buscar_por_produtor(db,production.id,producer.id) is None
                notices.emitir_producao(db,production,'etapa_concluida','credit-after-return',clientes=False,produtores=True)
                db.commit()
                assert db.query(PortalNotificacaoModel).filter_by(usuario_id=producer.id,chave_evento='credit-after-return').count()==0
                assert db.scalar(select(func.count()).select_from(CreditoEtapaModel))==4
                assert db.scalar(select(func.count()).select_from(ProducaoEtapaModel))==4
                assert db.scalar(select(func.count()).select_from(ProducaoEtapaAtribuicaoModel))==4
                reserve(db,production,lot)
                assert len(list_stages(db,production))==4
                assert db.scalar(select(func.count()).select_from(ProducaoEtapaModel))==8
                mapping=db.scalar(select(CreditoEtapaModel))
                mapping.ordem_no_item=99
                try: db.commit()
                except ValueError: db.rollback()
                else: raise AssertionError('economic stage origin overwritten')
        ''')

    def test_uploads_fail_closed_after_refund_or_complete_return(self):
        self.run_case('''
            with Session(engine) as db:
                proposal,charge=contract(db)
                payment=pay(db,charge)
                lot=db.scalar(select(CreditoLoteModel))
                production=operation(db)
                item=reserve(db,production,lot)
                quotas.verificar(db,production.id,tipo='material',mime_type='audio/mpeg',tamanho=10,nova_versao=None)
                try: quotas.verificar(db,production.id,tipo='previa',mime_type='audio/mpeg',tamanho=10,nova_versao=None)
                except quotas.CotaExcedida: pass
                else: raise AssertionError('work upload accepted before consumption')
                payment.status='reembolsado'
                financial.sincronizar_status(charge)
                db.commit()
                try: quotas.verificar(db,production.id,tipo='previa',mime_type='audio/mpeg',tamanho=10,nova_versao=None)
                except quotas.CotaExcedida: pass
                else: raise AssertionError('refunded credits allowed uploads')
                move(db,production,item,'devolucao')
                try: quotas.verificar(db,production.id,tipo='material',mime_type='audio/mpeg',tamanho=10,nova_versao=None)
                except quotas.CotaExcedida: pass
                else: raise AssertionError('returned credits fell back to historical unlimited uploads')
                legacy=operation(db,3)
                quotas.verificar(db,legacy.id,tipo='material',mime_type='audio/mpeg',tamanho=10,nova_versao=None)
        ''')

    def test_admin_exceptions_survive_contract_reaggregation(self):
        self.run_case('''
            with Session(engine) as db:
                seeded_quota(db)
                proposal,charge=contract(db)
                pay(db,charge)
                lot=db.scalar(select(CreditoLoteModel))
                production=operation(db)
                reserve(db,production,lot)
                quota=db.scalar(select(ProducaoCotaArquivoModel))
                quota.origem,quota.max_arquivos='admin',7
                policy=db.get(ProducaoPoliticaModel,production.id)
                policy.excecao={'cliente_ve_etapas':True}
                policy.motivo='Excecao autorizada na producao'
                db.commit()
                reserve(db,production,lot)
                assert db.scalar(select(ProducaoCotaArquivoModel)).max_arquivos==7
                assert policy.contrato['cliente_ve_etapas'] is False
                assert policies.vigentes(db,production.id)['cliente_ve_etapas'] is True
                assert policy.motivo=='Excecao autorizada na producao'
        ''')

    def test_credit_contract_without_stages_is_not_sold(self):
        self.run_case('''
            with Session(engine) as db:
                db.execute(delete(ServicoEtapaModel))
                db.commit()
                try: contract(db)
                except service.PropostaInvalida: db.rollback()
                else: raise AssertionError('service credits without execution contract were sold')
                assert db.scalar(select(func.count()).select_from(CreditoLoteModel))==0
                assert db.scalar(select(func.count()).select_from(PagamentoModel))==0
                legacy=db.scalar(select(PropostaModel))
                service.atualizar(db,legacy.id,PropostaUpdate(finalidade='producao'))
                with patch.object(resend.Emails,'send',return_value={'id':'synthetic-only'}):
                    sent=commercial.enviar(db,legacy.id)
                assert sent.finalidade=='producao' and sent.status=='enviada'
        ''')

    def test_stage_economic_mismatch_does_not_consume_credits(self):
        self.run_case('''
            with Session(engine) as db:
                proposal,charge=contract(db)
                pay(db,charge)
                lot=db.scalar(select(CreditoLoteModel))
                production=operation(db)
                item=reserve(db,production,lot)
                stage=db.scalar(select(ProducaoEtapaModel).where(ProducaoEtapaModel.valor>0))
                stage.valor=Decimal('999')
                production.status='em_producao'
                db.commit()
                try: move(db,production,item,'consumo')
                except allocations.AlocacaoConflito: pass
                else: raise AssertionError('divergent stage value consumed credits')
                assert allocations.listar(db,production.id)[0]['estado']=='reservada'
                assert db.scalar(select(func.count()).select_from(CreditoMovimentoModel))==1
                assert Decimal(wallet.carteira(db,1)['saldos'][0]['reservado'])==5
        ''')

    def test_stage_creation_failure_rolls_back_new_production_and_reservation(self):
        self.run_case('''
            from schemas.credito_alocacao import NovaProducaoCreditos
            with Session(engine) as db:
                proposal,charge=contract(db)
                pay(db,charge)
                lot=db.scalar(select(CreditoLoteModel))
                producer=UsuarioModel(username='failure-producer',password_hash='synthetic-only',role='produtor',ativo=True,is_admin=False)
                db.add(producer)
                db.commit()
                before=db.scalar(select(func.count()).select_from(OrcamentoModel))
                request=NovaProducaoCreditos(lote_id=lot.id,quantidade='5',produtor_id=producer.id,
                    titulo='Nova faixa',motivo='Reserva sintetica',idempotency_key=uuid4())
                original_flush=db.flush
                def broken_flush(*args,**kwargs):
                    if any(isinstance(row,CreditoEtapaModel) for row in db.new):
                        raise SQLAlchemyError('synthetic stage origin failure')
                    return original_flush(*args,**kwargs)
                with patch.object(db,'flush',side_effect=broken_flush):
                    try: allocations.criar_producao(db,1,request,actor=db.get(UsuarioModel,1))
                    except SQLAlchemyError: pass
                    else: raise AssertionError('partial production contract committed')
                assert db.scalar(select(func.count()).select_from(OrcamentoModel))==before
                assert db.scalar(select(func.count()).select_from(ProducaoModel))==0
                assert db.scalar(select(func.count()).select_from(ProducaoEtapaModel))==0
                assert db.scalar(select(func.count()).select_from(CreditoAlocacaoModel))==0
                assert Decimal(wallet.carteira(db,1)['saldos'][0]['disponivel'])==20
        ''')

    def test_downgrade_refuses_to_remove_existing_credit_stage_history(self):
        self.run_case('''
            import importlib
            with Session(engine) as db:
                proposal,charge=contract(db)
                pay(db,charge)
                production=operation(db)
                reserve(db,production,db.scalar(select(CreditoLoteModel)))
            migration=importlib.import_module('migrations.versions.b3d5f7a9c014_credito_etapas')
            with engine.connect() as connection, patch.object(migration.op,'get_bind',return_value=connection):
                try: migration.downgrade()
                except RuntimeError as error:
                    assert str(error)=='credit_stage_records_prevent_downgrade'
                else: raise AssertionError('credit stage history was removed by downgrade')
            with Session(engine) as db:
                assert db.scalar(select(func.count()).select_from(CreditoEtapaModel))==4
                assert db.scalar(select(func.count()).select_from(CreditoAlocacaoModel))==1
                assert db.scalar(select(func.count()).select_from(PagamentoModel))==1
        ''')


if __name__ == '__main__':
    unittest.main()
