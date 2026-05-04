# -*- coding: utf-8 -*-
# AI API Hub — 路由蓝图注册模块
# 将各功能模块的路由蓝图统一注册到 Flask 应用

from app.routes.providers import bp as providers_bp   # 提供商 CRUD 路由
from app.routes.models import bp as models_bp         # 模型 CRUD 路由
from app.routes.keys import bp as keys_bp             # 密钥 CRUD 路由
from app.routes.settings import bp as settings_bp     # 设置读写路由
from app.routes.stats import bp as stats_bp           # 统计数据路由
from app.routes.ai import bp as ai_bp                 # AI 解析+导入路由
from app.routes.system import bp as system_bp         # 系统路由（首页+关闭）


def register_blueprints(app):
    """将所有蓝图注册到 Flask 应用
    参数:
        app: Flask 应用实例
    """
    app.register_blueprint(system_bp)       # 注册系统路由（/）
    app.register_blueprint(providers_bp)    # 注册提供商路由（/api/providers）
    app.register_blueprint(models_bp)       # 注册模型路由（/api/models）
    app.register_blueprint(keys_bp)         # 注册密钥路由（/api/keys）
    app.register_blueprint(settings_bp)     # 注册设置路由（/api/settings）
    app.register_blueprint(stats_bp)        # 注册统计路由（/api/stats）
    app.register_blueprint(ai_bp)           # 注册 AI 路由（/api/ai）
