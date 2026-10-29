from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def tmp_path(request) -> Path:
    """Workspace-backed replacement for pytest tmp_path in the managed Windows sandbox."""
    root = Path(__file__).resolve().parent / "tests" / "_workspace_tmp"
    root.mkdir(exist_ok=True)
    path = root / f"{request.node.name}-{uuid4().hex}"
    path.mkdir(exist_ok=True)
    return path
