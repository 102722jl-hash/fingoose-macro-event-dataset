"""Read-only reconciliation for a FinGoose v2 candidate manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


COUNT_FILES = {
    'milestones': 'event_milestones.jsonl',
    'episodes': 'event_episodes.jsonl',
    'graphs': 'transmission_graphs.jsonl',
    'windows': 'market_windows.jsonl',
    'cases': 'benchmark_cases.jsonl',
    'labels': 'hidden/benchmark_labels.jsonl',
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding='utf-8').splitlines() if line.strip())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')


def audit_manifest(data_root: Path, manifest_path: Path) -> dict[str, Any]:
    root = data_root.resolve()
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    errors: list[str] = []
    rebuilt_files: list[dict[str, Any]] = []
    actual_paths: dict[str, Path] = {}

    for entry in sorted(manifest.get('files', []), key=lambda row: row['path']):
        relative = entry['path']
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append(f'PATH_ESCAPE:{relative}')
            continue
        if not candidate.is_file():
            errors.append(f'MISSING_FILE:{relative}')
            continue
        actual_paths[relative] = candidate
        actual_hash = _sha256(candidate)
        try:
            actual_count = _record_count(candidate)
        except UnicodeDecodeError:
            errors.append(f'NON_UTF8_FILE:{relative}')
            continue
        if actual_hash != entry.get('sha256'):
            errors.append(f'HASH_MISMATCH:{relative}')
        if actual_count != entry.get('record_count'):
            errors.append(f'RECORD_COUNT_MISMATCH:{relative}')
        rebuilt_files.append({
            'path': relative,
            'record_count': actual_count,
            'sha256': actual_hash,
        })

    rebuilt_counts = dict(manifest.get('counts', {}))
    for key, relative in COUNT_FILES.items():
        path = actual_paths.get(relative)
        if path is not None:
            rebuilt_counts[key] = _record_count(path)
    milestones_path = actual_paths.get('event_milestones.jsonl')
    if milestones_path is not None:
        rebuilt_counts['events'] = len({row['event_id'] for row in _read_jsonl(milestones_path)})

    for key, actual in rebuilt_counts.items():
        if key in manifest.get('counts', {}) and manifest['counts'][key] != actual:
            errors.append(f'COUNT_MISMATCH:{key}')

    rebuilt_manifest = {
        'counts': rebuilt_counts,
        'dataset_version': manifest.get('dataset_version'),
        'files': rebuilt_files,
        'generated_at': manifest.get('generated_at'),
        'release_tier': manifest.get('release_tier'),
        'schema_version': manifest.get('schema_version'),
    }
    current_hash = _sha256(manifest_path)
    rebuilt_hash = hashlib.sha256(_json_bytes(rebuilt_manifest)).hexdigest()
    return {
        'status': 'READY_FOR_BASELINE_APPROVAL' if not errors else 'BLOCKED',
        'errors': errors,
        'current_manifest_sha256': current_hash,
        'rebuilt_manifest_sha256': rebuilt_hash,
        'current_manifest': manifest,
        'rebuilt_manifest': rebuilt_manifest,
    }


def write_reconciliation(
    audit: dict[str, Any],
    output_root: Path,
    *,
    frozen_manifest_sha256: str,
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / 'manifest.rebuilt.json').write_bytes(_json_bytes(audit['rebuilt_manifest']))
    transition = {
        'current_manifest_sha256': audit['current_manifest_sha256'],
        'errors': audit['errors'],
        'frozen_manifest_sha256': frozen_manifest_sha256,
        'rebuilt_manifest_sha256': audit['rebuilt_manifest_sha256'],
        'status': audit['status'],
    }
    (output_root / 'baseline_transition.json').write_bytes(_json_bytes(transition))
    readme = [
        '# FinGoose v2 Baseline Reconciliation',
        '',
        f"status={audit['status']}",
        f"frozen_manifest_sha256={frozen_manifest_sha256}",
        f"current_manifest_sha256={audit['current_manifest_sha256']}",
        f"rebuilt_manifest_sha256={audit['rebuilt_manifest_sha256']}",
        f"error_count={len(audit['errors'])}",
        '',
        'This output is read-only reconciliation evidence. It does not adopt or overwrite a production baseline.',
    ]
    (output_root / 'README.md').write_text('\n'.join(readme) + '\n', encoding='utf-8', newline='\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--manifest-path', type=Path)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--frozen-manifest-sha256', required=True)
    args = parser.parse_args()
    manifest_path = args.manifest_path or args.data_root / 'manifest.json'
    audit = audit_manifest(args.data_root, manifest_path)
    write_reconciliation(
        audit,
        args.output_root,
        frozen_manifest_sha256=args.frozen_manifest_sha256,
    )
    print(json.dumps({key: value for key, value in audit.items() if key not in {'current_manifest', 'rebuilt_manifest'}}, ensure_ascii=False, indent=2))
    return 0 if audit['status'] == 'READY_FOR_BASELINE_APPROVAL' else 1


if __name__ == '__main__':
    raise SystemExit(main())