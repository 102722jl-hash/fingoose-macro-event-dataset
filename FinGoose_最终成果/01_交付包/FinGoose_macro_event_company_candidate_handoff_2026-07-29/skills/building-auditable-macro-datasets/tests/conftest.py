from hashlib import sha256
from pathlib import Path
import shutil
import sys
import tempfile

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def tmp_path(request) -> Path:
    skill_token = sha256(str(Path(__file__).resolve().parents[1]).encode("utf-8")).hexdigest()[:12]
    root = Path(tempfile.gettempdir()) / "building-auditable-macro-datasets-tests" / skill_token
    token = sha256(request.node.nodeid.encode("utf-8")).hexdigest()[:16]
    path = root / token
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    yield path
    shutil.rmtree(path)
    if root.exists() and not any(root.iterdir()):
        root.rmdir()
