# AI API Hub — 大模型API管理平台

一个纯自定义的本地 AI 大模型 API 信息管理工具。所有提供商、模型、密钥均由用户自行添加，无预置数据。

## 功能特性

- **完全自定义**：无预置数据，按需添加你的 API 提供商和模型
- **AI 智能解析**：粘贴 API 文档、上传文件或输入 URL，AI 自动识别提供商和模型信息并一键导入
- **提供商管理**：添加、编辑、删除 API 提供商（支持分类：国外主流/国内主流/其他）
- **模型管理**：记录模型 ID、Token 限制、多模态支持、函数调用、定价等信息
- **灵活计费**：支持按量计费（tokens）和按次收费两种定价方式
- **密钥管理**：集中管理 API 密钥，脱敏显示，一键复制，本地安全存储
- **多 URL 支持**：每个提供商可配置多个 API 地址（如不同计费方式），分别指定接口格式
- **一键复制**：Base URL 和 API Key 均支持一键复制到剪贴板
- **全局搜索**：按名称、描述搜索提供商
- **仪表盘**：类别筛选 + 提供商卡片网格
- **模型列表**：全局模型表格，支持筛选、排序、按提供商折叠
- **XSS 防护**：所有用户输入均经过 HTML 转义
- **可打包为 exe**：支持 PyInstaller 打包为独立 Windows 可执行文件

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

## 使用说明

1. **添加提供商**：点击侧边栏底部的「+ 添加提供商」按钮，可添加多个 API URL（如按量计费、按次计费等不同地址）
2. **添加模型**：进入提供商详情页，点击「+ 添加模型」，选择计费方式（按量计费 / 按次收费）
3. **添加密钥**：进入提供商详情页，点击「+ 添加密钥」
4. **一键复制**：在提供商详情页和密钥列表中，点击「复制」按钮即可复制 Base URL 或 API Key
5. **AI 智能解析**：
   - 先在「AI 设置」页面配置 AI 服务（API 格式、URL、Key、模型名），支持 OpenAI 和 Anthropic 格式
   - 在「AI 解析」页面通过文本粘贴、文件上传（docx/pdf/xlsx/图片）或 URL 抓取输入文档
   - 预览识别结果，确认后点击「一键导入」（可选替换或补充模式）
6. **全局查看**：侧边栏的「模型列表」和「API密钥」页面可查看所有数据
7. **模型筛选**：全局模型列表支持搜索、逐列筛选、排序、按提供商折叠
8. **搜索**：在「API提供商」页面使用搜索栏

## 技术栈

- **后端**：Python + Flask + SQLite
- **前端**：原生 HTML/CSS/JavaScript（无框架依赖）
- **打包**：PyInstaller

## 项目结构

```
ai-api-hub/
├── run.py                # 启动入口
├── build.py              # PyInstaller 打包脚本
├── icon.py               # 图标生成器
├── requirements.txt      # Python 依赖
├── app/
│   ├── __init__.py       # Flask 应用工厂
│   ├── database.py       # 数据库连接、表结构、迁移
│   ├── routes/
│   │   ├── system.py     # 首页渲染 + 服务器关闭
│   │   ├── providers.py  # 提供商 CRUD
│   │   ├── models.py     # 模型 CRUD
│   │   ├── keys.py       # 密钥 CRUD
│   │   ├── settings.py   # 全局设置
│   │   ├── stats.py      # 统计数据
│   │   └── ai.py         # AI 解析 + 导入
│   └── services/
│       ├── ai_service.py       # AI API 调用（OpenAI/Anthropic）
│       ├── file_parser.py      # 文档解析（docx/pdf/xlsx）
│       ├── web_scraper.py      # 网页抓取
│       └── provider_aliases.py # 提供商名称归一化
├── templates/
│   └── index.html        # 单页应用 HTML
├── static/
│   ├── css/style.css     # 样式表（深色主题）
│   └── js/app.js         # 前端逻辑
└── ai_api_hub.db         # SQLite 数据库（运行时自动创建）
```

## 数据存储

所有数据存储在本地 SQLite 数据库文件 `ai_api_hub.db` 中，位于程序运行目录。首次运行会自动创建空数据库。

## 注意事项

- API 密钥仅存储在本地，请妥善保管数据库文件
- 默认绑定 `127.0.0.1`，仅本机可访问
- 可通过设置环境变量 `FLASK_DEBUG=1` 开启调试模式
