# AI API Hub — 大模型API管理平台

一个纯自定义的本地 AI 大模型 API 信息管理工具 + API 转接/代理服务器。所有提供商、模型、密钥均由用户自行添加，无预置数据。

## 功能特性

### 管理功能
- **完全自定义**：无预置数据，按需添加你的 API 提供商和模型
- **AI 智能解析**：粘贴 API 文档、上传文件或输入 URL，AI 自动识别提供商和模型信息并一键导入
- **提供商管理**：添加、编辑、删除 API 提供商（支持分类：国外主流/国内主流/其他）
- **模型管理**：记录模型 ID、Token 限制、多模态支持、函数调用、定价等信息
- **灵活计费**：支持按量计费（tokens）和按次收费两种定价方式
- **密钥管理**：集中管理 API 密钥，脱敏显示，一键复制，本地安全存储
- **多 URL 支持**：每个提供商可配置多个 API 地址（如不同计费方式），分别指定接口格式（OpenAI / Anthropic）
- **一键复制**：Base URL 和 API Key 均支持一键复制到剪贴板
- **全局搜索**：按名称、描述搜索提供商
- **仪表盘**：类别筛选 + 提供商卡片网格
- **模型列表**：全局模型表格，支持筛选、排序、按提供商折叠
- **XSS 防护**：所有用户输入均经过 HTML 转义

### API 转接/代理功能
- **三种协议端点**：
  - `POST /v1/chat/completions` — OpenAI Chat Completions 格式（适配 Cherry Studio、OpenCat 等）
  - `POST /v1/responses` — OpenAI Responses API 格式（适配 Codex CLI）
  - `POST /v1/messages` — Anthropic Messages 格式（适配 Claude Code）
- **GET /v1/models** — 模型列表端点（OpenAI 格式）
- **三 Key 分协议方案**：三把独立的 API Key，每把绑定一个输出协议，不同客户端软件用不同 Key 互不干扰
- **自动协议转换**：9 种组合全支持（3 种客户端协议 × 3 种厂商协议），自动翻译请求和响应格式
- **模型自动路由**：根据请求中的 model 名自动查找对应厂商、密钥和 API 地址
- **思考/推理内容支持**：DeepSeek-R1、Mimo 等 reasoning 模型的思考过程正确映射到各协议格式
- **内容策略验证**：转发前自动校验参数合法性（max_tokens、temperature、top_p 等）
- **流式输出**：支持 SSE 流式响应，三种协议均支持 streaming
- **厂商适配器**：DeepSeek/Mimo/GLM 等厂商的特殊行为通过适配器模式统一处理
- **本地安全**：厂商 API Key 永远不暴露给客户端，转接服务通过独立的转接 Key 认证

## 快速开始

### 方式一：直接运行 Python

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 运行程序：
```bash
python run.py
```

3. 浏览器会自动打开 http://localhost:5000

### 方式二：打包成 exe

1. 安装打包依赖：
```bash
pip install pyinstaller
```

2. 运行打包脚本：
```bash
python build.py
```

3. 在 `dist` 目录找到生成的 `AI-API-Hub.exe`

## API 转接使用指南

### 1. 配置提供商和密钥

先在平台上添加 API 提供商（含 API URL）和模型，并为每个提供商配置 API Key。

### 2. 生成转接 Key

在「API 转接」页面，分别为三种协议生成专用 Key：
- **Chat 专用 Key**（`sk-chat-...`）：给 Cherry Studio、OpenCat 等 OpenAI 兼容客户端使用
- **Anthropic 专用 Key**（`sk-anthropic-...`）：给 Claude Code 使用
- **Responses 专用 Key**（`sk-responses-...`）：给 Codex CLI 使用

开启转接开关，保存设置。

### 3. 配置客户端

**Cherry Studio / OpenCat 等 OpenAI 兼容客户端：**
- API 地址：`http://127.0.0.1:5000/v1`
- API Key：Chat 专用 Key

**Claude Code：**
- 设置 Anthropic 转接端点作为 API 地址
- API Key：Anthropic 专用 Key

**Codex CLI：**
- API 地址：`http://127.0.0.1:5000/v1`
- API Key：Responses 专用 Key

### 4. curl 测试

**OpenAI Chat Completions：**
```bash
curl -s http://127.0.0.1:5000/v1/chat/completions \
  -H "Authorization: Bearer <Chat 专用 Key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "system", "content": "你是一个有帮助的助手"},
      {"role": "user", "content": "你好"}
    ]
  }'
```

**OpenAI Responses API：**
```bash
curl -s http://127.0.0.1:5000/v1/responses \
  -H "Authorization: Bearer <Responses 专用 Key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "input": "你好，请介绍一下你自己",
    "instructions": "你是一个有帮助的助手"
  }'
```

**Anthropic Messages：**
```bash
curl -s http://127.0.0.1:5000/v1/messages \
  -H "x-api-key: <Anthropic 专用 Key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 1024,
    "messages": [
      {"role": "user", "content": "你好"}
    ]
  }'
```

**模型列表：**
```bash
curl -s http://127.0.0.1:5000/v1/models \
  -H "Authorization: Bearer <任意转接 Key>"
```

## 使用说明

