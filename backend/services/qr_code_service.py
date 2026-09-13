"""Payment URL -> in-memory PNG. Never fetch the payment address."""
import base64
from io import BytesIO
from urllib.parse import urlsplit

import qrcode
from pydantic import HttpUrl, TypeAdapter
from qrcode.exceptions import DataOverflowError


def gerar_qr_code(url: str) -> str:
    try:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc or parts.username or parts.password:
            raise ValueError()
        if any(character.isspace() or ord(character) < 32 for character in url):
            raise ValueError()
        TypeAdapter(HttpUrl).validate_python(url)
    except (ValueError, TypeError):
        raise ValueError("Link de pagamento invalido. Use uma URL http ou https sem credenciais.") from None
    output = BytesIO()
    try:
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        qr.make_image(fill_color="black", back_color="white").save(output, format="PNG")
    except DataOverflowError:
        raise ValueError("Link de pagamento longo demais para o QR Code.") from None
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")
