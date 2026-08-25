"""独立的消费者端纯文字 API；部署时仅由同源 Nginx 精确路径代理。"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from llm import LLMClient, ReviewIncompleteError
from weiquan_consumer import (
    ConsumerAnalysisService,
    ConsumerInputError,
    InvalidProviderResponseError,
    ProviderUnavailableError,
)
from weiquan_business import BusinessAnalysisService, InvalidBusinessResponseError


logger = logging.getLogger(__name__)
REQUESTS_PER_MINUTE = 20
REQUEST_WINDOW_SECONDS = 60
MAX_INFLIGHT_REQUESTS = 2

app = FastAPI(title="消费维权助手消费者端", docs_url=None, redoc_url=None, openapi_url=None)
_request_times: deque[float] = deque()
_rate_lock = asyncio.Lock()
_inflight = asyncio.Semaphore(MAX_INFLIGHT_REQUESTS)


class ConsumerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


class DeepSeekConsumerProvider:
    """复用既有服务端 DeepSeek 客户端；不创建浏览器端 Key 或 mock 兜底。"""

    def __init__(self) -> None:
        self._client = LLMClient()

    async def chat(self, messages: list[dict[str, str]], *, temperature: float, max_tokens: int) -> str:
        try:
            return await self._client.chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
        except (ReviewIncompleteError, httpx.TimeoutException) as exc:
            raise ProviderUnavailableError("provider unavailable") from exc


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message}, headers={"X-Request-ID": str(uuid.uuid4())})


def _log_provider_outcome(endpoint: str, status: int, started: float, exc: BaseException | None = None) -> None:
    """仅记录无正文的运维元数据，供 Provider 稳定性排查。"""
    latency_ms = int((time.monotonic() - started) * 1000)
    error_type = type(exc.__cause__).__name__ if exc and exc.__cause__ else type(exc).__name__ if exc else "none"
    logger.warning(
        "weiquan provider outcome endpoint=%s status=%d latency_ms=%d error_type=%s",
        endpoint,
        status,
        latency_ms,
        error_type,
    )


@app.middleware("http")
async def no_case_cache(request: Request, call_next):
    response = await call_next(request)
    if request.url.path in {"/api/consumer", "/api/business"}:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(_: Request, __: RequestValidationError) -> JSONResponse:
    return _error(400, "请以文字描述争议情况，并删除无关敏感信息。")


async def _take_rate_limit_slot() -> bool:
    now = time.monotonic()
    async with _rate_lock:
        while _request_times and now - _request_times[0] >= REQUEST_WINDOW_SECONDS:
            _request_times.popleft()
        if len(_request_times) >= REQUESTS_PER_MINUTE:
            return False
        _request_times.append(now)
        return True


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/api/consumer")
async def consumer_analysis(payload: ConsumerRequest) -> JSONResponse:
    if not await _take_rate_limit_slot():
        return _error(429, "当前请求较多，请稍后再试。")
    started = time.monotonic()
    try:
        async with _inflight:
            result = await ConsumerAnalysisService(DeepSeekConsumerProvider()).analyze(payload.text)
        return JSONResponse(status_code=200, content=result)
    except ConsumerInputError as exc:
        return _error(400, str(exc))
    except InvalidProviderResponseError:
        _log_provider_outcome("consumer", 502, started)
        return _error(502, "智能分析暂未返回可用结果，请稍后重试。")
    except ProviderUnavailableError as exc:
        _log_provider_outcome("consumer", 503, started, exc)
        return _error(503, "智能分析服务当前不可用，请稍后重试。")
    except Exception as exc:  # Do not log raw request/model data or exception text.
        _log_provider_outcome("consumer", 500, started, exc)
        return _error(500, "暂时无法完成分析，请稍后重试。")


@app.post("/api/business")
async def business_analysis(payload: ConsumerRequest) -> JSONResponse:
    if not await _take_rate_limit_slot():
        return _error(429, "当前请求较多，请稍后再试。")
    started = time.monotonic()
    try:
        async with _inflight:
            result = await BusinessAnalysisService(DeepSeekConsumerProvider()).analyze(payload.text)
        return JSONResponse(status_code=200, content=result)
    except ConsumerInputError as exc:
        return _error(400, str(exc))
    except InvalidBusinessResponseError:
        _log_provider_outcome("business", 502, started)
        return _error(502, "智能分析暂未返回可用结果，请稍后重试。")
    except ProviderUnavailableError as exc:
        _log_provider_outcome("business", 503, started, exc)
        return _error(503, "智能分析服务当前不可用，请稍后重试。")
    except Exception as exc:  # Do not log raw request/model data or exception text.
        _log_provider_outcome("business", 500, started, exc)
        return _error(500, "暂时无法完成分析，请稍后重试。")
