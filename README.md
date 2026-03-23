# DocuFlowLarkAI

Desktop-first migration tool for Feishu/Lark knowledge bases.  
即开即用、无浏览器依赖、支持模板化迁移与实时监控。

## 中文

### 项目简介
DocuFlowLarkAI 是一个面向企业知识库建设的桌面应用，帮助团队将本地文档批量迁移到飞书/多维知识空间，并通过模板复用、实时看板和自动化校验提升迁移效率与质量。

<img width="3440" height="1406" alt="image" src="https://github.com/user-attachments/assets/0907fd2b-ce82-45ff-9ca2-dd1700ecee5e" />

<img width="3440" height="1406" alt="image" src="https://github.com/user-attachments/assets/1b0b1f91-68d5-4ff8-94ba-4e5010afc8c6" />

### 最新模板升级
你已扩展行业模板为「核心供给端 + 深度应用端」共 10 大类，覆盖从技术供给到业务落地的完整知识体系：

- 核心供给端：软件、互联网、电子设备
- 深度应用端：金融、零售、物流、医疗、教育、交通、媒体

这 10 类模板可直接用于新建任务，也可在模板管理中二次编辑、复用和导入导出。

### 核心能力
- 实时查看：通过 WebSocket 实时展示任务进度、文件状态、吞吐趋势和运行状态。
- 模板复用：支持模板新建、编辑、导入、导出，减少重复搭建目录结构。
- 大模型自动校验：支持 LLM 节点决策与质量校验，降低人工检查成本。
- 无损上传：源文件不被改写，支持同名检测并标记“重复”后安全跳过。
- 桌面即开即用：基于 pywebview 的无浏览器桌面体验，适配 Windows 使用习惯。
- 动态并发：根据系统 CPU/内存状态自动调节并发线程，提高上传效率并保证稳定性。
- 隐私保护：敏感配置（如 App Secret、LLM Key）采用加密存储，支持一键清空配置。

### 典型使用流程
1. 配置飞书应用信息并完成授权。
2. 选择行业模板（10 大类）或导入自定义模板。
3. 创建迁移任务并添加本地文件。
4. 执行上传，实时查看成功/重复/失败状态。
5. 在监控页面复盘结果并导出模板沉淀为团队资产。

### 快速开始
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

### 项目结构
```text
DocuFlowLarkAI/
├─ backend/           # FastAPI 后端、任务编排、飞书与LLM集成
├─ frontend/          # 前端页面与交互逻辑
├─ config/            # 配置文件（敏感字段加密落盘）
├─ data/              # 模板数据、数据库、运行日志
├─ templates/         # 导入导出模板目录
└─ scripts/           # 启动与打包脚本
```

### 适用场景
- 企业知识库初始化搭建
- 老系统文档迁移到飞书知识库
- 多部门模板标准化治理
- 行业知识体系沉淀与复用

### 注意事项
- 首次使用请先完成飞书 OAuth 授权。
- 若 8000 端口被占用，请先释放端口再启动。
- 若启动异常，请优先查看 `data/logs/desktop_boot.log`、`app.log`、`error.log`。

---

## English (Brief)

DocuFlowLarkAI is a desktop-oriented migration tool for Feishu/Lark knowledge bases, featuring:

- Real-time migration monitoring
- Reusable template management
- Optional LLM-based validation
- Lossless upload with duplicate detection
- One-click desktop packaging (EXE)

The template system now includes 10 industry domains:
Software, Internet, Electronics, Finance, Retail, Logistics, Healthcare, Education, Transportation, and Media.
