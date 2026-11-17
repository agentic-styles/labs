"""Contracts for the model-facing document extraction boundary."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ExtractionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


Confidence = Annotated[float, Field(ge=0, le=1)]


class Location(ExtractionModel):
    unlocode: str | None = None
    facility_code: str | None = None


class Route(ExtractionModel):
    port_of_loading: Location | None = None
    port_of_discharge: Location | None = None
    transshipment_ports: list[Location] = Field(default_factory=list)
    etd: str | None = None
    eta: str | None = None


class Party(ExtractionModel):
    role: Literal["SHIPPER", "CONSIGNEE", "NOTIFY_PARTY"]
    name: str
    country_code: str | None = None
    address: str | None = None


class ExtractedDocumentMetadata(ExtractionModel):
    issued_at: str | None = None
    language: str | None = None
    extraction_confidence: Confidence | None = None
    field_confidences: dict[str, Confidence] = Field(default_factory=dict)


class Cargo(ExtractionModel):
    description: str | None = None
    commodity_code: str | None = None
    hs_code: str | None = None
    is_dangerous_goods: bool | None = None
    un_number: str | None = None
    proper_shipping_name: str | None = None
    imdg_class: str | None = None
    subsidiary_risks: list[str] = Field(default_factory=list)
    packing_group: str | None = None
    marine_pollutant: bool | None = None
    flash_point_c: float | None = None
    total_packages: int | None = None
    package_type: str | None = None
    net_weight_kg: float | None = None
    gross_weight_kg: float | None = None


class Equipment(ExtractionModel):
    container_type: str | None = None
    quantity: int | None = None
    reefer_settings: dict[str, Any] | None = None


class BookingRequest(ExtractionModel):
    metadata: ExtractedDocumentMetadata | None = None
    booking_reference: str | None = None
    carrier_code: str | None = None
    vessel_operator_code: str | None = None
    service_code: str | None = None
    route: Route | None = None
    parties: list[Party] = Field(default_factory=list)
    cargo: Cargo | None = None
    equipment: Equipment | None = None


class DgdDeclaration(Cargo):
    pass


class PreliminaryDgd(ExtractionModel):
    metadata: ExtractedDocumentMetadata | None = None
    booking_reference: str | None = None
    declaration: DgdDeclaration | None = None
    shipper_declaration_signed: bool | None = None


class PhysicalProperties(ExtractionModel):
    flash_point_c: float | None = None


class TransportInformation(ExtractionModel):
    un_number: str | None = None
    proper_shipping_name: str | None = None
    imdg_class: str | None = None
    packing_group: str | None = None
    marine_pollutant: bool | None = None


class SdsExtract(ExtractionModel):
    metadata: ExtractedDocumentMetadata | None = None
    product_name: str | None = None
    manufacturer: str | None = None
    physical_properties: PhysicalProperties | None = None
    transport_information: TransportInformation | None = None


class ExtractedDocuments(ExtractionModel):
    booking_request: BookingRequest | None = None
    dgd: PreliminaryDgd | None = None
    sds: SdsExtract | None = None


class ExtractedFactEvidence(ExtractionModel):
    fact_path: str = Field(
        pattern=r"^documents\.(booking_request|dgd|sds)(\.[A-Za-z0-9_*]+(\[[0-9]+\])*)*$"
    )
    value: Any
    document_type: Literal["BOOKING_REQUEST", "PRELIMINARY_DGD", "SDS_EXTRACT"]
    page: int = Field(ge=1)
    evidence_text: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class FactSubmission(ExtractionModel):
    documents: ExtractedDocuments


class DecisionEvidenceSubmission(ExtractionModel):
    evidence: list[ExtractedFactEvidence]


class CompletionSubmission(ExtractionModel):
    summary: str = Field(min_length=1, max_length=1000)
