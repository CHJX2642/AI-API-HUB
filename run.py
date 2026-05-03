# -*- coding: utf-8 -*-
# AI API Hub — 应用启动入口
# 负责初始化数据库、打印启动信息、打开浏览器、启动 Flask 服务器

import sys                    # 系统接口，用于路径设置
import os                     # 操作系统接口，用于路径处理
import webbrowser             # 浏览器控制模块，用于自动打开页面
import threading              # 多线程模块，用于后台打开浏览器
import time                   # 时间模块，用于延迟等待服务器启动

# 将脚本所在目录加入 Python 路径，确保打包后也能正确导入模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 从 app 模块导入 Flask 应用和初始化函数
from app import app, init_db


def open_browser():
    """延迟 1.5 秒后打开浏览器，等待服务器启动完成"""
    time.sleep(1.5)                                          # 等待 Flask 服务器启动
    webbrowser.open('http://localhost:5000')                  # 在默认浏览器中打开应用


if __name__ == '__main__':
    init_db()                                                # 初始化数据库表结构（如已存在则跳过）

    # 打印启动信息横幅
    print("=" * 50)                                          # 分隔线
    print("  AI API 大模型集合平台")                           # 应用名称
    print("  访问地址: http://localhost:5000")                 # 访问地址
    print("=" * 50)                                          # 分隔线

    # 在后台线程中打开浏览器（daemon=True 表示主线程退出时自动结束）
    threading.Thread(target=open_browser, daemon=True).start()

    # 启动 Flask 服务器
    # host='127.0.0.1' 仅本机可访问（安全）
    # port=5000 监听端口
    # debug=False 生产模式（通过环境变量 FLASK_DEBUG=1 可开启调试）
    app.run(
        debug=os.environ.get('FLASK_DEBUG', '0') == '1',     # 通过环境变量控制调试模式
        host='127.0.0.1',                                    # 仅绑定本机地址
        port=5000                                            # 监听端口
    )
