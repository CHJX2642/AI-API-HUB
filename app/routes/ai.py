# -*- coding: utf-8 -*-
# AI API Hub — AI 解析 + 导入路由模块
# 提供 AI 智能解析文档/URL/图片，以及批量导入解析结果的功能

import os                              # 操作系统接口，用于文件扩展名处理
import json                            # JSON 处理
import base64                          # Base64 编码，用于图片多模态 API
import urllib.error                    # HTTP 错误处理
from flask import Blueprint, request, jsonify, current_app  # Flask 核心模块
from app.database import get_db, parse_provider_row          # 数据库工具函数
from app.services.ai_service import call_ai_service, AI_PARSE_PROMPT  # AI 调用服务
from app.services.file_parser import extract_text_from_docx, extract_text_from_pdf, extract_text_from_excel  # 文件解析
from app.services.web_scraper import fetch_url_content       # 网页抓取
from app.services.provider_aliases import normalize_provider_name  # 提供商名称归一化

bp = Blueprint('ai', __name__)         # 创建 AI 蓝图


@bp.route('/api/ai/parse', methods=['POST'])
def ai_parse():
    """调用 AI 解析文档内容，支持文本、文件上传、URL 三种模式"""
    try:
        # 判断请求类型：multipart（文件/URL）还是 JSON（文本）
        is_multipart = request.content_type and 'multipart/form-data' in request.content_type

        if is_multipart:
            mode = request.form.get('mode', 'text')   # 从表单获取模式
        else:
            data = request.json
            if not data:
                return jsonify({'error': '请求数据为空'}), 400
            mode = 'text'                              # JSON 请求默认为文本模式

        # ====== 文本模式 ======
        if mode == 'text':
            if is_multipart:
                content = request.form.get('content', '').strip()
            else:
                content = data.get('content', '')
            if not content:
                return jsonify({'error': '请输入要解析的文档内容'}), 400
            # 构建消息：系统提示词 + 用户内容
            messages = [
                {'role': 'system', 'content': AI_PARSE_PROMPT},
                {'role': 'user', 'content': content}
            ]
            result = call_ai_service(messages)         # 调用 AI 服务
            if isinstance(result, tuple):              # 错误时返回元组
                return result
            return jsonify(result)                     # 成功时返回 JSON

        # ====== URL 模式 ======
        elif mode == 'url':
            url = request.form.get('url', '').strip()
            if not url:
                return jsonify({'error': '请输入网页 URL'}), 400
            if not url.startswith(('http://', 'https://')):
                return jsonify({'error': 'URL 必须以 http:// 或 https:// 开头'}), 400

            # 先尝试本地抓取网页内容
            try:
                content = fetch_url_content(url)
            except ValueError as e:
                return jsonify({'error': str(e)}), 400

            if content:
                # 本地抓取成功，将内容发给 AI 解析
                messages = [
                    {'role': 'system', 'content': AI_PARSE_PROMPT},
                    {'role': 'user', 'content': f'以下是从网页 {url} 抓取的内容：\n\n{content}'}
                ]
            else:
                # 本地抓取失败（Cloudflare/JS渲染等），直接把 URL 发给 AI
                messages = [
                    {'role': 'system', 'content': AI_PARSE_PROMPT},
                    {'role': 'user', 'content': f'请访问这个网页并提取其中的 API 提供商和模型信息：\n{url}'}
                ]

            result = call_ai_service(messages)
            if isinstance(result, tuple):
                return result
            return jsonify(result)

        # ====== 文件上传模式 ======
        elif mode == 'file':
            file = request.files.get('file')
            if not file or not file.filename:
                return jsonify({'error': '请选择要上传的文件'}), 400

            # 从 Flask 配置读取允许的文件格式
            allowed = current_app.config.get('ALLOWED_EXTENSIONS', set())
            image_exts = current_app.config.get('IMAGE_EXTENSIONS', set())

            ext = os.path.splitext(file.filename)[1].lower()  # 获取文件扩展名
            if ext not in allowed:
                return jsonify({'error': f'不支持的文件格式 {ext}，支持: {", ".join(sorted(allowed))}'}), 400

            # .doc 和 .xls 旧格式提示转换
            if ext == '.doc':
                return jsonify({'error': '不支持 .doc 格式，请转换为 .docx 后重试'}), 400
            if ext == '.xls':
                return jsonify({'error': '不支持 .xls 格式，请转换为 .xlsx 后重试'}), 400

            file_bytes = file.read()                   # 读取文件内容
            if not file_bytes:
                return jsonify({'error': '文件为空'}), 400

            # 图片：发送 base64 到多模态 API
            if ext in image_exts:
                # 扩展名到 MIME 类型的映射
                mime_map = {'.jpg': 'jpeg', '.jpeg': 'jpeg', '.png': 'png', '.gif': 'gif', '.webp': 'webp'}
                mime = mime_map.get(ext, 'jpeg')
                b64 = base64.b64encode(file_bytes).decode('utf-8')  # 编码为 base64
                # 构建多模态消息（文本 + 图片）
                messages = [
                    {'role': 'system', 'content': AI_PARSE_PROMPT},
                    {'role': 'user', 'content': [
                        {'type': 'text', 'text': '请从这张图片中提取 API 提供商和模型信息。'},
                        {'type': 'image_url', 'image_url': {'url': f'data:image/{mime};base64,{b64}'}}
                    ]}
                ]
                result = call_ai_service(messages)
                if isinstance(result, tuple):
                    return result
                return jsonify(result)

            # 文档：本地提取文本后发送给 AI
            try:
                if ext == '.docx':
                    content = extract_text_from_docx(file_bytes)
                elif ext == '.pdf':
                    content = extract_text_from_pdf(file_bytes)
                elif ext == '.xlsx':
                    content = extract_text_from_excel(file_bytes)
                else:
                    return jsonify({'error': f'暂不支持 {ext} 格式'}), 400
            except Exception as e:
                return jsonify({'error': f'文件解析失败: {str(e)}'}), 400

            # 检查提取的内容是否有效
            if not content or len(content.strip()) < 5:
                return jsonify({'error': '文件内容为空或无法提取文字（可能是扫描件或图片型 PDF）'}), 400

            # 将提取的文本发给 AI 解析
            messages = [
                {'role': 'system', 'content': AI_PARSE_PROMPT},
                {'role': 'user', 'content': f'以下是从文件 {file.filename} 中提取的内容：\n\n{content}'}
            ]
            result = call_ai_service(messages)
            if isinstance(result, tuple):
                return result
            return jsonify(result)

        else:
            return jsonify({'error': f'未知的解析模式: {mode}'}), 400

    # ====== 统一错误处理 ======
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='ignore')
        return jsonify({'error': f'AI 服务返回错误 ({e.code}): {error_body[:200]}'}), 502
    except urllib.error.URLError as e:
        return jsonify({'error': f'无法连接到 AI 服务: {str(e.reason)}'}), 502
    except json.JSONDecodeError:
        return jsonify({'error': 'AI 返回的内容不是有效 JSON'}), 502
    except Exception as e:
        return jsonify({'error': f'AI 解析失败: {str(e)}'}), 500


