from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Iterable, Tuple
import zipfile

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from xml.etree.ElementTree import Element, SubElement, tostring, register_namespace

from ..models.finance import FinanceCompany
from ..models.finance_ref import FinanceCounterparty
from ..models.finance_invoices import FinanceInvoice


def _d(x) -> Decimal:
    if x is None:
        return Decimal("0")
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def _iso(dt: date | None) -> str:
    return dt.isoformat() if dt else ""


@dataclass
class InvoiceTotals:
    net: Decimal
    tax: Decimal
    gross: Decimal


def compute_totals(inv: FinanceInvoice) -> InvoiceTotals:
    net = Decimal("0")
    tax = Decimal("0")
    gross = Decimal("0")
    for ln in inv.lines:
        net += _d(ln.net_amount)
        tax += _d(ln.tax_amount)
        gross += _d(ln.gross_amount)
    return InvoiceTotals(net=net, tax=tax, gross=gross)


def build_invoice_pdf_bytes(
    inv: FinanceInvoice,
    company: FinanceCompany,
    cp: FinanceCounterparty | None,
    logo_path: str | None = None,
    lang: str | None = None,
) -> bytes:
    """Generate a simple invoice PDF.

    This is not Factur-X PDF/A-3 compliant; it is a readable invoice PDF.
    The XML export is provided separately.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    lang = (lang or "en").split("-")[0].lower()
    is_br = (getattr(inv, "fiscal_country", "EU") or "EU").upper() == "BR"

    labels = {
        "fr": {
            "invoice": "Facture",
            "nota_fiscal": "Note fiscale",
            "issue_date": "Date d'emission",
            "due_date": "Date d'echeance",
            "seller": "Vendeur",
            "buyer": "Acheteur",
            "vat": "TVA",
            "tax": "Impots",
            "description": "Description",
            "qty": "Qt",
            "unit": "Unite",
            "total": "Total",
            "net": "Net",
        },
        "pt": {
            "invoice": "Fatura",
            "nota_fiscal": "Nota Fiscal",
            "issue_date": "Data de emissao",
            "due_date": "Data de vencimento",
            "seller": "Emitente",
            "buyer": "Cliente",
            "vat": "IVA",
            "tax": "Impostos",
            "description": "Descricao",
            "qty": "Qtd",
            "unit": "Unit",
            "total": "Total",
            "net": "Liquido",
        },
        "es": {
            "invoice": "Factura",
            "nota_fiscal": "Factura fiscal",
            "issue_date": "Fecha de emision",
            "due_date": "Fecha de vencimiento",
            "seller": "Emisor",
            "buyer": "Cliente",
            "vat": "IVA",
            "tax": "Impuestos",
            "description": "Descripcion",
            "qty": "Cant.",
            "unit": "Unit.",
            "total": "Total",
            "net": "Neto",
        },
        "it": {
            "invoice": "Fattura",
            "nota_fiscal": "Nota fiscale",
            "issue_date": "Data emissione",
            "due_date": "Scadenza",
            "seller": "Cedente",
            "buyer": "Cessionario",
            "vat": "IVA",
            "tax": "Imposte",
            "description": "Descrizione",
            "qty": "Qta",
            "unit": "Unita",
            "total": "Totale",
            "net": "Netto",
        },
        "de": {
            "invoice": "Rechnung",
            "nota_fiscal": "Steuerrechnung",
            "issue_date": "Ausstellungsdatum",
            "due_date": "Falligkeitsdatum",
            "seller": "Verkaufer",
            "buyer": "Kaufer",
            "vat": "MwSt",
            "tax": "Steuern",
            "description": "Beschreibung",
            "qty": "Menge",
            "unit": "Einheit",
            "total": "Gesamt",
            "net": "Netto",
        },
    }.get(lang, {
        "invoice": "Invoice",
        "nota_fiscal": "Tax Invoice",
        "issue_date": "Issue date",
        "due_date": "Due date",
        "seller": "Seller",
        "buyer": "Buyer",
        "vat": "VAT",
        "tax": "Taxes",
        "description": "Description",
        "qty": "Qty",
        "unit": "Unit",
        "total": "Total",
        "net": "Net",
    })

    # Header
    c.setFont("Helvetica-Bold", 14)
    title_label = labels["nota_fiscal"] if is_br else labels["invoice"]
    c.drawString(20 * mm, h - 20 * mm, f"{title_label} {inv.invoice_number}")
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, h - 28 * mm, f"{labels['issue_date']}: {_iso(inv.issue_date)}")
    if inv.due_date:
        c.drawString(20 * mm, h - 34 * mm, f"{labels['due_date']}: {_iso(inv.due_date)}")

    if logo_path:
        try:
            logo = ImageReader(logo_path)
            c.drawImage(logo, 150 * mm, h - 36 * mm, width=40 * mm, height=14 * mm, preserveAspectRatio=True, anchor='n')
        except Exception:
            pass

    # Company block
    y = h - 50 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, labels["seller"])
    c.setFont("Helvetica", 10)
    y -= 5 * mm
    c.drawString(20 * mm, y, company.name)
    y -= 5 * mm
    if company.address_line1:
        c.drawString(20 * mm, y, company.address_line1)
        y -= 5 * mm
    if company.address_line2:
        c.drawString(20 * mm, y, company.address_line2)
        y -= 5 * mm
    city_line = " ".join([p for p in [company.postal_code, company.city] if p])
    if city_line:
        c.drawString(20 * mm, y, city_line)
        y -= 5 * mm
    if company.country_code:
        c.drawString(20 * mm, y, company.country_code)
        y -= 5 * mm
    if company.vat_number:
        c.drawString(20 * mm, y, f"{labels['vat']}: {company.vat_number}")
        y -= 5 * mm

    # Buyer block
    y2 = h - 50 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(120 * mm, y2, labels["buyer"])
    c.setFont("Helvetica", 10)
    y2 -= 5 * mm
    if cp:
        c.drawString(120 * mm, y2, cp.name)
        y2 -= 5 * mm
        if cp.address_line1:
            c.drawString(120 * mm, y2, cp.address_line1)
            y2 -= 5 * mm
        if cp.address_line2:
            c.drawString(120 * mm, y2, cp.address_line2)
            y2 -= 5 * mm
        city_line = " ".join([p for p in [cp.postal_code, cp.city] if p])
        if city_line:
            c.drawString(120 * mm, y2, city_line)
            y2 -= 5 * mm
        if cp.country_code:
            c.drawString(120 * mm, y2, cp.country_code)
            y2 -= 5 * mm
        if cp.vat_number:
            c.drawString(120 * mm, y2, f"{labels['vat']}: {cp.vat_number}")

    # Lines table header
    y = h - 90 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, labels["description"])
    c.drawString(120 * mm, y, labels["qty"])
    c.drawString(140 * mm, y, labels["unit"])
    c.drawString(165 * mm, y, labels["total"])
    c.line(20 * mm, y - 2 * mm, 190 * mm, y - 2 * mm)

    c.setFont("Helvetica", 10)
    y -= 8 * mm
    for ln in inv.lines:
        if y < 30 * mm:
            c.showPage()
            y = h - 20 * mm
        c.drawString(20 * mm, y, (ln.description or "")[:70])
        c.drawRightString(135 * mm, y, f"{_d(ln.quantity):.2f}")
        c.drawRightString(160 * mm, y, f"{_d(ln.unit_price):.2f}")
        c.drawRightString(190 * mm, y, f"{_d(ln.gross_amount):.2f}")
        y -= 6 * mm

    totals = compute_totals(inv)
    y -= 5 * mm
    c.line(120 * mm, y, 190 * mm, y)
    y -= 7 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(160 * mm, y, labels["net"])
    c.drawRightString(190 * mm, y, f"{totals.net:.2f} {inv.currency}")
    y -= 6 * mm
    tax_label = labels["tax"] if is_br else labels["vat"]
    c.drawRightString(160 * mm, y, tax_label)
    c.drawRightString(190 * mm, y, f"{totals.tax:.2f} {inv.currency}")
    if is_br:
        y -= 6 * mm
        total_icms = sum((_d(getattr(ln, "icms_amount", 0)) for ln in inv.lines), Decimal("0"))
        total_ipi = sum((_d(getattr(ln, "ipi_amount", 0)) for ln in inv.lines), Decimal("0"))
        total_pis = sum((_d(getattr(ln, "pis_amount", 0)) for ln in inv.lines), Decimal("0"))
        total_cofins = sum((_d(getattr(ln, "cofins_amount", 0)) for ln in inv.lines), Decimal("0"))
        c.setFont("Helvetica", 9)
        c.drawRightString(190 * mm, y, f"ICMS {total_icms:.2f} | IPI {total_ipi:.2f} | PIS {total_pis:.2f} | COFINS {total_cofins:.2f}")
        c.setFont("Helvetica-Bold", 10)
    y -= 6 * mm
    c.drawRightString(160 * mm, y, labels["total"])
    c.drawRightString(190 * mm, y, f"{totals.gross:.2f} {inv.currency}")

    c.showPage()
    c.save()
    return buf.getvalue()


def build_facturx_cii_xml_bytes(inv: FinanceInvoice, company: FinanceCompany, cp: FinanceCounterparty | None) -> bytes:
    """Build a pragmatic Factur-X XML (CII / EN16931).

    Notes:
    - The full Factur-X specification is PDF/A-3 + embedded XML.
    - Here we generate the EN16931 CII XML payload (usable for many systems).
    """

    # Namespaces
    ns_rsm = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    ns_ram = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    ns_udt = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"

    register_namespace("rsm", ns_rsm)
    register_namespace("ram", ns_ram)
    register_namespace("udt", ns_udt)

    def rsm(tag: str) -> str:
        return f"{{{ns_rsm}}}{tag}"

    def ram(tag: str) -> str:
        return f"{{{ns_ram}}}{tag}"

    def udt(tag: str) -> str:
        return f"{{{ns_udt}}}{tag}"

    root = Element(rsm("CrossIndustryInvoice"))

    # Context / guideline
    ctx = SubElement(root, rsm("ExchangedDocumentContext"))
    gpar = SubElement(ctx, ram("GuidelineSpecifiedDocumentContextParameter"))
    # EN16931 guideline + Factur-X profile (basic)
    SubElement(gpar, ram("ID")).text = "urn:factur-x.eu:1p0:basic"

    # Document header
    doc = SubElement(root, rsm("ExchangedDocument"))
    SubElement(doc, ram("ID")).text = inv.invoice_number
    SubElement(doc, ram("TypeCode")).text = "380"  # commercial invoice
    issue = SubElement(doc, ram("IssueDateTime"))
    dts = SubElement(issue, udt("DateTimeString"), {"format": "102"})
    dts.text = inv.issue_date.strftime("%Y%m%d")

    # Trade transaction
    sctt = SubElement(root, rsm("SupplyChainTradeTransaction"))

    # Lines
    for idx, ln in enumerate(inv.lines, start=1):
        li = SubElement(sctt, ram("IncludedSupplyChainTradeLineItem"))
        doc_line = SubElement(li, ram("AssociatedDocumentLineDocument"))
        SubElement(doc_line, ram("LineID")).text = str(idx)

        prod = SubElement(li, ram("SpecifiedTradeProduct"))
        SubElement(prod, ram("Name")).text = ln.description

        agr = SubElement(li, ram("SpecifiedLineTradeAgreement"))
        price = SubElement(agr, ram("NetPriceProductTradePrice"))
        SubElement(price, ram("ChargeAmount")).text = f"{_d(ln.unit_price):.4f}"

        deliv = SubElement(li, ram("SpecifiedLineTradeDelivery"))
        qty = SubElement(deliv, ram("BilledQuantity"), {"unitCode": "C62"})
        qty.text = f"{_d(ln.quantity):.4f}"

        sett = SubElement(li, ram("SpecifiedLineTradeSettlement"))
        tax = SubElement(sett, ram("ApplicableTradeTax"))
        SubElement(tax, ram("TypeCode")).text = "VAT"
        SubElement(tax, ram("CategoryCode")).text = "S"
        SubElement(tax, ram("RateApplicablePercent")).text = f"{_d(ln.vat_rate):.2f}"

        summ = SubElement(sett, ram("SpecifiedTradeSettlementLineMonetarySummation"))
        SubElement(summ, ram("LineTotalAmount")).text = f"{_d(ln.net_amount):.2f}"

    # Header agreement (seller/buyer)
    hta = SubElement(sctt, ram("ApplicableHeaderTradeAgreement"))
    seller = SubElement(hta, ram("SellerTradeParty"))
    SubElement(seller, ram("Name")).text = company.name
    if company.vat_number:
        taxreg = SubElement(seller, ram("SpecifiedTaxRegistration"))
        SubElement(taxreg, ram("ID"), {"schemeID": "VA"}).text = company.vat_number
    if company.address_line1 or company.city:
        addr = SubElement(seller, ram("PostalTradeAddress"))
        if company.postal_code:
            SubElement(addr, ram("PostcodeCode")).text = company.postal_code
        if company.city:
            SubElement(addr, ram("CityName")).text = company.city
        if company.address_line1:
            SubElement(addr, ram("LineOne")).text = company.address_line1
        if company.address_line2:
            SubElement(addr, ram("LineTwo")).text = company.address_line2
        if company.country_code:
            SubElement(addr, ram("CountryID")).text = company.country_code

    buyer = SubElement(hta, ram("BuyerTradeParty"))
    SubElement(buyer, ram("Name")).text = (cp.name if cp else "")
    if cp and cp.vat_number:
        taxreg = SubElement(buyer, ram("SpecifiedTaxRegistration"))
        SubElement(taxreg, ram("ID"), {"schemeID": "VA"}).text = cp.vat_number
    if cp and (cp.address_line1 or cp.city):
        addr = SubElement(buyer, ram("PostalTradeAddress"))
        if cp.postal_code:
            SubElement(addr, ram("PostcodeCode")).text = cp.postal_code
        if cp.city:
            SubElement(addr, ram("CityName")).text = cp.city
        if cp.address_line1:
            SubElement(addr, ram("LineOne")).text = cp.address_line1
        if cp.address_line2:
            SubElement(addr, ram("LineTwo")).text = cp.address_line2
        if cp.country_code:
            SubElement(addr, ram("CountryID")).text = cp.country_code

    # Header settlement
    hts = SubElement(sctt, ram("ApplicableHeaderTradeSettlement"))
    SubElement(hts, ram("InvoiceCurrencyCode")).text = inv.currency

    # Tax totals grouped
    by_rate: dict[str, Tuple[Decimal, Decimal]] = {}
    for ln in inv.lines:
        r = f"{_d(ln.vat_rate):.2f}"
        impon, imposta = by_rate.get(r, (Decimal("0"), Decimal("0")))
        impon += _d(ln.net_amount)
        imposta += _d(ln.tax_amount)
        by_rate[r] = (impon, imposta)
    for rate, (impon, imposta) in by_rate.items():
        tax = SubElement(hts, ram("ApplicableTradeTax"))
        SubElement(tax, ram("CalculatedAmount")).text = f"{imposta:.2f}"
        SubElement(tax, ram("TypeCode")).text = "VAT"
        SubElement(tax, ram("BasisAmount")).text = f"{impon:.2f}"
        SubElement(tax, ram("CategoryCode")).text = "S"
        SubElement(tax, ram("RateApplicablePercent")).text = rate

    totals = compute_totals(inv)
    ms = SubElement(hts, ram("SpecifiedTradeSettlementHeaderMonetarySummation"))
    SubElement(ms, ram("LineTotalAmount")).text = f"{totals.net:.2f}"
    SubElement(ms, ram("TaxBasisTotalAmount")).text = f"{totals.net:.2f}"
    SubElement(ms, ram("TaxTotalAmount")).text = f"{totals.tax:.2f}"
    SubElement(ms, ram("GrandTotalAmount")).text = f"{totals.gross:.2f}"
    SubElement(ms, ram("DuePayableAmount")).text = f"{totals.gross:.2f}"

    return tostring(root, encoding="utf-8", xml_declaration=True)


def build_fatturapa_xml_bytes(inv: FinanceInvoice, company: FinanceCompany, cp: FinanceCounterparty | None) -> bytes:
    """Build a minimal FatturaPA XML (schema v1.2, FPR12).

    This is a pragmatic MVP. For strict SDI submission, you will likely need:
    - progressive transmission id
    - PEC/SDI code
    - more detailed VAT breakdown
    - validation against official XSD
    """
    ns = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"
    register_namespace("p", ns)
    def p(tag: str) -> str:
        return f"{{{ns}}}{tag}"

    root = Element(p("FatturaElettronica"), {"versione": "FPR12"})

    header = SubElement(root, p("FatturaElettronicaHeader"))
    dati_trasm = SubElement(header, p("DatiTrasmissione"))
    SubElement(dati_trasm, p("IdTrasmittente"))
    # For MVP we just use country + vat as IdTrasmittente
    idt = list(dati_trasm)[0]
    SubElement(idt, p("IdPaese")).text = company.country_code or "IT"
    SubElement(idt, p("IdCodice")).text = (company.vat_number or "00000000000")[:28]
    SubElement(dati_trasm, p("ProgressivoInvio")).text = inv.invoice_number[:10]
    SubElement(dati_trasm, p("FormatoTrasmissione")).text = "FPR12"
    SubElement(dati_trasm, p("CodiceDestinatario")).text = (cp.sdi_code if cp and cp.sdi_code else "0000000")
    if cp and cp.pec_email:
        SubElement(dati_trasm, p("PECDestinatario")).text = cp.pec_email

    ced = SubElement(header, p("CedentePrestatore"))
    dati_anag = SubElement(ced, p("DatiAnagrafici"))
    id_fisc = SubElement(dati_anag, p("IdFiscaleIVA"))
    SubElement(id_fisc, p("IdPaese")).text = company.country_code or "IT"
    SubElement(id_fisc, p("IdCodice")).text = (company.vat_number or "00000000000")[:28]
    anag = SubElement(dati_anag, p("Anagrafica"))
    SubElement(anag, p("Denominazione")).text = company.name
    if company.siret:
        SubElement(dati_anag, p("CodiceFiscale")).text = company.siret

    sede = SubElement(ced, p("Sede"))
    SubElement(sede, p("Indirizzo")).text = company.address_line1 or ""
    SubElement(sede, p("CAP")).text = company.postal_code or ""
    SubElement(sede, p("Comune")).text = company.city or ""
    SubElement(sede, p("Provincia")).text = (company.state or "")[:2]
    SubElement(sede, p("Nazione")).text = company.country_code or "IT"

    cessionario = SubElement(header, p("CessionarioCommittente"))
    dati_anag_c = SubElement(cessionario, p("DatiAnagrafici"))
    if cp and cp.vat_number:
        id_fisc_c = SubElement(dati_anag_c, p("IdFiscaleIVA"))
        SubElement(id_fisc_c, p("IdPaese")).text = cp.country_code or "IT"
        SubElement(id_fisc_c, p("IdCodice")).text = cp.vat_number[:28]
    if cp and cp.tax_id:
        SubElement(dati_anag_c, p("CodiceFiscale")).text = cp.tax_id
    anag_c = SubElement(dati_anag_c, p("Anagrafica"))
    SubElement(anag_c, p("Denominazione")).text = (cp.name if cp else "")

    sede_c = SubElement(cessionario, p("Sede"))
    SubElement(sede_c, p("Indirizzo")).text = (cp.address_line1 if cp else "") or ""
    SubElement(sede_c, p("CAP")).text = (cp.postal_code if cp else "") or ""
    SubElement(sede_c, p("Comune")).text = (cp.city if cp else "") or ""
    SubElement(sede_c, p("Provincia")).text = ((cp.state if cp else "") or "")[:2]
    SubElement(sede_c, p("Nazione")).text = (cp.country_code if cp else None) or "IT"

    body = SubElement(root, p("FatturaElettronicaBody"))
    dati_gen = SubElement(body, p("DatiGenerali"))
    dati_doc = SubElement(dati_gen, p("DatiGeneraliDocumento"))
    SubElement(dati_doc, p("TipoDocumento")).text = "TD01"  # invoice
    SubElement(dati_doc, p("Divisa")).text = inv.currency
    SubElement(dati_doc, p("Data")).text = _iso(inv.issue_date)
    SubElement(dati_doc, p("Numero")).text = inv.invoice_number

    beni = SubElement(body, p("DatiBeniServizi"))
    for i, ln in enumerate(inv.lines, start=1):
        dett = SubElement(beni, p("DettaglioLinee"))
        SubElement(dett, p("NumeroLinea")).text = str(i)
        SubElement(dett, p("Descrizione")).text = ln.description
        SubElement(dett, p("Quantita")).text = f"{_d(ln.quantity):.2f}"
        SubElement(dett, p("PrezzoUnitario")).text = f"{_d(ln.unit_price):.4f}"
        SubElement(dett, p("PrezzoTotale")).text = f"{_d(ln.net_amount):.2f}"
        SubElement(dett, p("AliquotaIVA")).text = f"{_d(ln.vat_rate):.2f}"

    # VAT summary (group by rate)
    by_rate: dict[str, Tuple[Decimal, Decimal]] = {}
    for ln in inv.lines:
        r = f"{_d(ln.vat_rate):.2f}"
        impon, imposta = by_rate.get(r, (Decimal("0"), Decimal("0")))
        impon += _d(ln.net_amount)
        imposta += _d(ln.tax_amount)
        by_rate[r] = (impon, imposta)

    for rate, (impon, imposta) in by_rate.items():
        rie = SubElement(beni, p("DatiRiepilogo"))
        SubElement(rie, p("AliquotaIVA")).text = rate
        SubElement(rie, p("ImponibileImporto")).text = f"{impon:.2f}"
        SubElement(rie, p("Imposta")).text = f"{imposta:.2f}"
        SubElement(rie, p("EsigibilitaIVA")).text = "I"

    totals = compute_totals(inv)
    SubElement(dati_doc, p("ImportoTotaleDocumento")).text = f"{totals.gross:.2f}"

    return tostring(root, encoding="utf-8", xml_declaration=True)


def _compute_br_tax_components(base: Decimal, icms_rate: Decimal, ipi_rate: Decimal, pis_rate: Decimal, cofins_rate: Decimal) -> dict[str, Decimal]:
    icms = (base * icms_rate / Decimal("100")).quantize(Decimal("0.01"))
    ipi = (base * ipi_rate / Decimal("100")).quantize(Decimal("0.01"))
    pis = (base * pis_rate / Decimal("100")).quantize(Decimal("0.01"))
    cofins = (base * cofins_rate / Decimal("100")).quantize(Decimal("0.01"))
    return {
        "icms": icms,
        "ipi": ipi,
        "pis": pis,
        "cofins": cofins,
        "tax_total": (icms + ipi + pis + cofins).quantize(Decimal("0.01")),
    }


def build_nfe_br_xml_bytes(
    inv: FinanceInvoice,
    company: FinanceCompany,
    cp: FinanceCounterparty | None,
    *,
    icms_rate: Decimal = Decimal("18.00"),
    ipi_rate: Decimal = Decimal("0.00"),
    pis_rate: Decimal = Decimal("1.65"),
    cofins_rate: Decimal = Decimal("7.60"),
) -> bytes:
    """Build a pragmatic NFe-like XML payload for Brazil with core tax blocks.

    This is an integration starter and not a complete SEFAZ submission payload.
    """
    root = Element("NFe")
    inf = SubElement(root, "infNFe", {
        "versao": "4.00",
        "Id": f"NFe{inv.invoice_number}",
    })

    ide = SubElement(inf, "ide")
    SubElement(ide, "cNF").text = str(inv.cnf_code or inv.id)
    SubElement(ide, "natOp").text = str(inv.natureza_operacao or ("VENDA" if (inv.invoice_type or "sale") == "sale" else "COMPRA"))
    SubElement(ide, "mod").text = str(inv.document_model or "55")
    SubElement(ide, "serie").text = str(inv.document_series or "1")
    SubElement(ide, "nNF").text = inv.invoice_number
    SubElement(ide, "dhEmi").text = _iso(inv.issue_date)
    SubElement(ide, "tpNF").text = "1" if (inv.invoice_type or "sale") == "sale" else "0"
    SubElement(ide, "idDest").text = str(inv.operation_destination or "1")
    SubElement(ide, "indPag").text = str(inv.payment_indicator or "0")
    SubElement(ide, "indPres").text = str(inv.presence_indicator or "1")
    SubElement(ide, "finNFe").text = str(inv.invoice_purpose or "1")
    SubElement(ide, "tpEmis").text = str(inv.emission_type or "1")
    SubElement(ide, "tpAmb").text = "1" if (inv.sefaz_environment or "homologation") == "production" else "2"

    emit = SubElement(inf, "emit")
    SubElement(emit, "xNome").text = company.name
    company_tax_id = (
        getattr(company, "tax_id", None)
        or getattr(company, "vat_number", None)
        or getattr(company, "registration_number", None)
    )
    if company_tax_id:
        normalized_tax_id = "".join(ch for ch in str(company_tax_id) if ch.isdigit())
        if len(normalized_tax_id) <= 11:
            SubElement(emit, "CPF").text = normalized_tax_id or str(company_tax_id)
        else:
            SubElement(emit, "CNPJ").text = normalized_tax_id or str(company_tax_id)
    end_emit = SubElement(emit, "enderEmit")
    SubElement(end_emit, "xLgr").text = company.address_line1 or ""
    SubElement(end_emit, "xMun").text = company.city or ""
    SubElement(end_emit, "UF").text = (company.state or "").upper()[:2] or "SP"
    SubElement(end_emit, "CEP").text = (company.postal_code or "").replace("-", "")[:8]
    SubElement(end_emit, "cPais").text = "1058"
    SubElement(end_emit, "xPais").text = "BRASIL"

    dest = SubElement(inf, "dest")
    SubElement(dest, "xNome").text = (cp.name if cp else "CONSUMIDOR FINAL")
    if cp and cp.tax_id:
        if len((cp.tax_id or "").strip()) <= 11:
            SubElement(dest, "CPF").text = cp.tax_id
        else:
            SubElement(dest, "CNPJ").text = cp.tax_id
    SubElement(dest, "indFinal").text = "1" if bool(inv.final_consumer) else "0"

    total_base = Decimal("0")
    total_icms = Decimal("0")
    total_ipi = Decimal("0")
    total_pis = Decimal("0")
    total_cofins = Decimal("0")

    for idx, ln in enumerate(inv.lines, start=1):
        det = SubElement(inf, "det", {"nItem": str(idx)})
        prod = SubElement(det, "prod")
        SubElement(prod, "cProd").text = str(idx)
        SubElement(prod, "xProd").text = ln.description
        SubElement(prod, "qCom").text = f"{_d(ln.quantity):.4f}"
        SubElement(prod, "vUnCom").text = f"{_d(ln.unit_price):.4f}"
        SubElement(prod, "vProd").text = f"{_d(ln.net_amount):.2f}"
        SubElement(prod, "NCM").text = str(getattr(ln, "ncm_code", None) or "00000000")
        SubElement(prod, "CFOP").text = str(getattr(ln, "cfop_code", None) or "5102")
        if getattr(ln, "cest_code", None):
            SubElement(prod, "CEST").text = str(ln.cest_code)

        imposto = SubElement(det, "imposto")
        base = _d(ln.net_amount)
        line_icms_rate = _d(getattr(ln, "icms_rate", None) if getattr(ln, "icms_rate", None) is not None else icms_rate)
        line_ipi_rate = _d(getattr(ln, "ipi_rate", None) if getattr(ln, "ipi_rate", None) is not None else ipi_rate)
        line_pis_rate = _d(getattr(ln, "pis_rate", None) if getattr(ln, "pis_rate", None) is not None else pis_rate)
        line_cofins_rate = _d(getattr(ln, "cofins_rate", None) if getattr(ln, "cofins_rate", None) is not None else cofins_rate)
        taxes = _compute_br_tax_components(base, line_icms_rate, line_ipi_rate, line_pis_rate, line_cofins_rate)

        line_icms_amount = _d(getattr(ln, "icms_amount", None)) if getattr(ln, "icms_amount", None) is not None else taxes["icms"]
        line_ipi_amount = _d(getattr(ln, "ipi_amount", None)) if getattr(ln, "ipi_amount", None) is not None else taxes["ipi"]
        line_pis_amount = _d(getattr(ln, "pis_amount", None)) if getattr(ln, "pis_amount", None) is not None else taxes["pis"]
        line_cofins_amount = _d(getattr(ln, "cofins_amount", None)) if getattr(ln, "cofins_amount", None) is not None else taxes["cofins"]

        icms = SubElement(imposto, "ICMS")
        icms00 = SubElement(icms, "ICMS00")
        SubElement(icms00, "orig").text = "0"
        SubElement(icms00, "CST").text = str(getattr(ln, "cst_icms", None) or "00")
        SubElement(icms00, "vBC").text = f"{base:.2f}"
        SubElement(icms00, "pICMS").text = f"{line_icms_rate:.2f}"
        SubElement(icms00, "vICMS").text = f"{line_icms_amount:.2f}"

        ipi = SubElement(imposto, "IPI")
        ipitrib = SubElement(ipi, "IPITrib")
        SubElement(ipitrib, "CST").text = str(getattr(ln, "cst_ipi", None) or "50")
        SubElement(ipitrib, "vBC").text = f"{base:.2f}"
        SubElement(ipitrib, "pIPI").text = f"{line_ipi_rate:.2f}"
        SubElement(ipitrib, "vIPI").text = f"{line_ipi_amount:.2f}"

        pis = SubElement(imposto, "PIS")
        pisaliq = SubElement(pis, "PISAliq")
        SubElement(pisaliq, "CST").text = str(getattr(ln, "cst_pis", None) or "01")
        SubElement(pisaliq, "vBC").text = f"{base:.2f}"
        SubElement(pisaliq, "pPIS").text = f"{line_pis_rate:.2f}"
        SubElement(pisaliq, "vPIS").text = f"{line_pis_amount:.2f}"

        cofins = SubElement(imposto, "COFINS")
        cofinsaliq = SubElement(cofins, "COFINSAliq")
        SubElement(cofinsaliq, "CST").text = str(getattr(ln, "cst_cofins", None) or "01")
        SubElement(cofinsaliq, "vBC").text = f"{base:.2f}"
        SubElement(cofinsaliq, "pCOFINS").text = f"{line_cofins_rate:.2f}"
        SubElement(cofinsaliq, "vCOFINS").text = f"{line_cofins_amount:.2f}"

        total_base += base
        total_icms += line_icms_amount
        total_ipi += line_ipi_amount
        total_pis += line_pis_amount
        total_cofins += line_cofins_amount

    total = SubElement(inf, "total")
    icmstot = SubElement(total, "ICMSTot")
    SubElement(icmstot, "vBC").text = f"{total_base:.2f}"
    SubElement(icmstot, "vICMS").text = f"{total_icms:.2f}"
    SubElement(icmstot, "vIPI").text = f"{total_ipi:.2f}"
    SubElement(icmstot, "vPIS").text = f"{total_pis:.2f}"
    SubElement(icmstot, "vCOFINS").text = f"{total_cofins:.2f}"
    SubElement(icmstot, "vProd").text = f"{total_base:.2f}"
    vnf = (total_base + total_icms + total_ipi + total_pis + total_cofins).quantize(Decimal("0.01"))
    SubElement(icmstot, "vNF").text = f"{vnf:.2f}"

    return tostring(root, encoding="utf-8", xml_declaration=True)


def build_invoice_export_zip(
    *,
    inv: FinanceInvoice,
    company: FinanceCompany,
    cp: FinanceCounterparty | None,
    country: str,
    logo_path: str | None = None,
) -> Tuple[str, bytes]:
    """Return (filename, zip_bytes). country in {'fr','it','br'}"""
    pdf = build_invoice_pdf_bytes(inv, company, cp, logo_path=logo_path)
    c = (country or "fr").lower()
    if c == "fr":
        xml = build_facturx_cii_xml_bytes(inv, company, cp)
        xml_name = f"invoice_{inv.invoice_number}_facturx.xml"
        zip_name = f"invoice_{inv.invoice_number}_FR.zip"
    elif c == "it":
        xml = build_fatturapa_xml_bytes(inv, company, cp)
        xml_name = f"invoice_{inv.invoice_number}_fatturapa.xml"
        zip_name = f"invoice_{inv.invoice_number}_IT.zip"
    else:
        xml = build_nfe_br_xml_bytes(inv, company, cp)
        xml_name = f"invoice_{inv.invoice_number}_nfe_br.xml"
        zip_name = f"invoice_{inv.invoice_number}_BR.zip"

    out = BytesIO()
    with zipfile.ZipFile(out, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"invoice_{inv.invoice_number}.pdf", pdf)
        z.writestr(xml_name, xml)

    return zip_name, out.getvalue()
