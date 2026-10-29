import json
from pathlib import Path

import pytest

from fingoose_training.loaders import JsonlError, load_source_bundle, read_json, read_jsonl


def test_read_jsonl_reports_path_and_line_for_bad_json(tmp_path: Path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"event_id":"event-01"}\nnot-json\n', encoding="utf-8")

    with pytest.raises(JsonlError, match=r"bad\.jsonl:2"):
        read_jsonl(path)


def test_read_jsonl_rejects_duplicate_stable_ids(tmp_path: Path):
    path = tmp_path / "rows.jsonl"
    row = {"event_id": "event-01", "case_id": "qa-1"}
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(JsonlError, match="duplicate case_id"):
        read_jsonl(path, unique_key="case_id")


def test_read_json_requires_an_object(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        read_json(path)


def test_load_source_bundle_uses_only_explicit_configured_files(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "visible.jsonl").write_text('{"event_id":"event-01"}\n', encoding="utf-8")
    (source_dir / "hidden.jsonl").write_text('{"secret":true}\n', encoding="utf-8")
    config = {
        "sources": {
            "macro": {
                "base_dir": "source",
                "files": {"event_episodes": "visible.jsonl"},
            }
        }
    }

    bundle, paths = load_source_bundle(tmp_path, config)

    assert bundle == {"event_episodes": [{"event_id": "event-01"}]}
    assert paths == {"event_episodes": source_dir / "visible.jsonl"}
