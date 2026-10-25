"""Edge-like protection inside the API: scanner probes and request floods (pedido do responsável).

In memory and per instance on purpose: it runs on every request, so it must not touch the
database. Login, budget, newsletter and checkout keep their persistent limits as before.
"""
import os
import re
import threading
import time
from collections import deque

# Paths that only exist on other stacks; asking for them is a probe, not a visit.
VARREDURA = re.compile(
    r"(?:^|/)(?:wp-admin|wp-login|wp-content|wp-includes|xmlrpc\.php|phpmyadmin|pma|\.env|\.git|\.svn|\.aws|"
    r"\.ds_store|server-status|actuator|cgi-bin|vendor/phpunit|boaform|HNAP1|owa)(?:$|[/.?])|\.(?:php|asp|aspx|jsp|cgi)$",
    re.IGNORECASE,
)


def _int_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Protecao:
    def __init__(self, *, limite_minuto=None, varreduras=None, janela_varredura=600, bloqueio=900, max_ips=50000):
        self.limite_minuto = limite_minuto or _int_env("PROTECAO_LIMITE_MINUTO", 900)
        self.varreduras = varreduras or _int_env("PROTECAO_VARREDURAS", 5)
        self.janela_varredura = janela_varredura
        self.bloqueio = bloqueio
        self.max_ips = max_ips
        self._lock = threading.Lock()
        self._minuto = {}
        self._strikes = {}
        self._bloqueados = {}
        self.estatisticas = {"varreduras": 0, "excesso": 0, "bloqueadas": 0, "desde": time.time()}

    def _limpar(self, agora):
        if len(self._minuto) + len(self._strikes) + len(self._bloqueados) < self.max_ips:
            return
        self._minuto = {ip: value for ip, value in self._minuto.items() if value[0] == int(agora // 60)}
        self._strikes = {ip: q for ip, q in self._strikes.items() if q and q[-1] > agora - self.janela_varredura}
        self._bloqueados = {ip: until for ip, until in self._bloqueados.items() if until > agora}

    def avaliar(self, ip, path, agora=None):
        """Returns (decision, retry_after): "ok", "varredura" (404), "excesso" or "bloqueado" (429)."""
        agora = time.time() if agora is None else agora
        with self._lock:
            self._limpar(agora)
            until = self._bloqueados.get(ip)
            if until and until > agora:
                self.estatisticas["bloqueadas"] += 1
                return "bloqueado", int(until - agora) + 1
            if VARREDURA.search(path):
                self.estatisticas["varreduras"] += 1
                strikes = self._strikes.setdefault(ip, deque())
                strikes.append(agora)
                while strikes and strikes[0] <= agora - self.janela_varredura:
                    strikes.popleft()
                if len(strikes) >= self.varreduras:
                    self._bloqueados[ip] = agora + self.bloqueio
                return "varredura", 0
            bucket = int(agora // 60)
            current, count = self._minuto.get(ip, (bucket, 0))
            count = count + 1 if current == bucket else 1
            self._minuto[ip] = (bucket, count)
            if count > self.limite_minuto:
                self.estatisticas["excesso"] += 1
                return "excesso", 60 - int(agora % 60)
            return "ok", 0

    def resumo(self):
        with self._lock:
            agora = time.time()
            return {**self.estatisticas, "ips_bloqueados": sum(1 for until in self._bloqueados.values() if until > agora)}


protecao = Protecao()
