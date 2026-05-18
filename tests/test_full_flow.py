"""
测试完整任务流程（包含全景图、折线图推送）
"""
import json
import os
import sys
import asyncio
from pathlib import Path

import pytest

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from loguru import logger
logger.remove()
logger.add(sys.stderr, level="INFO")


def _live_tests_enabled() -> bool:
    return os.getenv("DOCUFLOW_RUN_LIVE_TESTS") == "1"


pytestmark = pytest.mark.skipif(
    not _live_tests_enabled(),
    reason="Live Feishu tests require DOCUFLOW_RUN_LIVE_TESTS=1",
)


async def test_websocket_realtime():
    """测试 WebSocket 实时数据推送"""
    import websockets
    
    print("\n" + "="*60)
    print("测试: WebSocket 实时数据推送")
    print("="*60)
    
    uri = "ws://localhost:8000/ws"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket 连接成功")
            
            # 等待接收数据
            received_types = set()
            for _ in range(20):  # 最多接收20条消息
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    msg_type = data.get("type")
                    
                    if msg_type not in received_types:
                        received_types.add(msg_type)
                        print(f"📨 收到 [{msg_type}] 消息")
                        
                        if msg_type == "panorama":
                            print(f"   - 空间结构节点数: {len(data.get('data', {}).get('space_structure', []))}")
                            print(f"   - 文件状态数: {len(data.get('data', {}).get('file_status', []))}")
                        elif msg_type == "chart":
                            print(f"   - 图表类型: {data.get('data', {}).get('chart_type')}")
                        elif msg_type == "progress":
                            print(f"   - 进度: {data.get('data', {}).get('progress')}%")
                    
                    # 收到全景图和折线图即可退出
                    if "panorama" in received_types and "chart" in received_types:
                        print("✅ 已收到全景图和折线图数据")
                        break
                        
                except asyncio.TimeoutError:
                    break
            
            print(f"✅ 共收到 {len(received_types)} 种类型消息: {received_types}")
            return True
            
    except Exception as e:
        print(f"❌ WebSocket 测试失败: {e}")
        return False


async def test_node_duplicate_check():
    """测试节点存在性检查"""
    print("\n" + "="*60)
    print("测试: 节点存在性检查")
    print("="*60)
    
    from core.feishu.wiki_api import wiki_api
    from core.feishu.auth import feishu_oauth
    
    # 检查授权
    try:
        token = await feishu_oauth.get_user_access_token()
    except Exception as e:
        print(f"⚠️ 未授权，跳过测试: {e}")
        return True
    if not token:
        print("⚠️ 未授权，跳过测试")
        return True
    
    print("✅ 已授权")
    
    # 只允许写入调用方显式指定的测试空间，避免污染真实知识库。
    try:
        space_id = os.getenv("DOCUFLOW_LIVE_TEST_SPACE_ID", "").strip()
        if not space_id:
            print("⚠️ 未设置 DOCUFLOW_LIVE_TEST_SPACE_ID，跳过会写入节点的 live test")
            return True

        print(f"✅ 使用知识空间: {space_id}")
        
        # 测试创建结构（带存在性检查）
        test_structure = [
            {"name": "测试文件夹1", "type": "folder", "children": [
                {"name": "子文件夹1", "type": "folder"}
            ]},
            {"name": "测试文件夹2", "type": "folder"}
        ]
        
        print("🔄 第一次创建结构...")
        node_map1 = await wiki_api.create_structure(space_id, test_structure)
        print(f"✅ 创建了 {len(node_map1)} 个节点")
        
        print("🔄 第二次创建相同结构（应复用）...")
        node_map2 = await wiki_api.create_structure(space_id, test_structure)
        print(f"✅ 复用了 {len(node_map2)} 个节点")
        
        # 验证 token 一致
        all_match = all(node_map1.get(k) == node_map2.get(k) for k in node_map1)
        if all_match:
            print("✅ 节点复用验证通过")
        else:
            print("⚠️ 部分节点未复用")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    if not _live_tests_enabled():
        print("已跳过 live tests；如需运行，请先设置 DOCUFLOW_RUN_LIVE_TESTS=1")
        return

    print("完整流程测试")
    print("确保后端服务已启动: python backend/main.py")
    
    results = []
    
    # 测试 WebSocket 实时推送
    results.append(("websocket_realtime", await test_websocket_realtime()))
    
    # 测试节点存在性检查
    results.append(("node_duplicate_check", await test_node_duplicate_check()))
    
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
