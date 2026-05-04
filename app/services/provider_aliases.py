# -*- coding: utf-8 -*-
# AI API Hub — 提供商名称别名映射模块
# 用于将各种中英文别名归一化为标准标识名，实现去重匹配

# 别名映射字典：键为各种可能的别名（中文、英文、缩写），值为标准标识名
PROVIDER_ALIASES = {
    # 小米 / mimo 系列
    '小米': 'xiaomi', 'mimo': 'xiaomi', 'xiaomi': 'xiaomi', '小米大模型': 'xiaomi',
    # 豆包 / 火山引擎 / 字节跳动
    '豆包': 'volcengine', '火山': 'volcengine', 'volcengine': 'volcengine',
    'doubao': 'volcengine', 'bytedance': 'volcengine', '字节': 'volcengine',
    # 通义千问 / 阿里云
    '通义': 'alibaba', '通义千问': 'alibaba', 'qwen': 'alibaba', '阿里': 'alibaba',
    'alibaba': 'alibaba', 'dashscope': 'alibaba', 'tongyi': 'alibaba',
    # 文心一言 / 百度
    '文心': 'baidu', '文心一言': 'baidu', 'ernie': 'baidu', '百度': 'baidu',
    'baidu': 'baidu', 'qianfan': 'baidu',
    # 智谱 / ChatGLM
    '智谱': 'zhipu', 'zhipu': 'zhipu', 'chatglm': 'zhipu', 'glm': 'zhipu',
    # 月之暗面 / Kimi
    '月之暗面': 'moonshot', 'kimi': 'moonshot', 'moonshot': 'moonshot',
    # DeepSeek / 深度求索
    'deepseek': 'deepseek', '深度求索': 'deepseek',
    # 讯飞 / 星火
    '讯飞': 'spark', '星火': 'spark', 'spark': 'spark', 'xfyun': 'spark', 'iFlytek': 'spark',
    # 零一万物 / Yi
    '零一万物': 'yi', 'yi': 'yi', '01.ai': 'yi',
    # 百川
    '百川': 'baichuan', 'baichuan': 'baichuan',
    # MiniMax
    'minimax': 'minimax',
    # OpenAI / ChatGPT / GPT
    'openai': 'openai', 'chatgpt': 'openai', 'gpt': 'openai',
    # Anthropic / Claude
    'anthropic': 'anthropic', 'claude': 'anthropic',
    # Google / Gemini
    'google': 'google', 'gemini': 'google',
    # Mistral
    'mistral': 'mistral',
    # Groq
    'groq': 'groq',
    # 硅基流动
    '硅基流动': 'siliconflow', 'siliconflow': 'siliconflow',
    # 阶跃星辰
    '阶跃星辰': 'stepfun', 'stepfun': 'stepfun', 'step': 'stepfun',
}


def normalize_provider_name(name, display_name=''):
    """将提供商名称归一化为标准标识名，用于去重匹配
    参数:
        name: 英文标识名（如 'mimo'）
        display_name: 显示名称（如 '小米大模型'）
    返回:
        标准标识名（如 'xiaomi'）
    """
    name_lower = name.lower().strip()           # 转小写并去空格
    display_lower = display_name.lower().strip() # 显示名称转小写

    # 优先用 name 匹配别名表
    if name_lower in PROVIDER_ALIASES:
        return PROVIDER_ALIASES[name_lower]

    # 其次用 display_name 匹配别名表
    if display_lower in PROVIDER_ALIASES:
        return PROVIDER_ALIASES[display_lower]

    # 都没匹配到，返回原始 name（小写）
    return name_lower
