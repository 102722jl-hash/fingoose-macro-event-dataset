import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "code" / "fingoose_ui_release.py"
SPEC = importlib.util.spec_from_file_location("fingoose_ui_release", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def test_bundle_round_trip_and_event_hashes(tmp_path):
    bundle = {"events": [{"event_id": "event-01", "title": "保留原文"}]}
    path = tmp_path / "ui_data_bundle.js"
    module.write_bundle(path, bundle)
    assert module.load_bundle(path) == bundle
    assert module.event_hashes(bundle) == {"event-01": module.value_sha(bundle["events"][0])}


def test_bundle_rejects_wrong_prefix(tmp_path):
    path = tmp_path / "ui_data_bundle.js"
    path.write_text("window.WRONG={};", encoding="utf-8")
    try:
        module.load_bundle(path)
    except ValueError as exc:
        assert str(exc) == "UI_BUNDLE_PREFIX_INVALID"
    else:
        raise AssertionError("wrong prefix accepted")
