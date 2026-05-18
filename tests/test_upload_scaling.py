import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))


def test_task_upload_capacity_allows_10000_total_documents():
    from main import MAX_TASK_UPLOAD_FILES, _ensure_task_upload_capacity

    task = {
        "files": [{"name": f"file_{index}.md"} for index in range(MAX_TASK_UPLOAD_FILES - 1)],
        "duplicates": [],
    }

    _ensure_task_upload_capacity(task, 1)


def test_task_upload_capacity_rejects_more_than_10000_total_documents():
    from main import MAX_TASK_UPLOAD_FILES, _ensure_task_upload_capacity

    task = {
        "files": [{"name": f"file_{index}.md"} for index in range(MAX_TASK_UPLOAD_FILES)],
        "duplicates": [],
    }

    with pytest.raises(HTTPException) as exc_info:
        _ensure_task_upload_capacity(task, 1)

    assert exc_info.value.status_code == 400
    assert str(MAX_TASK_UPLOAD_FILES) in exc_info.value.detail


def test_frontend_batches_large_task_uploads():
    frontend = (Path(__file__).parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")

    assert "const MAX_TASK_UPLOAD_FILES = 10000;" in frontend
    assert "const UPLOAD_BATCH_SIZE = 500;" in frontend
    assert "for (let start = 0; start < selectedFiles.length; start += UPLOAD_BATCH_SIZE)" in frontend
    assert "selectedFiles.slice(start, start + UPLOAD_BATCH_SIZE)" in frontend


def test_upload_route_accepts_more_than_1000_files(tmp_path):
    from main import app, app_state, manager
    import main as main_module
    import config as config_module

    task_id = "bulk-1001"
    original_tasks = dict(app_state["tasks"])
    app_state["tasks"] = {
        task_id: {
            "id": task_id,
            "name": "Bulk upload",
            "status": "pending",
            "progress": 0,
            "template_id": None,
            "target_space_id": None,
            "files": [],
            "duplicates": [],
        }
    }

    files = [
        ("files", (f"file_{index}.md", b"x", "text/markdown"))
        for index in range(1001)
    ]

    try:
        with (
            patch.object(config_module, "CACHE_DIR", tmp_path),
            patch.object(main_module, "_resolve_duplicate_check_space_id", AsyncMock(return_value=None)),
            patch.object(manager, "send_log", AsyncMock()),
        ):
            response = TestClient(app).post(f"/api/tasks/{task_id}/upload", files=files)
    finally:
        app_state["tasks"] = original_tasks

    assert response.status_code == 200
    assert len(response.json()["uploaded"]) == 1001
