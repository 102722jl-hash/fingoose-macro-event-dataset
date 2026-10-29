from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Path:
    """Keep pytest scratch data inside the Windows workspace sandbox."""
    path = ROOT / "work" / "_pytest_tmp" / f"{request.node.name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path
