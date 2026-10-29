from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from fingoose_official_pdf import extract_pdf_pages
from fingoose_public_sources import SourcePolicy, SourcePolicyError


ROOT = Path(__file__).resolve().parent
HISTORICAL_EVIDENCE_VERSION = 'fingoose-historical-company-impact-evidence-v1.0'


class HistoricalEvidenceError(ValueError):
    """Raised when a historical company disclosure cannot enter the isolated evidence layer."""


def historical_source_id(company_code: str, report_type: str) -> str:
    return 'historical-cninfo-' + company_code.lower().replace('.', '-') + '-' + report_type.replace('_', '-')


def build_historical_report_manifest(
    row: Mapping[str, Any], *, workspace_root: Path = ROOT,
    page_count_reader: Callable[[Path], int] | None = None,
) -> dict[str, Any]:
    """Validate one historical report without applying v0.3 report-period restrictions."""
    try:
        SourcePolicy.from_config().validate_url(str(row['source_url']))
    except (KeyError, SourcePolicyError) as error:
        raise HistoricalEvidenceError(str(error)) from error
    snapshot = workspace_root / str(row.get('local_snapshot_path') or '')
    if not snapshot.is_file():
        raise HistoricalEvidenceError('SNAPSHOT_NOT_FOUND')
    actual_hash = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    if actual_hash != row.get('content_sha256'):
        raise HistoricalEvidenceError('SNAPSHOT_HASH_MISMATCH')
    try:
        page_count = (page_count_reader or (lambda path: len(PdfReader(str(path), strict=False).pages)))(snapshot)
    except Exception as error:
        raise HistoricalEvidenceError('PDF_UNREADABLE') from error
    if page_count != row.get('page_count'):
        raise HistoricalEvidenceError('PDF_PAGE_COUNT_MISMATCH')
    return {
        'source_id': historical_source_id(str(row['company_code']), str(row['report_type'])),
        'source_kind': 'historical_company_report',
        'publisher': 'CNINFO',
        'source_url': str(row['source_url']),
        'published_at': str(row['announcement_date']) + 'T00:00:00+08:00',
        'retrieved_at': str(row.get('retrieved_at') or datetime.now(timezone.utc).isoformat()),
        'local_snapshot_path': str(row['local_snapshot_path']),
        'content_sha256': actual_hash,
        'media_type': 'application/pdf',
        'source_policy': 'public_official_only',
        'snapshot_status': 'verified',
        'evidence_scope': 'historical_event_impact_only',
        'company_code': str(row['company_code']),
        'report_type': str(row['report_type']),
        'announcement_date': str(row['announcement_date']),
        'page_count': page_count,
        'formal_sample_generation_allowed': False,
    }


def build_historical_page_evidence(
    manifest_rows: Iterable[Mapping[str, Any]], *, workspace_root: Path = ROOT,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for manifest in manifest_rows:
        snapshot = workspace_root / str(manifest['local_snapshot_path'])
        pages = extract_pdf_pages(snapshot, source_id=str(manifest['source_id']))
        if len(pages) != manifest['page_count']:
            raise HistoricalEvidenceError('PDF_PAGE_COUNT_MISMATCH')
        for page in pages:
            evidence.append({
                'source_id': manifest['source_id'],
                'source_url': manifest['source_url'],
                'published_at': manifest['published_at'],
                'content_sha256': manifest['content_sha256'],
                'source_locator': str(manifest['local_snapshot_path']) + ':page=' + str(page['page_number']),
                'page_number': page['page_number'],
                'statement': page['text'],
                'text_sha256': page['text_sha256'],
                'extraction_status': page['extraction_status'],
                'company_code': manifest['company_code'],
                'report_type': manifest['report_type'],
                'evidence_scope': 'historical_event_impact_only',
                'model_visible': False,
                'formal_sample_generation_allowed': False,
            })
    return evidence

def derive_q2_fact(q1_fact: Mapping[str, Any], h1_fact: Mapping[str, Any]) -> dict[str, Any]:
    """Derive one 2022Q2 fact from comparable official Q1 and H1 cumulative facts."""
    for field, error_code in (
        ('company_code', 'Q2_FACT_COMPANY_MISSING'),
        ('metric', 'Q2_FACT_METRIC_MISSING'),
        ('unit', 'Q2_FACT_UNIT_MISSING'),
        ('source_id', 'Q2_FACT_SOURCE_MISSING'),
        ('source_locator', 'Q2_FACT_LOCATOR_MISSING'),
        ('text_sha256', 'Q2_FACT_HASH_MISSING'),
    ):
        if not q1_fact.get(field) or not h1_fact.get(field):
            raise HistoricalEvidenceError(error_code)
    if q1_fact.get('report_type') != 'q1_2022' or h1_fact.get('report_type') != 'h1_2022':
        raise HistoricalEvidenceError('Q2_FACT_REPORT_TYPE_INVALID')
    if q1_fact['company_code'] != h1_fact['company_code']:
        raise HistoricalEvidenceError('Q2_FACT_COMPANY_MISMATCH')
    if q1_fact['metric'] != h1_fact['metric']:
        raise HistoricalEvidenceError('Q2_FACT_METRIC_MISMATCH')
    if q1_fact['unit'] != h1_fact['unit']:
        raise HistoricalEvidenceError('Q2_FACT_UNIT_MISMATCH')
    for fact in (q1_fact, h1_fact):
        value = fact.get('value')
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise HistoricalEvidenceError('Q2_FACT_VALUE_INVALID')
        if not math.isfinite(float(value)):
            raise HistoricalEvidenceError('Q2_FACT_VALUE_INVALID')
        if not isinstance(fact['text_sha256'], str) or len(fact['text_sha256']) != 64:
            raise HistoricalEvidenceError('Q2_FACT_HASH_INVALID')
    try:
        q1_decimal = Decimal(str(q1_fact['value']))
        h1_decimal = Decimal(str(h1_fact['value']))
    except (InvalidOperation, ValueError) as error:
        raise HistoricalEvidenceError('Q2_FACT_VALUE_INVALID') from error
    result_decimal = h1_decimal - q1_decimal
    value_decimal = format(result_decimal, 'f')
    value = int(result_decimal) if result_decimal == result_decimal.to_integral_value() else float(result_decimal)
    evidence_refs = [
        {
            'source_id': str(fact['source_id']),
            'source_locator': str(fact['source_locator']),
            'text_sha256': str(fact['text_sha256']),
        }
        for fact in (q1_fact, h1_fact)
    ]
    return {
        'company_code': str(q1_fact['company_code']),
        'metric': str(q1_fact['metric']),
        'unit': str(q1_fact['unit']),
        'period': '2022Q2',
        'value': value,
        'value_decimal': value_decimal,
        'derivation_type': 'cumulative_difference',
        'calculation': {
            'formula': 'h1_cumulative - q1_cumulative',
            'h1_cumulative_value': h1_fact['value'],
            'q1_cumulative_value': q1_fact['value'],
            'h1_cumulative_value_decimal': format(h1_decimal, 'f'),
            'q1_cumulative_value_decimal': format(q1_decimal, 'f'),
            'result': value,
            'result_decimal': value_decimal,
            'unit': str(q1_fact['unit']),
        },
        'evidence_refs': evidence_refs,
        'evidence_scope': 'historical_event_impact_only',
        'model_visible': False,
        'formal_sample_generation_allowed': False,
    }


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + '\n' for row in rows), encoding='utf-8')



