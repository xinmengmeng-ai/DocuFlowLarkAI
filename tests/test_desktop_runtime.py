import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_existing_backend_must_match_current_runtime_dir(tmp_path):
    import desktop_app

    current_runtime = tmp_path / "source-runtime"
    release_runtime = tmp_path / "release-runtime"
    current_runtime.mkdir()
    release_runtime.mkdir()

    matching_payload = {
        "status": "ready",
        "stats": {},
        "active_tasks": 0,
        "runtime": {"base_dir": str(current_runtime)},
    }
    mismatched_payload = {
        "status": "ready",
        "stats": {},
        "active_tasks": 0,
        "runtime": {"base_dir": str(release_runtime)},
    }
    legacy_payload = {
        "status": "ready",
        "stats": {},
        "active_tasks": 0,
    }

    assert desktop_app._backend_payload_matches_runtime(matching_payload, current_runtime)
    assert not desktop_app._backend_payload_matches_runtime(mismatched_payload, current_runtime)
    assert not desktop_app._backend_payload_matches_runtime(legacy_payload, current_runtime)
