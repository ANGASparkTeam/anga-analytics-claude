"""Settings from env and the properties.yaml registry."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from fastmcp.exceptions import ToolError

log = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "Asia/Bangkok"
DEFAULT_PROPERTIES_FILE = "properties.yaml"


@dataclass(frozen=True)
class PropertyConfig:
    alias: str
    id: str
    name: str
    timezone: str = DEFAULT_TIMEZONE
    currency: str | None = None
    key_events: tuple[str, ...] = ()

    def ref(self) -> dict[str, str]:
        return {"alias": self.alias, "id": self.id, "name": self.name}


@dataclass
class PropertyRegistry:
    properties: dict[str, PropertyConfig] = field(default_factory=dict)
    default: str | None = None
    source: str = ""

    def resolve(self, prop: str | None) -> PropertyConfig:
        """Resolve an alias, numeric id, or None (default) to a PropertyConfig."""
        if prop is None or not str(prop).strip():
            if not self.default or self.default not in self.properties:
                raise ToolError(
                    "No default GA4 property is configured. Pass `property` "
                    "(alias or numeric id) or set `default` in "
                    f"{self.source or DEFAULT_PROPERTIES_FILE}."
                )
            return self.properties[self.default]
        key = str(prop).strip()
        if key in self.properties:
            return self.properties[key]
        for cfg in self.properties.values():
            if cfg.id == key:
                return cfg
        stripped = key.removeprefix("properties/")
        if stripped.isdigit():
            return PropertyConfig(alias=stripped, id=stripped, name=stripped)
        known = ", ".join(sorted(self.properties)) or "(none configured)"
        raise ToolError(
            f"Unknown property '{prop}'. Use one of the aliases [{known}] "
            "or a numeric GA4 property id. Call list_properties to see them."
        )


def _validate_tz(alias: str, tz: str) -> str:
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Property '{alias}': unknown timezone '{tz}'") from exc
    return tz


def parse_properties(data: dict | None, source: str = "") -> PropertyRegistry:
    data = data or {}
    props: dict[str, PropertyConfig] = {}
    for alias, raw in (data.get("properties") or {}).items():
        raw = raw or {}
        if "id" not in raw:
            raise ValueError(f"Property '{alias}' is missing `id`")
        props[str(alias)] = PropertyConfig(
            alias=str(alias),
            id=str(raw["id"]).removeprefix("properties/"),
            name=str(raw.get("name") or alias),
            timezone=_validate_tz(str(alias), str(raw.get("timezone") or DEFAULT_TIMEZONE)),
            currency=raw.get("currency"),
            key_events=tuple(raw.get("key_events") or ()),
        )
    default = data.get("default")
    if default is None and len(props) == 1:
        default = next(iter(props))
    if default is not None and default not in props:
        raise ValueError(f"default '{default}' is not defined under `properties`")
    return PropertyRegistry(props, default, source)


def load_registry(path: str | os.PathLike[str] | None = None) -> PropertyRegistry:
    file = Path(path or os.environ.get("GA4_PROPERTIES_FILE", DEFAULT_PROPERTIES_FILE))
    if not file.is_file():
        log.warning("Properties file %s not found; only numeric property ids will work", file)
        return PropertyRegistry(source=str(file))
    return parse_properties(yaml.safe_load(file.read_text(encoding="utf-8")), str(file))


_registry: PropertyRegistry | None = None


def get_registry() -> PropertyRegistry:
    global _registry
    if _registry is None:
        _registry = load_registry()
    return _registry


def set_registry(registry: PropertyRegistry | None) -> None:
    """Override (or with None, reset) the cached registry; used by tests."""
    global _registry
    _registry = registry
