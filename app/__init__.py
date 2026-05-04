# -*- coding: utf-8 -*-
# AI API Hub — Flask 应用工厂模块
# 负责创建和配置 Flask 应用实例，注册所有路由蓝图

import os                              # 操作系统接口，用于路径拼接
from flask import Flask                # Flask 核心类


def create_app(config_dict=None):
    """创建并配置 Flask 应用实例（工厂模式）
    参数:
        config_dict: 可选的配置字典，由 run.py 传入
    返回:
        配置完成的 Flask 应用实例
    """
    # 计算项目根目录（app/ 的上级目录）
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 创建 Flask 实例，指定静态文件和模板的绝对路径
    app = Flask(
        __name__,
        static_folder=os.path.join(base_dir, 'static'),       # CSS/JS 文件目录
        template_folder=os.path.join(base_dir, 'templates')    # HTML 模板目录
    )

    # 将 run.py 中的配置参数注入 Flask app.config
    if config_dict:
        app.config.update(config_dict)

    # 导入并注册所有路由蓝图（分模块组织路由）
    from app.routes import register_blueprints
    register_blueprints(app)

    return app                           # 返回配置好的应用实例
