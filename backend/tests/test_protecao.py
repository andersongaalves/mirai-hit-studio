"""Scanner probes and request floods are stopped before the routes."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.protecao import VARREDURA, Protecao  # noqa: E402


class ProtecaoTests(unittest.TestCase):
    def test_probe_paths_are_recognised_and_app_paths_are_not(self):
        for path in ("/wp-admin", "/wp-login.php", "/.env", "/.git/config", "/phpmyadmin/index", "/x.php",
                     "/vendor/phpunit/src", "/cgi-bin/luci", "/actuator/health", "/server-status"):
            self.assertTrue(VARREDURA.search(path), path)
        for path in ("/auth/login", "/portal/cliente/producoes", "/admin/notificacoes", "/beats/3/preview",
                     "/checkout/11111111-1111-1111-1111-111111111111/pix", "/environment", "/github"):
            self.assertFalse(VARREDURA.search(path), path)

    def test_repeated_probes_block_the_ip_for_a_while(self):
        guard = Protecao(limite_minuto=100, varreduras=3, janela_varredura=600, bloqueio=900)
        self.assertEqual(guard.avaliar("1.1.1.1", "/wp-admin", agora=1000)[0], "varredura")
        self.assertEqual(guard.avaliar("1.1.1.1", "/.env", agora=1001)[0], "varredura")
        self.assertEqual(guard.avaliar("1.1.1.1", "/servicos", agora=1002)[0], "ok")
        self.assertEqual(guard.avaliar("1.1.1.1", "/x.php", agora=1003)[0], "varredura")
        decision, retry = guard.avaliar("1.1.1.1", "/servicos", agora=1004)
        self.assertEqual(decision, "bloqueado")
        self.assertGreater(retry, 800)
        self.assertEqual(guard.avaliar("2.2.2.2", "/servicos", agora=1004)[0], "ok")
        self.assertEqual(guard.avaliar("1.1.1.1", "/servicos", agora=1904)[0], "ok")
        self.assertEqual(guard.resumo()["varreduras"], 3)

    def test_old_probes_expire_and_floods_are_limited_per_minute(self):
        guard = Protecao(limite_minuto=3, varreduras=2, janela_varredura=60, bloqueio=60)
        guard.avaliar("3.3.3.3", "/.env", agora=0)
        self.assertEqual(guard.avaliar("3.3.3.3", "/.env", agora=120)[0], "varredura")
        self.assertEqual(guard.avaliar("3.3.3.3", "/servicos", agora=121)[0], "ok")
        for _ in range(2):
            self.assertEqual(guard.avaliar("4.4.4.4", "/servicos", agora=180)[0], "ok")
        self.assertEqual(guard.avaliar("4.4.4.4", "/servicos", agora=181)[0], "ok")
        self.assertEqual(guard.avaliar("4.4.4.4", "/servicos", agora=182)[0], "excesso")
        self.assertEqual(guard.avaliar("4.4.4.4", "/servicos", agora=240)[0], "ok")

    def test_memory_stays_bounded(self):
        guard = Protecao(limite_minuto=10, varreduras=5, max_ips=10)
        for index in range(100):
            guard.avaliar(f"10.0.0.{index}", "/servicos", agora=60 * index)
        self.assertLessEqual(len(guard._minuto), 11)


if __name__ == "__main__":
    unittest.main()
