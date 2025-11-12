# utils/pdf_utils.py
from reportlab.lib.pagesizes import A4

def agregar_pie_pdf(c, width, height):
    """Agrega marca de agua/pie institucional al PDF"""
    c.setFont("Courier-Bold", 10)
    texto = "Fusion Cable - Chile 450 | Tel: 3725-468892"
    text_width = c.stringWidth(texto, "Courier-Bold", 10)
    c.drawString(width - text_width - 40, 20, texto)
