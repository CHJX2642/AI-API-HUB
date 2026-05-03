# -*- coding: utf-8 -*-
# AI API Hub — 大模型API管理平台后端
# 基于 Flask 的 REST API 服务，提供提供商、模型、密钥的 CRUD 操作

import os                        # 操作系统接口，用于路径处理
import sys                       # 系统接口，用于判断是否为 PyInstaller 打包环境
import json                      # JSON 处理模块
import sqlite3                   # SQLite 数据库驱动
import urllib.request             # HTTP 请求模块，用于调用 AI API
import urllib.error               # HTTP 错误处理
from flask import Flask, render_template, request, jsonify  # Flask 核心模块


def get_data_dir():
    """获取数据目录：打包环境下返回 exe 所在目录，否则返回脚本所在目录"""
    if getattr(sys, 'frozen', False):                       # PyInstaller 打包后 sys.frozen 为 True
        return os.path.dirname(sys.executable)              # 返回 exe 文件所在目录
    return os.path.dirname(os.path.abspath(__file__))       # 返回当前脚本所在目录


# 数据库文件路径，与程序放在同一目录下
DATA_DIR = get_data_dir()
DB_PATH = os.path.join(DATA_DIR, 'ai_api_hub.db')

# 创建 Flask 应用实例，指定静态文件和模板目录
app = Flask(__name__, static_folder='static', template_folder='templates')


def get_db():
    """获取数据库连接，设置 row_factory 以便以字典方式访问行数据"""
    conn = sqlite3.connect(DB_PATH)     # 建立 SQLite 连接
    conn.row_factory = sqlite3.Row      # 设置行工厂为 Row，支持 dict() 转换
    return conn                         # 返回连接对象


def init_db():
    """初始化数据库表结构，仅在表不存在时创建"""
    conn = get_db()                     # 获取数据库连接
    cursor = conn.cursor()              # 创建游标

    # 创建 API 提供商表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
            name TEXT NOT NULL,                     -- 英文标识名，如 'openai'
            display_name TEXT NOT NULL,             -- 显示名称，如 'OpenAI'
            base_url TEXT,                          -- API 基础 URL
            description TEXT,                       -- 提供商描述
            category TEXT DEFAULT 'other',          -- 分类：international/domestic/other
            is_active INTEGER DEFAULT 1,            -- 是否启用（1=启用）
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP   -- 更新时间
        )
    ''')

    # 创建 API 模型表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
            provider_id INTEGER,                    -- 所属提供商 ID（外键）
            model_id TEXT NOT NULL,                 -- 模型标识，如 'gpt-4o'
            display_name TEXT NOT NULL,             -- 显示名称，如 'GPT-4o'
            description TEXT,                       -- 模型描述
            max_tokens INTEGER,                     -- 最大 Token 数
            supports_streaming INTEGER DEFAULT 1,   -- 是否支持流式输出
            supports_vision INTEGER DEFAULT 0,      -- 是否支持多模态（Vision）
            supports_function_calling INTEGER DEFAULT 0,  -- 是否支持函数调用
            price_input REAL,                       -- 输入价格（$/1K tokens）
            price_output REAL,                      -- 输出价格（$/1K tokens）
            is_active INTEGER DEFAULT 1,            -- 是否启用
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
            FOREIGN KEY (provider_id) REFERENCES api_providers(id)  -- 外键约束
        )
    ''')

    # 创建 API 密钥表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
            provider_id INTEGER,                    -- 所属提供商 ID（外键）
            key_name TEXT NOT NULL,                 -- 密钥名称，如 '主密钥'
            api_key TEXT,                           -- API 密钥值
            notes TEXT,                             -- 备注信息
            is_active INTEGER DEFAULT 1,            -- 是否启用
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
            FOREIGN KEY (provider_id) REFERENCES api_providers(id)  -- 外键约束
        )
    ''')

    # 创建全局设置表（key-value 形式，用于存储 AI 配置等）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,                       -- 设置项名称（主键）
            value TEXT,                                 -- 设置值
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 更新时间
        )
    ''')

    conn.commit()   # 提交建表语句
    conn.close()    # 关闭连接


