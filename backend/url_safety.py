"""外部网页抓取的最小 SSRF 前置校验。"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse


def validate_public_http_url(url: str) -> None:
    """仅允许解析到公网地址的 HTTP(S) URL。"""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("仅支持有效的 HTTP(S) 网址")
    if parsed.username or parsed.password:
        raise ValueError("网址不能包含账号信息")
    try:
        addresses = {
            item[4][0] for item in socket.getaddrinfo(parsed.hostname, None)
        }
    except socket.gaierror as exc:
        raise ValueError("网址域名无法解析") from exc
    if not addresses:
        raise ValueError("网址域名无法解析")
    for address in addresses:
        if not ipaddress.ip_address(address).is_global:
            raise ValueError("不允许抓取内网、回环或保留地址")


async def get_public_redirect_safe(client, url: str, max_redirects: int = 3):
    """逐跳校验重定向目标，禁止 HTTP 客户端跟随到内网。"""
    current = url
    for _ in range(max_redirects + 1):
        validate_public_http_url(current)
        response = await client.get(current, follow_redirects=False)
        if response.is_redirect:
            location = response.headers.get("location")
            if not location:
                raise ValueError("重定向地址无效")
            current = urljoin(current, location)
            continue
        validate_public_http_url(str(response.url))
        return response
    raise ValueError("重定向次数超过限制")
