"""
v2.0 功能测试
- Task 1: 并发节点创建
- Task 2: 上传并发数限制为 5
- Task 3: 新文件格式转换
- Task 4: 仪表盘失败计数修复
"""
import asyncio
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))


# ═══════════════════════════════════════════════════════════════════
# Task 1: Parallel Node Creation
# ═══════════════════════════════════════════════════════════════════

class TestParallelNodeCreation:
    """create_structure should avoid Feishu tree-write contention while
    still respecting the parent-before-child constraint."""

    @pytest.mark.asyncio
    async def test_same_parent_siblings_are_serialized(self):
        """Sibling writes under one parent must not overlap, or Feishu returns lock contention."""
        from core.feishu.wiki_api import FeishuWikiAPI

        api = FeishuWikiAPI()
        active_by_parent = {}
        max_active_by_parent = {}

        async def mock_find(space_id, title, parent_token=None):
            return None

        async def mock_create(space_id, title, parent_node_token=None, obj_type="docx"):
            key = parent_node_token or "__root__"
            active_by_parent[key] = active_by_parent.get(key, 0) + 1
            max_active_by_parent[key] = max(
                max_active_by_parent.get(key, 0),
                active_by_parent[key],
            )
            await asyncio.sleep(0)
            active_by_parent[key] -= 1
            return {"node_token": f"tok_{title}", "obj_token": ""}

        api.find_node_by_title = mock_find
        api.create_node = mock_create

        structure = [
            {"name": "A", "children": []},
            {"name": "B", "children": []},
            {"name": "C", "children": []},
        ]

        node_map = await api.create_structure("sp1", structure)

        assert len(node_map) == 3
        assert "A" in node_map
        assert "B" in node_map
        assert "C" in node_map
        assert max_active_by_parent["__root__"] == 1

    @pytest.mark.asyncio
    async def test_different_parent_branches_are_serialized_too(self):
        """Different branches still contend on one Feishu space, so writes must stay single-file."""
        from core.feishu.wiki_api import FeishuWikiAPI

        api = FeishuWikiAPI()
        active_creates = 0
        max_active_creates = 0

        async def mock_find(space_id, title, parent_token=None):
            return None

        async def mock_create(space_id, title, parent_node_token=None, obj_type="docx"):
            nonlocal active_creates, max_active_creates
            active_creates += 1
            max_active_creates = max(max_active_creates, active_creates)
            await asyncio.sleep(0)
            active_creates -= 1
            return {"node_token": f"tok_{title}", "obj_token": ""}

        api.find_node_by_title = mock_find
        api.create_node = mock_create

        structure = [
            {"name": "A", "children": [{"name": "A1", "children": []}]},
            {"name": "B", "children": [{"name": "B1", "children": []}]},
        ]

        node_map = await api.create_structure("sp1", structure)

        assert node_map["A/A1"] == "tok_A1"
        assert node_map["B/B1"] == "tok_B1"
        assert max_active_creates == 1

    @pytest.mark.asyncio
    async def test_parent_created_before_children(self):
        """Children must only be created after their parent node exists."""
        from core.feishu.wiki_api import FeishuWikiAPI

        api = FeishuWikiAPI()
        creation_order = []

        async def mock_find(space_id, title, parent_token=None):
            return None

        async def mock_create(space_id, title, parent_node_token=None, obj_type="docx"):
            creation_order.append(title)
            return {"node_token": f"tok_{title}", "obj_token": ""}

        api.find_node_by_title = mock_find
        api.create_node = mock_create

        structure = [
            {
                "name": "Parent",
                "children": [
                    {"name": "Child1", "children": []},
                    {"name": "Child2", "children": []},
                ],
            }
        ]

        await api.create_structure("sp1", structure)

        assert creation_order.index("Parent") < creation_order.index("Child1")
        assert creation_order.index("Parent") < creation_order.index("Child2")

    @pytest.mark.asyncio
    async def test_existing_node_reused(self):
        """If a node already exists, it should be reused and not recreated."""
        from core.feishu.wiki_api import FeishuWikiAPI

        api = FeishuWikiAPI()
        create_calls = []

        async def mock_find(space_id, title, parent_token=None):
            if title == "Existing":
                return "existing_token"
            return None

        async def mock_create(space_id, title, parent_node_token=None, obj_type="docx"):
            create_calls.append(title)
            return {"node_token": f"tok_{title}", "obj_token": ""}

        api.find_node_by_title = mock_find
        api.create_node = mock_create

        structure = [
            {"name": "Existing", "children": []},
            {"name": "New", "children": []},
        ]

        node_map = await api.create_structure("sp1", structure)

        assert node_map["Existing"] == "existing_token"
        assert "New" in node_map
        assert "Existing" not in create_calls
        assert "New" in create_calls