# ====================== 路由定义 ======================

@app.route('/')
def index():
    """主页路由，返回前端单页应用"""
    return render_template('index.html')    # 渲染 templates/index.html


# ---------- 提供商相关路由 ----------

@app.route('/api/providers', methods=['GET'])
def get_providers():
    """获取提供商列表，支持按类别筛选和关键词搜索"""
    conn = get_db()                                         # 获取数据库连接
    try:
        category = request.args.get('category')             # 从查询参数获取类别筛选
        search = request.args.get('search')                 # 从查询参数获取搜索关键词
        query = 'SELECT * FROM api_providers WHERE 1=1'     # 基础查询语句
        params = []                                         # 查询参数列表

        if category:                                        # 如果指定了类别
            query += ' AND category = ?'                    # 添加类别过滤条件
            params.append(category)                         # 添加类别参数

        if search:                                          # 如果有搜索关键词
            query += ' AND (name LIKE ? OR display_name LIKE ? OR description LIKE ?)'  # 模糊搜索三个字段
            params.extend([f'%{search}%'] * 3)              # 添加三个搜索参数

        query += ' ORDER BY display_name'                   # 按显示名称排序
        providers = conn.execute(query, params).fetchall()  # 执行查询
        return jsonify([dict(p) for p in providers])        # 返回 JSON 数组
    finally:
        conn.close()                                        # 确保关闭连接


@app.route('/api/providers/<int:provider_id>', methods=['GET'])
def get_provider(provider_id):
    """获取单个提供商详情，包含其所有模型和密钥"""
    conn = get_db()                                         # 获取数据库连接
    try:
        # 查询提供商基本信息
        provider = conn.execute(
            'SELECT * FROM api_providers WHERE id = ?', (provider_id,)
        ).fetchone()

        if not provider:                                    # 提供商不存在
            return jsonify({'error': 'Provider not found'}), 404  # 返回 404

        # 查询该提供商下的所有模型
        models = conn.execute(
            'SELECT * FROM api_models WHERE provider_id = ? ORDER BY display_name',
            (provider_id,)
        ).fetchall()

        # 查询该提供商下的所有密钥
        keys = conn.execute(
            'SELECT * FROM api_keys WHERE provider_id = ?',
            (provider_id,)
        ).fetchall()

        # 组装返回数据
        result = dict(provider)                             # 转换提供商为字典
        result['models'] = [dict(m) for m in models]        # 添加模型列表
        result['keys'] = [dict(k) for k in keys]            # 添加密钥列表
        return jsonify(result)                              # 返回 JSON
    finally:
        conn.close()                                        # 确保关闭连接


@app.route('/api/providers', methods=['POST'])
def create_provider():
    """创建新提供商"""
    data = request.json                                     # 获取请求 JSON 数据
    if not data:                                            # 如果没有请求体
        return jsonify({'error': '请求数据不能为空'}), 400   # 返回 400 错误

    conn = get_db()                                         # 获取数据库连接
    try:
        cursor = conn.cursor()                              # 创建游标
        cursor.execute('''
            INSERT INTO api_providers (name, display_name, base_url, description, category)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            data['name'],                                   # 英文标识名（必填）
            data['display_name'],                           # 显示名称（必填）
            data.get('base_url'),                           # Base URL（可选）
            data.get('description'),                        # 描述（可选）
            data.get('category', 'other')                   # 类别，默认 'other'
        ))
        conn.commit()                                       # 提交事务
        return jsonify({'id': cursor.lastrowid, 'message': 'Created successfully'}), 201
    finally:
        conn.close()                                        # 确保关闭连接


@app.route('/api/providers/<int:provider_id>', methods=['PUT'])
def update_provider(provider_id):
    """更新提供商信息"""
    data = request.json                                     # 获取请求 JSON 数据
    if not data:                                            # 如果没有请求体
        return jsonify({'error': '请求数据不能为空'}), 400   # 返回 400 错误

    conn = get_db()                                         # 获取数据库连接
    try:
        cursor = conn.cursor()                              # 创建游标
        cursor.execute('''
            UPDATE api_providers
            SET name=?, display_name=?, base_url=?, description=?, category=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (
            data['name'],                                   # 英文标识名
            data['display_name'],                           # 显示名称
            data.get('base_url'),                           # Base URL
            data.get('description'),                        # 描述
            data.get('category'),                           # 类别
            provider_id                                     # 要更新的提供商 ID
        ))
        conn.commit()                                       # 提交事务

        if cursor.rowcount == 0:                            # 如果没有更新到任何行
            return jsonify({'error': 'Provider not found'}), 404  # 提供商不存在

        return jsonify({'message': 'Updated successfully'})  # 返回成功
    finally:
        conn.close()                                        # 确保关闭连接


