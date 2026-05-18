import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import BackgroundTasks


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.mark.asyncio
async def test_deleting_running_task_cancels_background_work():
    import main as main_module

    task_id = "cancel-on-delete"
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def never_finishes(running_task_id):
        assert running_task_id == task_id
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    original_tasks = dict(main_module.app_state["tasks"])
    original_handles = dict(main_module.app_state.get("task_handles", {}))
    original_status = main_module.app_state["system_status"]

    try:
        main_module.app_state["tasks"] = {
            task_id: {
                "id": task_id,
                "name": "Cancel on delete",
                "status": "pending",
                "progress": 0,
                "files": [],
                "duplicates": [],
            }
        }
        main_module.app_state["task_handles"] = {}
        main_module.app_state["system_status"] = "ready"

        with (
            patch.object(main_module, "run_migration_task", never_finishes),
            patch.object(main_module.manager, "send_log", AsyncMock()),
        ):
            await main_module.start_task(task_id, BackgroundTasks())
            assert task_id in main_module.app_state["task_handles"]
            await asyncio.wait_for(started.wait(), timeout=1)

            await main_module.delete_task(task_id)
            await asyncio.wait_for(cancelled.wait(), timeout=1)
            await asyncio.sleep(0)

        assert task_id not in main_module.app_state["tasks"]
        assert task_id not in main_module.app_state["task_handles"]
        assert main_module.app_state["system_status"] == "ready"
    finally:
        for handle in main_module.app_state.get("task_handles", {}).values():
            if not handle.done():
                handle.cancel()
        main_module.app_state["tasks"] = original_tasks
        main_module.app_state["task_handles"] = original_handles
        main_module.app_state["system_status"] = original_status