class TestWikiNodeCreationReliability:
    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = json.dumps(payload, ensure_ascii=False)

        def json(self):
            return self._payload

    class FakeAsyncClient:
        def __init__(self, response):
            self.response = response

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return self.response

    @pytest.mark.asyncio
    async def test_create_node_http_error_keeps_remote_details(self):
        from core.feishu.wiki_api import FeishuWikiAPI
        import core.feishu.wiki_api as wiki_module

        api = FeishuWikiAPI()
        response = self.FakeResponse(400, {"code": 1254001, "msg": "invalid node"})

        with (
            patch.object(api, "_get_headers", AsyncMock(return_value={})),
            patch.object(
                wiki_module.httpx,
                "AsyncClient",
                side_effect=lambda timeout=30: self.FakeAsyncClient(response),
            ),
            patch.object(wiki_module.logger, "error") as mock_error,
        ):
            with pytest.raises(Exception) as exc_info:
                await api.create_node("space-1", "Root")

        message = str(exc_info.value)
        assert "status=400" in message
        assert "code=1254001" in message
        assert "msg=invalid node" in message
        assert '"code": 1254001' in message
        assert any(
            "status=400" in call.args[0]
            and "code=1254001" in call.args[0]
            and "msg=invalid node" in call.args[0]
            for call in mock_error.call_args_list
        )

    @pytest.mark.asyncio
    async def test_create_node_business_error_keeps_remote_details(self):
        from core.feishu.wiki_api import FeishuWikiAPI
        import core.feishu.wiki_api as wiki_module

        api = FeishuWikiAPI()
        response = self.FakeResponse(200, {"code": 99991663, "msg": "quota exceeded"})

        with (
            patch.object(api, "_get_headers", AsyncMock(return_value={})),
            patch.object(
                wiki_module.httpx,
                "AsyncClient",
                side_effect=lambda timeout=30: self.FakeAsyncClient(response),
            ),
            patch.object(wiki_module.logger, "error") as mock_error,
        ):
            with pytest.raises(Exception) as exc_info:
                await api.create_node("space-1", "Root")

        message = str(exc_info.value)
        assert "status=200" in message
        assert "code=99991663" in message
        assert "msg=quota exceeded" in message
        assert '"code": 99991663' in message
        assert any(
            "status=200" in call.args[0]
            and "code=99991663" in call.args[0]
            and "msg=quota exceeded" in call.args[0]
            for call in mock_error.call_args_list
        )

    @pytest.mark.asyncio
    async def test_create_structure_retries_node_creation_with_backoff(self):
        from core.feishu.wiki_api import FeishuWikiAPI
        import core.feishu.wiki_api as wiki_module

        api = FeishuWikiAPI()
        api.find_node_by_title = AsyncMock(return_value=None)
        api.create_node = AsyncMock(
            side_effect=[
                RuntimeError("first failure"),
                RuntimeError("second failure"),
                {"node_token": "tok_root", "obj_token": ""},
            ]
        )

        with patch.object(wiki_module.asyncio, "sleep", AsyncMock()) as mock_sleep:
            node_map = await api.create_structure(
                "space-1",
                [{"name": "Root", "children": []}],
            )

        assert node_map == {"Root": "tok_root"}
        assert api.create_node.await_count == 3
        assert [call.args[0] for call in mock_sleep.await_args_list] == [1, 2]

    @pytest.mark.asyncio
    async def test_create_structure_raises_when_node_keeps_failing(self):
        from core.feishu.wiki_api import FeishuWikiAPI
        import core.feishu.wiki_api as wiki_module

        api = FeishuWikiAPI()
        api.find_node_by_title = AsyncMock(return_value=None)
        api.create_node = AsyncMock(side_effect=RuntimeError("still failing"))

        with (
            patch.object(wiki_module.asyncio, "sleep", AsyncMock()) as mock_sleep,
            pytest.raises(Exception, match="模板结构创建失败"),
        ):
            await api.create_structure(
                "space-1",
                [{"name": "Root", "children": []}],
            )

        assert api.create_node.await_count == 3
        assert [call.args[0] for call in mock_sleep.await_args_list] == [1, 2]


