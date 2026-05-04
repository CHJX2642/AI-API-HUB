# -*- coding: utf-8 -*-
# AI API Hub — 模型 CRUD 路由模块
# 提供 AI 模型的增删改查功能

from flask import Blueprint, request, jsonify  # Flask 核心模块
from app.database import get_db                # 数据库连接函数

bp = Blueprint('models', __name__)             # 创建模型蓝图


@bp.route('/api/models', methods=['GET'])
def get_all_models():
    """获取所有模型列表（带提供商名称），用于全局模型页面"""
    conn = get_db()
    try:
        # 联表查询：获取模型信息及其提供商名称
        models = conn.execute('''
            SELECT m.*, p.display_name as provider_name
            FROM api_models m
            LEFT JOIN api_providers p ON m.provider_id = p.id
            ORDER BY p.display_name, m.display_name
        ''').fetchall()
        return jsonify([dict(m) for m in models])
    finally:
        conn.close()


@bp.route('/api/providers/<int:provider_id>/models', methods=['GET'])
def get_models(provider_id):
    """获取指定提供商下的所有模型"""
    conn = get_db()
    try:
        models = conn.execute(
            'SELECT * FROM api_models WHERE provider_id = ? ORDER BY display_name',
            (provider_id,)
        ).fetchall()
        return jsonify([dict(m) for m in models])
    finally:
        conn.close()


@bp.route('/api/providers/<int:provider_id>/models', methods=['POST'])
def create_model(provider_id):
    """为指定提供商创建新模型"""
    data = request.json
    if not data:
        return jsonify({'error': '请求数据不能为空'}), 400

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO api_models (provider_id, model_id, display_name, description,
                max_tokens, supports_vision, supports_function_calling,
                price_input, price_input_cached, price_output,
                pricing_type, price_per_request)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            provider_id,                   # 所属提供商 ID
            data['model_id'],              # 模型标识（必填）
            data['display_name'],          # 显示名称（必填）
            data.get('description'),       # 描述
            data.get('max_tokens'),        # 最大 Token 数
            1 if data.get('supports_vision') else 0,         # 是否支持多模态
            1 if data.get('supports_function_calling') else 0,  # 是否支持函数调用
            data.get('price_input'),       # 输入价格
            data.get('price_input_cached'),# 缓存价格
            data.get('price_output'),      # 输出价格
            data.get('pricing_type', 'per_token'),  # 计费方式
            data.get('price_per_request')  # 按次收费价格
        ))
        conn.commit()
        return jsonify({'id': cursor.lastrowid, 'message': 'Created successfully'}), 201
    finally:
        conn.close()


@bp.route('/api/models/<int:model_id>', methods=['PUT'])
def update_model(model_id):
    """更新模型信息"""
    data = request.json
    if not data:
        return jsonify({'error': '请求数据不能为空'}), 400

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE api_models SET
                model_id=?, display_name=?, description=?,
                max_tokens=?, supports_vision=?, supports_function_calling=?,
                price_input=?, price_input_cached=?, price_output=?,
                pricing_type=?, price_per_request=?
            WHERE id=?
        ''', (
            data['model_id'],
            data['display_name'],
            data.get('description'),
            data.get('max_tokens'),
            1 if data.get('supports_vision') else 0,
            1 if data.get('supports_function_calling') else 0,
            data.get('price_input'),
            data.get('price_input_cached'),
            data.get('price_output'),
            data.get('pricing_type', 'per_token'),
            data.get('price_per_request'),
            model_id
        ))
        conn.commit()

        if cursor.rowcount == 0:       # 模型不存在
            return jsonify({'error': 'Model not found'}), 404

        return jsonify({'message': 'Updated successfully'})
    finally:
        conn.close()


@bp.route('/api/models/<int:model_id>', methods=['DELETE'])
def delete_model(model_id):
    """删除单个模型"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM api_models WHERE id = ?', (model_id,))
        conn.commit()

        if cursor.rowcount == 0:       # 模型不存在
            return jsonify({'error': 'Model not found'}), 404

        return jsonify({'message': 'Deleted successfully'})
    finally:
        conn.close()
