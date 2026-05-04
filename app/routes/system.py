# -*- coding: utf-8 -*-
# AI API Hub — 系统路由模块
# 提供首页渲染和服务器关闭功能

import werkzeug.serving                  # Werkzeug 开发服务器，用于优雅关闭
from flask import Blueprint, render_template, jsonify  # Flask 核心模块

bp = Blueprint('system', __name__)       # 创建系统蓝图


@bp.route('/')
def index():
    """主页路由：返回前端单页应用 HTML"""
    return render_template('index.html') # 渲染 templates/index.html


@bp.route('/api/shutdown', methods=['POST'])
def shutdown():
    """关闭服务器接口：前端调用后优雅停止 Flask 服务"""
    shutdown_server()                    # 调用关闭函数
    return jsonify({'message': 'Server shutting down...'})


def shutdown_server():
    """优雅关闭 Werkzeug 开发服务器"""
    func = werkzeug.serving.shutdown     # 获取关闭函数引用
    if func is None:                     # 如果不在 Werkzeug 环境中
        raise RuntimeError('Not running with the Werkzeug Server')
    func()                               # 执行关闭
