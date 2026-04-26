from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "configs" / "settings.yaml"


class Settings:
    def __init__(self, raw: Dict[str, Any]) -> None:
        self._raw = raw
        self.project_name: str = raw.get("project_name", "RSS-Modul")
        self.environment: str = raw.get("environment", "dev")
        self.paths: Dict[str, Any] = raw.get("paths", {})
        self.database: Dict[str, Any] = raw.get("database", {})
        self.logging: Dict[str, Any] = raw.get("logging", {})
        self.sources: Dict[str, Any] = raw.get("sources", {})
        self.ai: Dict[str, Any] = raw.get("ai", {})
        self.servicesblock: Dict[str, Any] = raw.get("servicesblock", {})

    def get_source_config(self, name: str) -> Dict[str, Any]:
        return self.sources.get(name, {})

    def get_ai_config(self) -> Dict[str, Any]:
        return self.ai

    def get_path(self, key: str, default: str | None = None) -> str | None:
        return self.paths.get(key, default)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"settings.yaml not found: {CONFIG_PATH}")
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return Settings(raw)