@app.route('/api/providers/<int:provider_id>', methods=['DELETE'])
def delete_provider(provider_id):
    """删除提供商及其所有关联数据（模型、密钥）"""
    conn = get_db()                                         # 获取数据库连接
    try:
        cursor = conn.cursor()                              # 创建游标
        # 使用事务确保原子性操作
        cursor.execute('DELETE FROM api_models WHERE provider_id = ?', (provider_id,))  # 先删模型
        cursor.execute('DELETE FROM api_keys WHERE provider_id = ?', (provider_id,))    # 再删密钥
        cursor.execute('DELETE FROM api_providers WHERE id = ?', (provider_id,))        # 最后删提供商
        conn.commit()                                       # 统一提交事务
        return jsonify({'message': 'Deleted successfully'})  # 返回成功
    except Exception as e:                                  # 如果发生任何错误
        conn.rollback()                                     # 回滚事务，防止部分删除
        return jsonify({'error': str(e)}), 500              # 返回错误信息
    finally:
        conn.close()                                        # 确保关闭连接


# ---------- 模型相关路由 ----------

@app.route('/api/models', methods=['GET'])
def get_all_models():
    """获取所有模型列表（带提供商名称），用于全局模型页面"""
    conn = get_db()                                         # 获取数据库连接
    try:
        # 联表查询，获取模型信息及其提供商名称
        models = conn.execute('''
            SELECT m.*, p.display_name as provider_name
            FROM api_models m
            LEFT JOIN api_providers p ON m.provider_id = p.id
            ORDER BY p.display_name, m.display_name
        ''').fetchall()
        return jsonify([dict(m) for m in models])           # 返回 JSON 数组
    finally:
        conn.close()                                        # 确保关闭连接


@app.route('/api/providers/<int:provider_id>/models', methods=['GET'])
def get_models(provider_id):
    """获取指定提供商下的所有模型"""
    conn = get_db()                                         # 获取数据库连接
    try:
        models = conn.execute(
            'SELECT * FROM api_models WHERE provider_id = ? ORDER BY display_name',
            (provider_id,)
        ).fetchall()
        return jsonify([dict(m) for m in models])           # 返回 JSON 数组
    finally:
        conn.close()                                        # 确保关闭连接


