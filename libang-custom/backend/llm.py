"""AI 深度分析模块 — 支持多种 LLM 后端（含重试机制）"""
import json
import os
import time
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的广告合规审查专家。请分析以下广告文案，找出其中的违规风险点。

要求：
1. 列出具体的违规词语和原因
2. 指出涉及的法律法规条款
3. 给出修改建议
4. 给出合规评分（0-100分）"""

# API Key 与对应 Base URL 的绑定映射
_KEY_URL_MAP = {
    "MIMO_API_KEY": ("MIMO_BASE_URL", "https://api.deepseek.com/v1"),
    "OPENAI_API_KEY": ("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    "DEEPSEEK_API_KEY": ("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
}

_KEY_MODEL_MAP = {
    "MIMO_API_KEY": "mimo/mimo-auto",
    "OPENAI_API_KEY": "gpt-4o-mini",
    "DEEPSEEK_API_KEY": "deepseek-chat",
}


def validate_config():
    """启动时校验 API Key 与 Base URL 是否匹配"""
    active_key_src = None
    api_key = ""
    for key_src in ["MIMO_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"]:
        val = os.environ.get(key_src, "")
        if val:
            active_key_src = key_src
            api_key = val
            break
    if not api_key:
        return False, "未配置任何 API Key"
    url_env, default_url = _KEY_URL_MAP[active_key_src]
    configured_url = os.environ.get(url_env, "")
    model = _get_model(active_key_src)
    actual_url = configured_url or default_url
    return True, f"LLM 配置: key={active_key_src}, url={actual_url}, model={model}"


def _get_config():
    active_key_src = None
    api_key = ""
    for key_src in ["MIMO_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"]:
        val = os.environ.get(key_src, "")
        if val:
            active_key_src = key_src
            api_key = val
            break
    if not api_key:
        return "", "", ""
    url_env, default_url = _KEY_URL_MAP[active_key_src]
    base_url = os.environ.get(url_env, default_url)
    model = _get_model(active_key_src)
    return api_key, base_url.rstrip("/"), model


def _get_model(active_key_src):
    model = os.environ.get("LLM_MODEL", "") or os.environ.get("OPENAI_MODEL", "")
    if model:
        return model
    return _KEY_MODEL_MAP.get(active_key_src, "deepseek-chat")


def analyze(text, industry="", timeout=60, max_retries=3):
    """调用 LLM 分析广告文案合规性（含指数退避重试）"""
    api_key, base_url, model = _get_config()
    if not api_key:
        return "AI 分析不可用：未配置 API Key"
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if industry:
        messages[0]["content"] += f"\n\n行业背景：{industry}"
    messages.append({"role": "user", "content": f"请分析以下广告文案：\n\n{text}"})
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2048,
    }
    data = json.dumps(body).encode("utf-8")
    url = f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            resp = urllib.request.urlopen(req, timeout=timeout)
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            status = e.code
            error_body = e.read().decode("utf-8", errors="replace")[:200]
            if 400 <= status < 500 and status not in (429, 503):
                return f"AI 分析失败 (HTTP {status}): {error_body}"
            last_error = f"HTTP {status}: {error_body}"
            logger.warning(f"LLM 请求失败 (尝试 {attempt}/{max_retries}): {last_error}")
        except urllib.error.URLError as e:
            last_error = f"网络错误: {e.reason}"
            logger.warning(f"LLM 网络错误 (尝试 {attempt}/{max_retries}): {last_error}")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"LLM 异常 (尝试 {attempt}/{max_retries}): {last_error}")
        if attempt < max_retries:
            sleep_time = 2 ** attempt
            time.sleep(sleep_time)
    return f"AI 分析失败（已重试 {max_retries} 次）: {last_error}"
