"""Shared test helpers: tiny in-memory file fixtures and upload utilities."""
from __future__ import annotations

import io


def make_text_pdf(text: str) -> bytes:
    """Build a minimal, valid single-page PDF containing ``text``.

    Hand-assembled with a correct xref table so pypdf reads it without
    recovery — no reportlab dependency required.
    """
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>",
    ]
    stream = b"BT /F1 24 Tf 72 700 Td (" + text.encode() + b") Tj ET"
    objs.append(b"<</Length " + str(len(stream)).encode() + b">>stream\n" + stream + b"\nendstream")
    objs.append(b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>")

    out = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + o + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += (
        b"trailer<</Size " + str(len(objs) + 1).encode() + b"/Root 1 0 R>>\n"
        b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF"
    )
    return out


def make_encrypted_pdf(password: str = "secret") -> bytes:
    """A password-protected PDF whose text cannot be extracted without the key."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt(password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def upload_bytes(client, filename: str, data: bytes, content_type: str = "application/octet-stream"):
    """POST a file to the upload endpoint and return the raw response."""
    return client.post(
        "/api/documents/upload",
        files={"file": (filename, data, content_type)},
    )


def upload_text_doc(client, filename: str, text: str):
    """Upload a plain-text document and assert success; return the JSON body."""
    res = upload_bytes(client, filename, text.encode("utf-8"), "text/plain")
    assert res.status_code == 200, res.text
    return res.json()
