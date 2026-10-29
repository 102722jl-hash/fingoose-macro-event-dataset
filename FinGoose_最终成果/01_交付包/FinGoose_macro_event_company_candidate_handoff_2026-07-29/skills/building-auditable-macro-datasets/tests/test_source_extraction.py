from source_extractors import normalize_search_hit, normalize_evidence_candidate, store_snapshot


def test_search_hit_keeps_query_rank_and_adapter():
    hit = normalize_search_hit(
        query="site:who.int pandemic declaration",
        adapter="fixture-search",
        rank=1,
        url="https://www.who.int/example",
        title="WHO statement",
    )
    assert hit["query"] == "site:who.int pandemic declaration"
    assert hit["adapter"] == "fixture-search"
    assert hit["rank"] == 1
    assert hit["candidate_url"] == "https://www.who.int/example"


def test_evidence_candidate_requires_quote_locator_and_url():
    result = normalize_evidence_candidate({
        "source_url": "https://example.test/official",
        "publisher": "Official publisher",
        "published_at": "2026-01-01T00:00:00Z",
        "original_quote": "Official text",
        "locator": {"type": "html_text", "value": "Official text"},
        "retrieved_at": "2026-01-02T00:00:00Z",
        "snapshot_sha256": "a" * 64,
    })
    assert result["evidence_id"].startswith("evidence-")
    assert result["acceptance_status"] == "CANDIDATE"


def test_search_snippet_cannot_become_source_fact():
    result = normalize_evidence_candidate({
        "source_url": "https://example.test/official",
        "search_snippet": "snippet only",
    })
    assert result["acceptance_status"] == "REJECTED"
    assert result["acceptance_reason"] == "ORIGINAL_QUOTE_MISSING"


def test_store_snapshot_writes_exact_bytes_and_stable_relative_path(tmp_path):
    payload = b"official body"
    result = store_snapshot(
        tmp_path,
        source_url="https://example.test/official",
        content_bytes=payload,
        content_type="text/html",
        retrieved_at="2026-01-02T00:00:00Z",
        allow_raw_storage=True,
    )
    stored = tmp_path / result["snapshot_path"]
    assert stored.read_bytes() == payload
    assert stored.name == f'{result["snapshot_sha256"]}.html'
    assert result["raw_storage_status"] == "STORED"


def test_store_snapshot_honors_raw_storage_policy(tmp_path):
    result = store_snapshot(
        tmp_path,
        source_url="https://example.test/restricted",
        content_bytes=b"licensed body",
        content_type="application/pdf",
        retrieved_at="2026-01-02T00:00:00Z",
        allow_raw_storage=False,
    )
    assert result["snapshot_path"] is None
    assert result["snapshot_sha256"]
    assert result["raw_storage_status"] == "NOT_STORED_BY_POLICY"
    assert not (tmp_path / "snapshots").exists()
