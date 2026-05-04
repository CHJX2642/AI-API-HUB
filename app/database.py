# -*- coding: utf-8 -*-
# AI API Hub — 数据库模块
# 提供数据库连接、表结构初始化、数据迁移、行解析等功能

import os                              # 操作系统接口，用于路径处理
import sys                             # 系统接口，用于判断打包环境
import json                            # JSON 处理，用于 api_urls 字段解析
import sqlite3                         # SQLite 数据库驱动
from flask import current_app          # 当前 Flask 应用上下文，用于读取配置


def get_data_dir():
    """获取数据目录：打包环境下返回 exe 所在目录，否则返回项目根目录"""
    if getattr(sys, 'frozen', False):                       # PyInstaller 打包后 sys.frozen 为 True
        return os.path.dirname(sys.executable)              # 返回 exe 文件所在目录
    # 否则返回 app/ 的上级目录（即项目根目录）
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_db():
    """获取数据库连接，设置 row_factory 以便以字典方式访问行数据"""
    # 从 Flask 配置中读取数据库文件名
    db_name = current_app.config.get('DB_NAME', 'ai_api_hub.db')
    # 拼接完整的数据库文件路径
    db_path = os.path.join(get_data_dir(), db_name)
    conn = sqlite3.connect(db_path)     # 建立 SQLite 连接
    conn.row_factory = sqlite3.Row      # 设置行工厂为 Row，支持 dict() 转换
    return conn                         # 返回连接对象


def parse_provider_row(p):
    """将 provider Row 对象转为 dict，并解析 api_urls JSON 字段
    参数:
        p: sqlite3.Row 对象
    返回:
        dict，其中 api_urls 已从 JSON 字符串解析为 Python 列表
    """
    d = dict(p)                         # 将 Row 转为普通字典
    if d.get('api_urls'):               # 如果 api_urls 字段有值
        try:
            d['api_urls'] = json.loads(d['api_urls'])   # 解析 JSON 字符串为列表
        except (json.JSONDecodeError, TypeError):
            d['api_urls'] = []          # 解析失败则设为空列表
    else:
        d['api_urls'] = []              # 无值时设为空列表
    return d                            # 返回解析后的字典


def init_db():
    """初始化数据库表结构（如已存在则跳过），并执行数据迁移"""
    # 从配置获取数据库路径
    db_name = current_app.config.get('DB_NAME', 'ai_api_hub.db')
    db_path = os.path.join(get_data_dir(), db_name)
    conn = sqlite3.connect(db_path)     # 建立连接
    conn.row_factory = sqlite3.Row      # 支持字典方式访问
    cursor = conn.cursor()              # 创建游标

    # ====== 创建 API 提供商表 ======
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
            name TEXT NOT NULL,                     -- 英文标识名，如 'openai'
            display_name TEXT NOT NULL,             -- 显示名称，如 'OpenAI'
            base_url TEXT,                          -- API 基础 URL（旧字段，保留兼容）
            openai_url TEXT,                        -- OpenAI 格式完整 URL（旧字段）
            anthropic_url TEXT,                     -- Anthropic 格式完整 URL（旧字段）
            api_urls TEXT,                          -- 自定义 URL 列表（JSON 格式）
            description TEXT,                       -- 提供商描述
            category TEXT DEFAULT 'other',          -- 分类：international/domestic/other
            is_active INTEGER DEFAULT 1,            -- 是否启用（1=启用）
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP   -- 更新时间
        )
    ''')

    # ====== 创建 API 模型表 ======
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
            price_input REAL,                       -- 输入价格（¥/1M tokens）
            price_input_cached REAL,                -- 缓存命中输入价格（¥/1M tokens）
            price_output REAL,                      -- 输出价格（¥/1M tokens）
            is_active INTEGER DEFAULT 1,            -- 是否启用
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
            FOREIGN KEY (provider_id) REFERENCES api_providers(id)  -- 外键约束
        )
    ''')

    # ====== 创建 API 密钥表 ======
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

    # ====== 创建全局设置表（key-value 形式） ======
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,                       -- 设置项名称（主键）
            value TEXT,                                 -- 设置值
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 更新时间
        )
    ''')

    # ====== 数据库迁移：为已有表添加新字段（已存在则忽略） ======
    migrations = [
        'ALTER TABLE api_models ADD COLUMN price_input_cached REAL',      # 缓存价格字段
        'ALTER TABLE api_providers ADD COLUMN openai_url TEXT',            # OpenAI URL 字段
        'ALTER TABLE api_providers ADD COLUMN anthropic_url TEXT',         # Anthropic URL 字段
        'ALTER TABLE api_providers ADD COLUMN api_urls TEXT',              # 自定义 URL 列表字段
        'ALTER TABLE api_models ADD COLUMN pricing_type TEXT DEFAULT "per_token"',  # 计费方式
        'ALTER TABLE api_models ADD COLUMN price_per_request REAL',        # 按次收费价格（元/次）
    ]
    for sql in migrations:              # 遍历所有迁移语句
        try:
            cursor.execute(sql)         # 执行迁移
        except sqlite3.OperationalError:
            pass                        # 字段已存在则跳过

    # ====== 数据迁移：将旧的 openai_url/anthropic_url 转为 api_urls JSON ======
    rows = conn.execute(
        'SELECT id, openai_url, anthropic_url, api_urls FROM api_providers'
    ).fetchall()                        # 查询所有提供商的 URL 字段
    for row in rows:                    # 遍历每条记录
        if row['api_urls']:             # 如果已有 api_urls，跳过
            continue
        urls = []                       # 构建 URL 列表
        if row['openai_url']:           # 有 OpenAI URL
            urls.append({'label': 'OpenAI', 'url': row['openai_url'], 'format': 'openai'})
        if row['anthropic_url']:        # 有 Anthropic URL
            urls.append({'label': 'Anthropic', 'url': row['anthropic_url'], 'format': 'anthropic'})
        if urls:                        # 如果有数据，更新 api_urls 字段
            cursor.execute(
                'UPDATE api_providers SET api_urls = ? WHERE id = ?',
                (json.dumps(urls, ensure_ascii=False), row['id'])
            )

    conn.commit()                       # 提交所有变更
    conn.close()                        # 关闭连接
