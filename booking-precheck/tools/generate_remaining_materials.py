from __future__ import annotations

import copy
import html
import json
import os
from pathlib import Path

import pdfplumber
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(os.environ.get("BOOKING_PRECHECK_MATERIALS_ROOT", Path(__file__).resolve().parents[1] / "assets")).resolve()
PACKS_DIR = ROOT / "document-packs"
POLICY_DIR = ROOT / "policy-documents"
SNAPSHOT_PATH = ROOT / "policy_snapshot.json"

NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#2F75B5")
PALE_BLUE = colors.HexColor("#D9EAF7")
PALE_GRAY = colors.HexColor("#F3F5F7")
DARK_GRAY = colors.HexColor("#344054")
RED = colors.HexColor("#B42318")


def make_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=18, leading=22, textColor=NAVY, spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"], fontName="Helvetica",
            fontSize=8.5, leading=11, textColor=DARK_GRAY, spaceAfter=9,
        ),
        "section": ParagraphStyle(
            "section", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=10.5, leading=13, textColor=NAVY, spaceBefore=7, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName="Helvetica",
            fontSize=8.5, leading=11, textColor=DARK_GRAY,
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"], fontName="Helvetica",
            fontSize=7.4, leading=9.5, textColor=DARK_GRAY,
        ),
        "small_white": ParagraphStyle(
            "small_white", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=7.4, leading=9.5, textColor=colors.white,
        ),
        "notice": ParagraphStyle(
            "notice", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=8.5, leading=11, textColor=RED,
        ),
    }


STYLES = make_styles()


