from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pdfplumber

from .config import Settings


def _line_value(text: str, label: str) -> str | None:
    match = re.search(rf"(?m)^{re.escape(label)}\s+(.+)$", text)
    return match.group(1).strip() if match else None


def _boolean(value: str | None) -> bool | None:
    if value is None: return None
    return value.upper() in {"YES", "TRUE", "SIGNED"}


def _provided(value: str | None) -> str | None:
    return None if value is None or value.upper() in {"NOT PROVIDED", "N/A"} else value


def _number(value: str | None) -> float | None:
    value = _provided(value)
    return float(value.split()[0]) if value else None


def extract_pdf_document(path: Path, document_type: str, confidence: float = 0.99) -> dict[str, Any]:
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    text = "\n".join(pages)
    document_id = _line_value(text, "Document ID")
    version = int(_line_value(text, "Document Version") or 1)
    metadata = {"document_id": document_id, "document_type": document_type, "file_name": path.name,
                "mime_type": "application/pdf", "issued_at": _line_value(text, "Issue Date"), "language": "en",
                "synthetic": True, "extraction_confidence": confidence,
                "field_confidences": {"un_number": confidence, "imdg_class": confidence, "gross_weight_kg": confidence},
                "document_version": version}
    if document_type == "BOOKING_REQUEST":
        loading = (_line_value(text, "Port of Loading") or " / ").split(" / ")
        discharge = (_line_value(text, "Port of Discharge") or " / ").split(" / ")
        equipment = (_line_value(text, "Equipment") or "1 x UNKNOWN").split(" x ")
        packages = (_line_value(text, "Packages") or "0 UNKNOWN").split(maxsplit=1)
        class_pg = (_line_value(text, "IMDG Class / Packing Group") or " / ").split(" / ")
        imdg = class_pg[0] if class_pg[0] else _line_value(text, "IMDG Class")
        pg = class_pg[1] if len(class_pg)>1 and class_pg[1] else _line_value(text, "Packing Group")
        consignee = _provided(_line_value(text, "Consignee"))
        metadata["document_id"] = document_id or f"{_line_value(text, 'Booking Reference')}-BOOKING_REQUEST"
        return {"metadata": metadata, "booking_reference": _line_value(text, "Booking Reference"),
                "carrier_code": _line_value(text, "Carrier"), "vessel_operator_code": _line_value(text, "Vessel Operator"),
                "service_code": _line_value(text, "Service"),
                "route": {"port_of_loading": {"unlocode": loading[0], "facility_code": loading[1] if len(loading)>1 else None},
                          "port_of_discharge": {"unlocode": discharge[0], "facility_code": discharge[1] if len(discharge)>1 else None},
                          "transshipment_ports": [], "etd": _line_value(text, "ETD"), "eta": _line_value(text, "ETA")},
                "parties": ([{"role":"SHIPPER", "name": _line_value(text,"Shipper")}] if _line_value(text,"Shipper") else []) +
                           ([{"role":"CONSIGNEE", "name": consignee}] if consignee else []),
                "cargo": {"description": _line_value(text,"Description"), "commodity_code": _line_value(text,"Commodity Code"),
                          "is_dangerous_goods": _boolean(_line_value(text,"Dangerous Goods")), "un_number": _line_value(text,"UN Number"),
                          "proper_shipping_name": _provided(_line_value(text,"Proper Shipping Name")), "imdg_class": _provided(imdg), "packing_group": _provided(pg),
                          "marine_pollutant": _boolean(_line_value(text,"Marine Pollutant")), "total_packages": int(packages[0]),
                          "package_type": packages[1], "net_weight_kg": float((_line_value(text,"Net Weight") or "0").split()[0]),
                          "gross_weight_kg": float((_line_value(text,"Gross Weight") or "0").split()[0])},
                "equipment": {"quantity": int(equipment[0]), "container_type": equipment[1], "reefer_settings": None}}
    if document_type == "PRELIMINARY_DGD":
        packages = (_line_value(text, "Number and Type of Packages") or "0 UNKNOWN").split(maxsplit=1)
        return {"metadata": metadata, "booking_reference": _line_value(text,"Booking Reference"),
                "declaration": {"un_number": _provided(_line_value(text,"UN Number")), "proper_shipping_name": _provided(_line_value(text,"Proper Shipping Name")),
                    "imdg_class": _provided(_line_value(text,"IMDG Class")), "packing_group": _provided(_line_value(text,"Packing Group")),
                    "marine_pollutant": _boolean(_line_value(text,"Marine Pollutant")), "total_packages": int(packages[0]),
                    "package_type": packages[1], "net_weight_kg": float((_line_value(text,"Net Weight") or "0").split()[0]),
                    "gross_weight_kg": float((_line_value(text,"Gross Weight") or "0").split()[0])},
                "shipper_declaration_signed": _boolean(_line_value(text,"Declaration Status"))}
    if document_type == "SDS_EXTRACT":
        return {"metadata": metadata, "product_name": _line_value(text,"Product Name"), "manufacturer": _line_value(text,"Manufacturer"),
                "physical_properties": {"flash_point_c": _number(_line_value(text,"Flash Point"))},
                "transport_information": {"un_number": _line_value(text,"UN Number"),
                    "proper_shipping_name": _line_value(text,"UN Proper Shipping Name"), "imdg_class": _line_value(text,"Transport Hazard Class"),
                    "packing_group": _provided(_line_value(text,"Packing Group")), "marine_pollutant": _boolean(_line_value(text,"Marine Pollutant"))}
                if "Section 14" in text else None}
    raise ValueError(f"Unknown document type: {document_type}")