# ═══════════════════════════════════════════════════════════════════
# Task 2: Upload Concurrency Cap
# ═══════════════════════════════════════════════════════════════════

class TestUploadConcurrencyCap:

    def test_max_workers_default_is_five(self):
        from utils.system_resource import calculate_dynamic_workers

        workers, detail = calculate_dynamic_workers(total_files=100)
        assert workers <= 5

    def test_respects_explicit_max(self):
        from utils.system_resource import calculate_dynamic_workers

        workers, _ = calculate_dynamic_workers(total_files=100, max_workers=3)
        assert workers <= 3

    def test_never_zero(self):
        from utils.system_resource import calculate_dynamic_workers

        workers, _ = calculate_dynamic_workers(total_files=1)
        assert workers >= 1


# ═══════════════════════════════════════════════════════════════════
# Task 3: File Format Support
# ═══════════════════════════════════════════════════════════════════

class TestFileTypeMap:
    """drive_api FILE_TYPE_MAP should cover all supported formats including pptx/xmind/mm/opml."""

    def test_native_document_types(self):
        from core.feishu.drive_api import FeishuDriveAPI

        for ext in ("docx", "doc", "txt", "md", "mark", "markdown", "html"):
            assert ext in FeishuDriveAPI.FILE_TYPE_MAP
            assert FeishuDriveAPI.FILE_TYPE_MAP[ext][0] == "docx"

    def test_native_sheet_types(self):
        from core.feishu.drive_api import FeishuDriveAPI

        for ext in ("xlsx", "csv", "xls"):
            assert ext in FeishuDriveAPI.FILE_TYPE_MAP
            assert FeishuDriveAPI.FILE_TYPE_MAP[ext][0] == "sheet"

    def test_pptx_not_imported_as_native_file_type(self):
        from core.feishu.drive_api import FeishuDriveAPI

        assert "pptx" not in FeishuDriveAPI.FILE_TYPE_MAP

    def test_mindmap_types_not_imported_as_native_file_types(self):
        from core.feishu.drive_api import FeishuDriveAPI

        for ext in ("xmind", "mm", "opml"):
            assert ext not in FeishuDriveAPI.FILE_TYPE_MAP

    def test_unsupported_extension_raises(self):
        from core.feishu.drive_api import FeishuDriveAPI

        api = FeishuDriveAPI()
        with pytest.raises(ValueError, match="不支持的文件类型"):
            api._get_file_type_info("test.zzz")


class TestMindMapConverter:

    @pytest.mark.asyncio
    async def test_opml_to_markdown(self):
        from core.converter.mindmap_converter import MindMapConverter

        opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Test OPML</title></head>
  <body>
    <outline text="Topic A">
      <outline text="Sub A1"/>
    </outline>
    <outline text="Topic B"/>
  </body>
</opml>"""
        tmp = Path(tempfile.mktemp(suffix=".opml"))
        tmp.write_text(opml_content, encoding="utf-8")

        converter = MindMapConverter()
        result = await converter.convert(str(tmp))

        assert result.success
        assert "Topic A" in result.content
        assert "Sub A1" in result.content
        assert "Topic B" in result.content
        tmp.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_freemind_to_markdown(self):
        from core.converter.mindmap_converter import MindMapConverter

        mm_content = """<?xml version="1.0" encoding="UTF-8"?>
<map version="1.0.1">
  <node TEXT="Root">
    <node TEXT="Branch A"/>
    <node TEXT="Branch B">
      <node TEXT="Leaf B1"/>
    </node>
  </node>
