import json

from audit_outputs import canonical_json, init_run, sha256_path


def test_canonical_json_is_stable():
    left = canonical_json({"b": [2, 1], "a": "中文"})
    right = canonical_json({"a": "中文", "b": [2, 1]})
    assert left == right == '{"a":"中文","b":[2,1]}\n'


def test_init_run_creates_immutable_audit_contract(tmp_path):
    run_dir = init_run(
        tmp_path,
        run_id="run-test-001",
        request={"mode": "audit", "profile": "fingoose"},
    )
    assert json.loads((run_dir / "request.json").read_text(encoding="utf-8")) == {
        "mode": "audit",
        "profile": "fingoose",
        "run_id": "run-test-001",
    }
    assert sha256_path(run_dir / "request.json")
    assert (run_dir / "base_unified_events.jsonl").exists()
    assert (run_dir / "content_candidates.jsonl").exists()
    assert (run_dir / "accepted_content.jsonl").exists()


def test_init_run_refuses_to_overwrite(tmp_path):
    init_run(tmp_path, run_id="run-test-001", request={"mode": "audit"})
    try:
        init_run(tmp_path, run_id="run-test-001", request={"mode": "audit"})
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing run must not be overwritten")
