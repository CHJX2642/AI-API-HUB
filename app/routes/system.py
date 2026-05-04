# -*- coding: utf-8 -*-
# AI API Hub — 系统路由模块
# 提供首页渲染和服务器关闭功能

import os
import threading
from flask import Blueprint, render_template, jsonify, request  # Flask 核心模块

bp = Blueprint('system', __name__)       # 创建系统蓝图


@bp.route('/')
def index():
    """主页路由：返回前端单页应用 HTML"""
    return render_template('index.html') # 渲染 templates/index.html


@bp.route('/api/shutdown', methods=['POST'])
def shutdown():
    """关闭服务器接口：前端调用后优雅停止 Flask 服务"""
    shutdown_server()
    return jsonify({'message': 'Server shutting down...'})


def shutdown_server():
    """关闭 Werkzeug 开发服务器（兼容新版 werkzeug + exe 打包）"""
    import time
    # 新版 werkzeug 通过 environ 传递 shutdown 函数
    func = request.environ.get('werkzeug.server.shutdown')
    if func is not None:
        func()
    else:
        # 降级方案：延迟 0.5s 确保响应发出后强制退出
        def _exit():
            time.sleep(0.5)
            os._exit(0)
        threading.Thread(target=_exit, daemon=True).start()
