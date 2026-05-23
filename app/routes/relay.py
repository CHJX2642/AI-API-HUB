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

@bp.route('/v1/v1/chat/completions', methods=['POST'])
def relay_chat_completions_legacy():
    """兼容 /v1/v1/chat/completions 路径"""
    return relay_chat_completions()


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

@bp.route('/v1/v1/responses', methods=['POST'])
def relay_responses_legacy():
    """兼容 /v1/v1/responses 路径"""
    return relay_responses()


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

    # DEBUG: 记录请求信息
    print(f"[relay/messages] model={data.get('model')}, stream={data.get('stream')}, "
          f"msg_count={len(data.get('messages',[]))}, output_protocol={output_protocol}",
          flush=True)

    # 流式处理
    if data.get('stream'):
        return handle_anthropic_stream(data, output_protocol)

    # 非流式处理
    result, status = handle_relay(data, 'anthropic', output_protocol)
    # 错误响应转为 Anthropic 错误格式
    if status >= 400:
        err_msg = result.get('error', '未知错误')
        anthropic_error = {
            'type': 'error',
            'error': {
                'type': 'api_error',
                'message': err_msg,
            }
        }
        resp = jsonify(anthropic_error)
    else:
        resp = jsonify(result)
    resp.headers['anthropic-version'] = '2023-06-01'
    return resp, status


# 兼容用户误配置：ANTHROPIC_BASE_URL 带了 /v1 后缀导致请求路径变成 /v1/v1/messages
@bp.route('/v1/v1/messages', methods=['POST'])
def relay_messages_legacy():
    """兼容 /v1/v1/messages 路径重定向到正确端点"""
    return relay_messages()


@bp.route('/v1/v1/messages/count_tokens', methods=['POST'])
def relay_count_tokens_legacy():
    """兼容 /v1/v1/messages/count_tokens 路径"""
    return relay_count_tokens()