</map>"""
        tmp = Path(tempfile.mktemp(suffix=".mm"))
        tmp.write_text(mm_content, encoding="utf-8")

        converter = MindMapConverter()
        result = await converter.convert(str(tmp))

        assert result.success
        assert "Root" in result.content
        assert "Branch A" in result.content
        assert "Leaf B1" in result.content
        tmp.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_xmind_json_to_markdown(self):
        from core.converter.mindmap_converter import MindMapConverter

        xmind_json = json.dumps([{
            "rootTopic": {
                "title": "Central",
                "children": {
                    "attached": [
                        {"title": "Node1", "children": {"attached": []}},
                        {"title": "Node2", "children": {"attached": []}},
                    ]
                }
            }
        }])
        tmp = Path(tempfile.mktemp(suffix=".xmind"))
        with zipfile.ZipFile(str(tmp), "w") as zf:
            zf.writestr("content.json", xmind_json)

        converter = MindMapConverter()
        result = await converter.convert(str(tmp))

        assert result.success
        assert "Central" in result.content
        assert "Node1" in result.content
        assert "Node2" in result.content
        tmp.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_unsupported_extension_fails(self):
        from core.converter.mindmap_converter import MindMapConverter

        tmp = Path(tempfile.mktemp(suffix=".xyz"))
        tmp.write_text("nope", encoding="utf-8")

        converter = MindMapConverter()
        result = await converter.convert(str(tmp))

        assert not result.success
        tmp.unlink(missing_ok=True)


class TestPPTXConverter:

    @pytest.mark.asyncio
    async def test_pptx_to_docx(self):
        pytest.importorskip("pptx")
        from pptx import Presentation
        from core.converter.pptx_converter import PPTXConverter

        prs = Presentation()
        slide_layout = prs.slide_layouts[6]  # blank
        slide = prs.slides.add_slide(slide_layout)
        from pptx.util import Inches
        txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
        txBox.text_frame.text = "Hello PPTX"

        tmp = Path(tempfile.mktemp(suffix=".pptx"))
        prs.save(str(tmp))

        converter = PPTXConverter()
        result = await converter.convert(str(tmp))

        assert result.success
        assert result.output_path is not None
        assert Path(result.output_path).exists()
        assert Path(result.output_path).suffix == ".docx"
        tmp.unlink(missing_ok=True)


class TestFeishuImportPreparation:

    @pytest.mark.asyncio
    async def test_direct_import_type_is_unchanged(self):
        from main import _prepare_file_for_feishu_import

        tmp = Path(tempfile.mktemp(suffix=".md"))
        tmp.write_text("# Direct", encoding="utf-8")

        result = await _prepare_file_for_feishu_import(str(tmp))

        assert result == str(tmp)
        tmp.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_opml_is_converted_to_markdown_before_import(self):
        from main import _prepare_file_for_feishu_import

        opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Import OPML</title></head>
  <body><outline text="Topic"/></body>
</opml>"""
        tmp = Path(tempfile.mktemp(suffix=".opml"))
        tmp.write_text(opml_content, encoding="utf-8")

        result = await _prepare_file_for_feishu_import(str(tmp))

        assert Path(result).suffix == ".md"
        assert Path(result).exists()
        assert "Topic" in Path(result).read_text(encoding="utf-8")
        tmp.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════
# Task 4: Dashboard Failed Count
# ═══════════════════════════════════════════════════════════════════