1. **添加提供商**：点击侧边栏底部的「+ 添加提供商」按钮，可添加多个 API URL（如按量计费、按次计费等不同地址）
2. **添加模型**：进入提供商详情页，点击「+ 添加模型」，选择计费方式（按量计费 / 按次收费）
3. **添加密钥**：进入提供商详情页，点击「+ 添加密钥」
4. **一键复制**：在提供商详情页和密钥列表中，点击「复制」按钮即可复制 Base URL 或 API Key
5. **AI 智能解析**：
   - 先在「AI 设置」页面配置 AI 服务（API 格式、URL、Key、模型名），支持 OpenAI 和 Anthropic 格式
   - 在「AI 解析」页面通过文本粘贴、文件上传（docx/pdf/xlsx/图片）或 URL 抓取输入文档
   - 预览识别结果，确认后点击「一键导入」（可选替换或补充模式）
6. **API 转接**：
   - 在「API 转接」页面为三种协议分别生成专用 Key
   - 开启转接开关，将对应的 Key 和端点配置到各客户端软件中
   - 可用模型列表自动显示所有已配置密钥的模型
7. **全局查看**：侧边栏的「模型列表」和「API密钥」页面可查看所有数据
8. **模型筛选**：全局模型列表支持搜索、逐列筛选、排序、按提供商折叠
9. **搜索**：在「API提供商」页面使用搜索栏

## 转接协议说明

转接服务通过**内部归一化**实现 3×3 协议互转。客户端请求先转为内部通用格式，再转为厂商格式；厂商响应同理反向转换。

| 客户端 ↓ \ 厂商 → | OpenAI Chat | Anthropic | OpenAI Responses |
|---|---|---|---|
| **Chat Completions** | 直通转发 | Chat↔Anthropic 翻译 | Chat↔Responses 翻译 |
| **Anthropic Messages** | Anthropic↔Chat 翻译 | 直通转发 | Anthropic↔Responses 翻译 |
| **Responses API** | Responses↔Chat 翻译 | Responses↔Anthropic 翻译 | 直通转发 |

输出协议由 Key 绑定（优先级：X-Output-Protocol 请求头 > Key 绑定 > 数据库设置 > 跟随输入协议）。

## 技术栈

- **后端**：Python + Flask + SQLite
- **前端**：原生 HTML/CSS/JavaScript（无框架依赖）
- **打包**：PyInstaller

## 项目结构

```
ai-api-hub/
├── run.py                     # 启动入口 + 所有可配置参数
├── build.py                   # PyInstaller 打包脚本
├── icon.py                    # 图标生成器
├── requirements.txt           # Python 依赖
├── app/
│   ├── __init__.py            # Flask 应用工厂
│   ├── database.py            # 数据库连接、表结构、迁移
│   ├── routes/
│   │   ├── __init__.py        # 蓝图注册
│   │   ├── system.py          # 首页渲染 + 服务器关闭
│   │   ├── providers.py       # 提供商 CRUD
│   │   ├── models.py          # 模型 CRUD
│   │   ├── keys.py            # 密钥 CRUD
│   │   ├── settings.py        # 全局设置
│   │   ├── stats.py           # 统计数据
│   │   ├── ai.py              # AI 解析 + 导入
│   │   └── relay.py           # API 转接路由（三种协议端点 + 流式 SSE）
│   └── services/
│       ├── relay_service.py   # 转接核心服务（认证/路由/协议转换/适配器/SSE格式化）
│       ├── ai_service.py      # AI API 调用（OpenAI/Anthropic）
│       ├── file_parser.py     # 文档解析（docx/pdf/xlsx）
│       ├── web_scraper.py     # 网页抓取
│       └── provider_aliases.py # 提供商名称归一化
├── templates/
│   └── index.html             # 单页应用 HTML
├── static/
│   ├── css/style.css          # 样式表（深色主题）
│   └── js/app.js              # 前端逻辑
└── ai_api_hub.db              # SQLite 数据库（首次运行自动创建，删除即重置）
```

## 数据存储

所有数据存储在本地 SQLite 数据库文件 `ai_api_hub.db` 中，位于程序运行目录。

- **首次运行**：自动创建空数据库（无预置数据）
- **重置数据**：删除 `ai_api_hub.db` 文件后重新启动即可恢复到空白状态
- **转接设置**：API Key、开关等配置均存储在数据库中

## 可配置参数

所有可配置参数集中在 `run.py` 顶部，包括：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `127.0.0.1` | 监听地址，`0.0.0.0` 允许外部访问 |
| `PORT` | `5000` | 监听端口 |
| `DEBUG` | `False` | 调试模式（环境变量 `FLASK_DEBUG=1` 也可开启） |
| `OPEN_BROWSER` | `True` | 启动时是否自动打开浏览器 |
| `DB_NAME` | `ai_api_hub.db` | SQLite 数据库文件名 |
| `MAX_UPLOAD_SIZE` | `16 MB` | 上传文件最大大小 |
| `AI_REQUEST_TIMEOUT` | `60` | AI 服务请求超时（秒） |
| `AI_MAX_TOKENS` | `4000` | AI 解析最大输出 token 数 |
| `RELAY_TIMEOUT` | `120` | API 转接请求超时（秒） |
| `RELAY_DEFAULT_MAX_TOKENS` | `2048` | 转接默认最大 token 数 |

## 注意事项

- API 密钥仅存储在本地 SQLite 数据库中，请妥善保管数据库文件
- 删除 `ai_api_hub.db` 即可清除所有配置和数据，保护隐私
- 默认绑定 `127.0.0.1`，仅本机可访问。如需局域网访问，修改 `run.py` 中 `HOST = '0.0.0.0'`
- 可通过设置环境变量 `FLASK_DEBUG=1` 开启调试模式
- 转接服务的厂商 API Key 永不暴露给客户端，安全性由转接 Key 保证
