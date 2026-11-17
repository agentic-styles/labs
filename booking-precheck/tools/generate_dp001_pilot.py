from __future__ import annotations

import json
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(os.environ.get("BOOKING_PRECHECK_MATERIALS_ROOT", Path(__file__).resolve().parents[1] / "assets")).resolve()
PACK_DIR = ROOT / "document-packs" / "DP-001"
SOURCE_DIR = PACK_DIR / "source"
PDF_DIR = PACK_DIR / "output" / "pdf"
CASE_PATH = ROOT / "cases" / "TC-001" / "input.json"

NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#2F75B5")
PALE_BLUE = colors.HexColor("#D9EAF7")
PALE_GRAY = colors.HexColor("#F3F5F7")
DARK_GRAY = colors.HexColor("#344054")
GREEN = colors.HexColor("#1F7A4C")


def load_case() -> dict:
    return json.loads(CASE_PATH.read_text(encoding="utf-8"))


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=23,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=DARK_GRAY,
            spaceAfter=10,
        ),
        "section": ParagraphStyle(
            "section",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=NAVY,
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=DARK_GRAY,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=DARK_GRAY,
        ),
        "center": ParagraphStyle(
            "center",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            alignment=TA_CENTER,
            textColor=NAVY,
        ),
    }


STYLES = styles()


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D0D5DD"))
    canvas.line(18 * mm, 14 * mm, 192 * mm, 14 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(18 * mm, 9 * mm, "TRAINING-LINE synthetic workshop document - not valid for operational use")
    canvas.drawRightString(192 * mm, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


def make_doc(path: Path, title: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    return SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=19 * mm,
        title=title,
        author="TRAINING-LINE Workshop",
        subject="Synthetic booking precheck training document",
    )


def field_table(rows, widths=(58 * mm, 112 * mm), header=None):
    data = []
    if header:
        data.append([Paragraph(header[0], STYLES["small"]), Paragraph(header[1], STYLES["small"])])
    data.extend(
        [[Paragraph(str(k), STYLES["small"]), Paragraph(str(v), STYLES["small"])] for k, v in rows]
    )
    table = Table(data, colWidths=list(widths), repeatRows=1 if header else 0)
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#B8C2CC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (0, -1), PALE_GRAY),
        ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def banner(text):
    t = Table([[Paragraph(text, STYLES["center"])]], colWidths=[170 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.8, BLUE),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def booking_markdown(case):
    b = case["documents"]["booking_request"]
    c = b["cargo"]
    r = b["route"]
    parties = {p["role"]: p for p in b["parties"]}
    return f"""# Synthetic Booking Request - DP-001

Training data only. Not valid for a real booking.

## Booking and voyage

- Booking Reference: {b['booking_reference']}
- Carrier: {b['carrier_code']}
- Vessel Operator: {b['vessel_operator_code']}
- Service: {b['service_code']}
- POL: {r['port_of_loading']['unlocode']} / {r['port_of_loading']['facility_code']}
- POD: {r['port_of_discharge']['unlocode']} / {r['port_of_discharge']['facility_code']}
- ETD: {r['etd']}
- ETA: {r['eta']}
- Equipment: {b['equipment']['quantity']} x {b['equipment']['container_type']}

## Parties

- Shipper: {parties['SHIPPER']['name']} ({parties['SHIPPER']['country_code']})
- Consignee: {parties['CONSIGNEE']['name']} ({parties['CONSIGNEE']['country_code']})

## Cargo

- Description: {c['description']}
- Commodity Code: {c['commodity_code']}
- UN Number: {c['un_number']}
- Proper Shipping Name: {c['proper_shipping_name']}
- IMDG Class: {c['imdg_class']}
- Packing Group: {c['packing_group']}
- Marine Pollutant: {str(c['marine_pollutant']).lower()}
- Packages: {c['total_packages']} {c['package_type']}
- Net Weight: {c['net_weight_kg']} KGS
- Gross Weight: {c['gross_weight_kg']} KGS
"""


def dgd_markdown(case):
    d = case["documents"]["dgd"]
    c = d["declaration"]
    return f"""# Synthetic Preliminary Dangerous Goods Declaration - DP-001

Training data only. Not a legal dangerous-goods declaration.

- Document ID: {d['metadata']['document_id']}
- Document Version: {d['metadata']['document_version']}
- Booking Reference: {d['booking_reference']}
- UN Number: {c['un_number']}
- Proper Shipping Name: {c['proper_shipping_name']}
- IMDG Class: {c['imdg_class']}
- Packing Group: {c['packing_group']}
- Marine Pollutant: {str(c['marine_pollutant']).lower()}
- Packages: {c['total_packages']} {c['package_type']}
- Net Weight: {c['net_weight_kg']} KGS
- Gross Weight: {c['gross_weight_kg']} KGS
- Shipper Declaration Signed: {'YES' if d['shipper_declaration_signed'] else 'NO'}
"""


def sds_markdown(case):
    s = case["documents"]["sds"]
    t = s["transport_information"]
    return f"""# Synthetic SDS Extract - DP-001

Training excerpt only. Not a complete Safety Data Sheet.

## Section 1 - Identification

- Product Name: {s['product_name']}
- Manufacturer: {s['manufacturer']}
- Issue Date: {s['metadata']['issued_at']}

## Section 9 - Physical and Chemical Properties

- Flash Point: {s['physical_properties']['flash_point_c']} deg C

## Section 14 - Transport Information

- UN Number: {t['un_number']}
- Proper Shipping Name: {t['proper_shipping_name']}
- IMDG Class: {t['imdg_class']}
- Packing Group: {t['packing_group']}
- Marine Pollutant: {str(t['marine_pollutant']).lower()}
"""


def build_booking_pdf(case):
    b = case["documents"]["booking_request"]
    c = b["cargo"]
    r = b["route"]
    parties = {p["role"]: p for p in b["parties"]}
    story = [
        Paragraph("TRAINING-LINE", STYLES["subtitle"]),
        Paragraph("Booking Request", STYLES["title"]),
        banner("SYNTHETIC TRAINING DOCUMENT - DP-001"),
        Paragraph("Booking and voyage", STYLES["section"]),
        field_table(
            [
                ("Booking Reference", b["booking_reference"]),
                ("Carrier", b["carrier_code"]),
                ("Vessel Operator", b["vessel_operator_code"]),
                ("Service", b["service_code"]),
                ("Port of Loading", f"{r['port_of_loading']['unlocode']} / {r['port_of_loading']['facility_code']}"),
                ("Port of Discharge", f"{r['port_of_discharge']['unlocode']} / {r['port_of_discharge']['facility_code']}"),
                ("ETD", r["etd"]),
                ("ETA", r["eta"]),
                ("Equipment", f"{b['equipment']['quantity']} x {b['equipment']['container_type']}"),
            ]
        ),
        Paragraph("Parties", STYLES["section"]),
        field_table(
            [
                ("Shipper", f"{parties['SHIPPER']['name']} - {parties['SHIPPER']['country_code']}"),
                ("Consignee", f"{parties['CONSIGNEE']['name']} - {parties['CONSIGNEE']['country_code']}"),
            ]
        ),
        Paragraph("Cargo declaration", STYLES["section"]),
        field_table(
            [
                ("Description", c["description"]),
                ("Commodity Code", c["commodity_code"]),
                ("Dangerous Goods", "YES"),
                ("UN Number", c["un_number"]),
                ("Proper Shipping Name", c["proper_shipping_name"]),
                ("IMDG Class / Packing Group", f"{c['imdg_class']} / {c['packing_group']}"),
                ("Marine Pollutant", str(c["marine_pollutant"]).upper()),
                ("Packages", f"{c['total_packages']} {c['package_type']}"),
                ("Net Weight", f"{c['net_weight_kg']} KGS"),
                ("Gross Weight", f"{c['gross_weight_kg']} KGS"),
            ]
        ),
    ]
    make_doc(PDF_DIR / "booking-request.pdf", "Synthetic Booking Request DP-001").build(
        story, onFirstPage=footer, onLaterPages=footer
    )


def build_dgd_pdf(case):
    d = case["documents"]["dgd"]
    c = d["declaration"]
    description = f"{c['un_number']} {c['proper_shipping_name']}, {c['imdg_class']}, PG {c['packing_group']}"
    story = [
        Paragraph("TRAINING-LINE", STYLES["subtitle"]),
        Paragraph("Preliminary Dangerous Goods Declaration", STYLES["title"]),
        banner("SYNTHETIC TRAINING DOCUMENT - NOT A LEGAL DECLARATION"),
        Paragraph("Document control", STYLES["section"]),
        field_table(
            [
                ("Document ID", d["metadata"]["document_id"]),
                ("Document Version", d["metadata"]["document_version"]),
                ("Issue Date", d["metadata"]["issued_at"]),
                ("Booking Reference", d["booking_reference"]),
            ]
        ),
        Paragraph("Dangerous goods description", STYLES["section"]),
        field_table(
            [
                ("Transport Description", description),
                ("UN Number", c["un_number"]),
                ("Proper Shipping Name", c["proper_shipping_name"]),
                ("IMDG Class", c["imdg_class"]),
                ("Packing Group", c["packing_group"]),
                ("Marine Pollutant", str(c["marine_pollutant"]).upper()),
                ("Number and Type of Packages", f"{c['total_packages']} {c['package_type']}"),
                ("Net Weight", f"{c['net_weight_kg']} KGS"),
                ("Gross Weight", f"{c['gross_weight_kg']} KGS"),
            ]
        ),
        Paragraph("Shipper declaration", STYLES["section"]),
        Paragraph(
            "I declare that the contents of this synthetic training consignment are fully and accurately described for workshop use.",
            STYLES["body"],
        ),
        Spacer(1, 5 * mm),
        field_table(
            [
                ("Declaration Status", "SIGNED" if d["shipper_declaration_signed"] else "NOT SIGNED"),
                ("Signed By", "SYNTHETIC SHANGHAI CHEMICAL CO"),
                ("Signature Date", d["metadata"]["issued_at"]),
            ]
        ),
    ]
    make_doc(PDF_DIR / "preliminary-dgd.pdf", "Synthetic Preliminary DGD DP-001").build(
        story, onFirstPage=footer, onLaterPages=footer
    )


def build_sds_pdf(case):
    s = case["documents"]["sds"]
    t = s["transport_information"]
    story = [
        Paragraph("Synthetic Safety Data Sheet Extract", STYLES["title"]),
        banner("TRAINING EXCERPT ONLY - NOT A COMPLETE SAFETY DATA SHEET"),
        Paragraph("Section 1 - Identification", STYLES["section"]),
        field_table(
            [
                ("Product Name", s["product_name"]),
                ("Manufacturer", s["manufacturer"]),
                ("Issue Date", s["metadata"]["issued_at"]),
                ("Recommended Use", "Synthetic coating material for workshop demonstration"),
            ]
        ),
        Paragraph("Section 9 - Physical and Chemical Properties", STYLES["section"]),
        field_table(
            [
                ("Appearance", "Colored liquid"),
                ("Odor", "Solvent-like"),
                ("Flash Point", f"{s['physical_properties']['flash_point_c']} deg C"),
                ("Relative Density", "0.95 - synthetic training value"),
            ]
        ),
        Paragraph("Training notice", STYLES["section"]),
        Paragraph(
            "Sections not shown in this extract are outside the scope of the booking precheck workshop. "
            "This document must not be used for workplace safety or transport decisions.",
            STYLES["body"],
        ),
        PageBreak(),
        Paragraph("Synthetic Safety Data Sheet Extract", STYLES["title"]),
        Paragraph("Section 14 - Transport Information", STYLES["section"]),
        field_table(
            [
                ("UN Number", t["un_number"]),
                ("UN Proper Shipping Name", t["proper_shipping_name"]),
                ("Transport Hazard Class", t["imdg_class"]),
                ("Packing Group", t["packing_group"]),
                ("Marine Pollutant", str(t["marine_pollutant"]).upper()),
                ("Transport Mode", "Sea - synthetic workshop scope"),
            ]
        ),
        Spacer(1, 7 * mm),
        Paragraph("Document control", STYLES["section"]),
        field_table(
            [
                ("Document ID", s["metadata"]["document_id"]),
                ("Document Version", s["metadata"]["document_version"]),
                ("Language", s["metadata"]["language"]),
                ("Synthetic", "YES"),
            ]
        ),
    ]
    make_doc(PDF_DIR / "sds-extract.pdf", "Synthetic SDS Extract DP-001").build(
        story, onFirstPage=footer, onLaterPages=footer
    )


def truth_fact(path, value, page, evidence, section, normalization=None):
    item = {
        "fact_path": path,
        "expected_value": value,
        "normalization": normalization or [],
        "evidence": {
            "page": page,
            "section": section,
            "evidence_text": evidence,
        },
    }
    return item


def build_ground_truth(case):
    b = case["documents"]["booking_request"]
    c = b["cargo"]
    r = b["route"]
    d = case["documents"]["dgd"]
    dc = d["declaration"]
    s = case["documents"]["sds"]
    st = s["transport_information"]
    truth = {
        "schema_version": "0.1",
        "pack_id": "DP-001",
        "case_ref": "TC-001",
        "documents": [
            {
                "document_id": b["metadata"]["document_id"],
                "document_type": "BOOKING_REQUEST",
                "document_version": 1,
                "source_path": "output/pdf/booking-request.pdf",
                "expected_page_count": 1,
                "text_layer_required": True,
                "facts": [
                    truth_fact("documents.booking_request.carrier_code", b["carrier_code"], 1, b["carrier_code"], "Booking and voyage"),
                    truth_fact("documents.booking_request.vessel_operator_code", b["vessel_operator_code"], 1, b["vessel_operator_code"], "Booking and voyage"),
                    truth_fact("documents.booking_request.service_code", b["service_code"], 1, b["service_code"], "Booking and voyage"),
                    truth_fact("documents.booking_request.route.port_of_loading.unlocode", r["port_of_loading"]["unlocode"], 1, r["port_of_loading"]["unlocode"], "Booking and voyage"),
                    truth_fact("documents.booking_request.route.port_of_discharge.unlocode", r["port_of_discharge"]["unlocode"], 1, r["port_of_discharge"]["unlocode"], "Booking and voyage"),
                    truth_fact("documents.booking_request.route.etd", r["etd"], 1, r["etd"], "Booking and voyage", ["DATE_TO_ISO"]),
                    truth_fact("documents.booking_request.route.eta", r["eta"], 1, r["eta"], "Booking and voyage", ["DATE_TO_ISO"]),
                    truth_fact("documents.booking_request.cargo.un_number", c["un_number"], 1, c["un_number"], "Cargo declaration", ["UN_NUMBER_CANONICAL"]),
                    truth_fact("documents.booking_request.cargo.proper_shipping_name", c["proper_shipping_name"], 1, c["proper_shipping_name"], "Cargo declaration", ["PSN_CANONICAL"]),
                    truth_fact("documents.booking_request.cargo.imdg_class", c["imdg_class"], 1, c["imdg_class"], "Cargo declaration"),
                    truth_fact("documents.booking_request.cargo.packing_group", c["packing_group"], 1, c["packing_group"], "Cargo declaration"),
                    truth_fact("documents.booking_request.cargo.total_packages", c["total_packages"], 1, f"{c['total_packages']} {c['package_type']}", "Cargo declaration"),
                    truth_fact("documents.booking_request.cargo.gross_weight_kg", c["gross_weight_kg"], 1, f"{c['gross_weight_kg']} KGS", "Cargo declaration", ["UNIT_TO_KG"]),
                    truth_fact("documents.booking_request.equipment.container_type", b["equipment"]["container_type"], 1, b["equipment"]["container_type"], "Booking and voyage"),
                ],
            },
            {
                "document_id": d["metadata"]["document_id"],
                "document_type": "PRELIMINARY_DGD",
                "document_version": 1,
                "source_path": "output/pdf/preliminary-dgd.pdf",
                "expected_page_count": 1,
                "text_layer_required": True,
                "facts": [
                    truth_fact("documents.dgd.declaration.un_number", dc["un_number"], 1, dc["un_number"], "Dangerous goods description", ["UN_NUMBER_CANONICAL"]),
                    truth_fact("documents.dgd.declaration.proper_shipping_name", dc["proper_shipping_name"], 1, dc["proper_shipping_name"], "Dangerous goods description", ["PSN_CANONICAL"]),
                    truth_fact("documents.dgd.declaration.imdg_class", dc["imdg_class"], 1, dc["imdg_class"], "Dangerous goods description"),
                    truth_fact("documents.dgd.declaration.packing_group", dc["packing_group"], 1, dc["packing_group"], "Dangerous goods description"),
                    truth_fact("documents.dgd.declaration.marine_pollutant", dc["marine_pollutant"], 1, str(dc["marine_pollutant"]).upper(), "Dangerous goods description"),
                    truth_fact("documents.dgd.declaration.total_packages", dc["total_packages"], 1, f"{dc['total_packages']} {dc['package_type']}", "Dangerous goods description"),
                    truth_fact("documents.dgd.declaration.gross_weight_kg", dc["gross_weight_kg"], 1, f"{dc['gross_weight_kg']} KGS", "Dangerous goods description", ["UNIT_TO_KG"]),
                    truth_fact("documents.dgd.shipper_declaration_signed", d["shipper_declaration_signed"], 1, "SIGNED", "Shipper declaration"),
                ],
            },
            {
                "document_id": s["metadata"]["document_id"],
                "document_type": "SDS_EXTRACT",
                "document_version": 1,
                "source_path": "output/pdf/sds-extract.pdf",
                "expected_page_count": 2,
                "text_layer_required": True,
                "facts": [
                    truth_fact("documents.sds.product_name", s["product_name"], 1, s["product_name"], "Section 1"),
                    truth_fact("documents.sds.metadata.issued_at", s["metadata"]["issued_at"], 1, s["metadata"]["issued_at"], "Section 1", ["DATE_TO_ISO"]),
                    truth_fact("documents.sds.physical_properties.flash_point_c", s["physical_properties"]["flash_point_c"], 1, f"{s['physical_properties']['flash_point_c']} deg C", "Section 9"),
                    truth_fact("documents.sds.transport_information.un_number", st["un_number"], 2, st["un_number"], "Section 14", ["UN_NUMBER_CANONICAL"]),
                    truth_fact("documents.sds.transport_information.proper_shipping_name", st["proper_shipping_name"], 2, st["proper_shipping_name"], "Section 14", ["PSN_CANONICAL"]),
                    truth_fact("documents.sds.transport_information.imdg_class", st["imdg_class"], 2, st["imdg_class"], "Section 14"),
                    truth_fact("documents.sds.transport_information.packing_group", st["packing_group"], 2, st["packing_group"], "Section 14"),
                    truth_fact("documents.sds.transport_information.marine_pollutant", st["marine_pollutant"], 2, str(st["marine_pollutant"]).upper(), "Section 14"),
                ],
            },
        ],
    }
    (PACK_DIR / "ground-truth.json").write_text(
        json.dumps(truth, indent=2) + "\n", encoding="utf-8"
    )


def main():
    case = load_case()
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    (SOURCE_DIR / "booking-request.md").write_text(booking_markdown(case), encoding="utf-8")
    (SOURCE_DIR / "preliminary-dgd.md").write_text(dgd_markdown(case), encoding="utf-8")
    (SOURCE_DIR / "sds-extract.md").write_text(sds_markdown(case), encoding="utf-8")
    build_booking_pdf(case)
    build_dgd_pdf(case)
    build_sds_pdf(case)
    build_ground_truth(case)


if __name__ == "__main__":
    main()
