import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import config as config_module


def test_frozen_bootstrap_refreshes_existing_frontend_assets(monkeypatch, tmp_path):
    resource_dir = tmp_path / "resource"
    runtime_dir = tmp_path / "runtime"
    (resource_dir / "frontend").mkdir(parents=True)
    (runtime_dir / "frontend").mkdir(parents=True)

    (resource_dir / "frontend" / "index.html").write_text("new frontend", encoding="utf-8")
    (runtime_dir / "frontend" / "index.html").write_text("old frontend", encoding="utf-8")

    monkeypatch.setattr(config_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config_module, "RESOURCE_DIR", resource_dir)
    monkeypatch.setattr(config_module, "BASE_DIR", runtime_dir)

    config_module._bootstrap_runtime_dirs()

    assert (runtime_dir / "frontend" / "index.html").read_text(encoding="utf-8") == "new frontend"
