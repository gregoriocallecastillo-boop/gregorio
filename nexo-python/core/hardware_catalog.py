"""Fictitious hardware demo catalog with licensed real product photographs.

Photo attribution and licenses are displayed on the entry page and product detail.
Prices and quantities are examples, not supplier quotes.
"""
import json
from pathlib import Path

HARDWARE_PRODUCTS = [('Martillo de uña', 'FER-MARTILLO', 'Herramientas manuales', '7.50', '12.90', 48, 10),
 ('Cinta métrica retráctil', 'FER-CINTA', 'Medición', '4.20', '8.50', 75, 15),
 ('Atornillador inalámbrico con puntas',
  'FER-ATORN',
  'Herramientas eléctricas',
  '32.00',
  '49.90',
  7,
  10),
 ('Alicate universal', 'FER-ALICATE', 'Herramientas manuales', '6.80', '11.90', 40, 12),
 ('Destornillador plano', 'FER-DESTORN', 'Herramientas manuales', '2.60', '5.50', 0, 8),
 ('Llave ajustable', 'FER-LLAVE', 'Herramientas manuales', '9.40', '16.90', 16, 6),
 ('Tornillo para madera Phillips', 'FER-TORNILLO', 'Tornillería', '0.06', '0.15', 90, 20),
 ('Gafas de seguridad', 'FER-GAFAS', 'Protección personal', '3.10', '6.90', 5, 8)]

HARDWARE_PHOTOS = json.loads((Path(__file__).parent / "static/core/hardware/CREDITS.json").read_text(encoding="utf-8"))
