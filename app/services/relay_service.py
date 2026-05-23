# -*- coding: utf-8 -*-
# AI API Hub — API 转接服务模块
# 支持 OpenAI Chat / OpenAI Responses / Anthropic Messages 三种协议互转
# 核心思路：所有协议归一化为内部通用格式，消除 N×N 翻译矩阵

import json                            # JSON 序列化/反序列化
import uuid                            # 生成唯一请求 ID
import time                            # 时间戳
import ssl                             # SSL 上下文，用于调试时跳过证书验证
import urllib.request                  # HTTP 请求，调用下游厂商 API
import urllib.error                    # HTTP 错误处理
from flask import current_app          # Flask 应用上下文，读取配置
from app.database import get_db, parse_provider_row  # 数据库工具

# ====================== 内部格式定义 ======================
# 内部通用格式字段说明：
#   model:         请求的模型名
#   messages:      消息列表 [{"role":"user","content":"..."}]
#   temperature:   温度参数 (0-2)
#   max_tokens:    最大输出 token 数
#   stream:        是否流式
#   top_p:         核采样参数
#   stop:          停止词（字符串或列表）
#   tools:         工具定义列表（OpenAI 格式）
#   tool_choice:   工具选择策略
#   reasoning:     思考/推理内容（DeepSeek-R1/Mimo 等模型产生）
#   reasoning_done: 推理是否已完成

# ====================== ProviderAdapter 厂商适配器 ======================
# 每种厂商可能有特殊的行为差异，通过适配器模式统一处理。
# 当前支持的厂商适配：DeepSeek（含 reasoning 处理）、通用（直通）


class ProviderAdapter:
    """厂商适配器基类 — 提供默认的直通行为
    子类可覆写以下钩子来实现厂商特有逻辑：
      - prepare_request(internal, original_data, client_protocol)
      - process_response(internal_resp)
      - process_stream_delta(delta_dict, accumulated_state)
    """
    provider_name = 'generic'

    def prepare_request(self, internal, original_data, client_protocol):
        """请求发送前处理 — 可修改 internal 格式的请求"""
        return internal

    def process_response(self, internal_resp):
        """非流式响应后处理 — 可修改 internal 格式的响应"""
        return internal_resp

    def process_stream_delta(self, delta, state):
        """流式 delta 后处理
        delta: 厂商返回的原始 delta dict（可能含 reasoning_content）
        state:  累积状态 dict，可跨 chunk 保持状态
        返回: (content_text, finish_reason, extra_events)
          content_text:  当前 chunk 的文本内容
          finish_reason: 结束原因
          extra_events:  需要额外发送的事件列表（如 reasoning 事件）
        """
        return delta.get('content', '') or '', None, []

    def get_capabilities(self):
        """返回厂商能力描述"""
        return {'supports_reasoning': False, 'supports_tool_calls': True}


class DeepSeekAdapter(ProviderAdapter):
    """DeepSeek/Mimo 等 reasoning 模型适配器
    DeepSeek-R1 在 Chat API 中会返回 reasoning_content（思考过程），
    需要在三种输出协议中正确映射：
      - Chat:  直接保留 reasoning_content 字段
      - Responses: 转为 output 中的 reasoning item
      - Anthropic: 转为 thinking 类型的 content_block
    同时处理 DeepSeek 的 tool_call 与 reasoning 合并逻辑。
    """
    provider_name = 'deepseek'

    def __init__(self):
        self._stream_state = {}

    def process_response(self, internal_resp):
        """非流式响应处理 — reasoning 已由 openai_response_to_internal 捕获"""
        return internal_resp

    def process_stream_delta(self, delta, state):
        """流式 delta 处理 — 分离 reasoning_content 和 content"""
        content = delta.get('content', '') or ''
        reasoning = delta.get('reasoning_content', '') or ''
        finish = None
        extra_events = []

        # DeepSeek reasoning_content 通常在普通 content 之前发送
        if reasoning:
            state_key = id(state)
            if 'reasoning_chunks' not in state:
                state['reasoning_chunks'] = []
            state['reasoning_chunks'].append(reasoning)
            # 产出 reasoning 事件标记
            extra_events.append({'type': 'reasoning', 'content': reasoning})

        # 如果 reasoning 完成（开始出现正常 content），标记 reasoning_done
        if content and state.get('reasoning_chunks') and not state.get('reasoning_done'):
            state['reasoning_done'] = True

        return content, finish, extra_events

    def get_capabilities(self):
        return {'supports_reasoning': True, 'supports_tool_calls': True}


# 适配器注册表：根据 provider name 匹配
ADAPTER_REGISTRY = {
    'deepseek': DeepSeekAdapter,
    'mimo': DeepSeekAdapter,         # Mimo 也使用类似 reasoning 机制
    'glm': DeepSeekAdapter,          # 智谱 GLM 也有思考模式
}


