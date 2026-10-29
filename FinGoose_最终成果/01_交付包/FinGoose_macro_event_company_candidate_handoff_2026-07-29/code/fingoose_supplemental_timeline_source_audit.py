"""Parse and conservatively audit supplemental timeline source candidates."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


EVENT_HEADING_RE = re.compile(r'^#### Event-(\d{2})\b')
NODE_HEADING_RE = re.compile(
    r'^\d+\.\s+\*\*(fast-event-(\d{2})-M\d{2})\*\*\s*(?:\((.*)\))?\s*$'
)
TIMESTAMP_RE = re.compile(r'`([^`]+)`')
MARKET_OUTCOME_IDS = {'fast-event-06-M01', 'fast-event-08-M05'}


def canonicalize_candidate_url(candidate_url: str | None) -> str | None:
    """Return a direct HTTP(S) source URL, unwrapping Google q links."""
    if not candidate_url:
        return None
    value = candidate_url.strip().strip('<>')
    parsed = urlparse(value)
    hostname = (parsed.hostname or '').lower()
    if hostname in {'google.com', 'www.google.com'} and parsed.path in {'/search', '/url'}:
        query = parse_qs(parsed.query)
        wrapped = query.get('q', [None])[0]
        if not wrapped:
            return None
        value = unquote(wrapped).strip()
        parsed = urlparse(value)
        hostname = (parsed.hostname or '').lower()
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return None
    if hostname in {'google.com', 'www.google.com'}:
        return None
    return value


def _markdown_link(line: str) -> tuple[str, str]:
    link_start = line.find('[')
    separator = line.find('](', link_start + 1)
    link_end = line.rfind(')')
    if link_start < 0 or separator < 0 or link_end <= separator + 2:
        raise ValueError(f'Invalid official-link line: {line}')
    return line[link_start + 1:separator], line[separator + 2:link_end]


def parse_attachment_candidates(text: str) -> list[dict]:
    """Parse the 50-entry Markdown table and ignore the later example JSON block."""
    primary_section = text.split('### 二、', 1)[0]
    rows: list[dict] = []
    current_event_id: str | None = None
    current: dict | None = None

    for raw_line in primary_section.splitlines():
        line = raw_line.strip()
        event_match = EVENT_HEADING_RE.match(line)
        if event_match:
            current_event_id = f'event-{event_match.group(1)}'
            continue
        node_match = NODE_HEADING_RE.match(line)
        if node_match:
            if current is not None:
                rows.append(_complete_candidate(current))
            attachment_event_id = f'event-{node_match.group(2)}'
            if current_event_id != attachment_event_id:
                raise ValueError(
                    f'Node {node_match.group(1)} is under {current_event_id}, not {attachment_event_id}'
                )
            current = {
                'attachment_node_id': node_match.group(1),
                'attachment_event_id': attachment_event_id,
                'label': (node_match.group(3) or '').strip(),
            }
            continue
        if current is None:
            continue
        if line.startswith('* **时间戳**'):
            timestamp = TIMESTAMP_RE.search(line)
            if not timestamp:
                raise ValueError(f'Missing timestamp for {current["attachment_node_id"]}')
            current['claimed_at'] = timestamp.group(1)
        elif line.startswith('* **官方链接**'):
            publisher_label, candidate_url = _markdown_link(line)
            current['publisher_label'] = publisher_label
            current['candidate_url'] = candidate_url
            current['canonical_url'] = canonicalize_candidate_url(candidate_url)
        elif line.startswith('* **引用原文**'):
            current['claimed_quote'] = line.split('：', 1)[1].strip().strip('"')

    if current is not None:
        rows.append(_complete_candidate(current))
    return rows


def _complete_candidate(candidate: dict) -> dict:
    required = {
        'attachment_node_id', 'attachment_event_id', 'label', 'claimed_at',
        'publisher_label', 'candidate_url', 'canonical_url', 'claimed_quote',
    }
    missing = sorted(required.difference(candidate))
    if missing:
        raise ValueError(
            f'Incomplete candidate {candidate.get("attachment_node_id")}: {", ".join(missing)}'
        )
    return dict(candidate)


def apply_audit_policy(candidate: dict, review: dict) -> dict:
    """Apply non-negotiable event and evidence gates to a candidate review."""
    result = {
        **candidate,
        'semantic_alignment_target': review.get('semantic_alignment_target'),
        'decision': review.get('decision', 'PENDING'),
        'reason_code': review.get('reason_code', 'UNREVIEWED'),
        'reason': review.get('reason', 'Candidate has not completed independent evidence review.'),
        'fact_status': review.get('fact_status', 'UNVERIFIED'),
        'occurred_at_verification': {
            'status': review.get('occurred_at_status', 'UNVERIFIED'),
            'value': review.get('occurred_at'),
            'locator': review.get('occurred_at_locator'),
        },
        'first_public_at_verification': {
            'status': review.get('first_public_at_status', 'UNVERIFIED'),
            'value': review.get('first_public_at'),
            'locator': review.get('first_public_at_locator'),
        },
        'evidence_quote': review.get('evidence_quote'),
        'evidence_locator': review.get('evidence_locator'),
        'publisher': review.get('publisher'),
        'source_tier': review.get('source_tier'),
        'snapshot_path': review.get('snapshot_path'),
        'sha256': review.get('sha256'),
        'node_action_constraint': (
            'OBSERVES' if candidate['attachment_node_id'] in MARKET_OUTCOME_IDS
            else review.get('node_action_constraint')
        ),
        'can_prove_transmission': False,
    }

    if candidate['attachment_event_id'] == 'event-10':
        result.update({
            'semantic_alignment_target': None,
            'decision': 'REJECT',
            'reason_code': 'EVENT_MISMATCH',
            'reason': (
                'Attachment evidence concerns the 2024 China Section 301 chain; '
                'current event-10 is the 2025 broad reciprocal-tariff event.'
            ),
        })
        return result
    if not candidate.get('canonical_url'):
        result.update({
            'decision': 'REJECT',
            'reason_code': 'INVALID_OFFICIAL_URL',
            'reason': 'Candidate URL cannot be canonicalized to a direct HTTP(S) source URL.',
        })
        return result

    if review.get('decision') == 'ACCEPT':
        required_values = (
            review.get('fact_status') == 'VERIFIED',
            review.get('occurred_at_status') == 'VERIFIED',
            bool(review.get('occurred_at')),
            bool(review.get('occurred_at_locator')),
            review.get('first_public_at_status') == 'VERIFIED',
            bool(review.get('first_public_at')),
            bool(review.get('first_public_at_locator')),
            bool(review.get('evidence_quote')),
            bool(review.get('evidence_locator')),
            bool(review.get('publisher')),
            bool(review.get('source_tier')),
            bool(review.get('snapshot_path')),
            bool(re.fullmatch(r'[0-9a-f]{64}', review.get('sha256') or '')),
            bool(review.get('semantic_alignment_target')),
        )
        if not all(required_values):
            result.update({
                'decision': 'PENDING',
                'reason_code': 'INSUFFICIENT_PROMOTION_EVIDENCE',
                'reason': (
                    'Acceptance requires verified fact and dual times, evidence locator, '
                    'publisher/tier, semantic mapping, and a SHA-256 snapshot.'
                ),
            })
    return result


def verify_snapshot(path: Path, expected_sha256: str | None) -> bool:
    if not path.is_file() or not expected_sha256:
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha256.lower()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = ''.join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
        for row in rows
    )
    path.write_text(payload, encoding='utf-8', newline='\n')
