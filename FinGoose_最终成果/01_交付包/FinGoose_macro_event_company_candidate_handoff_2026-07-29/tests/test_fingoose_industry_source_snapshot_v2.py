from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def _output_root() -> Path:
    path = ROOT / "work/_test_event01_source_snapshot"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_snapshot_accepts_only_body_containing_required_quote() -> None:
    from fingoose_industry_source_snapshot_v2 import snapshot_source

    output_root = _output_root()
    target = {
        "source_id": "source-test",
        "source_url": "https://example.invalid/source",
        "media_type": "text/html",
        "required_quote": "\u6838\u9178\u68c0\u6d4b",
        "published_at": "2020-02-19T00:00:00+08:00",
        "usage_boundary": "PREDICTION_VISIBLE",
    }
    accepted = snapshot_source(
        target,
        output_root=output_root,
        fetch_bytes=lambda _: "<html><body>\u6838\u9178\u68c0\u6d4b\u4f5c\u4e3a\u75c5\u539f\u5b66\u8bc1\u636e</body></html>".encode(),
        accessed_at="2026-08-04T12:00:00+08:00",
    )
    assert accepted["fetch_status"] == "RETRIEVED_QUOTE_VERIFIED"
    assert (output_root / accepted["raw_snapshot_path"]).exists()

    rejected = snapshot_source(
        {**target, "source_id": "source-mismatch", "required_quote": "\u4e0d\u5b58\u5728\u7684\u53e5\u5b50"},
        output_root=output_root,
        fetch_bytes=lambda _: b"<html><body>only a title</body></html>",
        accessed_at="2026-08-04T12:00:00+08:00",
    )
    assert rejected["fetch_status"] == "CONTENT_MISMATCH"
    assert rejected["verified_quote"] is None


def test_snapshot_records_fetch_failure_without_creating_a_snapshot() -> None:
    from fingoose_industry_source_snapshot_v2 import snapshot_source

    def fail(_: str) -> bytes:
        raise TimeoutError("source timed out")

    result = snapshot_source(
        {
            "source_id": "source-timeout",
            "source_url": "https://example.invalid/timeout",
            "media_type": "text/html",
            "required_quote": "\u6b63\u6587",
        },
        output_root=_output_root(),
        fetch_bytes=fail,
        accessed_at="2026-08-04T12:00:00+08:00",
    )
    assert result["fetch_status"] == "FETCH_FAILED"
    assert result["raw_snapshot_path"] is None
    assert result["failure_reason"].startswith("TimeoutError:")

def test_snapshot_ignores_layout_whitespace_at_cjk_numeric_and_punctuation_boundaries() -> None:
    from fingoose_industry_source_snapshot_v2 import snapshot_source

    result = snapshot_source(
        {
            "source_id": "source-layout-whitespace",
            "source_url": "https://example.invalid/layout-whitespace",
            "media_type": "text/html",
            "required_quote": "3月份，社会消费品零售总额26450亿元，同比下降15.8%",
        },
        output_root=_output_root(),
        fetch_bytes=lambda _: (
            "<html><body>3 月份，社会消费品零售总额 26450 亿元，同比下降 15.8 %</body></html>"
        ).encode("utf-8"),
        accessed_at="2026-08-04T12:00:00+08:00",
    )

    assert result["fetch_status"] == "RETRIEVED_QUOTE_VERIFIED"
    assert result["verified_quote"] == "3月份，社会消费品零售总额26450亿元，同比下降15.8%"


def test_snapshot_preserves_semantic_spaces_between_english_words() -> None:
    from fingoose_industry_source_snapshot_v2 import snapshot_source

    result = snapshot_source(
        {
            "source_id": "source-english-boundary",
            "source_url": "https://example.invalid/english-boundary",
            "media_type": "text/html",
            "required_quote": "revenue passenger kilometres",
        },
        output_root=_output_root(),
        fetch_bytes=lambda _: b"<html><body>revenuepassenger kilometres</body></html>",
        accessed_at="2026-08-04T12:00:00+08:00",
    )

    assert result["fetch_status"] == "CONTENT_MISMATCH"
    assert result["verified_quote"] is None

def test_fetch_url_uses_fixed_browser_headers(monkeypatch) -> None:
    import fingoose_industry_source_snapshot_v2 as source_module

    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return b"official body"

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(source_module.urllib.request, "urlopen", fake_urlopen)

    assert source_module._fetch_url("https://example.invalid/official") == b"official body"
    assert captured["timeout"] == 45
    assert captured["request"].get_header("User-agent").startswith("Mozilla/5.0")
    assert "zh-CN" in captured["request"].get_header("Accept-language")
