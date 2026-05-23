# -*- coding: utf-8 -*-
# AI API Hub — 应用启动入口 + 所有可配置参数

import sys
import os
import webbrowser
import threading
import time

# 将脚本所在目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ====================== 可配置参数 ======================

# 服务器配置
HOST = '127.0.0.1'             # 监听地址，'0.0.0.0' 表示允许外部访问
PORT = 5000                    # 监听端口
DEBUG = False                  # 调试模式（可通过环境变量 FLASK_DEBUG=1 开启）
OPEN_BROWSER = True            # 启动时是否自动打开浏览器

# 数据库配置
DB_NAME = 'ai_api_hub.db'      # SQLite 数据库文件名

# 文件上传配置
MAX_UPLOAD_SIZE = 16 * 1024 * 1024   # 上传文件最大 16MB
ALLOWED_EXTENSIONS = {                 # AI 解析支持的文件格式
    '.docx', '.pdf', '.xlsx',
    '.jpg', '.jpeg', '.png', '.gif', '.webp'
}
IMAGE_EXTENSIONS = {                   # 图片格式（走多模态 API）
    '.jpg', '.jpeg', '.png', '.gif', '.webp'
}

# AI 服务配置
AI_REQUEST_TIMEOUT = 60        # AI API 请求超时（秒）
AI_MAX_TOKENS = 4000           # AI 最大输出 token 数
URL_FETCH_TIMEOUT = 15         # 网页抓取超时（秒）
URL_MAX_LENGTH = 100000        # 网页内容最大字符数

# API 转接配置
RELAY_TIMEOUT = 120            # 转接请求超时（秒）
RELAY_DEFAULT_MAX_TOKENS = 4096     # 转接默认最大 token 数
RELAY_VERIFY_SSL = False       # SSL 证书验证（调试时设 False，正式使用设 True）

# ====================== 启动逻辑 ======================

def open_browser():
    """延迟 1.5 秒后打开浏览器，等待服务器启动完成"""
    time.sleep(1.5)
    webbrowser.open(f'http://{HOST}:{PORT}')


if __name__ == '__main__':
    # 组装配置字典，传入 Flask app
    config = {
        'DB_NAME': DB_NAME,
        'MAX_CONTENT_LENGTH': MAX_UPLOAD_SIZE,
        'ALLOWED_EXTENSIONS': ALLOWED_EXTENSIONS,
        'IMAGE_EXTENSIONS': IMAGE_EXTENSIONS,
        'AI_REQUEST_TIMEOUT': AI_REQUEST_TIMEOUT,
        'AI_MAX_TOKENS': AI_MAX_TOKENS,
        'URL_FETCH_TIMEOUT': URL_FETCH_TIMEOUT,
        'URL_MAX_LENGTH': URL_MAX_LENGTH,
        'RELAY_TIMEOUT': RELAY_TIMEOUT,
        'RELAY_DEFAULT_MAX_TOKENS': RELAY_DEFAULT_MAX_TOKENS,
        'RELAY_VERIFY_SSL': RELAY_VERIFY_SSL,
    }

    # 创建 Flask 应用并初始化数据库
    from app import create_app
    from app.database import init_db

    app = create_app(config)
    with app.app_context():
        init_db()

    # 打印启动信息
    print("=" * 50)
    print("  AI API 大模型集合平台")
    print(f"  访问地址: http://{HOST}:{PORT}")
    print("=" * 50)

    # 自动打开浏览器
    if OPEN_BROWSER:
        threading.Thread(target=open_browser, daemon=True).start()

    # 启动 Flask 服务器
    debug = DEBUG or os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug, host=HOST, port=PORT)
