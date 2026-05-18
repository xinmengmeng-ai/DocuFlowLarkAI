# DocuFlowLarkAI

DocuFlowLarkAI 是一个面向飞书/Lark 知识库迁移的桌面优先工具。它提供即开即用、无浏览器依赖、模板化迁移、实时监控和可选的大模型辅助校验能力，帮助团队把本地文档批量迁移到飞书知识空间。

## 项目简介

DocuFlowLarkAI 面向企业知识库建设场景，重点解决批量迁移、模板复用、过程监控、重复文件识别和迁移质量复盘问题。应用采用 FastAPI 后端和 pywebview 桌面壳，适合 Windows 环境下直接交付和使用。

## 核心能力

- 实时查看：通过 WebSocket 实时展示任务进度、文件状态、吞吐趋势和运行状态。
- 模板复用：支持模板新建、编辑、导入、导出，减少重复搭建目录结构。
- 大模型自动校验：支持 LLM 节点决策与质量校验，降低人工检查成本。
- 无损上传：源文件不被改写，支持同名检测并标记“重复”后安全跳过。
- 桌面即开即用：基于 pywebview 的无浏览器桌面体验，适配 Windows 使用习惯。
- 动态并发：根据系统 CPU/内存状态自动调节并发线程，提高上传效率并保证稳定性。
- 隐私保护：敏感配置（如 App Secret、LLM Key）采用加密存储，支持一键清空配置。
- 飞书导入预转换：对飞书不支持直接导入的格式先转换为可导入内容，再进入飞书导入链路。

## 模板范围

模板系统覆盖“核心供给端 + 深度应用端”共 10 大类：

- 核心供给端：软件、互联网、电子设备
- 深度应用端：金融、零售、物流、医疗、教育、交通、媒体

这些模板可直接用于新建任务，也可在模板管理中二次编辑、复用和导入导出。

## 典型使用流程

1. 配置飞书应用信息并完成授权。
2. 选择行业模板或导入自定义模板。
3. 创建迁移任务并添加本地文件。
4. 执行上传，实时查看成功、重复、失败状态。
5. 在监控页面复盘结果，并将模板沉淀为团队资产。

## 快速开始

安装依赖：

```bash
pip install -r requirements.txt
```

Windows 桌面模式：

```bat
scripts\start.bat
```

仅启动后端：

```bat
scripts\start_backend.bat
```

打包桌面版（EXE）：

```bat
scripts\build.bat
```

自动化打包时可避免暂停：

```powershell
$env:NO_PAUSE='1'; cmd /c scripts\build.bat
```

## 项目结构

```text
DocuFlowLarkAI/
├─ backend/           # FastAPI 后端、任务编排、飞书与 LLM 集成
├─ frontend/          # 前端页面与交互逻辑
├─ config/            # 配置文件（敏感字段加密落盘）
├─ data/              # 模板数据、数据库、运行日志
├─ templates/         # 导入导出模板目录
└─ scripts/           # 启动与打包脚本
```

## 注意事项

- 首次使用请先完成飞书 OAuth 授权。
- 若 8000 端口被占用，请先释放端口再启动。
- 若启动异常，请优先查看 `data/logs/desktop_boot.log`、`app.log`、`error.log`。
- 发布包会包含 `LICENSE` 和 `THIRD_PARTY_NOTICES.md`。

## 开源协议

License: Apache-2.0

详见 [LICENSE](LICENSE) 和 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
