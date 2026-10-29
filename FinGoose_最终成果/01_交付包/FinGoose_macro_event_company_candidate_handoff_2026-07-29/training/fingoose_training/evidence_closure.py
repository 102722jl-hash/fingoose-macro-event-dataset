"""Fail-closed evidence consolidation and milestone evidence binding."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence


class EvidenceClosureError(ValueError):
    """Raised when evidence cannot be merged or bound unambiguously."""


_CRITICAL_FIELDS = ("original_quote", "locator", "source_url")
_FIELD_ALIASES = {
    "original_quote": ("original_quote", "quote"),
    "locator": ("locator", "locator_zh", "page_or_section_locator"),
    "source_url": ("source_url", "url"),
}
_METADATA_ALIASES = {
    "title": ("title", "document_title"),
    "publisher": ("publisher", "publisher_zh", "issuer"),
    "published_at": ("published_at", "first_public_at"),
    "snapshot_sha256": (
        "snapshot_sha256", "sha256", "source_snapshot_sha256", "content_sha256"
    ),
    "availability_scope": ("availability_scope", "visibility"),
    "review_status": ("review_status",),
}


def _nonempty(value: Any) -> bool:
    return value is not None and value != ""


def _nonblank_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _text(value: Any) -> str:
    return str(value).strip() if _nonempty(value) else ""


def _aliased_identifier(
    record: Mapping[str, Any], keys: Sequence[str], label: str
) -> str:
    values = [
        str(record[key]).strip()
        for key in keys
        if _nonempty(record.get(key)) and str(record[key]).strip()
    ]
    if len(set(values)) > 1:
        raise EvidenceClosureError(f"Conflicting {label} aliases: {values}")
    return values[0] if values else ""


def _evidence_identifier(record: Mapping[str, Any]) -> str:
    return _text(record.get("evidence_id")) or _text(record.get("source_id"))


def _canonical_value(record: Mapping[str, Any], field: str, evidence_id: str) -> Any:
    values: list[Any] = []
    for alias in _FIELD_ALIASES[field]:
        value = record.get(alias)
        if value in (None, ""):
            continue
        if field == "locator" and isinstance(value, Mapping):
            if not (
                _nonblank_string(value.get("type"))
                and _nonblank_string(value.get("value"))
            ):
                raise EvidenceClosureError(
                    f"Evidence ID {evidence_id!r} has malformed locator value"
                )
            clean = deepcopy(dict(value))
            clean["type"] = clean["type"].strip()
            clean["value"] = clean["value"].strip()
            values.append(clean)
            continue
        if not isinstance(value, str):
            raise EvidenceClosureError(
                f"Evidence ID {evidence_id!r} has malformed {field} value"
            )
        if value.strip():
            values.append(value.strip())
    if values and any(value != values[0] for value in values[1:]):
        raise EvidenceClosureError(
            f"Evidence ID {evidence_id!r} has conflicting {field} values"
        )
    return deepcopy(values[0]) if values else None


def _critical_present(field: str, value: Any) -> bool:
    if field == "locator" and isinstance(value, Mapping):
        return _nonblank_string(value.get("type")) and _nonblank_string(
            value.get("value")
        )
    return _nonblank_string(value)


def _values(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [] if not _nonempty(value) else [value]


def merge_evidence_records(*groups: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Merge evidence by ID, refusing conflicting primary-source fields."""

    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for record in group:
            if not isinstance(record, Mapping):
                continue
            evidence_id = _evidence_identifier(record)
            if not evidence_id:
                continue
            current = merged.setdefault(
                evidence_id,
                {
                    "evidence_id": evidence_id,
                    "source_record_ids": set(),
                    "supports_node_ids": set(),
                },
            )
            source_record_ids = {
                _text(source_id)
                for source_id in _values(record.get("source_record_ids"))
                if _text(source_id) and _text(source_id) != evidence_id
            }
            source_id = _text(record.get("source_id"))
            if source_id and source_id != evidence_id:
                source_record_ids.add(source_id)
            current["source_record_ids"].update(source_record_ids)
            for field in _CRITICAL_FIELDS:
                value = _canonical_value(record, field, evidence_id)
                if not _nonempty(value):
                    continue
                existing = current.get(field)
                if _nonempty(existing) and existing != value:
                    raise EvidenceClosureError(
                        f"Evidence ID {evidence_id!r} has conflicting {field} values"
                    )
                if not _nonempty(existing):
                    current[field] = value
            current["supports_node_ids"].update(
                _text(node_id)
                for node_id in _values(record.get("supports_node_ids"))
                if _text(node_id)
            )
            for field, aliases in _METADATA_ALIASES.items():
                if _nonempty(current.get(field)):
                    continue
                value = next(
                    (record.get(alias) for alias in aliases if _nonempty(record.get(alias))),
                    None,
                )
                if _nonempty(value):
                    current[field] = deepcopy(value)

    result: list[dict[str, Any]] = []
    for evidence_id in sorted(merged):
        record = merged[evidence_id]
        normalized = {
            "evidence_id": evidence_id,
            "original_quote": record.get("original_quote"),
            "locator": record.get("locator"),
            "source_url": record.get("source_url"),
            "supports_node_ids": sorted(record["supports_node_ids"]),
        }
        if record["source_record_ids"]:
            normalized["source_record_ids"] = sorted(record["source_record_ids"])
        normalized.update(
            {
                field: deepcopy(record[field])
                for field in _METADATA_ALIASES
                if _nonempty(record.get(field))
            }
        )
        normalized["missing"] = not all(
            _critical_present(field, normalized[field]) for field in _CRITICAL_FIELDS
        )
        result.append(normalized)
    return result


