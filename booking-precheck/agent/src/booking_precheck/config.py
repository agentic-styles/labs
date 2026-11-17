from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    assets_dir: Path
    llm_api_key: str | None
    llm_base_url: str
    llm_model: str

    @classmethod
    def from_env(cls) -> "Settings":
        configured_assets = os.getenv("BOOKING_PRECHECK_ASSETS")
        if configured_assets:
            assets_dir = Path(configured_assets).resolve()
        else:
            candidates = []
            for anchor in (Path.cwd(), Path(__file__).resolve()):
                candidates.extend(parent / "assets" for parent in [anchor, *anchor.parents])
            assets_dir = next((candidate for candidate in candidates if (candidate / "policy_snapshot.json").is_file()), candidates[0])
        return cls(
            assets_dir=assets_dir.resolve(),
            llm_api_key=os.getenv("LLM_API_KEY"),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            llm_model=os.getenv("LLM_MODEL", "deepseek-v4-flash"),
        )
