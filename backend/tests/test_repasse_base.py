"""Conservation of contractual producer pools, without database or provider access."""
import textwrap
import unittest

import test_bootstrap_database as isolated


class RepasseBaseTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(
            'from services.repasse_base_service import distribuir_pool, parcelas_produtor, reservar_parcela\n'
            + textwrap.dedent(source))

    def test_negotiated_price_and_stage_totals(self):
        self.run_case('''
            assert parcelas_produtor([16000, 40000, 24000]) == [12800, 32000, 19200]
            assert parcelas_produtor([0, 20000, 50000, 30000]) == [0, 16000, 40000, 24000]
        ''')

    def test_splitting_the_same_credit_origin_cannot_mint_payout_cents(self):
        self.run_case('''
            gross, producer, units = 3, parcelas_produtor([3])[0], 3
            pieces = []
            for _ in range(3):
                g, p = reservar_parcela(bruto_restante=gross, produtor_restante=producer,
                                       unidades_restantes=units, unidades=1)
                pieces.append((g, p))
                gross, producer, units = gross-g, producer-p, units-1
            assert sum(p for _, p in pieces) == 2
            assert sum(g for g, _ in pieces) == 3
            assert (gross, producer, units) == (0, 0, 0)
        ''')

    def test_return_restores_the_exact_pools(self):
        self.run_case('''
            gross, producer = reservar_parcela(bruto_restante=101, produtor_restante=81,
                                              unidades_restantes=10000, unidades=3333)
            remaining = (101-gross, 81-producer)
            assert (remaining[0]+gross, remaining[1]+producer) == (101, 81)
            assert reservar_parcela(bruto_restante=remaining[0], produtor_restante=remaining[1],
                                    unidades_restantes=6667, unidades=6667) == remaining
        ''')

    def test_large_deterministic_sample_conserves_every_origin(self):
        self.run_case('''
            import random
            rng = random.Random(513)
            for _ in range(2000):
                bases = [rng.randint(0, 10000) for _ in range(rng.randint(1, 10))]
                pools = parcelas_produtor(bases)
                assert sum(pools) == (sum(bases)*8+5)//10
                assert all(0 <= pool <= gross for pool, gross in zip(pools, bases))
                for gross, pool in zip(bases, pools):
                    split = distribuir_pool(pool, [gross//3, gross//3, gross-2*(gross//3)])
                    assert sum(split) == pool
        ''')

    def test_invalid_pools_fail_closed(self):
        self.run_case('''
            def rejected(operation):
                try: operation()
                except ValueError: return
                raise AssertionError('invalid payout pool accepted')
            for bases in ([-1], [True], [1.0]):
                rejected(lambda: parcelas_produtor(bases))
            for pool, bases in ((2, [1]), (-1, [1]), (True, [2])):
                rejected(lambda: distribuir_pool(pool, bases))
            rejected(lambda: reservar_parcela(bruto_restante=2, produtor_restante=3, unidades_restantes=1, unidades=1))
        ''')