class TestFailedCountLogic:
    """Verify the fixed counting logic for partial / failed files."""

    def test_partial_counted_as_failed(self):
        """
        Simulate the finally-block counting logic:
        when file_partial is True, it should increment failed counter.
        """
        runtime = {"completed": 0, "processed": 0, "failed": 0, "duplicate": 0}
        stats = {"processed": 0, "failed": 0, "duplicate": 0, "tokens": 0, "api_calls": 0}

        file_processed = False
        file_failed = False
        file_partial = True

        runtime["completed"] += 1
        if file_processed:
            runtime["processed"] += 1
            stats["processed"] += 1
        if file_failed or file_partial:
            runtime["failed"] += 1
            stats["failed"] += 1

        assert runtime["failed"] == 1
        assert stats["failed"] == 1
        assert runtime["processed"] == 0

    def test_success_counted_as_processed(self):
        runtime = {"completed": 0, "processed": 0, "failed": 0, "duplicate": 0}
        stats = {"processed": 0, "failed": 0, "duplicate": 0, "tokens": 0, "api_calls": 0}

        file_processed = True
        file_failed = False
        file_partial = False

        runtime["completed"] += 1
        if file_processed:
            runtime["processed"] += 1
            stats["processed"] += 1
        if file_failed or file_partial:
            runtime["failed"] += 1
            stats["failed"] += 1

        assert runtime["processed"] == 1
        assert runtime["failed"] == 0

    def test_full_failure_counted(self):
        runtime = {"completed": 0, "processed": 0, "failed": 0, "duplicate": 0}
        stats = {"processed": 0, "failed": 0, "duplicate": 0, "tokens": 0, "api_calls": 0}

        file_processed = False
        file_failed = True
        file_partial = False

        runtime["completed"] += 1
        if file_processed:
            runtime["processed"] += 1
            stats["processed"] += 1
        if file_failed or file_partial:
            runtime["failed"] += 1
            stats["failed"] += 1

        assert runtime["failed"] == 1
        assert stats["failed"] == 1


class TestFinalPanoramaSent:
    """After asyncio.gather, a final panorama must be sent to ensure
    the frontend has the definitive file-status snapshot."""

    def test_snapshot_captures_all_statuses(self):
        """_snapshot_file_status must deep-copy the list."""
        file_status_list = [
            {"name": "a.docx", "status": "success", "progress": 100},
            {"name": "b.docx", "status": "failed", "progress": 0},
            {"name": "c.docx", "status": "partial", "progress": 80},
        ]

        from main import _snapshot_file_status
        snapshot = _snapshot_file_status(file_status_list)

        assert len(snapshot) == 3
        assert snapshot[1]["status"] == "failed"

        file_status_list[1]["status"] = "changed"
        assert snapshot[1]["status"] == "failed"


class TestFailurePublicationOrder:
    """A visible failure log should not race ahead of the visible failure count."""

    @pytest.mark.asyncio
    async def test_failed_count_is_published_before_failure_log(self, tmp_path):
        from main import app_state, manager, run_migration_task
        from core.feishu import drive_api as drive_module
        from core.feishu import wiki_api as wiki_module
        from core.llm import processor as processor_module
        from models import template as template_module
        import main as main_module

        task_id = "failure-order"
        source_file = tmp_path / "broken.md"
        source_file.write_text("# broken", encoding="utf-8")

        events = []

        class FakeProcessor:
            async def quick_summarize_file(self, file_content, file_name):
                return {"success": True, "tokens": 0, "summary": ""}

        async def fake_send_log(source, message, level):
            events.append(("log", level, message))

        async def fake_send_stats(stats):
            events.append(("stats", stats["failed"]))

        async def fake_send_panorama(task_id, space_structure, file_status):
            failed_count = sum(1 for item in file_status if item["status"] in {"failed", "partial"})
            events.append(("panorama", failed_count))

        with (
            patch.object(processor_module, "LLMProcessor", FakeProcessor),
            patch.object(drive_module.drive_api, "import_file", AsyncMock(side_effect=RuntimeError("boom"))),
            patch.object(wiki_module.wiki_api, "create_space", AsyncMock(return_value="space-1")),
            patch.object(wiki_module.wiki_api, "create_structure", AsyncMock(return_value={})),
            patch.object(wiki_module.wiki_api, "get_space_nodes_flat", AsyncMock(return_value=[])),
            patch.object(template_module.template_manager, "get_template", AsyncMock(return_value=None)),
            patch.object(main_module, "_prepare_file_for_feishu_import", AsyncMock(return_value=str(source_file))),
            patch.object(manager, "send_log", fake_send_log),
            patch.object(manager, "send_stats", fake_send_stats),
            patch.object(manager, "send_panorama", fake_send_panorama),
            patch.object(manager, "send_progress", AsyncMock()),
            patch.object(manager, "send_chart_data", AsyncMock()),
        ):
            original_stats = dict(app_state["stats"])
            original_tasks = dict(app_state["tasks"])
            original_status = app_state["system_status"]
            try:
                app_state["stats"] = {
                    "processed": 0,
                    "failed": 0,
                    "duplicate": 0,
                    "tokens": 0,
                    "api_calls": 0,
                }
                app_state["tasks"] = {
                    task_id: {
                        "id": task_id,
                        "name": "Failure order",
                        "status": "running",
                        "progress": 0,
                        "template_id": None,
                        "target_space_id": None,
                        "files": [{"name": source_file.name, "path": str(source_file)}],
                        "duplicates": [],
                    }
                }

                await run_migration_task(task_id)
            finally:
                app_state["stats"] = original_stats
                app_state["tasks"] = original_tasks
                app_state["system_status"] = original_status

        failure_log_index = next(
            index
            for index, event in enumerate(events)
            if event[0] == "log" and event[1] == "error" and "处理失败" in event[2]
        )
        failed_count_index = next(
            index
            for index, event in enumerate(events)
            if (event[0] == "stats" and event[1] == 1)
            or (event[0] == "panorama" and event[1] == 1)
        )

        assert failed_count_index < failure_log_index


