"""
飞书知识库API封装 - 使用 user_access_token
"""
import asyncio
import httpx
from typing import List, Dict, Optional, Any
from loguru import logger

from .auth import feishu_oauth


class FeishuNodeCreateError(Exception):
    """创建知识库节点失败，保留飞书返回的原始上下文。"""

    def __init__(self, *, status_code: int, code: Any, msg: str, body: str):
        self.status_code = status_code
        self.code = code
        self.msg = msg
        self.body = body
        super().__init__(
            f"创建知识库节点失败: status={status_code}, code={code}, msg={msg}, body={body}"
        )


class TemplateStructureCreationError(Exception):
    """模板结构未能完整创建。"""

    def __init__(self, failed_paths: Dict[str, str]):
        self.failed_paths = dict(failed_paths)
        detail = "; ".join(f"{path}: {reason}" for path, reason in self.failed_paths.items())
        super().__init__(f"模板结构创建失败: {detail}")


class FeishuWikiAPI:
    """飞书知识库API封装"""
    
    BASE_URL = "https://open.feishu.cn/open-apis"
    
    async def _get_headers(self) -> Dict[str, str]:
        """获取请求头（包含 user_access_token）"""
        token = await feishu_oauth.get_user_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
    
    async def list_spaces(self, page_size: int = 10) -> List[Dict[str, Any]]:
        """
        获取知识空间列表
        
        API: GET /open-apis/wiki/v2/spaces
        权限: wiki:space:read
        """
        headers = await self._get_headers()
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/wiki/v2/spaces",
                headers=headers,
                params={"page_size": page_size}
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") == 0:
                items = data["data"].get("items", [])
                return [
                    {
                        "space_id": item["space_id"],
                        "name": item["name"],
                        "description": item.get("description", ""),
                        "owner": item.get("owner", {})
                    }
                    for item in items
                ]
            else:
                raise Exception(f"获取知识空间列表失败: {data}")
    
    async def create_space(self, name: str, description: str = "", check_duplicate: bool = True) -> str:
        """
        创建知识空间
        
        API: POST /open-apis/wiki/v2/spaces
        权限: wiki:space:write
        
        Args:
            name: 知识空间名称
            description: 描述
            check_duplicate: 是否检查重复（默认True）
        
        Returns:
            space_id: 创建的知识空间 ID，或已存在的同名空间ID
        """
        # 先检查是否已存在同名空间
        if check_duplicate:
            try:
                existing_spaces = await self.list_spaces()
                for space in existing_spaces:
                    if space.get("name") == name:
                        space_id = space.get("space_id")
                        logger.info(f"发现已存在的同名知识空间: {name} ({space_id})，直接复用")
                        return space_id
            except Exception as e:
                logger.warning(f"检查知识空间重复时出错: {e}，继续创建新空间")
        
        headers = await self._get_headers()
        
        payload = {
            "name": name,
            "description": description
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE_URL}/wiki/v2/spaces",
                headers=headers,
                json=payload
            )
            # 先读取响应内容用于调试
            try:
                data = resp.json()
            except:
                data = {"text": resp.text}
            
            logger.info(f"创建知识空间响应: status={resp.status_code}, code={data.get('code')}, msg={data.get('msg', 'N/A')}")
            
            if resp.status_code == 200 and data.get("code") == 0:
                space_id = data["data"]["space"]["space_id"]
                logger.info(f"创建知识空间成功: {name} ({space_id})")
                return space_id
            else:
                # 返回详细的错误信息
                error_msg = data.get('msg', '') or data.get('error', '') or str(data)
                raise Exception(f"创建知识空间失败 [{resp.status_code}]: {error_msg}")
    
    async def get_space(self, space_id: str) -> Dict[str, Any]:
        """
        获取知识空间详情
        
        API: GET /open-apis/wiki/v2/spaces/{space_id}
        权限: wiki:space:read
        """
        headers = await self._get_headers()
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/wiki/v2/spaces/{space_id}",
                headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") == 0:
                return data["data"]["space"]
            else:
                raise Exception(f"获取知识空间失败: {data}")
    
    async def list_nodes(self, space_id: str, 
                        parent_node_token: Optional[str] = None,
                        page_size: int = 50) -> List[Dict[str, Any]]:
        """
        获取知识空间节点列表
        
        API: GET /open-apis/wiki/v2/spaces/{space_id}/nodes
        权限: wiki:wiki 或 wiki:wiki:readonly
        """
        headers = await self._get_headers()
        
        params = {"page_size": page_size}
        if parent_node_token:
            params["parent_node_token"] = parent_node_token
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/wiki/v2/spaces/{space_id}/nodes",
                headers=headers,
                params=params
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") == 0:
                items = data["data"].get("items", [])
                return [
                    {
                        "node_token": item["node_token"],
                        "title": item["title"],
                        "node_type": item["node_type"],
                        "obj_type": item.get("obj_type", ""),
                        "parent_node_token": item.get("parent_node_token"),
                        "obj_token": item.get("obj_token")
                    }
                    for item in items
                ]
            else:
                raise Exception(f"获取节点列表失败: {data}")
    
    async def create_node(self, space_id: str, title: str, 
                         parent_node_token: Optional[str] = None,
                         obj_type: str = "docx") -> Dict[str, str]:
        """
        创建知识库节点
        
        API: POST /open-apis/wiki/v2/spaces/{space_id}/nodes
        权限: wiki:node:create 或 wiki:wiki
        
        Args:
            space_id: 知识空间ID
            title: 节点标题
            parent_node_token: 父节点token(为空则创建根节点)
            obj_type: 对象类型 (docx=新版文档, sheet=表格)
            
        Returns:
            Dict: {node_token, obj_token} 节点token和文档token
        """
        headers = await self._get_headers()
        
        json_data = {
            "title": title,
            "obj_type": obj_type,
            "node_type": "origin"
        }
        if parent_node_token:
            json_data["parent_node_token"] = parent_node_token
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE_URL}/wiki/v2/spaces/{space_id}/nodes",
                headers=headers,
                json=json_data
            )
            body = resp.text
            try:
                data = resp.json()
            except Exception:
                data = {}

            code = data.get("code")
            msg = data.get("msg") or data.get("message") or data.get("error") or ""
            
            if 200 <= resp.status_code < 300 and code == 0:
                node = data["data"]["node"]
                node_token = node["node_token"]
                obj_token = node.get("obj_token", "")
                logger.info(f"知识库节点创建成功: {node_token}, 文档ID: {obj_token}")
                return {
                    "node_token": node_token,
                    "obj_token": obj_token
                }

            error = FeishuNodeCreateError(
                status_code=resp.status_code,
                code=code,
                msg=msg,
                body=body,
            )
            logger.error(
                f"创建知识库节点失败 title={title}: "
                f"status={error.status_code}, code={error.code}, msg={error.msg}, body={error.body}"
            )
            raise error
    
    async def copy_node(self, space_id: str, node_token: str,
                       target_parent_token: Optional[str] = None,
                       title: Optional[str] = None) -> str:
        """
        复制知识库节点
        
        API: POST /open-apis/wiki/v2/spaces/{space_id}/nodes/{node_token}/copy
        权限: wiki:node:copy 或 wiki:wiki
        
        Returns:
            新节点的node_token
        """
        headers = await self._get_headers()
        
        json_data = {}
        if target_parent_token:
            json_data["target_parent_token"] = target_parent_token
        if title:
            json_data["title"] = title
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE_URL}/wiki/v2/spaces/{space_id}/nodes/{node_token}/copy",
                headers=headers,
                json=json_data
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") == 0:
                return data["data"]["node"]["node_token"]
            else:
                raise Exception(f"复制节点失败: {data}")
    
    async def delete_node(self, space_id: str, node_token: str) -> bool:
        """
        删除知识库节点
        
        API: DELETE /open-apis/wiki/v2/spaces/{space_id}/nodes/{node_token}
        """
        headers = await self._get_headers()
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                f"{self.BASE_URL}/wiki/v2/spaces/{space_id}/nodes/{node_token}",
                headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
            
            return data.get("code") == 0
    
    async def get_space_tree(self, space_id: str) -> Dict[str, Any]:
        """
        获取知识空间的完整树形结构
        """
        async def build_tree(parent_token: Optional[str] = None) -> List[Dict]:
            nodes = await self.list_nodes(space_id, parent_token)
            result = []
            
            for node in nodes:
                node_data = {
                    "node_token": node["node_token"],
                    "title": node["title"],
                    "node_type": node["node_type"],
                    "obj_type": node["obj_type"],
                    "children": []
                }
                
                # 递归获取子节点
                if node["node_type"] == "origin":
                    try:
                        children = await build_tree(node["node_token"])
                        node_data["children"] = children
                    except Exception as e:
                        logger.warning(f"获取子节点失败: {e}")
                
                result.append(node_data)
            
            return result
        
        space = await self.get_space(space_id)
        
        tree = {
            "space_id": space_id,
            "name": space.get("name", ""),
            "description": space.get("description", ""),
            "nodes": await build_tree()
        }
        
        return tree
    
    async def find_node_by_title(self, space_id: str, title: str, 
                                  parent_token: Optional[str] = None) -> Optional[str]:
        """
        根据标题查找节点
        
        Args:
            space_id: 知识空间ID
            title: 节点标题
            parent_token: 父节点token（可选）
            
        Returns:
            节点token，如果未找到则返回None
        """
        try:
            nodes = await self.list_nodes(space_id, parent_token)
            for node in nodes:
                if node.get("title") == title:
                    return node.get("node_token")
        except Exception as e:
            logger.warning(f"查找节点失败: {e}")
        return None
    
    async def create_structure(self, space_id: str, structure: List[Dict],
                              parent_token: Optional[str] = None,
                              max_concurrent: int = 1) -> Dict[str, str]:
        """
        批量创建知识库结构（带存在性检查）
        
        如果节点已存在则复用，不存在则创建。
        同一父节点下的兄弟节点串行创建，避免触发飞书锁竞争；
        飞书当前对同一知识空间的节点写入会产生锁竞争，因此模板建树阶段整体串行；
        子节点必须在父节点创建完成后才能开始。
        
        Args:
            space_id: 知识空间ID
            structure: 结构定义，格式为 [{"name": "xxx", "children": [...]}, ...]
            parent_token: 父节点token
            max_concurrent: 最大并发数；默认固定为 1，避免触发飞书 131009 锁竞争
            
        Returns:
            节点路径到token的映射
        """
        node_map: Dict[str, str] = {}
        failed_paths: Dict[str, str] = {}
        sem = asyncio.Semaphore(max_concurrent)
        parent_locks: Dict[str, asyncio.Lock] = {}

        def get_parent_lock(parent: Optional[str]) -> asyncio.Lock:
            key = parent or "__root__"
            if key not in parent_locks:
                parent_locks[key] = asyncio.Lock()
            return parent_locks[key]

        def format_failure_details(error: Exception) -> str:
            if isinstance(error, FeishuNodeCreateError):
                return (
                    f"status={error.status_code}, code={error.code}, "
                    f"msg={error.msg}, body={error.body}"
                )
            return f"status=N/A, code=N/A, msg={error}, body="

        async def create_node_with_retry(title: str, parent: Optional[str], current_path: str) -> Dict[str, str]:
            for attempt in range(1, 4):
                try:
                    async with get_parent_lock(parent):
                        return await self.create_node(
                            space_id=space_id,
                            title=title,
                            parent_node_token=parent,
                            obj_type="docx"
                        )
                except Exception as error:
                    logger.error(
                        f"创建节点失败 path={current_path}, attempt={attempt}/3, "
                        f"{format_failure_details(error)}"
                    )
                    if attempt == 3:
                        raise
                    await asyncio.sleep(2 ** (attempt - 1))

            raise RuntimeError(f"创建节点失败: {current_path}")

        async def create_or_find_single(item: Dict, parent: Optional[str], path: str):
            """查找或创建单个节点（受信号量保护）"""
            title = item.get("name", "未命名")
            current_path = f"{path}/{title}" if path else title

            async with sem:
                try:
                    existing_token = await self.find_node_by_title(
                        space_id=space_id,
                        title=title,
                        parent_token=parent
                    )

                    if existing_token:
                        node_token = existing_token
                        node_map[current_path] = node_token
                        logger.info(f"复用已存在节点: {current_path}")
                    else:
                        node_result = await create_node_with_retry(title, parent, current_path)
                        node_token = node_result["node_token"]
                        node_map[current_path] = node_token
                        logger.info(f"创建节点: {current_path}")

                    return node_token, current_path, item.get("children", [])

                except Exception as e:
                    failed_paths[current_path] = str(e)
                    logger.error(f"节点最终创建失败 path={current_path}: {e}")
                    return None, current_path, []

        async def create_level(items: List[Dict], parent: Optional[str], path: str):
            """并发创建同一层级的所有兄弟节点，然后递归处理各自的子节点"""
            results = await asyncio.gather(
                *(create_or_find_single(item, parent, path) for item in items),
                return_exceptions=True
            )

            child_tasks = []
            for result in results:
                if isinstance(result, BaseException):
                    logger.error(f"节点创建任务异常: {result}")
                    continue
                node_token, current_path, children = result
                if node_token and children:
                    child_tasks.append(create_level(children, node_token, current_path))

            if child_tasks:
                await asyncio.gather(*child_tasks, return_exceptions=True)

        await create_level(structure, parent_token, "")
        if failed_paths:
            raise TemplateStructureCreationError(failed_paths)
        return node_map

    
    async def move_docs_to_wiki(self, space_id: str, parent_wiki_token: str, 
                                 obj_type: str, obj_token: str, title: str = "") -> Dict[str, str]:
        """
        移动云空间文档至知识空间
        
        API: POST /open-apis/wiki/v2/spaces/{space_id}/nodes/move_docs_to_wiki
        权限: wiki:node:move 或 wiki:wiki
        
        Args:
            space_id: 目标知识空间ID
            parent_wiki_token: 目标父节点wiki_token（为空则挂载到根节点）
            obj_type: 对象类型 (docx/sheet/bitable)
            obj_token: 文档token（云文档token）
            title: 文档标题（可选）
            
        Returns:
            Dict: {node_token, url, task_id} 知识库节点token和访问URL
        """
        headers = await self._get_headers()
        
        json_data = {
            "obj_type": obj_type,
            "obj_token": obj_token
        }
        
        if parent_wiki_token:
            json_data["parent_wiki_token"] = parent_wiki_token
        
        logger.info(f"移动文档至知识空间: obj_type={obj_type}, obj_token={obj_token}, space_id={space_id}")
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE_URL}/wiki/v2/spaces/{space_id}/nodes/move_docs_to_wiki",
                headers=headers,
                json=json_data
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") == 0:
                result_data = data.get("data", {})
                wiki_token = result_data.get("wiki_token", "")
                task_id = result_data.get("task_id", "")
                
                if wiki_token:
                    logger.info(f"文档移动成功: wiki_token={wiki_token}")
                    return {
                        "node_token": wiki_token,
                        "url": f"https://my.feishu.cn/wiki/{wiki_token}",
                        "title": title
                    }
                elif task_id:
                    logger.info(f"文档移动任务创建成功: task_id={task_id}")
                    # 异步任务，返回task_id
                    return {
                        "node_token": "",
                        "url": "",
                        "title": title,
                        "task_id": task_id
                    }
                else:
                    raise Exception(f"移动文档返回异常: {result_data}")
            else:
                raise Exception(f"移动文档至知识空间失败: {data}")
    
    async def get_space_nodes_flat(self, space_id: str) -> List[Dict[str, Any]]:
        """
        获取知识空间所有节点（扁平化列表）
        
        用于LLM决策挂载点
        
        Returns:
            节点列表，每个节点包含路径信息
        """
        nodes = []
        
        async def fetch_children(parent_token: Optional[str] = None, parent_path: str = ""):
            """递归获取子节点"""
            try:
                children = await self.list_nodes(space_id, parent_token)
                for child in children:
                    # 只处理文件夹类型的节点作为潜在挂载点
                    node_type = child.get("node_type", "")
                    
                    current_path = f"{parent_path}/{child['title']}" if parent_path else child['title']
                    
                    node_info = {
                        "node_token": child["node_token"],
                        "title": child["title"],
                        "node_type": node_type,
                        "path": current_path,
                        "parent_node_token": parent_token
                    }
                    nodes.append(node_info)
                    
                    # 递归获取子节点（不管当前节点类型，都获取其下的文件夹）
                    await fetch_children(child["node_token"], current_path)
                    
            except Exception as e:
                logger.warning(f"获取节点失败 {parent_path}: {e}")
        
        await fetch_children()
        return nodes


# 全局实例
wiki_api = FeishuWikiAPI()