def load_document_pack_text(pack_dir: Path, stage_id: str = "S1") -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load source PDFs as page text without extracting business facts.

    This is the infrastructure boundary for the Agent path. Ground truth and
    canonical normalized fixtures are deliberately not read here.
    """
    manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
    stage = next(item for item in manifest["stages"] if item["stage_id"] == stage_id)
    documents = []
    for item in stage["documents"]:
        if not item["present"]:
            continue
        path = pack_dir / item["pdf_path"]
        with pdfplumber.open(path) as pdf:
            pages = [{"page": number, "text": page.extract_text() or ""} for number, page in enumerate(pdf.pages, 1)]
        full_text = "\n".join(page["text"] for page in pages)
        documents.append({
            "document_id": _line_value(full_text, "Document ID") or f"{manifest['pack_id']}-{item['document_type']}",
            "document_type": item["document_type"],
            "document_version": item.get("document_version", 1),
            "file_name": path.name,
            "pages": pages,
        })
    envelope = {"pack_id": manifest["pack_id"], "case_id": manifest["case_ref"], "stage_id": stage_id}
    return envelope, documents


def extract_document_pack(pack_dir: Path, stage_id: str = "S1") -> dict[str, Any]:
    manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
    stage = next(item for item in manifest["stages"] if item["stage_id"] == stage_id)
    documents: dict[str, Any] = {}
    keys = {"BOOKING_REQUEST":"booking_request", "PRELIMINARY_DGD":"dgd", "SDS_EXTRACT":"sds"}
    for item in stage["documents"]:
        key = keys[item["document_type"]]
        documents[key] = extract_pdf_document(pack_dir / item["pdf_path"], item["document_type"]) if item["present"] else None
    booking = documents["booking_request"]
    return {"schema_version":"0.2", "case_id": manifest["case_ref"], "submitted_at":"2026-08-10T09:00:00+08:00",
            "policy_context":{"snapshot_id":"TRAINING-LINE-CNSHA-AEJEA-2026-08-01", "carrier_code":"TRAINING-LINE", "training_only":True},
            "documents":documents, "fixture_type":"EXTRACTED_PDF_PACK"}


class DeepSeekExtractor:
    """Optional OpenAI-compatible fallback. The deterministic parser keeps workshop tests reproducible."""
    def __init__(self, settings: Settings):
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is required for LLM extraction mode")
        from openai import OpenAI
        self.client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        self.model = settings.llm_model

    def extract_text(self, text: str, schema: dict[str, Any]) -> dict[str, Any]:
        response = self.client.chat.completions.create(model=self.model, temperature=0,
            messages=[{"role":"system","content":"Extract only supported facts. Return JSON only."},
                      {"role":"user","content":json.dumps({"schema":schema,"document_text":text})}],
            response_format={"type":"json_object"})
        return json.loads(response.choices[0].message.content)