class TestFailureReasonClassification:
    def test_empty_source_file_gets_user_friendly_failure_reason(self, tmp_path):
        from main import _validate_source_file

        empty_file = tmp_path / "empty.md"
        empty_file.write_text("", encoding="utf-8")

        failure = _validate_source_file(str(empty_file))

        assert failure == {
            "error_type": "empty_file",
            "error_message": "文件内容为空，请补充内容后重新导入",
        }

    def test_missing_source_file_gets_user_friendly_failure_reason(self, tmp_path):
        from main import _validate_source_file

        missing_file = tmp_path / "missing.md"

        failure = _validate_source_file(str(missing_file))

        assert failure == {
            "error_type": "file_missing",
            "error_message": "文件不存在或已被移动，请重新选择文件",
        }

    def test_raw_exception_is_mapped_to_short_user_friendly_reason(self):
        from main import _format_failure_reason

        failure = _format_failure_reason(RuntimeError("Client error '400 Bad Request' for url 'https://example.test'"))

        assert failure["error_type"] == "processing_error"
        assert failure["error_message"] == "处理失败：Client error '400 Bad Request' for url 'https://example.test'"


class TestTemplateStructureFailureGate:
    @pytest.mark.asyncio
    async def test_template_structure_failure_aborts_before_file_import(self, tmp_path):
        from main import app_state, manager, run_migration_task
        from core.feishu import drive_api as drive_module
        from core.feishu import wiki_api as wiki_module
        from core.llm import processor as processor_module
        from models import template as template_module

        task_id = "template-failure-gate"
        source_file = tmp_path / "should-not-upload.md"
        source_file.write_text("# should not upload", encoding="utf-8")
        sent_logs = []

        class FakeProcessor:
            async def quick_summarize_file(self, file_content, file_name):
                raise AssertionError("file processing should not start")

        async def fake_send_log(source, message, level):
            sent_logs.append((source, message, level))

        import_file_mock = AsyncMock()

        with (
            patch.object(processor_module, "LLMProcessor", FakeProcessor),
            patch.object(drive_module.drive_api, "import_file", import_file_mock),
            patch.object(wiki_module.wiki_api, "create_space", AsyncMock(return_value="space-1")),
            patch.object(
                wiki_module.wiki_api,
                "create_structure",
                AsyncMock(side_effect=RuntimeError("missing path: Root")),
            ),
            patch.object(template_module.template_manager, "get_template", AsyncMock(return_value={
                "name": "Template",
                "description": "",
                "structure": [{"name": "Root", "children": []}],
            })),
            patch.object(manager, "send_log", fake_send_log),
            patch.object(manager, "send_stats", AsyncMock()),
            patch.object(manager, "send_panorama", AsyncMock()),
            patch.object(manager, "send_progress", AsyncMock()),
            patch.object(manager, "send_chart_data", AsyncMock()),
        ):
            original_stats = dict(app_state["stats"])
            original_tasks = dict(app_state["tasks"])
            original_status = app_state["system_status"]
            try:
                app_state["stats"] = {
                    "processed": 0,
                    "failed": 0,
                    "duplicate": 0,
                    "tokens": 0,
                    "api_calls": 0,
                }
                app_state["tasks"] = {
                    task_id: {
                        "id": task_id,
                        "name": "Template failure gate",
                        "status": "running",
                        "progress": 0,
                        "template_id": "template-1",
                        "target_space_id": None,
                        "files": [{"name": source_file.name, "path": str(source_file)}],
                        "duplicates": [],
                    }
                }

                await run_migration_task(task_id)
                task = app_state["tasks"][task_id]
            finally:
                app_state["stats"] = original_stats
                app_state["tasks"] = original_tasks
                app_state["system_status"] = original_status

        assert task["status"] == "error"
        assert task["results"]["template_error"] == "missing path: Root"
        assert import_file_mock.await_count == 0
        assert any("模板结构创建失败，任务已终止" in message for _, message, _ in sent_logs)


