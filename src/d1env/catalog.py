from pathlib import Path
from typing import Any

import yaml

from .models import Catalog, Profile


class UniqueSafeLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader: UniqueSafeLoader, node: yaml.MappingNode) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise ValueError("invalid or duplicate YAML key")
        result[key] = loader.construct_object(value_node)
    return result


UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def validate_profile(raw: dict[str, object]) -> Profile:
    return Profile.model_validate(raw)


def load_catalog(path: Path) -> Catalog:
    profiles = []
    for file in sorted(path.glob("*.yaml")):
        if file.is_symlink() or file.stat().st_size > 65536:
            raise ValueError("unsafe profile file")
        try:
            raw = yaml.load(file.read_text(encoding="utf-8"), Loader=UniqueSafeLoader)
        except yaml.YAMLError as exc:
            raise ValueError("invalid safe YAML") from exc
        if not isinstance(raw, dict):
            raise ValueError("profile must be an object")  # noqa: TRY004 - catalog validation error
        profiles.append(validate_profile(raw))
    if not profiles:
        raise ValueError("empty catalog")
    return Catalog(profiles=profiles)
