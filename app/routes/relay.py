# -*- coding: utf-8 -*-
# AI API Hub — API 转接路由模块
# 提供三种协议的转接端点：OpenAI Chat / OpenAI Responses / Anthropic Messages

import json                            # JSON 序列化/反序列化
import uuid                            # 生成唯一 ID
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app  # Flask 核心
from app.services.relay_service import (  # 转接服务函数
    authenticate_relay, resolve_model, sanitize_data,
    handle_relay,
    chat_to_internal, anthropic_to_internal, responses_to_internal,
    internal_to_openai_request, internal_to_anthropic_request,
    openai_response_to_internal, anthropic_response_to_internal,
    internal_to_chat_response, internal_to_responses_response, internal_to_anthropic_response,
    format_chat_sse, format_responses_sse, format_anthropic_sse,
    validate_relay_request, get_adapter,
)
from app.database import get_db        # 数据库连接

bp = Blueprint('relay', __name__)      # 创建转接蓝图


def get_request_json():
    """获取请求中的 JSON body，统一错误处理"""
    try:
        data = request.get_json(force=True, silent=False)
        if data is None:
            return None, (jsonify({'error': '请求体不能为空'}), 400)
        return data, None
    except Exception:
        return None, (jsonify({'error': '请求体必须是有效的 JSON'}), 400)


def check_relay_enabled():
    """检查转接服务是否已启用，未启用返回错误"""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = 'relay_enabled'"
        ).fetchone()
        enabled = row['value'] if row else '0'
        if enabled != '1':
            return jsonify({'error': '转接服务未启用，请在「API 转接」页面开启'}), 503
        return None
    finally:
        conn.close()


def resolve_output_protocol(key_protocol=None):
    """解析输出协议覆写
    优先级：X-Output-Protocol 头 > Key 绑定协议 > 数据库设置 > None（跟随输入）
    参数:
        key_protocol: authenticate_relay 返回的 Key 绑定协议（可为 None）
    """
    # ① 请求头优先级最高（允许单次请求临时覆盖）
    header_val = request.headers.get('X-Output-Protocol', '').strip().lower()
    if header_val in ('chat', 'responses', 'anthropic'):
        return header_val

    # ② Key 绑定的协议（新三 Key 方案的核心）
    if key_protocol in ('chat', 'responses', 'anthropic'):
        return key_protocol

    # ③ 数据库全局设置（向下兼容，不推荐使用）
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = 'relay_output_protocol'"
        ).fetchone()
        if row and row['value']:
            val = row['value'].strip().lower()
            if val in ('chat', 'responses', 'anthropic'):
                return val
    finally:
        conn.close()

    # ④ 不覆写，跟随输入协议
    return None


# ====================== OpenAI Chat Completions ======================

@bp.route('/v1/chat/completions', methods=['POST'])
def relay_chat_completions():
    """OpenAI Chat Completions 转接端点
    客户端请求格式: {"model": "xxx", "messages": [...]}
    """
    # 转接开关
    disabled = check_relay_enabled()
    if disabled:
        return disabled

    # 认证
    ok, key_protocol = authenticate_relay(request.headers)
    if not ok:
        return jsonify({'error': key_protocol}), 401

    # 解析请求
    data, err = get_request_json()
    if err:
        return err

    sanitize_data(data)                    # 清洗 "[undefined]" 等无效值
    output_protocol = resolve_output_protocol(key_protocol)

    # 流式处理
    if data.get('stream'):
        return handle_chat_stream(data, output_protocol)

    # 非流式处理
    result, status = handle_relay(data, 'chat', output_protocol)
    return jsonify(result), status


# ====================== OpenAI Responses API ======================

@bp.route('/v1/responses', methods=['POST'])
def relay_responses():
    """OpenAI Responses API 转接端点
    客户端请求格式: {"model": "xxx", "input": "...", "instructions": "..."}
    """
    # 转接开关
    disabled = check_relay_enabled()
    if disabled:
        return disabled

    # 认证
    ok, key_protocol = authenticate_relay(request.headers)
    if not ok:
        return jsonify({'error': key_protocol}), 401

    # 解析请求
    data, err = get_request_json()
    if err:
        return err

    sanitize_data(data)                    # 清洗 "[undefined]" 等无效值
    output_protocol = resolve_output_protocol(key_protocol)

    # 流式处理
    if data.get('stream'):
        return handle_responses_stream(data, output_protocol)

    # 非流式处理
    result, status = handle_relay(data, 'responses', output_protocol)
    return jsonify(result), status