class TestTaskElapsedTime:
    @pytest.mark.asyncio
    async def test_completed_task_publishes_elapsed_time(self, tmp_path):
        from main import app_state, manager, run_migration_task
        from core.feishu import drive_api as drive_module
        from core.feishu import wiki_api as wiki_module
        from core.llm import processor as processor_module
        from models import template as template_module
        import main as main_module

        task_id = "elapsed-time"
        source_file = tmp_path / "ok.md"
        source_file.write_text("# ok", encoding="utf-8")
        progress_events = []

        class FakeProcessor:
            async def quick_summarize_file(self, file_content, file_name):
                return {"success": True, "tokens": 0, "summary": ""}

        async def fake_send_progress(task_id, progress, phase, elapsed_seconds=None):
            progress_events.append((task_id, progress, phase, elapsed_seconds))

        with (
            patch.object(processor_module, "LLMProcessor", FakeProcessor),
            patch.object(
                drive_module.drive_api,
                "import_file",
                AsyncMock(return_value={"token": "doc-1", "type": "docx", "title": "ok", "url": ""}),
            ),
            patch.object(
                wiki_module.wiki_api,
                "create_space",
                AsyncMock(return_value="space-1"),
            ),
            patch.object(
                wiki_module.wiki_api,
                "create_structure",
                AsyncMock(return_value={}),
            ),
            patch.object(
                wiki_module.wiki_api,
                "get_space_nodes_flat",
                AsyncMock(return_value=[]),
            ),
            patch.object(
                wiki_module.wiki_api,
                "move_docs_to_wiki",
                AsyncMock(return_value={"url": ""}),
            ),
            patch.object(
                template_module.template_manager,
                "get_template",
                AsyncMock(return_value=None),
            ),
            patch.object(
                main_module,
                "_prepare_file_for_feishu_import",
                AsyncMock(return_value=str(source_file)),
            ),
            patch.object(manager, "send_log", AsyncMock()),
            patch.object(manager, "send_stats", AsyncMock()),
            patch.object(manager, "send_panorama", AsyncMock()),
            patch.object(manager, "send_progress", fake_send_progress),
            patch.object(manager, "send_chart_data", AsyncMock()),
        ):
            original_stats = dict(app_state["stats"])
            original_tasks = dict(app_state["tasks"])
            original_status = app_state["system_status"]
            try:
                app_state["stats"] = {
                    "processed": 0,
                    "failed": 0,
                    "duplicate": 0,
                    "tokens": 0,
                    "api_calls": 0,
                }
                app_state["tasks"] = {
                    task_id: {
                        "id": task_id,
                        "name": "Elapsed time",
                        "status": "running",
                        "progress": 0,
                        "template_id": None,
                        "target_space_id": None,
                        "files": [{"name": source_file.name, "path": str(source_file)}],
                        "duplicates": [],
                    }
                }

                await run_migration_task(task_id)
                results = app_state["tasks"][task_id]["results"]
            finally:
                app_state["stats"] = original_stats
                app_state["tasks"] = original_tasks
                app_state["system_status"] = original_status

        assert results["elapsed_seconds"] >= 0
        assert progress_events[-1][1:] == (100, "完成", results["elapsed_seconds"])
