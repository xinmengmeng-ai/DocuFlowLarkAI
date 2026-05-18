#!/usr/bin/env python
"""测试导入文件API"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from core.feishu.drive_api import drive_api


def _live_tests_enabled() -> bool:
    return os.getenv("DOCUFLOW_RUN_LIVE_TESTS") == "1"


pytestmark = pytest.mark.skipif(
    not _live_tests_enabled(),
    reason="Live Feishu tests require DOCUFLOW_RUN_LIVE_TESTS=1",
)


async def test_import():
    if not _live_tests_enabled():
        print("已跳过 live test；如需运行，请先设置 DOCUFLOW_RUN_LIVE_TESTS=1")
        return

    test_file = Path(__file__).parent.parent / "005-实施模板-计划与运营方案模板-v0.2-20181024.docx"
    
    if not test_file.exists():
        print(f"[ERROR] 测试文件不存在: {test_file}")
        return
    
    print(f"[INFO] 开始导入: {test_file.name}")
    
    try:
        result = await drive_api.import_file(str(test_file))
        print(f"[SUCCESS] 导入成功!")
        print(f"  Token: {result['token']}")
        print(f"  Type: {result['type']}")
        print(f"  URL: {result['url']}")
    except Exception as e:
        print(f"[ERROR] 导入失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_import())
