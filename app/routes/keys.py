# -*- coding: utf-8 -*-
# AI API Hub — API 密钥 CRUD 路由模块
# 提供 API 密钥的增删改查功能

from flask import Blueprint, request, jsonify  # Flask 核心模块
from app.database import get_db                # 数据库连接函数

bp = Blueprint('keys', __name__)               # 创建密钥蓝图


@bp.route('/api/keys', methods=['GET'])
def get_all_keys():
    """获取所有密钥列表（带提供商名称），用于全局密钥页面"""
    conn = get_db()
    try:
        # 联表查询：获取密钥信息及其提供商名称
        keys = conn.execute('''
            SELECT k.*, p.display_name as provider_name
            FROM api_keys k
            LEFT JOIN api_providers p ON k.provider_id = p.id
            ORDER BY p.display_name, k.key_name
        ''').fetchall()
        return jsonify([dict(k) for k in keys])
    finally:
        conn.close()


@bp.route('/api/providers/<int:provider_id>/keys', methods=['GET'])
def get_keys(provider_id):
    """获取指定提供商下的所有密钥"""
    conn = get_db()
    try:
        keys = conn.execute(
            'SELECT * FROM api_keys WHERE provider_id = ?',
            (provider_id,)
        ).fetchall()
        return jsonify([dict(k) for k in keys])
    finally:
        conn.close()


@bp.route('/api/providers/<int:provider_id>/keys', methods=['POST'])
def create_key(provider_id):
    """为指定提供商创建新密钥"""
    data = request.json
    if not data:
        return jsonify({'error': '请求数据不能为空'}), 400

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO api_keys (provider_id, key_name, api_key, notes)
            VALUES (?, ?, ?, ?)
        ''', (
            provider_id,               # 所属提供商 ID
            data['key_name'],          # 密钥名称（必填）
            data.get('api_key'),       # API 密钥值
            data.get('notes')          # 备注信息
        ))
        conn.commit()
        return jsonify({'id': cursor.lastrowid, 'message': 'Created successfully'}), 201
    finally:
        conn.close()


@bp.route('/api/keys/<int:key_id>', methods=['PUT'])
def update_key(key_id):
    """更新密钥信息"""
    data = request.json
    if not data:
        return jsonify({'error': '请求数据不能为空'}), 400

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE api_keys SET key_name=?, api_key=?, notes=?
            WHERE id=?
        ''', (
            data['key_name'],
            data.get('api_key'),
            data.get('notes'),
            key_id
        ))
        conn.commit()

        if cursor.rowcount == 0:       # 密钥不存在
            return jsonify({'error': 'Key not found'}), 404

        return jsonify({'message': 'Updated successfully'})
    finally:
        conn.close()


@bp.route('/api/keys/<int:key_id>', methods=['DELETE'])
def delete_key(key_id):
    """删除单个密钥"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM api_keys WHERE id = ?', (key_id,))
        conn.commit()

        if cursor.rowcount == 0:       # 密钥不存在
            return jsonify({'error': 'Key not found'}), 404

        return jsonify({'message': 'Deleted successfully'})
    finally:
        conn.close()
