"""300 Moroccan bookkeeping document fixture dataset.

Generates realistic bilingual (French and Arabic) invoices, receipts, and edge cases
with ground truth metadata for evaluating extraction accuracy.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from avenel.jurisdiction.loader import get_jurisdiction_pack


@dataclass(frozen=True)
class DocumentFixture:
    doc_id: str
    category: str
    language: str
    doc_type: str
    raw_content: bytes
    mime_type: str
    ground_truth: dict[str, Any]


FRENCH_SUPPLIERS = [
    ("Atlas Consulting SARL", "001234567890123", "12345678", "RC 45678 Casa", "12 Bd Zerktouni, Casablanca"),
    ("Maroc Télécom Solutions", "002345678901234", "23456789", "RC 12345 Rabat", "Avenue Annakhil, Hay Riad, Rabat"),
    ("Bureau Express Equipement", "003456789012345", "34567890", "RC 67890 Casa", "Zone Industrielle Sidi Maarouf"),
    ("Maghreb Logistique & Transport", "004567890123456", "45678901", "RC 98765 Tanger", "Tanger Med Port, Tanger"),
    ("Société Nouvelle d'Impression", "005678901234567", "56789012", "RC 54321 Casa", "45 Rue Mohammed Smiha, Casablanca"),
    ("Casablanca IT Services", "006789012345678", "67890123", "RC 78901 Casa", "Technopark, Route de Nouaceur, Casablanca"),
    ("Atlas Papeterie & Fournitures", "007890123456789", "78901234", "RC 89012 Marrakech", "Gueliz, Bd Mohammed VI, Marrakech"),
    ("Rabat Sécurité & Gardiennage", "008901234567890", "89012345", "RC 23456 Rabat", "Agdal, Avenue de France, Rabat"),
    ("Fès Nettoyage & Entretien", "009012345678901", "90123456", "RC 34567 Fès", "Route d'Imouzzer, Fès"),
    ("BTP Maroc Travaux SARL", "000123456789012", "01234567", "RC 65432 Kenitra", "Avenue Diouri, Kenitra"),
]

ARABIC_SUPPLIERS = [
    ("شركة الأطلس للاستشارات ش.م.م", "001234567890123", "12345678", "سجل تجاري 45678 الدار البيضاء", "شارع الزرقطوني، الدار البيضاء"),
    ("مؤسسة النور للتجارة والتوزيع", "002345678901234", "23456789", "سجل تجاري 12345 الرباط", "حي الرياض، شارع النخيل، الرباط"),
    ("شركة المغرب للخدمات التقنية", "003456789012345", "34567890", "سجل تجاري 67890 فاس", "طريق إيموزار، فاس"),
    ("مطبعة الأمل الحديثة", "004567890123456", "45678901", "سجل تجاري 98765 مراكش", "جليز، مراكش"),
    ("مؤسسة التجهيز المكتبي السريع", "005678901234567", "56789012", "سجل تجاري 54321 طنجة", "طنجة المدينة"),
]

AUTO_ENTREPRENEUR_SUPPLIERS = [
    ("Karim Benjelloun - Développeur Web (Auto-entrepreneur)", "009988776655443", "99887766", "AE-12345", "Casablanca"),
    ("Fatima Ezzahra Amrani - Traductrice (Auto-entrepreneur)", "008877665544332", "88776655", "AE-23456", "Rabat"),
    ("Rachid Tazi - Consultant Formateur (Auto-entrepreneur)", "007766554433221", "77665544", "AE-34567", "Marrakech"),
]


def generate_300_fixtures() -> list[DocumentFixture]:
    """Generates the comprehensive 300-document evaluation fixture suite."""
    pack = get_jurisdiction_pack()
    std_rate = float(pack.get_value("vat.rate.standard", 0.20))
    red_rate = float(pack.get_value("vat.rate.reduced_10", 0.10))

    random.seed(42)  # Deterministic generation
    fixtures: list[DocumentFixture] = []

    # 1. 160 French standard corporate invoices and receipts
    for i in range(1, 161):
        sup_name, sup_ice, sup_if, sup_rc, sup_addr = random.choice(FRENCH_SUPPLIERS)
        inv_no = f"FAC-2026-{1000 + i}"
        day = (i % 28) + 1
        month = ((i % 12) + 1)
        inv_date = f"2026-{month:02d}-{day:02d}"

        ht_val = round(random.uniform(500.0, 15000.0), 2)
        vat_val = round(ht_val * std_rate, 2)
        ttc_val = round(ht_val + vat_val, 2)

        is_receipt = (i % 6 == 0)
        doc_type = "receipt" if is_receipt else "purchase_invoice"
        pay_method = "bank_transfer" if not is_receipt else "cash"

        doc_text = f"""
{sup_name}
{sup_addr}
ICE: {sup_ice} | IF: {sup_if} | {sup_rc}
============================================================
{"QUITTANCE / REÇU DE CAISSE" if is_receipt else "FACTURE"}
Facture N°: {inv_no}
Date: {day:02d}/{month:02d}/2026
Mode de règlement: {pay_method}