def get_adapter(provider_name):
    """根据厂商名获取适配器实例"""
    adapter_cls = ADAPTER_REGISTRY.get(provider_name.lower(), ProviderAdapter)
    return adapter_cls()


# ====================== 内容策略验证 ======================

def validate_relay_request(internal, provider_info):
    """在转发前校验请求参数，避免不合规的请求传到厂商导致报错
    参数:
        internal: 内部格式的请求
        provider_info: resolve_model 返回的提供商信息
    返回:
        (True, None) 或 (False, error_message)
    """
    messages = internal.get('messages', [])
    model_name = provider_info.get('model_id', '')

    # ① 检查消息列表不为空
    if not messages:
        return False, '请求消息列表不能为空'

    # ② 检查 max_tokens 范围（1-200000），默认值从配置读取
    default_mt = current_app.config.get('RELAY_DEFAULT_MAX_TOKENS', 2048)
    max_tokens = internal.get('max_tokens', default_mt)
    if max_tokens is not None and (max_tokens < 1 or max_tokens > 200000):
        return False, f'max_tokens 超出有效范围 (1-200000): {max_tokens}'

    # ③ 检查 temperature 范围
    temperature = internal.get('temperature', 0.7)
    if temperature is not None and (temperature < 0 or temperature > 2):
        return False, f'temperature 超出有效范围 (0-2): {temperature}'

    # ④ 检查 top_p 范围
    top_p = internal.get('top_p', 1.0)
    if top_p is not None and (top_p < 0 or top_p > 1):
        return False, f'top_p 超出有效范围 (0-1): {top_p}'

    # ⑤ 检查 stop 字段 — 厂商是 Anthropic 格式时确保是 list
    # （内部格式统一处理，这里只做合法性检查）

    # ⑥ 检查 model 字段
    if not internal.get('model'):
        return False, 'model 字段不能为空'

    return True, None


# ====================== 认证 ======================

def sanitize_data(data):
    """清洗客户端请求中的无效值（如 "[undefined]" 字符串），替换为 None"""
    for key, val in list(data.items()):
        if isinstance(val, str) and val == '[undefined]':
            data[key] = None
    return data


def authenticate_relay(headers):
    """验证转接请求的 API Key，同时返回该 Key 绑定的输出协议
    支持三把协议专用 Key + 一把通用 Key（向下兼容）：
      relay_key_chat       → output_protocol='chat'
      relay_key_anthropic  → output_protocol='anthropic'
      relay_key_responses   → output_protocol='responses'
      relay_api_key        → output_protocol=None（跟随输入协议）
    参数:
        headers: 请求头字典（flask request.headers）
    返回:
        (True, output_protocol_or_None) 认证通过 + 绑定的协议
        (False, error_message)          认证失败
    """
    # 提取客户端提供的 Key
    auth_header = headers.get('Authorization', '')
    x_api_key = headers.get('x-api-key', '')

    provided_key = ''
    if auth_header.startswith('Bearer '):  # Bearer Token 格式
        provided_key = auth_header[7:]
    elif x_api_key:                        # x-api-key 头格式
        provided_key = x_api_key

    if not provided_key:                   # 未提供任何认证信息
        return False, '请在 Authorization 头中提供 Bearer Token，或使用 x-api-key 头'

    # 按优先级匹配：协议专用 Key > 通用 Key
    conn = get_db()
    try:
        # 查询所有 relay key 设置
        rows = conn.execute(
            "SELECT key, value FROM app_settings WHERE key LIKE 'relay_key_%' OR key = 'relay_api_key'"
        ).fetchall()
        settings = {r['key']: r['value'] for r in rows if r['value']}
    finally:
        conn.close()

    # 协议 Key → 输出协议映射
    KEY_PROTOCOL_MAP = {
        'relay_key_chat': 'chat',
        'relay_key_anthropic': 'anthropic',
        'relay_key_responses': 'responses',
    }

    # ① 先匹配三把协议专用 Key
    for key_name, protocol in KEY_PROTOCOL_MAP.items():
        expected = settings.get(key_name, '')
        if expected and provided_key == expected:
            return True, protocol

    # ② 再匹配通用 Key（无协议绑定 = 跟随输入）
    generic_key = settings.get('relay_api_key', '')
    if generic_key and provided_key == generic_key:
        return True, None

    # ③ 如果只配了通用 Key 但没有任何专用 Key，且提供的 key 看起来不对
    if not any(settings.get(k) for k in KEY_PROTOCOL_MAP) and not generic_key:
        return False, '转接服务未配置 API Key，请先在「API 转接」页面设置'

    return False, 'API Key 不正确'


# ====================== 模型路由 ======================