def esc(value) -> str:
    if value is None or value == "":
        return "NOT PROVIDED"
    if isinstance(value, bool):
        return "YES" if value else "NO"
    return html.escape(str(value))


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D0D5DD"))
    canvas.line(18 * mm, 14 * mm, 192 * mm, 14 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(18 * mm, 9 * mm, "TRAINING-LINE synthetic workshop material - not for operational use")
    canvas.drawRightString(192 * mm, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


def make_doc(path: Path, title: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    return SimpleDocTemplate(
        str(path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=17 * mm, bottomMargin=19 * mm, title=title,
        author="TRAINING-LINE Workshop", subject="Synthetic booking precheck workshop material",
    )


def banner(text: str, color=BLUE):
    table = Table([[Paragraph(esc(text), STYLES["small_white"])]], colWidths=[174 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("BOX", (0, 0), (-1, -1), 0.8, color),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def field_table(rows, variant="A", widths=(57 * mm, 117 * mm)):
    data = [[Paragraph(esc(k), STYLES["small"]), Paragraph(esc(v), STYLES["small"])] for k, v in rows]
    table = Table(data, colWidths=list(widths))
    label_color = PALE_GRAY if variant == "A" else PALE_BLUE
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#B8C2CC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (0, -1), label_color),
        ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
    ]))
    return table


def json_pointer_apply(document: dict, mutation: dict):
    parts = [p.replace("~1", "/").replace("~0", "~") for p in mutation["path"].split("/")[1:]]
    target = document
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    key = parts[-1]
    if mutation["op"] in {"add", "replace"}:
        if isinstance(target, list):
            if key == "-":
                target.append(copy.deepcopy(mutation["value"]))
            elif mutation["op"] == "add":
                target.insert(int(key), copy.deepcopy(mutation["value"]))
            else:
                target[int(key)] = copy.deepcopy(mutation["value"])
        else:
            target[key] = copy.deepcopy(mutation["value"])
    elif mutation["op"] == "remove":
        if isinstance(target, list):
            target.pop(int(key))
        else:
            target.pop(key, None)
    else:
        raise ValueError(f"Unsupported patch operation: {mutation['op']}")


def load_fixture_for_stage(manifest: dict, stage: dict) -> dict:
    fixture_path = (PACKS_DIR / manifest["pack_id"] / manifest["canonical_fixture_path"]).resolve()
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if manifest["case_ref"].startswith("TC-"):
        return fixture
    base_path = (fixture_path.parent / fixture["base_fixture_path"]).resolve()
    materialized = json.loads(base_path.read_text(encoding="utf-8"))
    step_id = stage.get("business_step_id", stage["stage_id"])
    step = next(item for item in fixture["steps"] if item["step_id"] == step_id)
    for mutation in step.get("mutations", []):
        json_pointer_apply(materialized, mutation)
    return materialized


def markdown_for(document_type: str, data: dict, pack_id: str, stage_id: str) -> str:
    heading = f"# Synthetic {document_type.replace('_', ' ').title()} - {pack_id} {stage_id}\n\n"
    notice = "Training data only. Not valid for operational use.\n\n"
    if document_type == "BOOKING_REQUEST":
        cargo, route = data["cargo"], data["route"]
        parties = {p["role"]: p for p in data.get("parties", [])}
        rows = [
            ("Booking Reference", data["booking_reference"]), ("Carrier", data["carrier_code"]),
            ("Vessel Operator", data["vessel_operator_code"]), ("Service", data["service_code"]),
            ("POL", f"{route['port_of_loading']['unlocode']} / {route['port_of_loading']['facility_code']}"),
            ("POD", f"{route['port_of_discharge']['unlocode']} / {route['port_of_discharge']['facility_code']}"),
            ("ETD", route["etd"]), ("ETA", route["eta"]),
            ("Shipper", parties.get("SHIPPER", {}).get("name")),
            ("Consignee", parties.get("CONSIGNEE", {}).get("name")),
            ("UN Number", cargo.get("un_number")), ("Proper Shipping Name", cargo.get("proper_shipping_name")),
            ("IMDG Class", cargo.get("imdg_class")), ("Packing Group", cargo.get("packing_group")),
            ("Packages", f"{cargo.get('total_packages')} {cargo.get('package_type')}"),
            ("Gross Weight", f"{cargo.get('gross_weight_kg')} KGS"),
        ]
    elif document_type == "PRELIMINARY_DGD":
        cargo = data["declaration"]
        rows = [
            ("Document ID", data["metadata"]["document_id"]), ("Booking Reference", data["booking_reference"]),
            ("UN Number", cargo.get("un_number")), ("Proper Shipping Name", cargo.get("proper_shipping_name")),
            ("IMDG Class", cargo.get("imdg_class")), ("Packing Group", cargo.get("packing_group")),
            ("Marine Pollutant", cargo.get("marine_pollutant")),
            ("Packages", f"{cargo.get('total_packages')} {cargo.get('package_type')}"),
            ("Gross Weight", f"{cargo.get('gross_weight_kg')} KGS"),
            ("Shipper Declaration Signed", data.get("shipper_declaration_signed")),
        ]
    else:
        transport = data.get("transport_information") or {}
        physical = data.get("physical_properties") or {}
        rows = [
            ("Product Name", data.get("product_name")), ("Manufacturer", data.get("manufacturer")),
            ("Issue Date", data["metadata"].get("issued_at")),
            ("Flash Point", f"{physical.get('flash_point_c')} deg C" if physical.get("flash_point_c") is not None else None),
            ("UN Number", transport.get("un_number")), ("Proper Shipping Name", transport.get("proper_shipping_name")),
            ("IMDG Class", transport.get("imdg_class")), ("Packing Group", transport.get("packing_group")),
            ("Marine Pollutant", transport.get("marine_pollutant")),
        ]
    body = "\n".join(f"- {key}: {esc(value)}" for key, value in rows)
    return heading + notice + body + "\n"


def build_booking_pdf(data: dict, path: Path, pack_id: str, stage_id: str, variant: str):
    cargo, route = data["cargo"], data["route"]
    parties = {p["role"]: p for p in data.get("parties", [])}
    is_email = variant.endswith("B")
    story = [
        Paragraph("TRAINING-LINE", STYLES["subtitle"]),
        Paragraph("Booking Request" if not is_email else "Booking Instruction Email", STYLES["title"]),
        banner(f"SYNTHETIC TRAINING DOCUMENT - {pack_id} / {stage_id}"),
    ]
    if is_email:
        story.extend([
            Paragraph("Message header", STYLES["section"]),
            field_table([
                ("From", "synthetic.shipper@example.training"),
                ("To", "booking.desk@example.training"),
                ("Subject", f"Booking request {data['booking_reference']}"),
                ("Received", data["metadata"].get("issued_at")),
            ], "B"),
        ])
    story.extend([
        Paragraph("Booking and voyage", STYLES["section"]),
        field_table([
            ("Booking Reference", data["booking_reference"]), ("Carrier", data["carrier_code"]),
            ("Vessel Operator", data["vessel_operator_code"]), ("Service", data["service_code"]),
            ("Port of Loading", f"{route['port_of_loading']['unlocode']} / {route['port_of_loading']['facility_code']}"),
            ("Port of Discharge", f"{route['port_of_discharge']['unlocode']} / {route['port_of_discharge']['facility_code']}"),
            ("ETD", route["etd"]), ("ETA", route["eta"]),
            ("Equipment", f"{data['equipment']['quantity']} x {data['equipment']['container_type']}"),
        ], "B" if is_email else "A"),
        Paragraph("Parties", STYLES["section"]),
        field_table([
            ("Shipper", parties.get("SHIPPER", {}).get("name")),
            ("Consignee", parties.get("CONSIGNEE", {}).get("name")),
        ], "B" if is_email else "A"),
        Paragraph("Cargo declaration", STYLES["section"]),
        field_table([
            ("Description", cargo.get("description")), ("Commodity Code", cargo.get("commodity_code")),
            ("Dangerous Goods", cargo.get("is_dangerous_goods")), ("UN Number", cargo.get("un_number")),
            ("Proper Shipping Name", cargo.get("proper_shipping_name")),
            ("IMDG Class", cargo.get("imdg_class")), ("Packing Group", cargo.get("packing_group")),
            ("Marine Pollutant", cargo.get("marine_pollutant")),
            ("Packages", f"{cargo.get('total_packages')} {cargo.get('package_type')}"),
            ("Net Weight", f"{cargo.get('net_weight_kg')} KGS"),
            ("Gross Weight", f"{cargo.get('gross_weight_kg')} KGS"),
        ], "B" if is_email else "A"),
    ])
    make_doc(path, f"Synthetic Booking Request {pack_id} {stage_id}").build(story, onFirstPage=footer, onLaterPages=footer)


def build_dgd_pdf(data: dict, path: Path, pack_id: str, stage_id: str, variant: str):
    cargo = data["declaration"]
    signed = data.get("shipper_declaration_signed")
    status = "SIGNED" if signed else "NOT SIGNED"
    story = [
        Paragraph("TRAINING-LINE", STYLES["subtitle"]),
        Paragraph("Preliminary Dangerous Goods Declaration", STYLES["title"]),
        banner(f"SYNTHETIC TRAINING FORM - {pack_id} / {stage_id}", RED if not signed else BLUE),
        Paragraph("Document control", STYLES["section"]),
        field_table([
            ("Document ID", data["metadata"]["document_id"]),
            ("Document Version", data["metadata"].get("document_version", 1)),
            ("Issue Date", data["metadata"].get("issued_at")),
            ("Booking Reference", data["booking_reference"]),
        ], "B" if variant.endswith("B") else "A"),
        Paragraph("Dangerous goods description", STYLES["section"]),
        field_table([
            ("UN Number", cargo.get("un_number")), ("Proper Shipping Name", cargo.get("proper_shipping_name")),
            ("IMDG Class", cargo.get("imdg_class")), ("Packing Group", cargo.get("packing_group")),
            ("Marine Pollutant", cargo.get("marine_pollutant")),
            ("Number and Type of Packages", f"{cargo.get('total_packages')} {cargo.get('package_type')}"),
            ("Net Weight", f"{cargo.get('net_weight_kg')} KGS"),
            ("Gross Weight", f"{cargo.get('gross_weight_kg')} KGS"),
        ], "B" if variant.endswith("B") else "A"),
        Paragraph("Shipper declaration", STYLES["section"]),
        Paragraph("The contents are declared for synthetic workshop use only.", STYLES["body"]),
        Spacer(1, 3 * mm),
        field_table([
            ("Declaration Status", status),
            ("Signed By", "SYNTHETIC SHANGHAI CHEMICAL CO" if signed else None),
            ("Signature Date", data["metadata"].get("issued_at") if signed else None),
        ], "B" if variant.endswith("B") else "A"),
    ]
    make_doc(path, f"Synthetic Preliminary DGD {pack_id} {stage_id}").build(story, onFirstPage=footer, onLaterPages=footer)


def build_sds_pdf(data: dict, path: Path, pack_id: str, stage_id: str, variant: str):
    transport = data.get("transport_information") or {}
    physical = data.get("physical_properties") or {}
    is_b = variant.endswith("B")
    story = [
        Paragraph("Synthetic Safety Data Sheet Extract", STYLES["title"]),
        banner(f"TRAINING EXCERPT ONLY - {pack_id} / {stage_id}"),
        Paragraph("Section 1 - Identification", STYLES["section"]),
        field_table([
            ("Product Name", data.get("product_name")), ("Manufacturer", data.get("manufacturer")),
            ("Issue Date", data["metadata"].get("issued_at")),
            ("Recommended Use", "Synthetic workshop demonstration material"),
        ], "B" if is_b else "A"),
        Paragraph("Section 9 - Physical and Chemical Properties", STYLES["section"]),
        field_table([
            ("Appearance", "Colored liquid" if transport.get("imdg_class") == "3" else "Synthetic packaged material"),
            ("Flash Point", f"{physical.get('flash_point_c')} deg C" if physical.get("flash_point_c") is not None else None),
            ("Relative Density", "0.95 - synthetic training value"),
        ], "B" if is_b else "A"),
        Paragraph("Training notice", STYLES["section"]),
        Paragraph("Sections not shown are outside the workshop scope. Do not use this extract for safety or transport decisions.", STYLES["body"]),
        PageBreak(),
        Paragraph("Synthetic Safety Data Sheet Extract", STYLES["title"]),
        Paragraph("Section 14 - Transport Information", STYLES["section"]),
        field_table([
            ("UN Number", transport.get("un_number")),
            ("UN Proper Shipping Name", transport.get("proper_shipping_name")),
            ("Transport Hazard Class", transport.get("imdg_class")),
            ("Packing Group", transport.get("packing_group")),
            ("Marine Pollutant", transport.get("marine_pollutant")),
            ("Transport Mode", "Sea - synthetic workshop scope"),
        ], "B" if is_b else "A"),
        Spacer(1, 6 * mm),
        Paragraph("Document control", STYLES["section"]),
        field_table([
            ("Document ID", data["metadata"]["document_id"]),
            ("Document Version", data["metadata"].get("document_version", 1)),
            ("Language", data["metadata"].get("language", "en")), ("Synthetic", True),
        ], "B" if is_b else "A"),
    ]
    make_doc(path, f"Synthetic SDS Extract {pack_id} {stage_id}").build(story, onFirstPage=footer, onLaterPages=footer)


def truth_fact(path, value, page, evidence, section, normalization=None):
    return {
        "fact_path": path, "expected_value": value, "normalization": normalization or [],
        "evidence": {"page": page, "section": section, "evidence_text": esc(evidence)},
    }


def truth_for_document(document_type: str, data: dict, source_path: str, stage_id: str):
    metadata = data["metadata"]
    facts = []
    page_count = 1
    if document_type == "BOOKING_REQUEST":
        cargo, route = data["cargo"], data["route"]
        parties = {p["role"]: p for p in data.get("parties", [])}
        facts = [
            truth_fact("documents.booking_request.vessel_operator_code", data["vessel_operator_code"], 1, data["vessel_operator_code"], "Booking and voyage"),
            truth_fact("documents.booking_request.service_code", data["service_code"], 1, data["service_code"], "Booking and voyage"),
            truth_fact("documents.booking_request.route.port_of_loading.unlocode", route["port_of_loading"]["unlocode"], 1, route["port_of_loading"]["unlocode"], "Booking and voyage"),
            truth_fact("documents.booking_request.route.port_of_discharge.unlocode", route["port_of_discharge"]["unlocode"], 1, route["port_of_discharge"]["unlocode"], "Booking and voyage"),
            truth_fact("documents.booking_request.route.etd", route["etd"], 1, route["etd"], "Booking and voyage", ["DATE_TO_ISO"]),
            truth_fact("documents.booking_request.route.eta", route["eta"], 1, route["eta"], "Booking and voyage", ["DATE_TO_ISO"]),
            truth_fact("documents.booking_request.cargo.un_number", cargo.get("un_number"), 1, cargo.get("un_number"), "Cargo declaration", ["UN_NUMBER_CANONICAL"]),
            truth_fact("documents.booking_request.cargo.proper_shipping_name", cargo.get("proper_shipping_name"), 1, cargo.get("proper_shipping_name"), "Cargo declaration", ["PSN_CANONICAL"]),
            truth_fact("documents.booking_request.cargo.imdg_class", cargo.get("imdg_class"), 1, cargo.get("imdg_class"), "Cargo declaration"),
            truth_fact("documents.booking_request.cargo.packing_group", cargo.get("packing_group"), 1, cargo.get("packing_group"), "Cargo declaration"),
            truth_fact("documents.booking_request.cargo.total_packages", cargo.get("total_packages"), 1, f"{cargo.get('total_packages')} {cargo.get('package_type')}", "Cargo declaration"),
            truth_fact("documents.booking_request.cargo.gross_weight_kg", cargo.get("gross_weight_kg"), 1, f"{cargo.get('gross_weight_kg')} KGS", "Cargo declaration", ["UNIT_TO_KG"]),
            truth_fact("documents.booking_request.parties.consignee", parties.get("CONSIGNEE", {}).get("name"), 1, parties.get("CONSIGNEE", {}).get("name"), "Parties"),
        ]
    elif document_type == "PRELIMINARY_DGD":
        cargo = data["declaration"]
        signed = data.get("shipper_declaration_signed")
        facts = [
            truth_fact("documents.dgd.declaration.un_number", cargo.get("un_number"), 1, cargo.get("un_number"), "Dangerous goods description", ["UN_NUMBER_CANONICAL"]),
            truth_fact("documents.dgd.declaration.proper_shipping_name", cargo.get("proper_shipping_name"), 1, cargo.get("proper_shipping_name"), "Dangerous goods description", ["PSN_CANONICAL"]),
            truth_fact("documents.dgd.declaration.imdg_class", cargo.get("imdg_class"), 1, cargo.get("imdg_class"), "Dangerous goods description"),
            truth_fact("documents.dgd.declaration.packing_group", cargo.get("packing_group"), 1, cargo.get("packing_group"), "Dangerous goods description"),
            truth_fact("documents.dgd.declaration.marine_pollutant", cargo.get("marine_pollutant"), 1, cargo.get("marine_pollutant"), "Dangerous goods description"),
            truth_fact("documents.dgd.declaration.total_packages", cargo.get("total_packages"), 1, f"{cargo.get('total_packages')} {cargo.get('package_type')}", "Dangerous goods description"),
            truth_fact("documents.dgd.declaration.gross_weight_kg", cargo.get("gross_weight_kg"), 1, f"{cargo.get('gross_weight_kg')} KGS", "Dangerous goods description", ["UNIT_TO_KG"]),
            truth_fact("documents.dgd.shipper_declaration_signed", signed, 1, "SIGNED" if signed else "NOT SIGNED", "Shipper declaration"),
        ]
    else:
        transport = data.get("transport_information") or {}
        physical = data.get("physical_properties") or {}
        page_count = 2
        facts = [
            truth_fact("documents.sds.product_name", data.get("product_name"), 1, data.get("product_name"), "Section 1"),
            truth_fact("documents.sds.metadata.issued_at", metadata.get("issued_at"), 1, metadata.get("issued_at"), "Section 1", ["DATE_TO_ISO"]),
            truth_fact("documents.sds.physical_properties.flash_point_c", physical.get("flash_point_c"), 1, f"{physical.get('flash_point_c')} deg C" if physical.get("flash_point_c") is not None else None, "Section 9"),
            truth_fact("documents.sds.transport_information.un_number", transport.get("un_number"), 2, transport.get("un_number"), "Section 14", ["UN_NUMBER_CANONICAL"]),
            truth_fact("documents.sds.transport_information.proper_shipping_name", transport.get("proper_shipping_name"), 2, transport.get("proper_shipping_name"), "Section 14", ["PSN_CANONICAL"]),
            truth_fact("documents.sds.transport_information.imdg_class", transport.get("imdg_class"), 2, transport.get("imdg_class"), "Section 14"),
            truth_fact("documents.sds.transport_information.packing_group", transport.get("packing_group"), 2, transport.get("packing_group"), "Section 14"),
            truth_fact("documents.sds.transport_information.marine_pollutant", transport.get("marine_pollutant"), 2, transport.get("marine_pollutant"), "Section 14"),
        ]
    return {
        "stage_id": stage_id, "document_id": metadata["document_id"], "document_type": document_type,
        "document_version": metadata.get("document_version", 1), "source_path": source_path,
        "expected_page_count": page_count, "text_layer_required": True, "facts": facts,
    }


def build_document_packs():
    for pack_number in range(2, 9):
        pack_id = f"DP-{pack_number:03d}"
        pack_dir = PACKS_DIR / pack_id
        manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
        truths = []
        for stage in manifest["stages"]:
            fixture = load_fixture_for_stage(manifest, stage)
            stage_id = stage["stage_id"]
            for doc_manifest in stage["documents"]:
                if not doc_manifest["present"]:
                    continue
                document_type = doc_manifest["document_type"]
                key = {"BOOKING_REQUEST": "booking_request", "PRELIMINARY_DGD": "dgd", "SDS_EXTRACT": "sds"}[document_type]
                data = fixture["documents"][key]
                if data is None:
                    raise ValueError(f"{pack_id} {stage_id} expects {document_type} but fixture is null")
                source_path = pack_dir / doc_manifest["source_path"]
                pdf_path = pack_dir / doc_manifest["pdf_path"]
                source_path.parent.mkdir(parents=True, exist_ok=True)
                source_path.write_text(markdown_for(document_type, data, pack_id, stage_id), encoding="utf-8")
                if document_type == "BOOKING_REQUEST":
                    build_booking_pdf(data, pdf_path, pack_id, stage_id, doc_manifest["template_variant"])
                elif document_type == "PRELIMINARY_DGD":
                    build_dgd_pdf(data, pdf_path, pack_id, stage_id, doc_manifest["template_variant"])
                else:
                    build_sds_pdf(data, pdf_path, pack_id, stage_id, doc_manifest["template_variant"])
                truths.append(truth_for_document(document_type, data, doc_manifest["pdf_path"], stage_id))
        ground_truth = {"schema_version": "0.1", "pack_id": pack_id, "case_ref": manifest["case_ref"], "documents": truths}
        (pack_dir / "ground-truth.json").write_text(json.dumps(ground_truth, indent=2) + "\n", encoding="utf-8")


POLICY_MAPPING = {
    "POL-001": {
        "title": "Dangerous Goods Acceptance Guide",
        "subtitle": "Fixed-route teaching policy - version 1.0",
        "rule_ids": [
            "CAR-CLASS-1-BLOCK", "CAR-CLASS-7-BLOCK", "CAR-LOW-FLASH-POINT-BLOCK",
            "CAR-REEFER-DG-BLOCK", "CAR-IBC-MANUAL-APPROVAL",
        ],
    },
    "POL-002": {
        "title": "Booking Precheck Documentation and Consistency Standard",
        "subtitle": "CNSHA to AEJEA / TRAIN-ME1 - version 1.0",
        "rule_ids": [
            "DOC-DGD-REQUIRED", "DOC-SDS-REQUIRED", "DOC-DGD-UN-REQUIRED",
            "DOC-DGD-PSN-REQUIRED", "DOC-SDS-S14-REQUIRED", "DOC-SDS-FRESHNESS",
            "DOC-CONSIGNEE-REQUIRED", "CON-BOOKING-DGD-UN", "CON-DGD-SDS-UN",
            "CON-DGD-SDS-CLASS", "CON-GROSS-WEIGHT", "CON-PACKAGE-COUNT",
            "CON-MARINE-POLLUTANT", "CON-FLASH-POINT", "ROU-SNAPSHOT-SCOPE",
            "ROU-PARTNER-OPERATOR", "TIM-DOCUMENT-CUTOFF", "CON-PACKING-GROUP",
            "DOC-DGD-SIGNATURE", "DOC-KEY-FIELD-LOW-CONFIDENCE", "GOV-SNAPSHOT-EXPIRED",
            "GOV-RULE-CONFLICT",
        ],
    },
    "POL-003": {
        "title": "Temporary Dangerous Goods Operations Notice",
        "subtitle": "AEJEA-TRAIN-T1 synthetic facility notice - notice 2026-09",
        "rule_ids": ["PORT-TEMPORARY-DG-SUSPENSION"],
    },
}


def policy_markdown(policy_id: str, meta: dict, rules: list[dict]) -> str:
    lines = [
        f"# {meta['title']}", "", f"Document ID: {policy_id}", f"{meta['subtitle']}", "",
        "Synthetic training policy only. Not a real carrier, port, or regulatory requirement.", "",
        "## Applicability", "",
        "- Carrier: TRAINING-LINE", "- Route: CNSHA to AEJEA", "- Service: TRAIN-ME1",
        "- Effective: 2026-08-01 through 2026-12-31", "",
    ]
    for index, rule in enumerate(rules, start=1):
        lines.extend([
            f"## {index}. {rule['name']}", "", f"Rule ID: {rule['rule_id']}",
            f"Policy statement: {rule['action']['message_template']}",
            f"Operational response: {rule['action']['result_status']}",
            f"Responsible queue: {rule['action'].get('routing_queue') or 'NOT APPLICABLE'}", "",
        ])
    return "\n".join(lines) + "\n"


def build_policy_pdf(policy_id: str, meta: dict, rules: list[dict], path: Path):
    story = [
        Paragraph("TRAINING-LINE WORKSHOP POLICY", STYLES["subtitle"]),
        Paragraph(esc(meta["title"]), STYLES["title"]),
        banner(f"{policy_id} - SYNTHETIC TRAINING POLICY"),
        Paragraph(esc(meta["subtitle"]), STYLES["subtitle"]),
        Paragraph("Applicability", STYLES["section"]),
        field_table([
            ("Carrier", "TRAINING-LINE"), ("Route", "CNSHA to AEJEA"),
            ("Service", "TRAIN-ME1"), ("Effective Period", "2026-08-01 through 2026-12-31"),
            ("Authority", "TRAINING-LINE Workshop Policy Owner"),
        ]),
        Spacer(1, 3 * mm),
        Paragraph("This is synthetic training content. It is not a real carrier, port, or regulatory requirement.", STYLES["notice"]),
    ]
    for index, rule in enumerate(rules, start=1):
        if index > 1 and (index - 1) % 4 == 0:
            story.append(PageBreak())
            story.append(Paragraph(esc(meta["title"]), STYLES["title"]))
        story.extend([
            Paragraph(f"{index}. {esc(rule['name'])}", STYLES["section"]),
            field_table([
                ("Rule ID", rule["rule_id"]),
                ("Policy Statement", rule["action"]["message_template"]),
                ("Operational Response", rule["action"]["result_status"]),
                ("Responsible Queue", rule["action"].get("routing_queue") or "NOT APPLICABLE"),
            ], "B"),
        ])
    make_doc(path, f"{policy_id} {meta['title']}").build(story, onFirstPage=footer, onLaterPages=footer)


def build_policy_documents():
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    rules_by_id = {rule["rule_id"]: rule for rule in snapshot["rules"]}
    index = {"schema_version": "0.1", "snapshot_id": snapshot["snapshot_id"], "documents": []}
    for policy_id, meta in POLICY_MAPPING.items():
        rules = [rules_by_id[rule_id] for rule_id in meta["rule_ids"]]
        policy_dir = POLICY_DIR / policy_id
        source_path = policy_dir / "source.md"
        pdf_path = policy_dir / "output" / "pdf" / f"{policy_id.lower()}-{meta['title'].lower().replace(' ', '-')}.pdf"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(policy_markdown(policy_id, meta, rules), encoding="utf-8")
        build_policy_pdf(policy_id, meta, rules, pdf_path)
        rule_evidence = []
        with pdfplumber.open(pdf_path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        for rule in rules:
            page_number = next((i + 1 for i, text in enumerate(pages) if rule["rule_id"] in text), None)
            if page_number is None:
                raise ValueError(f"Could not locate {rule['rule_id']} in {pdf_path}")
            rule_evidence.append({
                "rule_id": rule["rule_id"], "page": page_number,
                "evidence_text": rule["action"]["message_template"],
            })
        index["documents"].append({
            "policy_document_id": policy_id, "title": meta["title"],
            "source_path": str(source_path.relative_to(ROOT)),
            "pdf_path": str(pdf_path.relative_to(ROOT)),
            "effective_from": "2026-08-01", "effective_to": "2026-12-31",
            "rule_evidence": rule_evidence,
        })
    (POLICY_DIR / "POLICY_DOCUMENT_INDEX.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")


def main():
    build_document_packs()
    build_policy_documents()


if __name__ == "__main__":
    main()