Client: Société Marocaine de Commerce SA
ICE Client: 009876543210987

Désignation des prestations:
- Prestation de services professionnels et fournitures diverses
  Montant HT : {ht_val:.2f} MAD
  Taux TVA   : 20%
  Montant TVA: {vat_val:.2f} MAD

------------------------------------------------------------
Total HT : {ht_val:.2f} MAD
TVA 20% Base: {ht_val:.2f} Montant: {vat_val:.2f}
Total TTC: {ttc_val:.2f} MAD
============================================================
"""
        fixtures.append(
            DocumentFixture(
                doc_id=f"fr_inv_{i:03d}",
                category="french_corporate",
                language="fr",
                doc_type=doc_type,
                raw_content=doc_text.strip().encode("utf-8"),
                mime_type="application/pdf",
                ground_truth={
                    "invoice_number": inv_no,
                    "invoice_date": inv_date,
                    "supplier_ice": sup_ice,
                    "supplier_if": sup_if,
                    "total_ht": ht_val,
                    "total_vat": vat_val,
                    "total_ttc": ttc_val,
                    "payment_method": pay_method,
                    "supplier_is_auto_entrepreneur": False,
                    "doc_type": doc_type,
                },
            )
        )

    # 2. 60 Arabic invoices & receipts
    for i in range(1, 61):
        sup_name, sup_ice, sup_if, sup_rc, sup_addr = random.choice(ARABIC_SUPPLIERS)
        inv_no = f"INV-AR-{2000 + i}"
        day = (i % 28) + 1
        month = ((i % 12) + 1)
        inv_date = f"2026-{month:02d}-{day:02d}"

        ht_val = round(random.uniform(300.0, 8000.0), 2)
        vat_val = round(ht_val * std_rate, 2)
        ttc_val = round(ht_val + vat_val, 2)

        is_receipt = (i % 4 == 0)
        doc_type = "receipt" if is_receipt else "purchase_invoice"
        pay_method = "cash" if is_receipt else "bank_transfer"

        doc_text = f"""
{sup_name}
{sup_addr}
المعرف الموحد للشركة (ICE): {sup_ice}
التعريف الضريبي (IF): {sup_if} | {sup_rc}
============================================================
{"وصل أداء / إيصال" if is_receipt else "فاتورة تجارية"}
رقم الفاتورة: {inv_no}
التاريخ: {day:02d}/{month:02d}/2026
طريقة الدفع: {"نقداً" if pay_method == "cash" else "تحويل بنكي"}

الزبون: شركة التدبير الحديث ش.م.م
المعرف الموحد: 009876543210987

