"""Authoritative fields are deterministic. Decode the *rendered* QR independently."""
from io import BytesIO
import re
import pypdfium2 as pdfium
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from reportlab.pdfbase.pdfmetrics import stringWidth
import zxingcpp

WIDTH, HEIGHT = 540, 360
TITLES = {
    "product_name": "Product", "manufacturer_name": "Manufacturer",
    "manufacturer_address": "Address", "product_identifier": "Product ID",
    "pack_identifier": "Pack ID", "quantity": "Quantity", "material": "Material",
}

def make_label(fields, template, label_key, revision_number, defect=None):
    rendered = dict(fields)
    if defect == "missing":
        rendered.pop("manufacturer_name", None)
    if defect == "identifier":
        rendered["pack_identifier"] = "DEMO-WRONG-PACK"
    if defect == "applicability":
        rendered["sterile_claim"] = "STERILE"
    if defect == "text":
        rendered["unsupported_claim"] = "FDA CERTIFIED"
    if defect == "overflow":
        rendered["manufacturer_address"] = "SYNTHETIC UNAPPROVED ADDRESS " * 8
    b = BytesIO()
    c = Canvas(b, pagesize=(WIDTH, HEIGHT), invariant=1)
    c.setFillColorRGB(.06, .18, .24)
    c.rect(0, HEIGHT - 49, WIDTH, 49, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(22, HEIGHT - 28, "LabelTrace / SYNTHETIC DEMONSTRATION ONLY")
    c.setFillColorRGB(.06, .18, .24)
    c.setFont("Helvetica", 9)
    c.drawString(22, 292, f"{label_key} | Revision {revision_number} | US-English | Nonsterile")
    boxes = {}
    for i, (key, value) in enumerate(rendered.items()):
        x, y, w, h = 22, 265 - i * 23, template.get("field_width", 385), 19
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x, y, TITLES.get(key, key))
        c.setFont("Helvetica", 10)
        c.drawString(x + 105, y, str(value))
        boxes[key] = {"x": x + 105, "y": y, "width": w - 105, "height": h,
                      "text_width": stringWidth(str(value), "Helvetica", 10), "font_size": 10}
    payload = "DEMO-WRONG-CODE" if defect == "barcode" else fields["pack_identifier"]
    widget = qr.QrCodeWidget(payload)
    bounds = widget.getBounds()
    d = Drawing(95, 95, transform=[95/(bounds[2]-bounds[0]), 0, 0, 95/(bounds[3]-bounds[1]), 0, 0])
    d.add(widget)
    renderPDF.draw(d, c, 430, 150)
    c.setFont("Helvetica", 8)
    c.drawString(22, 48, "Internal synthetic catalog code. Not a UDI. Not for clinical or manufacturing use.")
    c.drawString(22, 32, "No FDA certification or complete regulatory compliance is claimed.")
    c.save()
    return b.getvalue(), rendered, boxes

def inspect_pdf(data: bytes):
    text = "\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(data)).pages)
    doc = pdfium.PdfDocument(data)
    page = doc[0]
    bitmap = page.render(scale=2.5).to_pil()
    decoded = [x.text for x in zxingcpp.read_barcodes(bitmap)]
    t = page.get_textpage()
    bounds = [t.get_charbox(i) for i in range(t.count_chars()) if not t.get_text_range(i, 1).isspace()]
    outside = any(x0 < 0 or y0 < 0 or x1 > WIDTH or y1 > HEIGHT for x0, y0, x1, y1 in bounds)
    t.close()
    page.close()
    doc.close()
    return {"text": text, "barcodes": decoded, "outside_page": outside}

def preview(data):
    doc = pdfium.PdfDocument(data)
    page = doc[0]
    image = page.render(scale=2).to_pil()
    b = BytesIO()
    image.save(b, format="PNG")
    page.close()
    doc.close()
    return b.getvalue()

def canonical_lines(fields, label_key, revision):
    return ["LabelTrace / SYNTHETIC DEMONSTRATION ONLY",
            f"{label_key} | Revision {revision} | US-English | Nonsterile",
            *[line for k, v in fields.items() for line in (TITLES.get(k, k), str(v))],
            "Internal synthetic catalog code. Not a UDI. Not for clinical or manufacturing use.",
            "No FDA certification or complete regulatory compliance is claimed."]

def normalized(text):
    return re.sub(r"\s+", " ", text).strip()
