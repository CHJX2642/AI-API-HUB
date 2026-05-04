# -*- coding: utf-8 -*-
# AI API Hub — AI 服务调用模块
# 支持 OpenAI 和 Anthropic 两种 API 格式，调用大模型进行文档解析

import json                            # JSON 序列化/反序列化
import urllib.request                  # HTTP 请求模块，用于调用 AI API
import urllib.error                    # HTTP 错误处理
from flask import jsonify, current_app # Flask 工具：JSON 响应、当前应用上下文
from app.database import get_db        # 数据库连接函数

# AI 解析的系统提示词，要求返回标准 JSON 格式
AI_PARSE_PROMPT = """你是一个 API 信息提取助手。用户会给你一段关于 AI 大模型 API 的文档或描述，你需要从中提取结构化的提供商和模型信息。

请严格按以下 JSON 格式返回，不要包含任何其他文字：
{
  "providers": [
    {
      "name": "英文标识名，如 openai",
      "display_name": "显示名称，如 OpenAI",
      "base_url": "API 基础 URL",
      "api_urls": [
        {"label": "URL名称，如OpenAI-按量", "url": "完整API地址", "format": "openai或anthropic"}
      ],
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
          "price_input": 输入价格每百万tokens(1M)，单位人民币元(数字或null),
          "price_input_cached": 缓存命中输入价格每百万tokens(1M)，单位人民币元(数字或null),
          "price_output": 输出价格每百万tokens(1M)，单位人民币元(数字或null)
        }
      ]
    }
  ]
}

规则：
- 如果文档中没有提到某个字段，设为 null
- category 根据厂商判断：国内厂商用 domestic，国外用 international，不确定用 other
- 价格统一使用 "每百万tokens(1M)" 为单位，如果是其他格式请转换
- name 使用英文小写标准标识名，如：openai, anthropic, google, deepseek, alibaba/qwen, baidu, zhipu, moonshot, volcengine, xiaomi, spark, yi, baichuan, minimax, siliconflow, stepfun, mistral, groq
- 如果文档中没有模型信息，models 可以为空数组
- 只返回 JSON，不要有其他任何内容"""


def call_ai_service(messages):
    """调用 AI 服务并返回解析结果（支持 OpenAI 和 Anthropic 两种格式）
    参数:
        messages: 消息列表，格式为 [{'role': 'system', 'content': '...'}, {'role': 'user', 'content': '...'}]
    返回:
        成功时返回解析后的 Python 对象（dict/list）
        失败时返回 (jsonify(error), status_code) 元组
    """
    # ====== 从数据库读取 AI 配置 ======
    conn = get_db()
    try:
        settings = {}                           # 存储所有设置项
        rows = conn.execute('SELECT key, value FROM app_settings').fetchall()
        for row in rows:                        # 遍历设置项构建字典
            settings[row['key']] = row['value']
        ai_url = settings.get('ai_url', '')     # AI API 完整地址
        ai_api_key = settings.get('ai_api_key', '')  # API 密钥
        ai_model = settings.get('ai_model', '')      # 模型名称
        ai_format = settings.get('ai_format', 'openai')  # API 格式：openai 或 anthropic

        # 检查必要配置是否完整
        if not ai_url or not ai_api_key or not ai_model:
            return jsonify({'error': '请先在「AI设置」中配置 AI 服务的 URL、API Key 和模型名'}), 400
    finally:
        conn.close()                            # 确保关闭数据库连接

    # 从 Flask 配置读取超时和 token 限制
    timeout = current_app.config.get('AI_REQUEST_TIMEOUT', 60)
    max_tokens = current_app.config.get('AI_MAX_TOKENS', 4000)

    # ====== Anthropic 格式 ======
    if ai_format == 'anthropic':
        system_text = ''                        # 系统提示词
        user_messages = []                      # 用户消息列表
        for msg in messages:                    # 分离系统消息和用户消息
            if msg['role'] == 'system':
                system_text = msg['content']
            else:
                user_messages.append(msg)

        # 构建请求体
        body = {
            'model': ai_model,                  # 模型名称
            'max_tokens': max_tokens,           # 最大输出 token
            'messages': user_messages           # 用户消息列表
        }
        if system_text:                         # 系统提示词作为单独字段
            body['system'] = system_text

        request_body = json.dumps(body).encode('utf-8')   # 序列化为 JSON 字节
        headers = {
            'Content-Type': 'application/json',           # 内容类型
            'x-api-key': ai_api_key,                      # Anthropic 认证头
            'anthropic-version': '2023-06-01'              # API 版本
        }

        # 发送 HTTP 请求
        req = urllib.request.Request(ai_url, data=request_body, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            response_data = json.loads(resp.read().decode('utf-8'))

        # 提取响应内容（Anthropic 格式：content[0].text）
        ai_content = response_data['content'][0]['text']

    # ====== OpenAI 格式 ======
    else:
        # 构建请求体
        request_body = json.dumps({
            'model': ai_model,                  # 模型名称
            'messages': messages,               # 完整消息列表
            'temperature': 0.1,                 # 低温度确保输出稳定
            'max_tokens': max_tokens            # 最大输出 token
        }).encode('utf-8')

        headers = {
            'Content-Type': 'application/json',           # 内容类型
            'Authorization': f'Bearer {ai_api_key}'       # OpenAI 认证头
        }

        # 发送 HTTP 请求
        req = urllib.request.Request(ai_url, data=request_body, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            response_data = json.loads(resp.read().decode('utf-8'))

        # 提取响应内容（OpenAI 格式：choices[0].message.content）
        ai_content = response_data['choices'][0]['message']['content']

    # ====== 处理 AI 返回内容 ======
    ai_content = ai_content.strip()             # 去除首尾空白
    # 如果 AI 返回了 markdown 代码块，提取其中的 JSON
    if ai_content.startswith('```'):
        lines = ai_content.split('\n')
        ai_content = '\n'.join(lines[1:-1])     # 去掉首尾的 ``` 行
        ai_content = ai_content.strip()

    return json.loads(ai_content)               # 解析 JSON 并返回