def build_milestone_evidence_aliases(timeline: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    """Return explicit canonical-milestone to evidence aliases from timeline rows."""

    aliases: dict[str, set[str]] = {}
    for row in timeline:
        if not isinstance(row, Mapping):
            continue
        fast_node_id = _text(row.get("fast_node_id"))
        canonical_id = _text(row.get("original_milestone_id"))
        if not (fast_node_id and canonical_id):
            continue
        evidence_ids = [_evidence_identifier(row)]
        nested_evidence = row.get("evidence")
        if isinstance(nested_evidence, (list, tuple)):
            evidence_ids.extend(
                _evidence_identifier(item)
                for item in nested_evidence
                if isinstance(item, Mapping)
            )
        for evidence_id in evidence_ids:
            if evidence_id:
                aliases.setdefault(canonical_id, set()).add(evidence_id)
    return {canonical_id: sorted(evidence_ids) for canonical_id, evidence_ids in sorted(aliases.items())}


def bind_milestone_evidence_aliases(
    milestones: Sequence[Mapping[str, Any]], aliases: Mapping[str, Sequence[str]]
) -> list[dict[str, Any]]:
    """Deep-copy milestones and add their explicitly aliased evidence sources."""

    bound = deepcopy(list(milestones))
    by_id: dict[str, dict[str, Any]] = {}
    for milestone in bound:
        if not isinstance(milestone, dict):
            continue
        milestone_id = _aliased_identifier(
            milestone, ("milestone_id", "id"), "milestone identity"
        )
        if milestone_id:
            if milestone_id in by_id:
                raise EvidenceClosureError(
                    f"duplicate canonical milestone: {milestone_id}"
                )
            by_id[milestone_id] = milestone

    for canonical_id in sorted(aliases):
        milestone = by_id.get(str(canonical_id))
        if milestone is None:
            raise EvidenceClosureError(
                f"Canonical milestone {canonical_id!r} does not exist"
            )
        raw_sources = milestone.get("sources") or []
        candidate_sources = deepcopy(raw_sources) if isinstance(raw_sources, list) else [deepcopy(raw_sources)]
        sources: list[Any] = []
        seen: set[str] = set()
        for source in candidate_sources:
            source_id = _evidence_identifier(source) if isinstance(source, Mapping) else ""
            if source_id and source_id in seen:
                continue
            sources.append(source)
            if source_id:
                seen.add(source_id)
        for evidence_id in sorted({_text(value) for value in aliases[canonical_id] if _text(value)}):
            if evidence_id not in seen:
                sources.append({"evidence_id": evidence_id})
                seen.add(evidence_id)
        milestone["sources"] = sources
    return bound
