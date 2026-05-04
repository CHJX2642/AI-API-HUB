# -*- coding: utf-8 -*-
# AI API Hub — 提供商 CRUD 路由模块
# 提供 API 提供商的增删改查功能

import json                              # JSON 处理，用于 api_urls 字段序列化
from flask import Blueprint, request, jsonify  # Flask 核心模块
from app.database import get_db, parse_provider_row  # 数据库工具函数

bp = Blueprint('providers', __name__)    # 创建提供商蓝图


@bp.route('/api/providers', methods=['GET'])
def get_providers():
    """获取提供商列表，支持按类别筛选和关键词搜索"""
    conn = get_db()                      # 获取数据库连接
    try:
        category = request.args.get('category')  # 从查询参数获取类别筛选
        search = request.args.get('search')      # 从查询参数获取搜索关键词
        query = 'SELECT * FROM api_providers WHERE 1=1'  # 基础查询（1=1 方便拼接条件）
        params = []                      # 查询参数列表（防 SQL 注入）

        if category:                     # 如果指定了类别
            query += ' AND category = ?'
            params.append(category)

        if search:                       # 如果有搜索关键词
            query += ' AND (name LIKE ? OR display_name LIKE ? OR description LIKE ?)'
            params.extend([f'%{search}%'] * 3)  # 模糊搜索三个字段

        query += ' ORDER BY display_name'        # 按显示名称排序
        providers = conn.execute(query, params).fetchall()
        return jsonify([parse_provider_row(p) for p in providers])  # 解析 api_urls JSON 后返回
    finally:
        conn.close()


@bp.route('/api/providers/<int:provider_id>', methods=['GET'])
def get_provider(provider_id):
    """获取单个提供商详情，包含其所有模型和密钥"""
    conn = get_db()
    try:
        # 查询提供商基本信息
        provider = conn.execute(
            'SELECT * FROM api_providers WHERE id = ?', (provider_id,)
        ).fetchone()

        if not provider:                 # 提供商不存在
            return jsonify({'error': 'Provider not found'}), 404

        # 查询该提供商下的所有模型（按显示名称排序）
        models = conn.execute(
            'SELECT * FROM api_models WHERE provider_id = ? ORDER BY display_name',
            (provider_id,)
        ).fetchall()

        # 查询该提供商下的所有密钥
        keys = conn.execute(
            'SELECT * FROM api_keys WHERE provider_id = ?',
            (provider_id,)
        ).fetchall()

        # 组装返回数据：提供商信息 + 模型列表 + 密钥列表
        result = parse_provider_row(provider)
        result['models'] = [dict(m) for m in models]
        result['keys'] = [dict(k) for k in keys]
        return jsonify(result)
    finally:
        conn.close()


@bp.route('/api/providers', methods=['POST'])
def create_provider():
    """创建新提供商"""
    data = request.json
    if not data:
        return jsonify({'error': '请求数据不能为空'}), 400

    conn = get_db()
    try:
        # api_urls 字段：如果是 list 则序列化为 JSON 字符串存储
        api_urls = data.get('api_urls')
        if isinstance(api_urls, list):
            api_urls = json.dumps(api_urls, ensure_ascii=False)

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO api_providers (name, display_name, base_url, api_urls, description, category)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data['name'],              # 英文标识名（必填）
            data['display_name'],      # 显示名称（必填）
            data.get('base_url'),      # Base URL（旧字段，兼容）
            api_urls,                  # 自定义 URL 列表 JSON
            data.get('description'),   # 描述（可选）
            data.get('category', 'other')  # 类别，默认 'other'
        ))
        conn.commit()
        return jsonify({'id': cursor.lastrowid, 'message': 'Created successfully'}), 201
    finally:
        conn.close()


@bp.route('/api/providers/<int:provider_id>', methods=['PUT'])
def update_provider(provider_id):
    """更新提供商信息"""
    data = request.json
    if not data:
        return jsonify({'error': '请求数据不能为空'}), 400

    conn = get_db()
    try:
        # api_urls 字段序列化
        api_urls = data.get('api_urls')
        if isinstance(api_urls, list):
            api_urls = json.dumps(api_urls, ensure_ascii=False)

        cursor = conn.cursor()
        cursor.execute('''
            UPDATE api_providers
            SET name=?, display_name=?, base_url=?, api_urls=?,
                description=?, category=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (
            data['name'],
            data['display_name'],
            data.get('base_url'),
            api_urls,
            data.get('description'),
            data.get('category'),
            provider_id
        ))
        conn.commit()

        if cursor.rowcount == 0:       # 没有更新到任何行
            return jsonify({'error': 'Provider not found'}), 404

        return jsonify({'message': 'Updated successfully'})
    finally:
        conn.close()


@bp.route('/api/providers/<int:provider_id>', methods=['DELETE'])
def delete_provider(provider_id):
    """删除提供商及其所有关联数据（模型、密钥）"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        # 使用事务确保原子性操作：先删子表，再删主表
        cursor.execute('DELETE FROM api_models WHERE provider_id = ?', (provider_id,))
        cursor.execute('DELETE FROM api_keys WHERE provider_id = ?', (provider_id,))
        cursor.execute('DELETE FROM api_providers WHERE id = ?', (provider_id,))
        conn.commit()

        if cursor.rowcount == 0:       # 提供商不存在
            return jsonify({'error': 'Provider not found'}), 404

        return jsonify({'message': 'Deleted successfully'})
    finally:
        conn.close()
