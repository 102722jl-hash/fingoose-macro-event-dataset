"""Load the newest additive implementation of the event Q&A builder."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_IMPLEMENTATIONS = sorted(Path(__file__).parent.glob("fingoose_qa_reasoning_v2_impl_*.py"))
if not _IMPLEMENTATIONS:
    raise ImportError("MISSING_QA_REASONING_IMPLEMENTATION")
_PATH = _IMPLEMENTATIONS[-1]
_NAME = _PATH.stem
_SPEC = importlib.util.spec_from_file_location(_NAME, _PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"INVALID_QA_REASONING_IMPLEMENTATION:{_PATH}")
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_NAME] = _MODULE
_SPEC.loader.exec_module(_MODULE)

for _key in getattr(_MODULE, "__all__", ()):
    globals()[_key] = getattr(_MODULE, _key)
__all__ = list(getattr(_MODULE, "__all__", ()))
