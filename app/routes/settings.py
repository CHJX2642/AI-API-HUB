# -*- coding: utf-8 -*-
# AI API Hub — 设置路由模块
# 提供全局设置的读取和更新功能（key-value 存储）

from flask import Blueprint, request, jsonify  # Flask 核心模块
from app.database import get_db                # 数据库连接函数

bp = Blueprint('settings', __name__)           # 创建设置蓝图


@bp.route('/api/settings', methods=['GET'])
def get_settings():
    """获取所有设置项，返回 key-value 字典"""
    conn = get_db()                            # 获取数据库连接
    try:
        rows = conn.execute('SELECT key, value FROM app_settings').fetchall()
        # 将行数据转为 {key: value} 字典格式返回
        return jsonify({row['key']: row['value'] for row in rows})
    finally:
        conn.close()                           # 确保关闭连接


@bp.route('/api/settings', methods=['PUT'])
def update_settings():
    """批量更新设置项（使用 upsert 语法：存在则更新，不存在则插入）"""
    data = request.json                        # 获取请求 JSON 数据
    if not data:                               # 如果没有请求体
        return jsonify({'error': '请求数据不能为空'}), 400

    conn = get_db()                            # 获取数据库连接
    try:
        cursor = conn.cursor()                 # 创建游标
        for key, value in data.items():        # 遍历所有设置项
            cursor.execute('''
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=?, updated_at=CURRENT_TIMESTAMP
            ''', (key, value, value))          # upsert：冲突时更新 value
        conn.commit()                          # 提交事务
        return jsonify({'message': 'Settings updated successfully'})
    finally:
        conn.close()                           # 确保关闭连接
