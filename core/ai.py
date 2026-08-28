# core/ai.py
import time
from datetime import datetime, timedelta
from openai import OpenAI
from core.config import get_all_providers, save_providers

def get_enabled_providers():
    providers = get_all_providers()
    today = datetime.now().date().isoformat()
    available = []
    for p in providers:
        if not p.get("enabled", True):
            continue
        if p.get("last_reset_date") != today:
            p["used_today"] = 0
            p["fail_count"] = 0
            p["last_reset_date"] = today
            save_providers(providers)
        if p.get("max_requests_per_day", 0) > 0 and p.get("used_today", 0) >= p["max_requests_per_day"]:
            continue
        if p.get("fail_count", 0) >= 3:
            continue
        available.append(p)
    available.sort(key=lambda x: x.get("priority", 100))
    return available

def record_api_usage(provider_id, success):
    providers = get_all_providers()
    for p in providers:
        if p.get("id") == provider_id:
            if success:
                p["used_today"] = p.get("used_today", 0) + 1
                p["fail_count"] = 0
            else:
                p["fail_count"] = p.get("fail_count", 0) + 1
            break
    save_providers(providers)

def _chat(provider, messages):
    """调用单个提供商的chat接口，成功返回内容，失败抛异常"""
    client = OpenAI(
        api_key=provider.get("api_key"),
        base_url=provider.get("base_url"),
        timeout=provider.get("timeout", 30)
    )
    response = client.chat.completions.create(
        model=provider["model_name"],
        messages=messages,
        temperature=0.8,
        stream=False
    )
    return response.choices[0].message.content

def call_ai_with_fallback(prompt, system_override=None):
    providers = get_enabled_providers()
    if not providers:
        return None
    messages = [{"role": "system", "content": system_override or "你是一个友好的AI助手"},
                {"role": "user", "content": prompt}]
    return _call_providers(providers, messages)

def call_with_messages(messages, model_override=None):
    """直接发送完整消息列表给AI。model_override：优先使用模型名匹配的提供商。"""
    providers = get_enabled_providers()
    if not providers:
        return None
    if model_override:
        matched = [p for p in providers if p.get("model_name") == model_override]
        if matched:
            return _call_providers(matched, messages)
        print(f"群指定模型「{model_override}」未在可用提供商中找到，回退默认")
    return _call_providers(providers, messages)

def _call_providers(providers, messages):
    """按优先级依次尝试所有提供商，成功即返回，全部失败返回None"""
    for provider in providers:
        try:
            content = _chat(provider, messages)
            if content:
                record_api_usage(provider["id"], True)
                return content
        except Exception as e:
            print(f"API {provider.get('name')} 调用失败: {e}")
            record_api_usage(provider["id"], False)
            continue
    return None