تفاصيل الفاتورة:
- تجهيزات وخدمات عامة
المجموع دون احتساب الضريبة: {ht_val:.2f} درهم
الضريبة على القيمة المضافة: {vat_val:.2f} درهم
TVA 20% Base: {ht_val:.2f} Montant: {vat_val:.2f}
المجموع مع احتساب الضريبة: {ttc_val:.2f} درهم
============================================================
"""
        fixtures.append(
            DocumentFixture(
                doc_id=f"ar_inv_{i:03d}",
                category="arabic_commercial",
                language="ar",
                doc_type=doc_type,
                raw_content=doc_text.strip().encode("utf-8"),
                mime_type="application/pdf",
                ground_truth={
                    "invoice_number": inv_no,
                    "invoice_date": inv_date,
                    "supplier_ice": sup_ice,
                    "supplier_if": sup_if,
                    "total_ht": ht_val,
                    "total_vat": vat_val,
                    "total_ttc": ttc_val,
                    "payment_method": pay_method,
                    "supplier_is_auto_entrepreneur": False,
                    "doc_type": doc_type,
                },
            )
        )

    # 3. 30 Cash receipts (half under 5000 MAD, half above 5000 MAD cash limit)
    for i in range(1, 31):
        sup_name, sup_ice, sup_if, sup_rc, sup_addr = random.choice(FRENCH_SUPPLIERS)
        inv_no = f"REC-CASH-{3000 + i}"
        day = (i % 28) + 1
        month = ((i % 12) + 1)
        inv_date = f"2026-{month:02d}-{day:02d}"

        if i <= 15:
            ht_val = round(random.uniform(500.0, 3500.0), 2)
        else:
            ht_val = round(random.uniform(5500.0, 9500.0), 2)

        vat_val = round(ht_val * std_rate, 2)
        ttc_val = round(ht_val + vat_val, 2)

        doc_text = f"""
{sup_name}
{sup_addr}
ICE: {sup_ice} | IF: {sup_if} | {sup_rc}
TICKET DE CAISSE / REÇU D'ESPÈCES
Facture N°: {inv_no}
Date: {day:02d}/{month:02d}/2026
Règlement: Espèces

Client: Entreprise Générale
Montant HT: {ht_val:.2f} MAD
TVA 20% Base: {ht_val:.2f} Montant: {vat_val:.2f}
Total TTC: {ttc_val:.2f} MAD
"""
        fixtures.append(
            DocumentFixture(
                doc_id=f"cash_rec_{i:03d}",
                category="cash_limits",
                language="fr",
                doc_type="receipt",
                raw_content=doc_text.strip().encode("utf-8"),
                mime_type="application/pdf",
                ground_truth={
                    "invoice_number": inv_no,
                    "invoice_date": inv_date,
                    "supplier_ice": sup_ice,
                    "supplier_if": sup_if,
                    "total_ht": ht_val,
                    "total_vat": vat_val,
                    "total_ttc": ttc_val,
                    "payment_method": "cash",
                    "supplier_is_auto_entrepreneur": False,
                    "doc_type": "receipt",
                },
            )
        )

    # 4. 15 Auto-entrepreneur invoices
    for i in range(1, 16):
        sup_name, sup_ice, sup_if, sup_rc, sup_addr = random.choice(AUTO_ENTREPRENEUR_SUPPLIERS)
        inv_no = f"AE-INV-{4000 + i}"
        day = (i % 28) + 1
        month = ((i % 12) + 1)
        inv_date = f"2026-{month:02d}-{day:02d}"

        ht_val = round(random.uniform(1000.0, 5000.0), 2)
        if i <= 10:
            vat_val = 0.0
            ttc_val = ht_val
            vat_clause = "Exonéré de TVA en vertu du statut d'Auto-entrepreneur (CGI art. 89)"
        else:
            vat_val = round(ht_val * std_rate, 2)
            ttc_val = round(ht_val + vat_val, 2)
            vat_clause = f"TVA 20%: {vat_val:.2f} MAD (Facturée par erreur)"

        doc_text = f"""
{sup_name}
Statut : Auto-entrepreneur
{sup_addr}
ICE: {sup_ice} | IF: {sup_if} | {sup_rc}
FACTURE DE PRESTATION
Facture N°: {inv_no}
Date: {day:02d}/{month:02d}/2026
Client: Fiduciaire Avenel Client SARL

Description: Développement et conseil technique
Total HT: {ht_val:.2f} MAD
{vat_clause}
Total TTC: {ttc_val:.2f} MAD
"""
        fixtures.append(
            DocumentFixture(
                doc_id=f"ae_inv_{i:03d}",
                category="auto_entrepreneur",
                language="fr",
                doc_type="purchase_invoice",
                raw_content=doc_text.strip().encode("utf-8"),
                mime_type="application/pdf",
                ground_truth={
                    "invoice_number": inv_no,
                    "invoice_date": inv_date,
                    "supplier_ice": sup_ice,
                    "supplier_if": sup_if,
                    "total_ht": ht_val,
                    "total_vat": vat_val,
                    "total_ttc": ttc_val,
                    "payment_method": "unspecified",
                    "supplier_is_auto_entrepreneur": True,
                    "doc_type": "purchase_invoice",
                },
            )
        )

    # 5. 15 Multi-rate and edge cases
    for i in range(1, 16):
        sup_name, sup_ice, sup_if, sup_rc, sup_addr = random.choice(FRENCH_SUPPLIERS)
        is_credit_note = (i <= 5)
        doc_type = "credit_note" if is_credit_note else "purchase_invoice"
        inv_no = f"AVOIR-2026-{5000 + i}" if is_credit_note else f"FAC-RED-2026-{5000 + i}"
        day = (i % 28) + 1
        month = ((i % 12) + 1)
        inv_date = f"2026-{month:02d}-{day:02d}"

        ht_val = round(random.uniform(1200.0, 6000.0), 2)
        vat_val = round(ht_val * red_rate, 2)
        ttc_val = round(ht_val + vat_val, 2)

        doc_text = f"""
{sup_name}
{sup_addr}
ICE: {sup_ice} | IF: {sup_if} | {sup_rc}
{"AVOIR / NOTE DE CRÉDIT" if is_credit_note else "FACTURE TAUX RÉDUIT"}
Facture N°: {inv_no}
Date: {day:02d}/{month:02d}/2026
Client: Atlas Distribution SA
ICE Client: 009876543210987

