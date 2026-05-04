# -*- coding: utf-8 -*-
# AI API Hub — 统计数据路由模块
# 提供仪表盘所需的统计数据（提供商/模型/密钥数量）

from flask import Blueprint, jsonify     # Flask 核心模块
from app.database import get_db          # 数据库连接函数

bp = Blueprint('stats', __name__)        # 创建统计蓝图


@bp.route('/api/stats', methods=['GET'])
def get_stats():
    """获取仪表盘统计数据：提供商数量、模型数量、密钥数量"""
    conn = get_db()                      # 获取数据库连接
    try:
        # 分别查询三个表的记录数
        providers = conn.execute('SELECT COUNT(*) FROM api_providers').fetchone()[0]
        models = conn.execute('SELECT COUNT(*) FROM api_models').fetchone()[0]
        keys = conn.execute('SELECT COUNT(*) FROM api_keys').fetchone()[0]
        return jsonify({                 # 返回 JSON 响应
            'providers': providers,      # 提供商数量
            'models': models,            # 模型数量
            'keys': keys                 # 密钥数量
        })
    finally:
        conn.close()                     # 确保关闭连接