def resolve_model(model_id):
    """根据模型名查找提供商信息、密钥和 API URL
    参数:
        model_id: 客户端请求的模型名，如 'gpt-4o'、'mimo-v2.5'
    返回:
        成功: (provider_info_dict, None)
        失败: (None, error_message)
    """
    conn = get_db()
    try:
        # 联表查询模型和提供商信息
        model = conn.execute('''
            SELECT m.*, p.name as provider_name, p.display_name as provider_display_name
            FROM api_models m
            JOIN api_providers p ON m.provider_id = p.id
            WHERE m.model_id = ? AND m.is_active = 1 AND p.is_active = 1
            ORDER BY m.id LIMIT 1
        ''', (model_id,)).fetchone()

        if not model:                    # 模型不存在
            # 列出所有可用模型，帮助用户排查
            all_models = conn.execute('''
                SELECT m.model_id FROM api_models m
                JOIN api_providers p ON m.provider_id = p.id
                WHERE m.is_active = 1 AND p.is_active = 1
                ORDER BY m.model_id
            ''').fetchall()
            available = [m['model_id'] for m in all_models]
            return None, f'未找到模型 "{model_id}"，可用模型: {", ".join(available[:20])}'

        provider_id = model['provider_id']  # 提供商 ID

        # 获取该提供商的活跃 API Key
        key_row = conn.execute(
            'SELECT api_key FROM api_keys WHERE provider_id = ? AND is_active = 1 LIMIT 1',
            (provider_id,)
        ).fetchone()
        if not key_row or not key_row['api_key']:  # 无可用密钥
            return None, f'提供商 "{model["provider_display_name"]}" 没有可用的 API Key'

        # 获取提供商信息（含 api_urls）
        provider = conn.execute(
            'SELECT * FROM api_providers WHERE id = ?', (provider_id,)
        ).fetchone()
        provider_data = parse_provider_row(provider)  # 解析 api_urls JSON

        # 从 api_urls 中选一个活跃的 URL
        api_urls = provider_data.get('api_urls', [])
        if not api_urls:                   # 没有配置 API URL
            return None, f'提供商 "{model["provider_display_name"]}" 没有配置 API URL'

        # 优先选与模型名匹配的 URL（同厂商可能有多个计费方案的 URL）
        selected_url = api_urls[0]         # 默认用第一个
        # 如果有多个 URL，尝试根据 key_name 匹配（按量/Token Plan 等）
        provider_format = selected_url.get('format', 'openai')

        return {
            'model_id': model['model_id'],
            'display_name': model['display_name'],
            'provider_id': provider_id,
            'provider_name': provider_data['name'],
            'provider_display_name': provider_data['display_name'],
            'api_url': selected_url['url'],
            'api_format': provider_format,      # 厂商 API 格式：'openai' 或 'anthropic'
            'api_key': key_row['api_key'],      # 厂商 API 密钥
        }, None
    finally:
        conn.close()