Hébergement hôtelier et restauration (Taux réduit de 10%)
Total HT: {ht_val:.2f} MAD
TVA 10% Base: {ht_val:.2f} Montant: {vat_val:.2f}
Total TTC: {ttc_val:.2f} MAD
"""
        fixtures.append(
            DocumentFixture(
                doc_id=f"edge_inv_{i:03d}",
                category="reduced_rate_credit_notes",
                language="fr",
                doc_type=doc_type,
                raw_content=doc_text.strip().encode("utf-8"),
                mime_type="application/pdf",
                ground_truth={
                    "invoice_number": inv_no,
                    "invoice_date": inv_date,
                    "supplier_ice": sup_ice,
                    "supplier_if": sup_if,
                    "total_ht": ht_val,
                    "total_vat": vat_val,
                    "total_ttc": ttc_val,
                    "payment_method": "unspecified",
                    "supplier_is_auto_entrepreneur": False,
                    "doc_type": doc_type,
                },
            )
        )

    # 6. 20 Bilingual / Mixed French-Arabic invoices
    for i in range(1, 21):
        sup_name_fr, sup_ice, sup_if, sup_rc, sup_addr_fr = random.choice(FRENCH_SUPPLIERS)
        sup_name_ar, _, _, _, _ = random.choice(ARABIC_SUPPLIERS)
        inv_no = f"FAC-MIX-{6000 + i}"
        day = (i % 28) + 1
        month = ((i % 12) + 1)
        inv_date = f"2026-{month:02d}-{day:02d}"

        ht_val = round(random.uniform(800.0, 7500.0), 2)
        vat_val = round(ht_val * std_rate, 2)
        ttc_val = round(ht_val + vat_val, 2)

        doc_text = f"""
{sup_name_fr} / {sup_name_ar}
{sup_addr_fr}
ICE / المعرف الموحد : {sup_ice}
IF / التعريف الضريبي : {sup_if} | RC: {sup_rc}
============================================================
FACTURE / فاتورة
Facture N° / رقم الفاتورة : {inv_no}
Date / التاريخ : {day:02d}/{month:02d}/2026
Client: Atlas Distribution SA / الزبون : شركة الأطلس
ICE Client / المعرف الموحد للزبون : 009876543210987

Désignation / البيان:
Prestations techniques et fournitures / خدمات تقنية
Total HT / المجموع دون الضريبة : {ht_val:.2f} MAD
TVA 20% Base: {ht_val:.2f} Montant: {vat_val:.2f}
Total TTC / المجموع شامل الضريبة : {ttc_val:.2f} MAD
============================================================
"""
        fixtures.append(
            DocumentFixture(
                doc_id=f"mixed_inv_{i:03d}",
                category="bilingual_mixed",
                language="mixed",
                doc_type="purchase_invoice",
                raw_content=doc_text.strip().encode("utf-8"),
                mime_type="application/pdf",
                ground_truth={
                    "invoice_number": inv_no,
                    "invoice_date": inv_date,
                    "supplier_ice": sup_ice,
                    "supplier_if": sup_if,
                    "total_ht": ht_val,
                    "total_vat": vat_val,
                    "total_ttc": ttc_val,
                    "payment_method": "unspecified",
                    "supplier_is_auto_entrepreneur": False,
                    "doc_type": "purchase_invoice",
                },
            )
        )

    return fixtures

