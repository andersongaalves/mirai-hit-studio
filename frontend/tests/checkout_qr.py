"""Encode synthetic Pix fixtures and decode their displayed QR images."""

import base64
import io
import json
import sys

import qrcode
import zxingcpp
from PIL import Image


def main():
    request = json.load(sys.stdin)
    if request["mode"] == "encode":
        image = qrcode.make(request["payload"])
        output = io.BytesIO()
        image.save(output, format="PNG")
        result = {"image": base64.b64encode(output.getvalue()).decode("ascii")}
    elif request["mode"] == "decode":
        image = Image.open(io.BytesIO(base64.b64decode(request["image"], validate=True)))
        barcode = zxingcpp.read_barcode(image)
        result = {"payload": barcode.text if barcode else None}
    else:
        raise ValueError("unsupported QR test operation")
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
