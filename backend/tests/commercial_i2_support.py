"""Transport-only fakes and loopback HTTP server for commercial I.2 tests."""
from contextlib import contextmanager
from copy import deepcopy
from functools import partial
import hashlib
import hmac
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import socket
from threading import Thread
import time
from uuid import uuid4

import requests
import uvicorn


class FakeResponse:
    def __init__(self, data, status=200):
        self.status_code, self.data, self.headers = status, data, {}

    def json(self):
        return deepcopy(self.data)


class PaymentTransport:
    """Run the real MercadoPago adapter, replacing only its HTTP session."""
    def __init__(self):
        self.orders = {}
        self.keys = {}
        self.calls = []
        self.next_status = 'action_required'
        self.timeout_next = False

    def request(self, method, url, **kwargs):
        assert url.startswith('https://api.mercadopago.com/v1/orders')
        self.calls.append(method)
        if method == 'GET':
            return FakeResponse(self.orders[url.rsplit('/', 1)[-1]])
        assert method == 'POST'
        data = kwargs['json']
        key = kwargs['headers']['X-Idempotency-Key']
        if key in self.keys:
            return FakeResponse(self.orders[self.keys[key]], 201)
        payment = data['transactions']['payments'][0]
        method_data = payment['payment_method']
        assert 'card_number' not in method_data and 'security_code' not in method_data
        is_pix = method_data['id'] == 'pix'
        method_data = {k: method_data[k] for k in ('id', 'type')}
        if is_pix:
            method_data.update(qr_code='I2-SYNTHETIC-NOT-PAYABLE',
                               ticket_url='https://www.mercadopago.com.br/payments/i2-test')
        elif self.next_status == 'action_required':
            method_data['transaction_security'] = {'url': 'https://www.mercadopago.com.br/auth/challenge'}
        identifier = 'I2-' + uuid4().hex
        status = self.next_status
        detail = 'waiting_transfer' if is_pix else 'pending_challenge'
        if status == 'processed':
            detail = 'accredited'
        order = dict(id=identifier, external_reference=data['external_reference'],
                     currency='BRL', total_amount=data['total_amount'], status=status,
                     status_detail=detail, transactions={'payments': [{
                         'id': 'PAY-' + identifier, 'amount': payment['amount'],
                         'status': status, 'status_detail': detail, 'payment_method': method_data}]})
        self.orders[identifier] = order
        self.keys[key] = identifier
        if self.timeout_next:
            self.timeout_next = False
            raise requests.Timeout('synthetic timeout')
        return FakeResponse(order, 201)

    def change(self, identifier, status, detail='accredited'):
        order = self.orders[identifier]
        order.update(status=status, status_detail=detail)
        order['transactions']['payments'][0].update(status=status, status_detail=detail)


def signed_webhook(http, identifier, secret, event_id=None, *, request_id=None,
                   timestamp=None, **body_fields):
    request_id = request_id or 'i2-' + uuid4().hex
    timestamp = timestamp or str(int(time.time()))
    manifest = f'id:{identifier};request-id:{request_id};ts:{timestamp};'
    digest = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return http.post('/webhooks/mercado-pago', params={'data.id': identifier, 'type': 'order'},
                     headers={'x-request-id': request_id, 'x-signature': f'ts={timestamp},v1={digest}'},
                     json={'type': 'order', 'data': {'id': identifier},
                           'id': event_id or uuid4().hex, **body_fields})


@contextmanager
def local_server(app, port=0):
    """No startup seed import; never listen outside loopback."""
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', port))
        config = uvicorn.Config(app, access_log=False, log_level='error', lifespan='off')
        server = uvicorn.Server(config)
        thread = Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError('I2 local server failed to start')
                time.sleep(.02)
            yield f'http://127.0.0.1:{listener.getsockname()[1]}'
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError('I2 local server failed to stop')


@contextmanager
def local_frontend_server(directory, port=0):
    """Serve the real frontend over loopback, including dynamic checkout paths."""
    class Server(ThreadingHTTPServer):
        request_queue_size = 128
        daemon_threads = True

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/admin':
                self.path = '/admin.html'
            elif self.path == '/produtor' or self.path.startswith('/produtor/'):
                self.path = '/portal-produtor.html'
            elif self.path == '/cliente' or self.path.startswith('/cliente/'):
                self.path = '/portal-cliente.html'
            elif re.fullmatch(r'/checkout/[0-9a-f-]{36}', self.path, re.IGNORECASE):
                self.path = '/checkout.html'
            return super().do_GET()

        def log_message(self, _format, *args):
            return None

    server = Server(
        ('127.0.0.1', port),
        partial(Handler, directory=str(Path(directory).resolve())),
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
