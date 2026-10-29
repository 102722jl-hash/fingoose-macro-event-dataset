"""Stable public import path for the unified builder."""

from .unified_builder_impl_002 import (
    BuildError,
    build_unified_events,
    group_by,
    index_unique,
)

__all__ = ["BuildError", "build_unified_events", "group_by", "index_unique"]
