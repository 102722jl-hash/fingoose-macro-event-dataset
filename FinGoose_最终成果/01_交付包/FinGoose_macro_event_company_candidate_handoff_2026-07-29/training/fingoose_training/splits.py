"""Explicit event-level dataset split helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


ALLOWED_SPLITS = {"train", "validation", "test"}


class SplitError(ValueError):
    """Raised when an event split is incomplete or leaks across partitions."""


def build_event_split_index(splits: dict[str, list[str]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for split_name, event_ids in splits.items():
        if split_name not in ALLOWED_SPLITS:
            raise SplitError(f"unsupported split: {split_name}")
        for event_id in event_ids:
            if event_id in index:
                raise SplitError(
                    f"{event_id} appears in both {index[event_id]} and {split_name}"
                )
            index[event_id] = split_name
    return index


def tag_samples(
    samples: list[dict[str, Any]], splits: dict[str, list[str]]
) -> list[dict[str, Any]]:
    split_index = build_event_split_index(splits)
    tagged: list[dict[str, Any]] = []
    for source in samples:
        event_id = source.get("event_id")
        if event_id not in split_index:
            raise SplitError(f"{event_id} missing from split manifest")
        row = deepcopy(source)
        row["split"] = split_index[event_id]
        tagged.append(row)
    return tagged