# ====================== Anthropic Messages ======================

@bp.route('/v1/messages', methods=['POST'])
def relay_messages():
    """Anthropic Messages 转接端点
    客户端请求格式: {"model": "xxx", "messages": [...], "max_tokens": 100}
    """
    # 转接开关
    disabled = check_relay_enabled()
    if disabled:
        return disabled

    # 认证（Anthropic 协议同时支持 x-api-key 和 Bearer）
    ok, key_protocol = authenticate_relay(request.headers)
    if not ok:
        return jsonify({'error': key_protocol}), 401

    # 解析请求
    data, err = get_request_json()
    if err:
        return err

    sanitize_data(data)                    # 清洗 "[undefined]" 等无效值
    output_protocol = resolve_output_protocol(key_protocol)

    # 流式处理
    if data.get('stream'):
        return handle_anthropic_stream(data, output_protocol)

    # 非流式处理
    result, status = handle_relay(data, 'anthropic', output_protocol)
    return jsonify(result), status


# ====================== 模型列表（OpenAI 格式） ======================

@bp.route('/v1/models', methods=['GET'])
def relay_models():
    """返回可用模型列表（OpenAI /v1/models 格式）
    列出所有已启用且有 API Key 的模型
    """
    # 转接开关
    disabled = check_relay_enabled()
    if disabled:
        return disabled

    # 认证
    ok, _ = authenticate_relay(request.headers)
    if not ok:
        return jsonify({'error': _}), 401

    conn = get_db()
    try:
        # 联表查询：所有有活跃 API Key 的模型
        models = conn.execute('''
            SELECT DISTINCT m.model_id, m.display_name, p.display_name as provider_name
            FROM api_models m
            JOIN api_providers p ON m.provider_id = p.id
            JOIN api_keys k ON k.provider_id = p.id
            WHERE m.is_active = 1 AND p.is_active = 1
                AND k.is_active = 1 AND k.api_key IS NOT NULL AND k.api_key != ''
            ORDER BY m.model_id
        ''').fetchall()

        data_list = []
        for m in models:
            data_list.append({
                'id': m['model_id'],
                'object': 'model',
                'owned_by': m['provider_name'],
            })

        return jsonify({
            'object': 'list',
            'data': data_list,
        })
    finally:
        conn.close()


# ====================== 流式处理 ======================

def handle_chat_stream(data, output_protocol=None):
    """处理 OpenAI Chat 流式请求"""
    if output_protocol is None:
        output_protocol = 'chat'
    internal = chat_to_internal(data)
    model_name = internal['model']
    provider_info, error = resolve_model(model_name)
    if error:
        return jsonify({'error': error}), 404

    valid, err_msg = validate_relay_request(internal, provider_info)
    if not valid:
        return jsonify({'error': err_msg}), 400

    adapter = get_adapter(provider_info['provider_name'])
    internal = adapter.prepare_request(internal, data, 'chat')

    def generate():
        yield from _stream_generator(internal, provider_info, output_protocol)

    return Response(
        stream_with_context(generate()),
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )


def handle_responses_stream(data, output_protocol=None):
    """处理 OpenAI Responses 流式请求"""
    if output_protocol is None:
        output_protocol = 'responses'
    internal = responses_to_internal(data)
    model_name = internal['model']
    provider_info, error = resolve_model(model_name)
    if error:
        return jsonify({'error': error}), 404

    valid, err_msg = validate_relay_request(internal, provider_info)
    if not valid:
        return jsonify({'error': err_msg}), 400

    adapter = get_adapter(provider_info['provider_name'])
    internal = adapter.prepare_request(internal, data, 'responses')

    def generate():
        yield from _stream_generator(internal, provider_info, output_protocol)

    return Response(
        stream_with_context(generate()),
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )


def handle_anthropic_stream(data, output_protocol=None):
    """处理 Anthropic 流式请求"""
    if output_protocol is None:
        output_protocol = 'anthropic'
    internal = anthropic_to_internal(data)
    model_name = internal['model']
    provider_info, error = resolve_model(model_name)
    if error:
        return jsonify({'error': error}), 404

    valid, err_msg = validate_relay_request(internal, provider_info)
    if not valid:
        return jsonify({'error': err_msg}), 400

    adapter = get_adapter(provider_info['provider_name'])
    internal = adapter.prepare_request(internal, data, 'anthropic')

    def generate():
        yield from _stream_generator(internal, provider_info, output_protocol)

    return Response(
        stream_with_context(generate()),
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )


def _stream_generator(internal, provider_info, output_protocol):
    """流式生成器：发送请求到厂商并逐行翻译 SSE
    output_protocol: 输出流式 SSE 的协议格式（chat/responses/anthropic）
    支持 DeepSeek/Mimo 等模型的 reasoning_content（思考过程）翻译"""
    import urllib.request
    import urllib.error

    internal['stream'] = True
    provider_format = provider_info['api_format']
    model_name = internal.get('model', '')
    adapter = get_adapter(provider_info['provider_name'])

    # 构建厂商请求
    if provider_format == 'openai':
        req_body, req_headers = internal_to_openai_request(
            internal, provider_info['api_key'], provider_info['model_id']
        )
    else:
        req_body, req_headers = internal_to_anthropic_request(
            internal, provider_info['api_key'], provider_info['model_id']
        )

    try:
        request_body = json.dumps(req_body, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(provider_info['api_url'], data=request_body, headers=req_headers)

        last_finish = None           # 结束标记
        reasoning_buf = []           # 累积 reasoning 文本（所有协议共享）

        # 协议特定状态初始化
        if output_protocol == 'responses':
            resp_id = 'resp_' + uuid.uuid4().hex[:24]
            msg_id = 'msg_' + uuid.uuid4().hex[:24]
            reasoning_item_id = None
            reasoning_started = False
            msg_init_sent = False    # output_item_added + content_part_added 是否已发送
            yield format_responses_sse('created', resp_id=resp_id, model=model_name)
            text_buf = []
        elif output_protocol == 'chat':
            chat_role_sent = False
        elif output_protocol == 'anthropic':
            text_block_started = False
            thinking_block_started = False
            yield format_anthropic_sse('message_start', model=model_name)

        with urllib.request.urlopen(req, timeout=current_app.config.get('RELAY_TIMEOUT', 120)) as resp:
            for line_bytes in resp:
                line = line_bytes.decode('utf-8').rstrip('\n').rstrip('\r')

                if not line or not line.startswith('data:'):
                    continue

                data_str = line[5:].strip()
                if data_str == '[DONE]':
                    break

                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                # 解析厂商 SSE chunk
                if provider_format == 'openai':
                    chunk_id = chunk.get('id', '')
                    choices = chunk.get('choices', [])
                    if not choices:
                        continue
                    delta = choices[0].get('delta', {})
                    content = delta.get('content', '') or ''
                    finish = choices[0].get('finish_reason')
                    role = delta.get('role', '')
                    reasoning = delta.get('reasoning_content', '') or ''
                else:
                    chunk_id = ''
                    role = ''
                    reasoning = ''
                    event_type = chunk.get('type', '')
                    if event_type == 'content_block_delta':
                        delta_block = chunk.get('delta', {})
                        if delta_block.get('type') == 'thinking_delta':
                            reasoning = delta_block.get('thinking', '') or ''
                        elif delta_block.get('type') == 'text_delta':
                            content = delta_block.get('text', '') or ''
                        else:
                            content = delta_block.get('text', '') or ''
                        finish = None
                    elif event_type == 'message_delta':
                        content = ''
                        finish = chunk.get('delta', {}).get('stop_reason', 'stop')
                    elif event_type == 'content_block_start':
                        content = ''
                        finish = None
                    else:
                        continue

                # 累积 reasoning
                if reasoning:
                    reasoning_buf.append(reasoning)

                # 跳过纯空 delta
                has_any = bool(content or reasoning)
                if not has_any and not finish and not (output_protocol == 'chat' and role):
                    continue

                # ================================================================
                # 根据输出协议生成 SSE 事件
                # ================================================================
                if output_protocol == 'responses':
                    # reasoning → reasoning item 事件序列
                    if reasoning:
                        if not reasoning_started:
                            reasoning_item_id = 'rs_' + uuid.uuid4().hex[:24]
                            yield format_responses_sse('reasoning_item_added',
                                resp_id=resp_id, item_id=reasoning_item_id)
                            yield format_responses_sse('reasoning_part_added',
                                resp_id=resp_id, item_id=reasoning_item_id)
                            reasoning_started = True
                        yield format_responses_sse('reasoning_delta',
                            resp_id=resp_id, item_id=reasoning_item_id, delta=reasoning)

                    if content:
                        # reasoning 结束后才初始化 message item
                        if reasoning_started and not msg_init_sent:
                            yield format_responses_sse('output_item_added',
                                resp_id=resp_id, msg_id=msg_id)
                            yield format_responses_sse('content_part_added',
                                resp_id=resp_id, msg_id=msg_id)
                            msg_init_sent = True
                        text_buf.append(content)
                        yield format_responses_sse('delta',
                            resp_id=resp_id, msg_id=msg_id, delta=content)

                    if finish:
                        last_finish = finish

                elif output_protocol == 'chat':
                    sent_role = role if not chat_role_sent else None
                    if role:
                        chat_role_sent = True
                    yield format_chat_sse(chunk_id, content, finish,
                        role=sent_role, model=model_name,
                        reasoning_content=reasoning)

                elif output_protocol == 'anthropic':
                    if reasoning:
                        if not thinking_block_started:
                            yield format_anthropic_sse('thinking_block_start')
                            thinking_block_started = True
                        yield format_anthropic_sse('thinking_delta', content=reasoning)
                    if content:
                        if thinking_block_started:
                            yield format_anthropic_sse('thinking_block_stop')
                            thinking_block_started = False
                        if not text_block_started:
                            yield format_anthropic_sse('content_block_start')
                            text_block_started = True
                        yield format_anthropic_sse('content_block_delta', content=content)
                    if finish:
                        last_finish = finish

        # ================================================================
        # 完成事件序列
        # ================================================================
        if output_protocol == 'responses':
            # 完成 reasoning item
            if reasoning_started:
                full_reasoning = ''.join(reasoning_buf)
                yield format_responses_sse('reasoning_part_done',
                    resp_id=resp_id, item_id=reasoning_item_id, text=full_reasoning)
                yield format_responses_sse('reasoning_item_done',
                    resp_id=resp_id, item_id=reasoning_item_id)
                # 如果还没有 message item（全是 reasoning 无文本），初始化一个空 message
                if not msg_init_sent:
                    yield format_responses_sse('output_item_added',
                        resp_id=resp_id, msg_id=msg_id)
                    yield format_responses_sse('content_part_added',
                        resp_id=resp_id, msg_id=msg_id)
            full_text = ''.join(text_buf)
            yield format_responses_sse('output_text_done',
                resp_id=resp_id, msg_id=msg_id, text=full_text)
            yield format_responses_sse('content_part_done',
                resp_id=resp_id, msg_id=msg_id, text=full_text)
            yield format_responses_sse('output_item_done',
                resp_id=resp_id, msg_id=msg_id, text=full_text)
            yield format_responses_sse('completed', resp_id=resp_id, model=model_name)

        elif output_protocol == 'anthropic':
            if thinking_block_started:
                yield format_anthropic_sse('thinking_block_stop')
            if text_block_started:
                yield format_anthropic_sse('content_block_stop')
            yield format_anthropic_sse('message_delta',
                finish_reason=last_finish or 'end_turn')
            yield format_anthropic_sse('message_stop')

        yield 'data: [DONE]\n\n'

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='ignore')
        safe_msg = json.dumps({'error': f'厂商 API 错误 ({e.code}): {error_body[:200]}'}, ensure_ascii=False)
        yield f'data: {safe_msg}\n\n'
        yield 'data: [DONE]\n\n'
    except Exception as e:
        safe_msg = json.dumps({'error': str(e)}, ensure_ascii=False)
        yield f'data: {safe_msg}\n\n'
        yield 'data: [DONE]\n\n'
