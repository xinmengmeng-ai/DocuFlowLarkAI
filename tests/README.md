# 测试目录

## 测试文件说明

### test_import_flow.py - 导入文件流程测试

测试新的导入文件流程：
1. 上传素材 → 获取 file_token
2. 创建导入任务 → 获取 ticket
3. 轮询导入结果 → 获取 docx_token/sheet_token
4. LLM 快速总结文件内容
5. 移动文档至知识空间

## 运行测试

```bash
# 进入测试目录
cd tests

# 运行导入流程测试
python test_import_flow.py
```

## Live tests

默认测试链不再访问真实飞书环境。需要手动验证真实飞书链路时，必须显式开启：

```bash
set DOCUFLOW_RUN_LIVE_TESTS=1
set DOCUFLOW_LIVE_TEST_SPACE_ID=<专用测试知识空间ID>
pytest test_full_flow.py test_import_api.py
```

`test_full_flow.py` 中会创建节点的用例只允许写入 `DOCUFLOW_LIVE_TEST_SPACE_ID` 指定的专用测试空间，不再默认写入账号下的第一个知识空间。

## 测试要求

1. **OAuth 授权**: 需要先完成飞书 OAuth 授权
2. **测试文件**: 项目根目录需要有 .docx 或 .txt 测试文件
3. **LLM 配置**: LLM 总结测试需要配置有效的 LLM API

## 支持的文件类型

| 文件类型 | 扩展名 | 导入为飞书文档 |
|---------|--------|---------------|
| Word | docx, doc | 文档 (docx) |
| 文本 | txt | 文档 (docx) |
| Markdown | md, markdown | 文档 (docx) |
| HTML | html | 文档 (docx) |
| Excel | xlsx, xls | 电子表格 (sheet) |
| CSV | csv | 电子表格 (sheet) |

## 旧测试文件

以下旧测试文件已删除（不再适用）：
- ❌ test_document_write.py - 旧 Blocks 插入测试
- ❌ debug_blocks.py - Blocks 格式调试
- ❌ debug_request.py - 请求体调试
