from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "configs" / "fingoose_research_candidate_v0_3.json"


MAX_RESPONSE_BYTES = 50 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 30
USER_AGENT = 'FinGoose/0.3 official-source-intake'


class SourceDownloadError(RuntimeError):
    '''Raised when an official source cannot be safely snapshotted.'''


@dataclass(frozen=True)
class SnapshotResult:
    path: Path
    content_sha256: str
    media_type: str


class SourcePolicyError(ValueError):
    """Raised when a URL cannot enter public-official evidence."""


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO timestamp and reject values without an explicit timezone."""
    if not isinstance(value, str):
        raise ValueError("INVALID_TIMESTAMP: expected an ISO timestamp string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"INVALID_TIMESTAMP: {value!r}") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"TIMEZONE_REQUIRED: {value!r}")
    return parsed


def _normalize_domain(value: str) -> str:
    domain = value.strip().lower().rstrip(".")
    if not domain or "/" in domain or ":" in domain:
        raise ValueError(f"invalid domain: {value!r}")
    try:
        return domain.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise ValueError(f"invalid domain: {value!r}") from error


def _matches_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


class SourcePolicy:
    def __init__(self, official_domains: list[str] | tuple[str, ...], forbidden_domains: list[str] | tuple[str, ...]):
        self.official_domains = tuple(_normalize_domain(domain) for domain in official_domains)
        self.forbidden_domains = tuple(_normalize_domain(domain) for domain in forbidden_domains)

    @classmethod
    def from_config(cls, config: Path | str | Mapping[str, Any] = DEFAULT_CONFIG_PATH) -> "SourcePolicy":
        if isinstance(config, Mapping):
            values = config
        else:
            values = json.loads(Path(config).read_text(encoding="utf-8"))
        if values.get("source_policy") != "public_official_only" or values.get("paid_vendor_data_allowed") is not False:
            raise SourcePolicyError("INVALID_SOURCE_POLICY_CONFIG")
        return cls(values["official_domains"], values["forbidden_domains"])

    def validate_url(self, source_url: str) -> str:
        """Return the normalized official host or raise a fail-closed policy error."""
        if not isinstance(source_url, str):
            raise SourcePolicyError("INVALID_SOURCE_URL")
        if source_url != source_url.strip() or any(
            ord(character) < 32 or ord(character) == 127
            for character in source_url
        ):
            raise SourcePolicyError(f"INVALID_SOURCE_URL: {source_url!r}")
        try:
            parsed = urlsplit(source_url)
            host = _normalize_domain(parsed.hostname or "")
            _ = parsed.port  # Trigger urllib's port syntax and range validation.
        except (ValueError, UnicodeError):
            raise SourcePolicyError(f"INVALID_SOURCE_URL: {source_url!r}") from None
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.netloc
            or parsed.netloc.endswith(":")
            or parsed.username
            or parsed.password
        ):
            raise SourcePolicyError(f"INVALID_SOURCE_URL: {source_url!r}")
        if any(_matches_domain(host, domain) for domain in self.forbidden_domains):
            raise SourcePolicyError(f"PAID_VENDOR_SOURCE_FORBIDDEN: {host}")
        if not any(_matches_domain(host, domain) for domain in self.official_domains):
            raise SourcePolicyError(f"UNAPPROVED_SOURCE_DOMAIN: {host}")
        return host


def snapshot_bytes(body: bytes, *, suffix: str, snapshot_root: Path) -> SnapshotResult:
    '''Atomically store bytes under their SHA-256 name, reusing identical content.'''
    if suffix not in {'.html', '.pdf'}:
        raise SourceDownloadError(f'INVALID_SNAPSHOT_SUFFIX: {suffix!r}')
    if not isinstance(body, bytes):
        raise TypeError('body must be bytes')
    content_sha256 = hashlib.sha256(body).hexdigest()
    snapshot_root.mkdir(parents=True, exist_ok=True)
    destination = snapshot_root / f'{content_sha256}{suffix}'
    if not destination.exists():
        with tempfile.NamedTemporaryFile(
            mode='wb', delete=False, dir=snapshot_root, prefix='.snapshot-', suffix='.tmp'
        ) as temporary:
            temporary.write(body)
            temporary_path = Path(temporary.name)
        try:
            os.replace(temporary_path, destination)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
    media_type = 'text/html' if suffix == '.html' else 'application/pdf'
    return SnapshotResult(destination, content_sha256, media_type)


def _response_media_type(response: Any) -> str:
    headers = getattr(response, 'headers', None)
    if headers is None:
        return ''
    if hasattr(headers, 'get_content_type'):
        return headers.get_content_type().lower()
    value = headers.get('Content-Type', '')
    return value.split(';', 1)[0].strip().lower()


def _read_limited(response: Any) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(64 * 1024)
        if not chunk:
            return b''.join(chunks)
        total += len(chunk)
        if total > MAX_RESPONSE_BYTES:
            raise SourceDownloadError('RESPONSE_SIZE_LIMIT_EXCEEDED')
        chunks.append(chunk)


def download_source(
    row: Mapping[str, Any],
    policy: SourcePolicy,
    snapshot_root: Path,
    *,
    opener: Callable[..., Any] = urlopen,
) -> SnapshotResult:
    '''Download a cataloged official source with strict media and size boundaries.'''
    source_url = row.get('source_url')
    expected_media_type = row.get('media_type')
    policy.validate_url(source_url)
    if expected_media_type not in {'text/html', 'application/pdf'}:
        raise SourceDownloadError(f'UNSUPPORTED_EXPECTED_MEDIA_TYPE: {expected_media_type!r}')
    request = Request(source_url, headers={'User-Agent': USER_AGENT})
    try:
        with opener(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            actual_media_type = _response_media_type(response)
            if actual_media_type != expected_media_type:
                display_media_type = actual_media_type or 'missing'
                raise SourceDownloadError(
                    f'MEDIA_TYPE_MISMATCH: expected={expected_media_type} actual={display_media_type}'
                )
            body = _read_limited(response)
    except SourceDownloadError:
        raise
    except Exception as error:
        raise SourceDownloadError(f'OFFICIAL_DOWNLOAD_FAILED: {type(error).__name__}') from error
    suffix = '.html' if expected_media_type == 'text/html' else '.pdf'
    return snapshot_bytes(body, suffix=suffix, snapshot_root=snapshot_root)
