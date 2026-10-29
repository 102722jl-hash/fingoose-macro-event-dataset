from pathlib import Path

import pytest


@pytest.fixture
def scratch_path() -> Path:
    """Use a pre-created workspace directory; managed Windows blocks pytest tmp_path."""
    path = Path(__file__).resolve().parent / "_scratch"
    path.mkdir(exist_ok=True)
    return path
