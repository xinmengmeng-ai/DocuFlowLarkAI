"""
测试模板导入导出功能
"""
import asyncio
import os
import sys
import json
from pathlib import Path

import pytest

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from loguru import logger
logger.remove()
logger.add(sys.stderr, level="INFO")

pytestmark = pytest.mark.skipif(
    os.getenv("DOCUFLOW_RUN_LIVE_TESTS") != "1",
    reason="Live template import/export tests are disabled unless DOCUFLOW_RUN_LIVE_TESTS=1",
)

ROOT_DIR = Path(__file__).resolve().parents[1]
TMP_DIR = ROOT_DIR / "tmp"
LIVE_BASE_URL = os.getenv("DOCUFLOW_LIVE_BASE_URL", "http://localhost:8000")


async def test_export_template():
    """测试导出模板"""
    import httpx
    
    print("\n" + "="*60)
    print("测试1: 导出模板")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        # 导出 product_kb 模板
        resp = await client.get(
            f"{LIVE_BASE_URL}/api/templates/product_kb/export"
        )
        
        if resp.status_code == 200:
            # 保存到文件
            TMP_DIR.mkdir(exist_ok=True)
            output_file = TMP_DIR / "exported_template.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(resp.json(), f, ensure_ascii=False, indent=2)
            print(f"✅ 导出成功: {output_file}")
            print(f"   内容预览: {json.dumps(resp.json(), ensure_ascii=False, indent=2)[:500]}...")
            return True
        else:
            print(f"❌ 导出失败: {resp.status_code} - {resp.text}")
            return False


async def test_import_template():
    """测试导入模板"""
    import httpx
    
    print("\n" + "="*60)
    print("测试2: 导入模板")
    print("="*60)
    
    # 创建测试 JSON
    test_template = {
        "name": "测试导入模板",
        "description": "通过API导入的测试模板",
        "structure": [
            {
                "id": "test1",
                "name": "测试文件夹1",
                "type": "folder",
                "children": [
                    {"id": "test1-1", "name": "子文档1", "type": "folder"}
                ]
            },
            {
                "id": "test2",
                "name": "测试文件夹2",
                "type": "folder"
            }
        ]
    }
    
    # 保存临时文件
    TMP_DIR.mkdir(exist_ok=True)
    temp_file = TMP_DIR / "temp_import.json"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(test_template, f, ensure_ascii=False)
    
    async with httpx.AsyncClient() as client:
        with open(temp_file, 'rb') as f:
            resp = await client.post(
                f"{LIVE_BASE_URL}/api/templates/import",
                files={"file": ("test_template.json", f, "application/json")}
            )
        
        if resp.status_code == 200:
            result = resp.json()
            print(f"✅ 导入成功: {result['template']['id']}")
            print(f"   名称: {result['template']['name']}")
            return True
        else:
            print(f"❌ 导入失败: {resp.status_code} - {resp.text}")
            return False


async def test_list_templates():
    """测试列出模板（验证导入结果）"""
    import httpx
    
    print("\n" + "="*60)
    print("测试3: 列出模板验证")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{LIVE_BASE_URL}/api/templates")
        
        if resp.status_code == 200:
            templates = resp.json()
            print(f"✅ 共有 {len(templates)} 个模板")
            for t in templates:
                print(f"   - {t['name']} ({t['id']})")
            return True
        else:
            print(f"❌ 查询失败: {resp.status_code}")
            return False


async def main():
    """运行所有测试"""
    print("模板导入导出测试")
    print("确保后端服务已启动: python backend/main.py")
    
    results = []
    
    # 测试导出
    results.append(("export", await test_export_template()))
    
    # 测试导入
    results.append(("import", await test_import_template()))
    
    # 测试列出
    results.append(("list", await test_list_templates()))
    
    # 清理临时文件
    temp_file = TMP_DIR / "temp_import.json"
    if temp_file.exists():
        temp_file.unlink()
    
    # 打印结果
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    print(f"\n总计: {passed}/{total} 通过")


if __name__ == "__main__":
    asyncio.run(main())