@bp.route('/v1/messages/count_tokens', methods=['POST'])
def relay_count_tokens():
    """Anthropic Messages count_tokens 端点
    Claude Code 使用此端点做上下文 token 计数管理
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

    # 简单估算：字符数 / 4 ≈ token 数（适用于中英文混合场景）
    total_chars = 0
    messages = data.get('messages', [])
    system = data.get('system', '')
    if isinstance(system, str):
        total_chars += len(system)
    elif isinstance(system, list):
        for item in system:
            if isinstance(item, dict) and item.get('type') == 'text':
                total_chars += len(item.get('text', ''))
    for msg in messages:
        content = msg.get('content', '')
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get('type') == 'text':
                    total_chars += len(block.get('text', ''))

    estimated_tokens = max(1, total_chars // 4)

    resp = jsonify({'input_tokens': estimated_tokens})
    resp.headers['anthropic-version'] = '2023-06-01'
    return resp, 200


# ====================== 模型列表（OpenAI 格式） ======================

@bp.route('/v1/v1/models', methods=['GET'])
def relay_models_legacy():
    """兼容 /v1/v1/models 路径"""
    return relay_models()


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
        print(f"[stream] ✗ model not found: {model_name}", flush=True)
        # 以 SSE 格式返回错误，避免客户端死等
        def err_gen():
            err_obj = json.dumps({'type': 'error', 'error': {'type': 'api_error', 'message': error}}, ensure_ascii=False)
            yield f'event: error\ndata: {err_obj}\n\n'
        return Response(stream_with_context(err_gen()), content_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'anthropic-version': '2023-06-01'})

    valid, err_msg = validate_relay_request(internal, provider_info)
    if not valid:
        print(f"[stream] ✗ validation failed: {err_msg}", flush=True)
        def err_gen():
            err_obj = json.dumps({'type': 'error', 'error': {'type': 'api_error', 'message': err_msg}}, ensure_ascii=False)
            yield f'event: error\ndata: {err_obj}\n\n'
        return Response(stream_with_context(err_gen()), content_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'anthropic-version': '2023-06-01'})

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
            'anthropic-version': '2023-06-01',
        }
    )


def _stream_generator(internal, provider_info, output_protocol):
    """流式生成器：发送请求到厂商并逐行翻译 SSE
    output_protocol: 输出流式 SSE 的协议格式（chat/responses/anthropic）
    支持 DeepSeek/Mimo 等模型的 reasoning_content（思考过程）翻译"""
    import urllib.request
    import urllib.error
    import ssl

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

        # DEBUG: 打印请求摘要
        msg_count = len(req_body.get('messages', []))
        mt = req_body.get('max_tokens', '?')
        print(f"[stream] → {provider_info['provider_name']}/{provider_info['model_id']} "
              f"via {provider_format} msgs={msg_count} max_tokens={mt} "
              f"url={provider_info['api_url'][:80]}", flush=True)

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
            tool_use_blocks = {}       # {openai_index: {'id':...,'name':...,'anthro_index':...,'started':bool}}
            next_block_index = 0       # Anthropic 内容块索引计数器
            yield format_anthropic_sse('message_start', model=model_name)

        # SSL 上下文：调试时跳过证书验证
        verify_ssl = current_app.config.get('RELAY_VERIFY_SSL', True)
        ssl_ctx = None if verify_ssl else ssl.create_default_context()
        if not verify_ssl:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(req, timeout=current_app.config.get('RELAY_TIMEOUT', 120), context=ssl_ctx) as resp:
            print(f"[stream] ← upstream response started, status={resp.status}", flush=True)
            chunk_count = 0
            raw_line_count = 0       # 上游返回的总行数（含空行和 event 行）
            for line_bytes in resp:
                line = line_bytes.decode('utf-8').rstrip('\n').rstrip('\r')
                raw_line_count += 1

                # DEBUG: 打印上游响应的前几行，方便排查
                if raw_line_count <= 3 and line:
                    print(f"[stream]   raw[{raw_line_count}]: {line[:200]}", flush=True)

                if not line or not line.startswith('data:'):
                    continue

                data_str = line[5:].strip()
                if data_str == '[DONE]':
                    break

                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                # DEBUG: 打印前几个有效 chunk 的类型
                if chunk_count < 3:
                    chunk_type = chunk.get('type', chunk.get('object', '?'))
                    print(f"[stream]   chunk[{chunk_count}]: type={chunk_type}", flush=True)

                # 解析厂商 SSE chunk
                raw_tool_calls = None  # OpenAI 格式的 tool_calls delta
                anthropic_tool_start = None  # Anthropic 格式的 tool_use content_block_start
                anthropic_tool_delta = None  # Anthropic 格式的 input_json_delta

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
                    raw_tool_calls = delta.get('tool_calls')  # 提取工具调用
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
                        elif delta_block.get('type') == 'input_json_delta':
                            # Anthropic 上游的工具调用参数增量
                            content = ''
                            anthropic_tool_delta = delta_block.get('partial_json', '') or ''
                        else:
                            content = delta_block.get('text', '') or ''
                        finish = None
                    elif event_type == 'message_delta':
                        content = ''
                        finish = chunk.get('delta', {}).get('stop_reason', 'stop')
                    elif event_type == 'content_block_start':
                        cb = chunk.get('content_block', {})
                        if cb.get('type') == 'tool_use':
                            # Anthropic 上游的工具调用开始
                            anthropic_tool_start = {
                                'id': cb.get('id', ''),
                                'name': cb.get('name', ''),
                            }
                        content = ''
                        finish = None
                    else:
                        continue

                # 累积 reasoning
                if reasoning:
                    reasoning_buf.append(reasoning)

                # 跳过纯空 delta（同时检查是否有工具调用）
                has_any = bool(content or reasoning or raw_tool_calls
                              or anthropic_tool_start or anthropic_tool_delta)
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
                        reasoning_content=reasoning,
                        tool_calls=raw_tool_calls)

                elif output_protocol == 'anthropic':
                    # --- reasoning / thinking ---
                    if reasoning:
                        if not thinking_block_started:
                            thinking_block_index = next_block_index
                            next_block_index += 1
                            yield format_anthropic_sse('thinking_block_start',
                                block_index=thinking_block_index)
                            thinking_block_started = True
                        yield format_anthropic_sse('thinking_delta',
                            content=reasoning, block_index=thinking_block_index)

                    # --- 普通文本 ---
                    if content:
                        if thinking_block_started:
                            yield format_anthropic_sse('thinking_block_stop',
                                block_index=thinking_block_index)
                            thinking_block_started = False
                        if not text_block_started:
                            text_block_index = next_block_index
                            next_block_index += 1
                            yield format_anthropic_sse('content_block_start',
                                block_index=text_block_index)
                            text_block_started = True
                        yield format_anthropic_sse('content_block_delta',
                            content=content, block_index=text_block_index)

                    # --- 工具调用（OpenAI 格式 → Anthropic tool_use） ---
                    if raw_tool_calls:
                        # 关闭 thinking block（如果还在）
                        if thinking_block_started:
                            yield format_anthropic_sse('thinking_block_stop',
                                block_index=thinking_block_index)
                            thinking_block_started = False
                        for tc in raw_tool_calls:
                            tc_index = tc.get('index', 0)
                            if tc_index not in tool_use_blocks:
                                # 新工具调用：分配 Anthropic 内容块索引
                                tool_use_blocks[tc_index] = {
                                    'id': tc.get('id', ''),
                                    'name': '',
                                    'anthro_index': next_block_index,
                                    'started': False,
                                }
                                next_block_index += 1
                            tu = tool_use_blocks[tc_index]
                            # 更新工具名（OpenAI 在第一个 chunk 里带 name）
                            fn = tc.get('function', {})
                            if fn.get('name'):
                                tu['name'] = fn['name']
                            if tc.get('id') and not tu['started']:
                                # 发送 tool_use content_block_start
                                tu['started'] = True
                                yield format_anthropic_sse('tool_use_block_start',
                                    block_index=tu['anthro_index'],
                                    tool_use_info={'id': tu['id'], 'name': tu['name']})
                            # 发送参数增量
                            args_delta = fn.get('arguments', '') or ''
                            if args_delta:
                                yield format_anthropic_sse('tool_use_delta',
                                    content=args_delta,
                                    block_index=tu['anthro_index'])

                    # --- Anthropic 格式上游的 tool_use ---
                    if anthropic_tool_start:
                        # 关闭 thinking block（如果还在）
                        if thinking_block_started:
                            yield format_anthropic_sse('thinking_block_stop',
                                block_index=thinking_block_index)
                            thinking_block_started = False
                        tu_id = anthropic_tool_start['id']
                        tu_name = anthropic_tool_start['name']
                        # 用 id 作为 key（Anthropic 格式只有一个 tool_use 在流中）
                        tool_key = f'anthropic_{tu_id}'
                        if tool_key not in tool_use_blocks:
                            tool_use_blocks[tool_key] = {
                                'id': tu_id,
                                'name': tu_name,
                                'anthro_index': next_block_index,
                                'started': True,
                            }
                            next_block_index += 1
                            yield format_anthropic_sse('tool_use_block_start',
                                block_index=tool_use_blocks[tool_key]['anthro_index'],
                                tool_use_info={'id': tu_id, 'name': tu_name})

                    if anthropic_tool_delta:
                        # 找到当前活跃的 tool_use 块并发送 delta
                        for tu in tool_use_blocks.values():
                            if tu['started']:
                                yield format_anthropic_sse('tool_use_delta',
                                    content=anthropic_tool_delta,
                                    block_index=tu['anthro_index'])
                                break

                    if finish:
                        last_finish = finish

                chunk_count += 1

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
            # 关闭所有已启动的内容块
            if thinking_block_started:
                yield format_anthropic_sse('thinking_block_stop',
                    block_index=thinking_block_index)
            if text_block_started:
                yield format_anthropic_sse('content_block_stop',
                    block_index=text_block_index)
            # 关闭所有已启动的 tool_use 块
            for tu in tool_use_blocks.values():
                if tu['started']:
                    yield format_anthropic_sse('tool_use_block_stop',
                        block_index=tu['anthro_index'])
            yield format_anthropic_sse('message_delta',
                finish_reason=last_finish or 'end_turn')
            yield format_anthropic_sse('message_stop')

        # OpenAI / Responses 协议用 [DONE] 标记流结束，Anthropic 协议已通过 message_stop 结束
        if output_protocol != 'anthropic':
            yield 'data: [DONE]\n\n'

        # 输出完成日志
        full_reasoning = ''.join(reasoning_buf)
        tool_count = len(tool_use_blocks) if output_protocol == 'anthropic' else 0
        print(f"[stream] ← done, chunks={chunk_count}, raw_lines={raw_line_count}, "
              f"protocol={output_protocol}, reason_len={len(full_reasoning)}, "
              f"tool_uses={tool_count}, last_finish={last_finish}", flush=True)
        if chunk_count == 0:
            print(f"[stream] ⚠ WARNING: zero content chunks from upstream! "
                  f"Possible upstream error or empty response.", flush=True)


    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='ignore')
        print(f"[stream] ✗ HTTP {e.code} from {provider_info['api_url'][:80]}: {error_body[:300]}", flush=True)
        safe_msg = json.dumps({'error': f'厂商 API 错误 ({e.code}): {error_body[:200]}'}, ensure_ascii=False)
        if output_protocol == 'anthropic':
            err_obj = json.dumps({'type': 'error', 'error': {'type': 'api_error', 'message': f'厂商 API 错误 ({e.code}): {error_body[:200]}'}}, ensure_ascii=False)
            yield f'event: error\ndata: {err_obj}\n\n'
        else:
            yield f'data: {safe_msg}\n\n'
            yield 'data: [DONE]\n\n'
    except Exception as e:
        print(f"[stream] ✗ Exception from {provider_info['api_url'][:80]}: {type(e).__name__}: {e}", flush=True)
        safe_msg = json.dumps({'error': str(e)}, ensure_ascii=False)
        if output_protocol == 'anthropic':
            err_obj = json.dumps({'type': 'error', 'error': {'type': 'api_error', 'message': str(e)}}, ensure_ascii=False)
            yield f'event: error\ndata: {err_obj}\n\n'
        else:
            yield f'data: {safe_msg}\n\n'
            yield 'data: [DONE]\n\n'
