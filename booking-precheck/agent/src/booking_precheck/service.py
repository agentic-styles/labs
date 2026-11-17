from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from .assets import apply_policy_variant, load_json, materialize_business_steps
from .agent_graph import build_single_agent_graph
from langchain_core.language_models import BaseChatModel
from .config import Settings
from .extractors import extract_document_pack
from .graph import build_graph


class BookingPrecheckService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        self.base_snapshot = load_json(self.settings.assets_dir / "policy_snapshot.json")
        self.policy_index = load_json(self.settings.assets_dir / "policy-documents" / "POLICY_DOCUMENT_INDEX.json")
        self.graph = build_graph()

    def run(
        self, facts: dict[str, Any], *, case_id: str | None = None, step_id: str | None = None,
        previous_run_id: str | None = None, trace_id: str | None = None,
        policy_fixture: dict[str, Any] | None = None, policy_variant: dict[str, Any] | None = None,
        human_confirmation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = self.graph.invoke({
            "facts": facts, "snapshot": apply_policy_variant(self.base_snapshot, policy_variant),
            "policy_index": self.policy_index, "case_id": case_id, "step_id": step_id,
            "previous_run_id": previous_run_id, "trace_id": trace_id,
            "policy_fixture": policy_fixture, "human_confirmation": human_confirmation,
        })
        return state["result"]

    def run_case(self, case_id: str) -> dict[str, Any]:
        case_dir = self.settings.assets_dir / "cases" / case_id
        facts = load_json(case_dir / "input.json")
        expected = load_json(case_dir / "expected.json")
        return self.run(facts, case_id=case_id, policy_fixture=expected.get("policy_fixture"))

    def run_business_case(self, case_id: str) -> list[dict[str, Any]]:
        case_path = self.settings.assets_dir / "business-cases" / case_id / "input.json"
        results = []
        previous_run_id = None
        trace_id = str(uuid4())
        for step, facts in materialize_business_steps(case_path):
            result = self.run(facts, case_id=case_id, step_id=step["step_id"], previous_run_id=previous_run_id,
                              trace_id=trace_id, policy_variant=step.get("policy_variant"),
                              human_confirmation=step.get("human_confirmation"))
            results.append(result)
            previous_run_id = result["run_id"]
        return results

    def run_document_pack(self, pack_id: str, stage_id: str = "S1") -> dict[str, Any]:
        pack_dir = self.settings.assets_dir / "document-packs" / pack_id
        facts = extract_document_pack(pack_dir, stage_id)
        manifest = load_json(pack_dir / "manifest.json")
        step_id = next((stage.get("business_step_id") for stage in manifest["stages"] if stage["stage_id"] == stage_id), stage_id)
        return self.run(facts, case_id=manifest["case_ref"], step_id=step_id)


class SingleAgentBookingPrecheckService:
    """Runs source document packs through the real model/tool Agent loop."""

    def __init__(self, settings: Settings | None = None, model: BaseChatModel | None = None):
        self.settings = settings or Settings.from_env()
        self.graph = build_single_agent_graph(self.settings, model)

    def run_document_pack(self, pack_id: str, stage_id: str = "S1") -> dict[str, Any]:
        return self.graph.invoke({"document_pack_id": pack_id, "stage_id": stage_id})["result"]
