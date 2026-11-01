"""Find the repo root and load lightwork.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONFIG_NAME = "lightwork.yaml"


def find_root(start: Path | None = None) -> Path:
    """Walk up from `start` to the folder holding lightwork.yaml; fall back to `start`."""
    here = (start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        if (folder / CONFIG_NAME).exists():
            return folder
    return here


def load_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_NAME
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def lightwork_dir(root: Path) -> Path:
    return root / ".lightwork"