@app.route('/api/providers/<int:provider_id>/models', methods=['POST'])
def create_model(provider_id):
    """为指定提供商创建新模型"""
    data = request.json                                     # 获取请求 JSON 数据
    if not data:                                            # 如果没有请求体
        return jsonify({'error': '请求数据不能为空'}), 400   # 返回 400 错误

    conn = get_db()                                         # 获取数据库连接
    try:
        cursor = conn.cursor()                              # 创建游标
        cursor.execute('''
            INSERT INTO api_models (provider_id, model_id, display_name, description,
                max_tokens, supports_streaming, supports_vision, supports_function_calling,
                price_input, price_output)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            provider_id,                                    # 所属提供商 ID
            data['model_id'],                               # 模型标识（必填）
            data['display_name'],                           # 显示名称（必填）
            data.get('description'),                        # 描述（可选）
            data.get('max_tokens'),                         # 最大 Token 数（可选）
            data.get('supports_streaming', 1),              # 流式输出支持，默认启用
            data.get('supports_vision', 0),                 # 多模态支持，默认关闭
            data.get('supports_function_calling', 0),       # 函数调用支持，默认关闭
            data.get('price_input'),                        # 输入价格（可选）
            data.get('price_output')                        # 输出价格（可选）
        ))
        conn.commit()                                       # 提交事务
        return jsonify({'id': cursor.lastrowid, 'message': 'Created successfully'}), 201
    finally:
        conn.close()                                        # 确保关闭连接


@app.route('/api/models/<int:model_id>', methods=['PUT'])
def update_model(model_id):
    """更新模型信息"""
    data = request.json                                     # 获取请求 JSON 数据
    if not data:                                            # 如果没有请求体
        return jsonify({'error': '请求数据不能为空'}), 400   # 返回 400 错误

    conn = get_db()                                         # 获取数据库连接
    try:
        cursor = conn.cursor()                              # 创建游标
        cursor.execute('''
            UPDATE api_models
            SET model_id=?, display_name=?, description=?, max_tokens=?,
                supports_streaming=?, supports_vision=?, supports_function_calling=?,
                price_input=?, price_output=?
            WHERE id=?
        ''', (
            data['model_id'],                               # 模型标识
            data['display_name'],                           # 显示名称
            data.get('description'),                        # 描述
            data.get('max_tokens'),                         # 最大 Token 数
            data.get('supports_streaming'),                 # 流式输出支持
            data.get('supports_vision'),                    # 多模态支持
            data.get('supports_function_calling'),          # 函数调用支持
            data.get('price_input'),                        # 输入价格
            data.get('price_output'),                       # 输出价格
            model_id                                        # 要更新的模型 ID
        ))
        conn.commit()                                       # 提交事务

        if cursor.rowcount == 0:                            # 如果没有更新到任何行
            return jsonify({'error': 'Model not found'}), 404  # 模型不存在

        return jsonify({'message': 'Updated successfully'})  # 返回成功
    finally:
        conn.close()                                        # 确保关闭连接


@app.route('/api/models/<int:model_id>', methods=['DELETE'])
def delete_model(model_id):
    """删除指定模型"""
    conn = get_db()                                         # 获取数据库连接
    try:
        conn.execute('DELETE FROM api_models WHERE id = ?', (model_id,))  # 执行删除
        conn.commit()                                       # 提交事务
        return jsonify({'message': 'Deleted successfully'})  # 返回成功
    finally:
        conn.close()                                        # 确保关闭连接


# ---------- 密钥相关路由 ----------

@app.route('/api/keys', methods=['GET'])
def get_all_keys():
    """获取所有密钥列表（带提供商名称），用于全局密钥页面"""
    conn = get_db()                                         # 获取数据库连接
    try:
        # 联表查询，获取密钥信息及其提供商名称
        keys = conn.execute('''
            SELECT k.*, p.display_name as provider_name
            FROM api_keys k
            LEFT JOIN api_providers p ON k.provider_id = p.id
            ORDER BY p.display_name, k.key_name
        ''').fetchall()
        return jsonify([dict(k) for k in keys])             # 返回 JSON 数组
    finally:
        conn.close()                                        # 确保关闭连接


@app.route('/api/providers/<int:provider_id>/keys', methods=['GET'])
def get_keys(provider_id):
    """获取指定提供商下的所有密钥"""
    conn = get_db()                                         # 获取数据库连接
    try:
        keys = conn.execute(
            'SELECT * FROM api_keys WHERE provider_id = ?',
            (provider_id,)
        ).fetchall()
        return jsonify([dict(k) for k in keys])             # 返回 JSON 数组
    finally:
        conn.close()                                        # 确保关闭连接


@app.route('/api/providers/<int:provider_id>/keys', methods=['POST'])
def create_key(provider_id):
    """为指定提供商创建新密钥"""
    data = request.json                                     # 获取请求 JSON 数据
    if not data:                                            # 如果没有请求体
        return jsonify({'error': '请求数据不能为空'}), 400   # 返回 400 错误

    conn = get_db()                                         # 获取数据库连接
    try:
        cursor = conn.cursor()                              # 创建游标
        cursor.execute('''
            INSERT INTO api_keys (provider_id, key_name, api_key, notes)
            VALUES (?, ?, ?, ?)
        ''', (
            provider_id,                                    # 所属提供商 ID
            data['key_name'],                               # 密钥名称（必填）
            data.get('api_key'),                            # API 密钥值（可选）
            data.get('notes')                               # 备注（可选）
        ))
        conn.commit()                                       # 提交事务
        return jsonify({'id': cursor.lastrowid, 'message': 'Created successfully'}), 201
    finally:
        conn.close()                                        # 确保关闭连接


@app.route('/api/keys/<int:key_id>', methods=['PUT'])
def update_key(key_id):
    """更新密钥信息"""
    data = request.json                                     # 获取请求 JSON 数据
    if not data:                                            # 如果没有请求体
        return jsonify({'error': '请求数据不能为空'}), 400   # 返回 400 错误

    conn = get_db()                                         # 获取数据库连接
    try:
        cursor = conn.cursor()                              # 创建游标
        cursor.execute('''
            UPDATE api_keys SET key_name=?, api_key=?, notes=? WHERE id=?
        ''', (
            data['key_name'],                               # 密钥名称
            data.get('api_key'),                            # API 密钥值
            data.get('notes'),                              # 备注
            key_id                                          # 要更新的密钥 ID
        ))
        conn.commit()                                       # 提交事务

        if cursor.rowcount == 0:                            # 如果没有更新到任何行
            return jsonify({'error': 'Key not found'}), 404  # 密钥不存在

        return jsonify({'message': 'Updated successfully'})  # 返回成功
    finally:
        conn.close()                                        # 确保关闭连接


@app.route('/api/keys/<int:key_id>', methods=['DELETE'])
def delete_key(key_id):
    """删除指定密钥"""
    conn = get_db()                                         # 获取数据库连接
    try:
        conn.execute('DELETE FROM api_keys WHERE id = ?', (key_id,))  # 执行删除
        conn.commit()                                       # 提交事务
        return jsonify({'message': 'Deleted successfully'})  # 返回成功
    finally:
        conn.close()                                        # 确保关闭连接


# ---------- 统计路由 ----------

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取仪表盘统计数据"""
    conn = get_db()                                         # 获取数据库连接
    try:
        # 查询各项计数
        providers_count = conn.execute('SELECT COUNT(*) FROM api_providers').fetchone()[0]  # 提供商总数
        models_count = conn.execute('SELECT COUNT(*) FROM api_models').fetchone()[0]        # 模型总数
        keys_count = conn.execute('SELECT COUNT(*) FROM api_keys').fetchone()[0]            # 密钥总数
        # 按类别统计提供商数量
        categories = conn.execute(
            'SELECT category, COUNT(*) as count FROM api_providers GROUP BY category'
        ).fetchall()

        return jsonify({
            'providers_count': providers_count,             # 提供商数量
            'models_count': models_count,                   # 模型数量
            'keys_count': keys_count,                       # 密钥数量
            'categories': [dict(c) for c in categories]     # 类别分布
        })
    finally:
        conn.close()                                        # 确保关闭连接


# ====================== 设置路由 ======================

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """获取所有设置项"""
    conn = get_db()                                         # 获取数据库连接
    try:
        rows = conn.execute('SELECT key, value FROM app_settings').fetchall()  # 查询所有设置
        return jsonify({row['key']: row['value'] for row in rows})  # 返回 key-value 字典
    finally:
        conn.close()                                        # 确保关闭连接


@app.route('/api/settings', methods=['PUT'])
def update_settings():
    """批量更新设置项"""
    data = request.json                                     # 获取请求 JSON 数据
    if not data:                                            # 如果没有请求体
        return jsonify({'error': '请求数据不能为空'}), 400   # 返回 400 错误

    conn = get_db()                                         # 获取数据库连接
    try:
        cursor = conn.cursor()                              # 创建游标
        for key, value in data.items():                     # 遍历所有设置项
            cursor.execute('''
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=?, updated_at=CURRENT_TIMESTAMP
            ''', (key, value, value))                       # 使用 upsert 语法
        conn.commit()                                       # 提交事务
        return jsonify({'message': 'Settings updated successfully'})
    finally:
        conn.close()                                        # 确保关闭连接


# ====================== AI 解析路由 ======================

# AI 解析的系统提示词，要求返回标准 JSON 格式
AI_PARSE_PROMPT = """你是一个 API 信息提取助手。用户会给你一段关于 AI 大模型 API 的文档或描述，你需要从中提取结构化的提供商和模型信息。

请严格按以下 JSON 格式返回，不要包含任何其他文字：
{
  "providers": [
    {
      "name": "英文标识名，如 openai",
      "display_name": "显示名称，如 OpenAI",
      "base_url": "API 基础 URL",
      "description": "简短描述",
      "category": "international 或 domestic 或 other",
      "models": [
        {
          "model_id": "模型标识，如 gpt-4o",
          "display_name": "显示名称，如 GPT-4o",
          "description": "模型描述",
          "max_tokens": 最大token数(整数或null),
          "supports_vision": true或false,
          "supports_function_calling": true或false,
          "price_input": 输入价格每1K tokens(数字或null),
          "price_output": 输出价格每1K tokens(数字或null)
        }
      ]
    }
  ]
}

规则：
- 如果文档中没有提到某个字段，设为 null
- category 根据厂商判断：国内厂商用 domestic，国外用 international，不确定用 other
- 价格如果是 "每百万tokens" 格式，转换为 "每1K tokens"（除以1000）
- 如果文档中没有模型信息，models 可以为空数组
- 只返回 JSON，不要有其他任何内容"""


@app.route('/api/ai/parse', methods=['POST'])
def ai_parse():
    """调用 AI 解析文档内容，提取 API 信息"""
    data = request.json                                     # 获取请求 JSON 数据
    if not data or not data.get('content'):                 # 如果没有文档内容
        return jsonify({'error': '请输入要解析的文档内容'}), 400

    conn = get_db()                                         # 获取数据库连接
    try:
        # 读取 AI 配置
        settings = {}
        rows = conn.execute('SELECT key, value FROM app_settings').fetchall()
        for row in rows:
            settings[row['key']] = row['value']

        ai_base_url = settings.get('ai_base_url', '').rstrip('/')  # AI API 基础 URL
        ai_api_key = settings.get('ai_api_key', '')                # AI API 密钥
        ai_model = settings.get('ai_model', '')                    # AI 模型名

        if not ai_base_url or not ai_api_key or not ai_model:      # 如果配置不完整
            return jsonify({'error': '请先在「AI设置」中配置 AI 服务的 Base URL、API Key 和模型名'}), 400
    finally:
        conn.close()                                        # 确保关闭连接

    # 构建 OpenAI 格式的请求体
    request_body = json.dumps({
        'model': ai_model,
        'messages': [
            {'role': 'system', 'content': AI_PARSE_PROMPT},  # 系统提示词
            {'role': 'user', 'content': data['content']}      # 用户文档内容
        ],
        'temperature': 0.1,                                  # 低温度，确保输出稳定
        'max_tokens': 4000                                   # 最大输出 token 数
    }).encode('utf-8')

    # 构建 HTTP 请求
    url = f"{ai_base_url}/chat/completions"                  # OpenAI 格式的聊天补全端点
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {ai_api_key}'              # Bearer token 认证
    }

    try:
        req = urllib.request.Request(url, data=request_body, headers=headers)  # 创建请求对象
        with urllib.request.urlopen(req, timeout=60) as resp:                  # 发送请求（60秒超时）
            response_data = json.loads(resp.read().decode('utf-8'))            # 解析响应

        # 提取 AI 返回的内容
        ai_content = response_data['choices'][0]['message']['content']  # 获取 AI 回复文本

        # 尝试解析 JSON（AI 可能会在 JSON 前后加 markdown 代码块标记）
        ai_content = ai_content.strip()                      # 去除首尾空白
        if ai_content.startswith('```'):                     # 如果以代码块开头
            # 去除 ```json 和 ``` 标记
            lines = ai_content.split('\n')                   # 按行分割
            ai_content = '\n'.join(lines[1:-1])              # 去掉首尾行
            ai_content = ai_content.strip()                  # 再次去空白

        parsed = json.loads(ai_content)                      # 解析 JSON
        return jsonify(parsed)                               # 返回解析结果

    except urllib.error.HTTPError as e:                      # HTTP 错误
        error_body = e.read().decode('utf-8', errors='ignore')  # 读取错误响应体
        return jsonify({'error': f'AI 服务返回错误 ({e.code}): {error_body[:200]}'}), 502
    except urllib.error.URLError as e:                       # 网络错误
        return jsonify({'error': f'无法连接到 AI 服务: {str(e.reason)}'}), 502
    except json.JSONDecodeError:                             # JSON 解析失败
        return jsonify({'error': f'AI 返回的内容不是有效 JSON: {ai_content[:200]}'}), 502
    except Exception as e:                                   # 其他错误
        return jsonify({'error': f'AI 解析失败: {str(e)}'}), 500


@app.route('/api/ai/import', methods=['POST'])
def ai_import():
    """导入 AI 解析结果，批量创建提供商和模型"""
    data = request.json                                     # 获取请求 JSON 数据
    if not data or not data.get('providers'):               # 如果没有提供商数据
        return jsonify({'error': '没有可导入的数据'}), 400

    conn = get_db()                                         # 获取数据库连接
    try:
        cursor = conn.cursor()                              # 创建游标
        imported_providers = 0                               # 导入的提供商计数
        imported_models = 0                                  # 导入的模型计数

        for provider_data in data['providers']:              # 遍历每个提供商
            # 插入提供商（如果同名已存在则跳过）
            cursor.execute('''
                INSERT INTO api_providers (name, display_name, base_url, description, category)
                SELECT ?, ?, ?, ?, ?
                WHERE NOT EXISTS (SELECT 1 FROM api_providers WHERE name = ?)
            ''', (
                provider_data.get('name', ''),               # 英文标识名
                provider_data.get('display_name', ''),       # 显示名称
                provider_data.get('base_url'),               # Base URL
                provider_data.get('description'),            # 描述
                provider_data.get('category', 'other'),      # 类别
                provider_data.get('name', '')                # 用于去重的名称
            ))

            if cursor.rowcount > 0:                          # 如果成功插入了新提供商
                imported_providers += 1                      # 计数加一
                provider_id = cursor.lastrowid               # 获取新提供商的 ID

                # 插入该提供商下的所有模型
                for model_data in provider_data.get('models', []):  # 遍历模型
                    cursor.execute('''
                        INSERT INTO api_models (provider_id, model_id, display_name, description,
                            max_tokens, supports_vision, supports_function_calling,
                            price_input, price_output)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        provider_id,                         # 所属提供商 ID
                        model_data.get('model_id', ''),      # 模型标识
                        model_data.get('display_name', ''),  # 显示名称
                        model_data.get('description'),       # 描述
                        model_data.get('max_tokens'),        # 最大 Token 数
                        1 if model_data.get('supports_vision') else 0,                # 多模态支持
                        1 if model_data.get('supports_function_calling') else 0,      # 函数调用支持
                        model_data.get('price_input'),       # 输入价格
                        model_data.get('price_output')       # 输出价格
                    ))
                    imported_models += 1                     # 模型计数加一

        conn.commit()                                       # 提交事务
        return jsonify({
            'message': f'导入完成：{imported_providers} 个提供商，{imported_models} 个模型',
            'providers': imported_providers,
            'models': imported_models
        })
    except Exception as e:                                   # 如果发生任何错误
        conn.rollback()                                     # 回滚事务
        return jsonify({'error': f'导入失败: {str(e)}'}), 500
    finally:
        conn.close()                                        # 确保关闭连接


# 程序入口：直接运行 app.py 时启动开发服务器
if __name__ == '__main__':
    init_db()                                               # 初始化数据库表结构
    app.run(debug=True, port=5000)                          # 启动 Flask 开发服务器
