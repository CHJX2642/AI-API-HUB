# -*- coding: utf-8 -*-
# AI API Hub — 网页内容抓取模块
# 使用 requests + BeautifulSoup 抓取网页并提取纯文本

import requests as http_requests       # HTTP 请求库（避免与 flask.request 冲突）
from bs4 import BeautifulSoup          # HTML 解析库
from flask import current_app          # 当前 Flask 应用上下文，用于读取配置


def fetch_url_content(url):
    """抓取网页内容：优先本地 requests，失败返回 None 让 AI 自行处理
    参数:
        url: 要抓取的网页 URL（必须以 http:// 或 https:// 开头）
    返回:
        提取的纯文本内容，或 None（抓取失败时）
    异常:
        ValueError: URL 格式不合法时抛出
    """
    # 验证 URL 格式
    if not url.startswith(('http://', 'https://')):
        raise ValueError('URL 必须以 http:// 或 https:// 开头')

    # 从 Flask 配置读取超时和长度限制
    timeout = current_app.config.get('URL_FETCH_TIMEOUT', 15)
    max_length = current_app.config.get('URL_MAX_LENGTH', 100000)

    # 模拟浏览器请求头，避免被反爬拦截
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }

    try:
        # 发送 GET 请求
        resp = http_requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)

        if resp.status_code == 403:       # 被 Cloudflare 等拦截
            return None                   # 返回 None，让 AI 自己处理

        resp.raise_for_status()           # 其他 HTTP 错误抛出异常
        resp.encoding = resp.apparent_encoding or 'utf-8'  # 自动检测编码

        # 解析 HTML 并去除无关标签
        soup = BeautifulSoup(resp.text, 'lxml')
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript']):
            tag.decompose()               # 移除这些标签及其内容

        # 提取纯文本
        text = soup.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        result = '\n'.join(lines)

        # 截断过长内容
        if len(result) > max_length:
            result = result[:max_length] + '\n\n[内容过长，已截断]'

        # 内容太短视为无效
        return result if len(result) > 20 else None

    except Exception:
        return None                       # 任何错误都返回 None，让 AI 自己处理