def flatten_content(content):
    """将 Responses API 的 content 数组展平为纯文本字符串
    content 可能是字符串、或 [{"type":"input_text","text":"..."}, ...] 数组
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get('type') == 'input_text':
                    parts.append(part.get('text', ''))
                # 跳过 image_url 等其他类型
            elif isinstance(part, str):
                parts.append(part)
        return '\n'.join(parts) if parts else ''
    return str(content) if content else ''


# ====================== 协议转换：请求 → 内部格式 ======================

def chat_to_internal(data):
    """OpenAI Chat Completions 请求 → 内部格式"""
    messages = []
    for msg in data.get('messages', []):
        if isinstance(msg, dict):
            messages.append({
                'role': msg.get('role', 'user'),
                'content': flatten_content(msg.get('content', '')),
            })
    internal = {
        'model': data.get('model', ''),
        'messages': messages,
        'temperature': data.get('temperature', 0.7),
        'max_tokens': data.get('max_tokens', 2048),
        'stream': data.get('stream', False),
        'top_p': data.get('top_p', 1.0),
        'stop': data.get('stop'),
        'tools': data.get('tools'),
        'tool_choice': data.get('tool_choice'),
    }
    return internal


def responses_to_internal(data):
    """OpenAI Responses API 请求 → 内部格式"""
    # 处理 input 字段：可能是字符串或消息数组
    raw_input = data.get('input', '')
    if isinstance(raw_input, str):         # 字符串 → 单个 user 消息
        messages = [{'role': 'user', 'content': raw_input}]
    elif isinstance(raw_input, list):      # 数组 → 直接映射
        messages = []
        for item in raw_input:
            if isinstance(item, dict):
                messages.append({
                    'role': item.get('role', 'user'),
                    'content': flatten_content(item.get('content', ''))
                })
    else:
        messages = []

    # instructions 字段 → system 消息（放在最前面）
    instructions = data.get('instructions', '')
    if instructions:
        messages.insert(0, {'role': 'system', 'content': instructions})

    internal = {
        'model': data.get('model', ''),
        'messages': messages,
        'temperature': data.get('temperature', 0.7),
        'max_tokens': data.get('max_output_tokens', 2048),  # Responses 用 max_output_tokens
        'stream': data.get('stream', False),
        'top_p': data.get('top_p', 1.0),
        'stop': data.get('stop'),
        'tools': data.get('tools'),
        'tool_choice': data.get('tool_choice'),
    }
    return internal


def anthropic_to_internal(data):
    """Anthropic Messages 请求 → 内部格式"""
    messages = []
    # 处理 system 字段（Anthropic 支持 string 或 array）
    system = data.get('system', '')
    if isinstance(system, list):           # Anthropic 新格式：system 可以是文本块数组
        system_text = ''.join(
            item.get('text', '') for item in system if isinstance(item, dict) and item.get('type') == 'text'
        )
    elif isinstance(system, str):
        system_text = system
    else:
        system_text = ''

    if system_text:                        # 将 system 转为 messages 中的第一条
        messages.append({'role': 'system', 'content': system_text})

    # 映射 Anthropic messages → OpenAI messages 格式
    for msg in data.get('messages', []):
        role = msg.get('role', 'user')
        content = msg.get('content', '')

        # Anthropic 的 content 可能是字符串或内容块数组
        if isinstance(content, list):      # 多模态内容块数组
            # 先提取纯文本部分
            text_parts = []
            image_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get('type') == 'text':
                        text_parts.append(block.get('text', ''))
                    elif block.get('type') == 'image':
                        # Anthropic image → OpenAI image_url 格式
                        source = block.get('source', {})
                        if source.get('type') == 'base64':
                            mime = source.get('media_type', 'image/png')
                            b64 = source.get('data', '')
                            image_parts.append({
                                'type': 'image_url',
                                'image_url': {'url': f'data:{mime};base64,{b64}'}
                            })
                    elif block.get('type') == 'tool_use':
                        image_parts.append(block)
                    elif block.get('type') == 'tool_result':
                        image_parts.append(block)

            if image_parts:                # 有图片，构建多模态 content
                combined = [{'type': 'text', 'text': '\n'.join(text_parts)}] if text_parts else []
                combined.extend(image_parts)
                messages.append({'role': role, 'content': combined})
            else:                          # 纯文本
                messages.append({'role': role, 'content': '\n'.join(text_parts)})
        elif isinstance(content, str):     # 纯字符串
            messages.append({'role': role, 'content': content})

    # 转换 tools 格式（Anthropic → OpenAI）
    tools = None
    raw_tools = data.get('tools', [])
    if raw_tools:
        tools = []
        for tool in raw_tools:
            if isinstance(tool, dict):
                tools.append({
                    'type': 'function',
                    'function': {
                        'name': tool.get('name', ''),
                        'description': tool.get('description', ''),
                        'parameters': tool.get('input_schema', {})
                    }
                })

    internal = {
        'model': data.get('model', ''),
        'messages': messages,
        'temperature': data.get('temperature', 0.7),
        'max_tokens': data.get('max_tokens', 2048),
        'stream': data.get('stream', False),
        'top_p': data.get('top_p', 1.0),
        'stop': data.get('stop_sequences'),  # Anthropic 用 stop_sequences
        'tools': tools,
        'tool_choice': data.get('tool_choice'),
    }
    return internal


# ====================== 内部格式 → 厂商请求 ======================

def internal_to_openai_request(internal, api_key, model=None):
    """内部格式 → OpenAI Chat Completions 请求"""
    body = {
        'model': model or internal['model'],
        'messages': internal['messages'],
        'temperature': internal.get('temperature', 0.7),
        'max_tokens': internal.get('max_tokens', 2048),
        'stream': internal.get('stream', False),
    }
    if internal.get('top_p'):
        body['top_p'] = internal['top_p']
    if internal.get('stop'):
        body['stop'] = internal['stop']
    if internal.get('tools'):
        body['tools'] = internal['tools']
    if internal.get('tool_choice'):
        body['tool_choice'] = internal['tool_choice']

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    return body, headers


def internal_to_anthropic_request(internal, api_key, model=None):
    """内部格式 → Anthropic Messages 请求"""
    # 提取 system 消息
    system_text = ''
    user_messages = []
    for msg in internal['messages']:
        if msg['role'] == 'system':
            system_text += msg['content'] + '\n'
        else:
            # 处理 content：如果是字符串则转为 Anthropic 格式
            content = msg['content']
            if isinstance(content, str):
                user_messages.append({
                    'role': msg['role'],
                    'content': [{'type': 'text', 'text': content}]
                })
            elif isinstance(content, list):
                # 尝试转换多模态格式
                blocks = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get('type') == 'text':
                            blocks.append({'type': 'text', 'text': block.get('text', '')})
                        elif block.get('type') == 'image_url':
                            # OpenAI image_url → Anthropic source 格式
                            url = block.get('image_url', {}).get('url', '')
                            if url.startswith('data:'):
                                # data:image/png;base64,xxx
                                try:
                                    header, b64_data = url.split(',', 1)
                                    mime = header.replace('data:', '').replace(';base64', '')
                                    blocks.append({
                                        'type': 'image',
                                        'source': {
                                            'type': 'base64',
                                            'media_type': mime,
                                            'data': b64_data
                                        }
                                    })
                                except ValueError:
                                    pass
                user_messages.append({
                    'role': msg['role'],
                    'content': blocks if blocks else [{'type': 'text', 'text': ''}]
                })

    body = {
        'model': model or internal['model'],
        'max_tokens': internal.get('max_tokens', 2048),
        'messages': user_messages,
        'stream': internal.get('stream', False),
    }
    if system_text.strip():
        body['system'] = system_text.strip()
    if internal.get('temperature') is not None:
        body['temperature'] = internal['temperature']
    if internal.get('top_p') is not None:
        body['top_p'] = internal['top_p']
    if internal.get('stop'):
        body['stop_sequences'] = internal['stop'] if isinstance(internal['stop'], list) else [internal['stop']]

    headers = {
        'Content-Type': 'application/json',
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01'
    }
    return body, headers


# ====================== 厂商响应 → 内部格式 ======================

def openai_response_to_internal(resp_body, model):
    """OpenAI Chat 响应 → 内部格式"""
    choice = resp_body.get('choices', [{}])[0]
    message = choice.get('message', {})
    usage = resp_body.get('usage', {})

    # 捕获 reasoning_content（DeepSeek-R1/Mimo 等思考模型的推理过程）
    reasoning = message.get('reasoning_content', None)

    return {
        'id': resp_body.get('id', f'chatcmpl-{uuid.uuid4().hex[:12]}'),
        'model': model,
        'content': message.get('content') or '',
        'finish_reason': choice.get('finish_reason', 'stop'),
        'reasoning': reasoning,              # 推理内容（可能为 None）
        'usage': {
            'prompt_tokens': usage.get('prompt_tokens', 0),
            'completion_tokens': usage.get('completion_tokens', 0),
            'total_tokens': usage.get('total_tokens', 0),
        },
        'tool_calls': message.get('tool_calls'),
    }


def anthropic_response_to_internal(resp_body, model):
    """Anthropic 响应 → 内部格式"""
    content_blocks = resp_body.get('content', [])
    # 合并所有 text 块
    text = ''
    tool_calls = []
    for block in content_blocks:
        if block.get('type') == 'text':
            text += block.get('text', '')
        elif block.get('type') == 'tool_use':
            tool_calls.append({
                'id': block.get('id', ''),
                'type': 'function',
                'function': {
                    'name': block.get('name', ''),
                    'arguments': json.dumps(block.get('input', {}))
                }
            })

    usage = resp_body.get('usage', {})
    return {
        'id': resp_body.get('id', f'msg_{uuid.uuid4().hex[:12]}'),
        'model': model,
        'content': text,
        'finish_reason': resp_body.get('stop_reason', 'end_turn'),
        'reasoning': None,                   # Anthropic 协议本身不使用 reasoning_content 字段
        'usage': {
            'prompt_tokens': usage.get('input_tokens', 0),
            'completion_tokens': usage.get('output_tokens', 0),
            'total_tokens': usage.get('input_tokens', 0) + usage.get('output_tokens', 0),
        },
        'tool_calls': tool_calls if tool_calls else None,
    }


# ====================== 内部格式 → 客户端响应 ======================

def internal_to_chat_response(internal):
    """内部格式 → OpenAI Chat Completions 响应"""
    message = {
        'role': 'assistant',
        'content': internal['content']
    }
    if internal.get('tool_calls'):
        message['tool_calls'] = internal['tool_calls']
    # 保留 reasoning_content（DeepSeek-R1/Mimo 等思考模型的推理过程）
    if internal.get('reasoning'):
        message['reasoning_content'] = internal['reasoning']

    return {
        'id': internal['id'],
        'object': 'chat.completion',
        'created': int(time.time()),
        'model': internal['model'],
        'choices': [{
            'index': 0,
            'message': message,
            'finish_reason': internal.get('finish_reason', 'stop'),
        }],
        'usage': internal.get('usage', {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
        }),
    }


def internal_to_responses_response(internal):
    """内部格式 → OpenAI Responses API 响应
    reasoning 内容会转为独立的 reasoning item 放在 output 最前面
    """
    output = []
    # reasoning 作为独立的 reasoning item
    if internal.get('reasoning'):
        output.append({
            'type': 'reasoning',
            'id': f"rs_{uuid.uuid4().hex[:12]}",
            'content': [{'type': 'input_text', 'text': internal['reasoning']}],
        })

    output.append({
        'type': 'message',
        'id': f"msg_{uuid.uuid4().hex[:12]}",
        'role': 'assistant',
        'content': [{
            'type': 'output_text',
            'text': internal['content']
        }]
    })

    return {
        'id': internal['id'].replace('chatcmpl-', 'resp_'),
        'object': 'response',
        'created_at': int(time.time()),
        'model': internal['model'],
        'output': output,
        'usage': {
            'input_tokens': internal.get('usage', {}).get('prompt_tokens', 0),
            'output_tokens': internal.get('usage', {}).get('completion_tokens', 0),
            'total_tokens': internal.get('usage', {}).get('total_tokens', 0),
        },
    }


def internal_to_anthropic_response(internal):
    """内部格式 → Anthropic Messages 响应
    reasoning 内容会转为 thinking 类型的 content_block 放在最前面
    """
    content_blocks = []
    # reasoning → Anthropic thinking block
    if internal.get('reasoning'):
        content_blocks.append({
            'type': 'thinking',
            'thinking': internal['reasoning'],
        })
    content_blocks.append({
        'type': 'text',
        'text': internal['content']
    })
    # 如果有 tool_calls，转为 Anthropic tool_use 块
    if internal.get('tool_calls'):
        for tc in internal['tool_calls']:
            try:
                tool_input = json.loads(tc['function']['arguments']) if isinstance(tc['function']['arguments'], str) else tc['function']['arguments']
            except (json.JSONDecodeError, TypeError):
                tool_input = {}
            content_blocks.append({
                'type': 'tool_use',
                'id': tc.get('id', f"toolu_{uuid.uuid4().hex[:12]}"),
                'name': tc['function']['name'],
                'input': tool_input
            })

    return {
        'id': internal['id'].replace('chatcmpl-', 'msg_'),
        'type': 'message',
        'role': 'assistant',
        'model': internal['model'],
        'content': content_blocks,
        'stop_reason': internal.get('finish_reason', 'end_turn'),
        'usage': {
            'input_tokens': internal.get('usage', {}).get('prompt_tokens', 0),
            'output_tokens': internal.get('usage', {}).get('completion_tokens', 0),
        },
    }


# ====================== HTTP 转发 ======================

def forward_to_provider(url, body, headers, timeout=None):
    """向厂商 API 发送 HTTP 请求并返回响应
    参数:
        url: 厂商 API 地址
        body: 请求体（dict，会自动序列化为 JSON）
        headers: 请求头（dict）
        timeout: 超时时间（秒），默认从配置读取
    返回:
        (response_dict, error_message) — 成功时 error 为 None
    """
    if timeout is None:
        timeout = current_app.config.get('RELAY_TIMEOUT', 120)
    # SSL 上下文：调试时跳过证书验证
    verify_ssl = current_app.config.get('RELAY_VERIFY_SSL', True)
    ssl_context = None if verify_ssl else ssl.create_default_context()
    if not verify_ssl:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    try:
        request_body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(url, data=request_body, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as resp:
            resp_body = json.loads(resp.read().decode('utf-8'))
        return resp_body, None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='ignore')
        try:
            error_json = json.loads(error_body)
            error_msg = error_json.get('error', {}).get('message', '') or str(error_json)
        except (json.JSONDecodeError, AttributeError):
            error_msg = error_body[:300]
        return None, f'厂商 API 返回错误 ({e.code}): {error_msg}'
    except urllib.error.URLError as e:
        print(f"[forward] ✗ URLError to {url[:60]}: {e.reason}", flush=True)
        return None, f'无法连接到厂商 API: {str(e.reason)}'
    except json.JSONDecodeError:
        print(f"[forward] ✗ JSONDecodeError from {url[:60]}", flush=True)
        return None, '厂商返回的不是有效 JSON'
    except Exception as e:
        print(f"[forward] ✗ Exception to {url[:60]}: {e}", flush=True)
        return None, f'请求失败: {str(e)}'


def format_chat_sse(msg_id, content, finish_reason, role=None, model='',
                    reasoning_content=''):
    """OpenAI Chat SSE 格式
    参数:
        reasoning_content: DeepSeek-R1/Mimo 等模型的思考过程文本
    """
    delta = {}
    if role:
        delta['role'] = role
        delta['content'] = content or ''    # role chunk 需要 content: ""
    elif content:
        delta['content'] = content
    # reasoning_content 保留在原位（OpenAI 非标准扩展，但 DeepSeek 客户端兼容）
    if reasoning_content:
        delta['reasoning_content'] = reasoning_content
    # finish chunk: delta 为空对象
    chunk = {
        'id': msg_id or f'chatcmpl-{uuid.uuid4().hex[:12]}',
        'object': 'chat.completion.chunk',
        'created': int(time.time()),
        'model': model,
        'choices': [{
            'index': 0,
            'delta': delta,
            'finish_reason': finish_reason,
        }],
    }
    return f'data: {json.dumps(chunk, ensure_ascii=False)}\n\n'


def format_responses_sse(event_type, resp_id='', msg_id='', model='',
                         delta=None, finish_reason=None, text='',
                         item_id=''):
    """OpenAI Responses SSE 格式 — 生成完整的流式事件序列
    event_type: created / output_item_added / content_part_added /
                delta / output_text_done / content_part_done / output_item_done / completed /
                reasoning_item_added / reasoning_part_added / reasoning_delta /
                reasoning_part_done / reasoning_item_done
    """
    # OpenAI Responses SSE 不需要 event: 行，只用 data: 行
    if event_type == 'created':
        chunk = {
            'type': 'response.created',
            'response': {
                'id': resp_id,
                'object': 'response',
                'status': 'in_progress',
                'model': model,
                'output': [],
            }
        }
    elif event_type == 'output_item_added':
        chunk = {
            'type': 'response.output_item.added',
            'output_index': 0,
            'item': {'id': msg_id, 'type': 'message', 'role': 'assistant', 'content': []},
        }
    elif event_type == 'content_part_added':
        chunk = {
            'type': 'response.content_part.added',
            'item_id': msg_id,
            'output_index': 0,
            'content_index': 0,
            'part': {'type': 'output_text', 'text': '', 'annotations': []},
        }
    elif event_type == 'delta':
        chunk = {
            'type': 'response.output_text.delta',
            'item_id': msg_id,
            'output_index': 0,
            'content_index': 0,
            'delta': delta or '',
        }
    elif event_type == 'output_text_done':
        chunk = {
            'type': 'response.output_text.done',
            'item_id': msg_id,
            'output_index': 0,
            'content_index': 0,
            'text': text,
        }
    elif event_type == 'content_part_done':
        chunk = {
            'type': 'response.content_part.done',
            'item_id': msg_id,
            'output_index': 0,
            'content_index': 0,
            'part': {'type': 'output_text', 'text': text, 'annotations': []},
        }
    elif event_type == 'output_item_done':
        chunk = {
            'type': 'response.output_item.done',
            'output_index': 0,
            'item': {
                'id': msg_id, 'type': 'message', 'role': 'assistant',
                'content': [{'type': 'output_text', 'text': text, 'annotations': []}],
            },
        }
    elif event_type == 'completed':
        chunk = {
            'type': 'response.completed',
            'response': {
                'id': resp_id,
                'object': 'response',
                'status': 'completed',
                'model': model,
            }
        }
    # ---- reasoning item 事件（DeepSeek-R1 等） ----
    elif event_type == 'reasoning_item_added':
        chunk = {
            'type': 'response.output_item.added',
            'output_index': 0,
            'item': {
                'id': item_id or msg_id,
                'type': 'reasoning',
                'content': [],
            },
        }
    elif event_type == 'reasoning_part_added':
        chunk = {
            'type': 'response.content_part.added',
            'item_id': item_id or msg_id,
            'output_index': 0,
            'content_index': 0,
            'part': {'type': 'reasoning_text', 'text': '', 'annotations': []},
        }
    elif event_type == 'reasoning_delta':
        chunk = {
            'type': 'response.reasoning_text.delta',
            'item_id': item_id or msg_id,
            'output_index': 0,
            'content_index': 0,
            'delta': delta or '',
        }
    elif event_type == 'reasoning_part_done':
        chunk = {
            'type': 'response.reasoning_text.done',
            'item_id': item_id or msg_id,
            'output_index': 0,
            'content_index': 0,
            'text': text,
        }
    elif event_type == 'reasoning_item_done':
        chunk = {
            'type': 'response.output_item.done',
            'output_index': 0,
            'item': {
                'id': item_id or msg_id,
                'type': 'reasoning',
                'content': [{'type': 'reasoning_text', 'text': text, 'annotations': []}],
            },
        }
    else:
        return f'data: {{}}\n\n'
    return f'data: {json.dumps(chunk, ensure_ascii=False)}\n\n'


# Anthropic SSE event_type → SSE event 行名称映射
_ANTHROPIC_SSE_EVENT_MAP = {
    'message_start':        'message_start',
    'content_block_start':  'content_block_start',
    'content_block_delta':  'content_block_delta',
    'content_block_stop':   'content_block_stop',
    'message_delta':        'message_delta',
    'message_stop':         'message_stop',
    'thinking_block_start': 'content_block_start',
    'thinking_delta':       'content_block_delta',
    'thinking_block_stop':  'content_block_stop',
    'ping':                 'ping',
}


def format_anthropic_sse(event_type, content='', finish_reason=None, model=''):
    """Anthropic Messages SSE 格式 — 生成完整的流式事件序列
    event_type: message_start / content_block_start / content_block_delta /
                content_block_stop / message_delta / message_stop /
                thinking_block_start / thinking_delta / thinking_block_stop
    """
    # 获取 SSE event 行名称
    sse_event = _ANTHROPIC_SSE_EVENT_MAP.get(event_type, 'message')
    if event_type == 'message_start':
        chunk = {
            'type': 'message_start',
            'message': {
                'id': f'msg_{uuid.uuid4().hex[:12]}',
                'type': 'message',
                'role': 'assistant',
                'model': model,
                'content': [],
                'stop_reason': None,
                'stop_sequence': None,
                'usage': {'input_tokens': 0, 'output_tokens': 0},
            }
        }
    elif event_type == 'content_block_start':
        chunk = {
            'type': 'content_block_start',
            'index': 0,
            'content_block': {'type': 'text', 'text': ''}
        }
    elif event_type == 'content_block_delta':
        chunk = {
            'type': 'content_block_delta',
            'index': 0,
            'delta': {'type': 'text_delta', 'text': content}
        }
    elif event_type == 'content_block_stop':
        chunk = {'type': 'content_block_stop', 'index': 0}
    elif event_type == 'message_delta':
        chunk = {
            'type': 'message_delta',
            'delta': {'stop_reason': finish_reason or 'end_turn'},
            'usage': {'output_tokens': 0}
        }
    elif event_type == 'message_stop':
        chunk = {'type': 'message_stop'}
    # ---- thinking block 事件（DeepSeek 等思考模型的推理过程） ----
    elif event_type == 'thinking_block_start':
        chunk = {
            'type': 'content_block_start',
            'index': 0,
            'content_block': {'type': 'thinking', 'thinking': ''}
        }
    elif event_type == 'thinking_delta':
        chunk = {
            'type': 'content_block_delta',
            'index': 0,
            'delta': {'type': 'thinking_delta', 'thinking': content}
        }
    elif event_type == 'thinking_block_stop':
        chunk = {'type': 'content_block_stop', 'index': 0}
    else:
        return f'event: {sse_event}\ndata: {{}}\n\n'
    return f'event: {sse_event}\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n'


# ====================== 主入口 ======================

def handle_relay(data, client_protocol, output_protocol=None):
    """转接请求主入口（非流式）
    参数:
        data: 客户端请求 JSON
        client_protocol: 'chat' / 'responses' / 'anthropic'（输入协议）
        output_protocol: 输出协议，None 表示与输入协议相同
    返回:
        (response_dict, status_code)
    """
    if output_protocol is None:            # 未指定则输出 = 输入
        output_protocol = client_protocol
    sanitize_data(data)                    # 清洗 "[undefined]" 等无效值
    # ① 客户端请求 → 内部格式
    if client_protocol == 'chat':
        internal = chat_to_internal(data)
    elif client_protocol == 'responses':
        internal = responses_to_internal(data)
    elif client_protocol == 'anthropic':
        internal = anthropic_to_internal(data)
    else:
        return {'error': f'不支持的协议: {client_protocol}'}, 400

    # ② 模型路由：查找对应厂商
    model_name = internal['model']
    provider_info, error = resolve_model(model_name)
    if error:
        return {'error': error}, 404

    # ③ 内容策略验证 — 拦截不合规请求，避免厂商报错
    valid, err_msg = validate_relay_request(internal, provider_info)
    if not valid:
        return {'error': err_msg}, 400

    # ④ 厂商适配器 — 根据厂商类型应用特殊处理
    adapter = get_adapter(provider_info['provider_name'])
    internal = adapter.prepare_request(internal, data, client_protocol)

    # ⑤ 内部格式 → 厂商格式请求
    provider_format = provider_info['api_format']
    if provider_format == 'openai':
        req_body, req_headers = internal_to_openai_request(
            internal, provider_info['api_key'], provider_info['model_id']
        )
    else:  # anthropic
        req_body, req_headers = internal_to_anthropic_request(
            internal, provider_info['api_key'], provider_info['model_id']
        )

    # ⑥ 发送请求到厂商
    resp_body, error = forward_to_provider(
        provider_info['api_url'], req_body, req_headers
    )
    if error:
        return {'error': error}, 502

    # ⑦ 厂商响应 → 内部格式
    if provider_format == 'openai':
        internal_resp = openai_response_to_internal(resp_body, model_name)
    else:  # anthropic
        internal_resp = anthropic_response_to_internal(resp_body, model_name)

    # ⑧ 适配器后处理响应
    internal_resp = adapter.process_response(internal_resp)

    # ⑨ 内部格式 → 客户端协议响应（使用输出协议）
    if output_protocol == 'chat':
        return internal_to_chat_response(internal_resp), 200
    elif output_protocol == 'responses':
        return internal_to_responses_response(internal_resp), 200
    else:  # anthropic
        return internal_to_anthropic_response(internal_resp), 200