@bp.route('/api/ai/import', methods=['POST'])
def ai_import():
    """导入 AI 解析结果，批量创建/更新提供商和模型"""
    data = request.json
    if not data or not data.get('providers'):
        return jsonify({'error': '没有可导入的数据'}), 400

    conn = get_db()
    try:
        cursor = conn.cursor()
        imported_providers = 0         # 新建的提供商计数
        imported_models = 0            # 新建的模型计数
        updated_providers = 0          # 更新的提供商计数
        updated_models = 0             # 更新的模型计数
        overwrite = data.get('overwrite', False)  # 是否替换已有数据

        for provider_data in data['providers']:   # 遍历每个提供商
            raw_name = provider_data.get('name', '')
            display_name = provider_data.get('display_name') or ''
            if not display_name:
                provider_data['display_name'] = raw_name  # display_name 兜底为 name

            # 归一化名称（如 mimo→xiaomi, 豆包→volcengine）
            name = normalize_provider_name(raw_name, display_name)
            provider_data['name'] = name

            # 查找是否已存在同名提供商
            cursor.execute('SELECT id, name FROM api_providers WHERE name = ?', (name,))
            existing = cursor.fetchone()

            # 精确没找到，用别名表反查数据库中已有的别名
            if not existing:
                cursor.execute('SELECT id, name FROM api_providers')
                for row in cursor.fetchall():
                    db_canonical = normalize_provider_name(row['name'], '')
                    if db_canonical == name:
                        existing = row
                        break

            # 处理 api_urls：AI 返回的是 list，转为 JSON 字符串存储
            api_urls_raw = provider_data.get('api_urls')
            if isinstance(api_urls_raw, list):
                api_urls_json = json.dumps(api_urls_raw, ensure_ascii=False)
            elif isinstance(api_urls_raw, str):
                api_urls_json = api_urls_raw
            else:
                api_urls_json = None

            if existing:
                # ====== 提供商已存在：更新 ======
                provider_id = existing['id']
                if overwrite:
                    # 替换模式：覆盖所有字段
                    cursor.execute('''
                        UPDATE api_providers SET
                            display_name=?, base_url=?, api_urls=?,
                            description=?, category=?, updated_at=CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (
                        provider_data.get('display_name', ''),
                        provider_data.get('base_url'),
                        api_urls_json,
                        provider_data.get('description'),
                        provider_data.get('category', 'other'),
                        provider_id
                    ))
                else:
                    # 补充模式：仅填充缺失字段（COALESCE 保留已有值）
                    cursor.execute('''
                        UPDATE api_providers SET
                            display_name   = COALESCE(NULLIF(display_name, ''), ?),
                            base_url       = COALESCE(NULLIF(base_url, ''), ?),
                            api_urls       = CASE WHEN api_urls IS NULL OR api_urls = '[]' OR api_urls = '' THEN ? ELSE api_urls END,
                            description    = COALESCE(NULLIF(description, ''), ?),
                            category       = CASE WHEN category = 'other' THEN ? ELSE category END,
                            updated_at     = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (
                        provider_data.get('display_name', ''),
                        provider_data.get('base_url'),
                        api_urls_json,
                        provider_data.get('description'),
                        provider_data.get('category', 'other'),
                        provider_id
                    ))
                updated_providers += 1
            else:
                # ====== 提供商不存在：新建 ======
                cursor.execute('''
                    INSERT INTO api_providers (name, display_name, base_url, api_urls, description, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    name,
                    provider_data.get('display_name', ''),
                    provider_data.get('base_url'),
                    api_urls_json,
                    provider_data.get('description'),
                    provider_data.get('category', 'other')
                ))
                imported_providers += 1
                provider_id = cursor.lastrowid

            # ====== 处理该提供商下的所有模型 ======
            for model_data in provider_data.get('models', []):
                model_id = model_data.get('model_id', '')
                if not model_id:
                    continue                       # 跳过没有 model_id 的模型
                if not model_data.get('display_name'):
                    model_data['display_name'] = model_id  # display_name 兜底

                # 查找是否已存在同名模型
                cursor.execute(
                    'SELECT id FROM api_models WHERE provider_id = ? AND model_id = ?',
                    (provider_id, model_id)
                )
                existing_model = cursor.fetchone()

                if existing_model:
                    if overwrite:
                        # 替换模式：覆盖所有字段
                        cursor.execute('''
                            UPDATE api_models SET
                                display_name=?, description=?, max_tokens=?,
                                supports_vision=?, supports_function_calling=?,
                                price_input=?, price_input_cached=?, price_output=?,
                                pricing_type=?, price_per_request=?
                            WHERE id = ?
                        ''', (
                            model_data.get('display_name', ''),
                            model_data.get('description'),
                            model_data.get('max_tokens'),
                            1 if model_data.get('supports_vision') else 0,
                            1 if model_data.get('supports_function_calling') else 0,
                            model_data.get('price_input'),
                            model_data.get('price_input_cached'),
                            model_data.get('price_output'),
                            model_data.get('pricing_type', 'per_token'),
                            model_data.get('price_per_request'),
                            existing_model['id']
                        ))
                    else:
                        # 补充模式：仅填充缺失字段
                        cursor.execute('''
                            UPDATE api_models SET
                                display_name            = COALESCE(NULLIF(display_name, ''), ?),
                                description             = COALESCE(NULLIF(description, ''), ?),
                                max_tokens              = COALESCE(max_tokens, ?),
                                supports_vision         = CASE WHEN ? = 1 THEN 1 ELSE supports_vision END,
                                supports_function_calling = CASE WHEN ? = 1 THEN 1 ELSE supports_function_calling END,
                                price_input             = COALESCE(price_input, ?),
                                price_input_cached      = COALESCE(price_input_cached, ?),
                                price_output            = COALESCE(price_output, ?),
                                pricing_type            = COALESCE(NULLIF(pricing_type, ''), ?),
                                price_per_request       = COALESCE(price_per_request, ?)
                            WHERE id = ?
                        ''', (
                            model_data.get('display_name', ''),
                            model_data.get('description'),
                            model_data.get('max_tokens'),
                            1 if model_data.get('supports_vision') else 0,
                            1 if model_data.get('supports_function_calling') else 0,
                            model_data.get('price_input'),
                            model_data.get('price_input_cached'),
                            model_data.get('price_output'),
                            model_data.get('pricing_type', 'per_token'),
                            model_data.get('price_per_request'),
                            existing_model['id']
                        ))
                    updated_models += 1
                else:
                    # 模型不存在：插入新模型
                    cursor.execute('''
                        INSERT INTO api_models (provider_id, model_id, display_name, description,
                            max_tokens, supports_vision, supports_function_calling,
                            price_input, price_input_cached, price_output,
                            pricing_type, price_per_request)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        provider_id, model_id,
                        model_data.get('display_name', ''),
                        model_data.get('description'),
                        model_data.get('max_tokens'),
                        1 if model_data.get('supports_vision') else 0,
                        1 if model_data.get('supports_function_calling') else 0,
                        model_data.get('price_input'),
                        model_data.get('price_input_cached'),
                        model_data.get('price_output'),
                        model_data.get('pricing_type', 'per_token'),
                        model_data.get('price_per_request')
                    ))
                    imported_models += 1

        conn.commit()                              # 提交整个事务
        return jsonify({
            'message': f'完成：新建 {imported_providers} 个提供商，{imported_models} 个模型；补充 {updated_providers} 个提供商，{updated_models} 个模型',
            'providers': imported_providers,
            'models': imported_models,
            'updated_providers': updated_providers,
            'updated_models': updated_models
        })
    except Exception as e:
        conn.rollback()                            # 出错时回滚事务
        return jsonify({'error': f'导入失败: {str(e)}'}), 500
    finally:
        conn.close()                               # 确保关闭连接
