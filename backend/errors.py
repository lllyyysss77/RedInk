"""统一 API 错误模型和分类器。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Union


ERROR_TYPE_BASE = "https://redink.app/errors"


@dataclass
class AppError:
    code: str
    title: str
    detail: str
    suggestion: str
    status: int = 500
    retryable: bool = False
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    @property
    def type(self) -> str:
        return f"{ERROR_TYPE_BASE}/{self.code.lower().replace('_', '-')}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "code": self.code,
            "title": self.title,
            "detail": self.detail,
            "suggestion": self.suggestion,
            "status": self.status,
            "retryable": self.retryable,
            "diagnostics": self.diagnostics,
        }

    def to_message(self) -> str:
        if self.suggestion:
            return f"{self.title}：{self.suggestion}"
        return f"{self.title}：{self.detail}"


def error_payload(error: Union[AppError, Exception, str], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    app_error = ensure_app_error(error, context=context)
    return {
        "success": False,
        "error": app_error.to_dict(),
        "error_message": app_error.to_message(),
    }


def ensure_app_error(error: Union[AppError, Exception, str], context: Optional[Dict[str, Any]] = None) -> AppError:
    if isinstance(error, AppError):
        if context:
            diagnostics = dict(error.diagnostics)
            diagnostics.update(_sanitize_diagnostics(context))
            return AppError(
                code=error.code,
                title=error.title,
                detail=error.detail,
                suggestion=error.suggestion,
                status=error.status,
                retryable=error.retryable,
                diagnostics=diagnostics,
            )
        return error
    return classify_error(error, context=context)


def classify_error(error: Union[Exception, str], context: Optional[Dict[str, Any]] = None) -> AppError:
    raw = str(error)
    text = raw.lower()
    diagnostics = _sanitize_diagnostics(context or {})
    diagnostics["raw"] = _summarize_raw(raw, 1000)

    status, upstream_message = _extract_status_and_message(raw)
    if status:
        diagnostics["http_status"] = status
    if upstream_message:
        diagnostics["upstream_message"] = _truncate(upstream_message, 500)

    host = _extract_host(raw) or diagnostics.get("base_url") or diagnostics.get("host")
    endpoint = diagnostics.get("endpoint") or _extract_endpoint(raw)

    if _looks_like_proxy_refused(text):
        return AppError(
            code="PROXY_UNAVAILABLE",
            title="本机代理不可用",
            detail="请求需要经过本机代理，但代理端口没有响应。",
            suggestion="请确认代理客户端已开启，且 HTTP/HTTPS 代理端口正在监听；不使用代理时请关闭相关环境变量。",
            status=400,
            retryable=True,
            diagnostics=diagnostics,
        )

    if _looks_like_fake_ip_tls(text):
        detail = f"无法稳定连接到 {host}" if host else "上游 TLS 连接在握手阶段被断开。"
        return AppError(
            code="NETWORK_FAKE_IP_TLS",
            title="网络代理连接异常",
            detail=detail,
            suggestion="请确认代理客户端已开启，或关闭 Fake-IP DNS 后重试。",
            status=400,
            retryable=True,
            diagnostics=diagnostics,
        )

    if "不支持 /v1/chat/completions" in raw or (
        "not support" in text and "chat/completions" in text
    ) or (
        "unsupported" in text and "chat/completions" in text
    ):
        return AppError(
            code="MODEL_ENDPOINT_MISMATCH",
            title="模型与接口不匹配",
            detail=upstream_message or "当前模型不支持 OpenAI Chat Completions 接口。",
            suggestion="请在设置中换成支持该接口的文字模型，或调整该服务商的 endpoint_type。",
            status=400,
            retryable=False,
            diagnostics=diagnostics,
        )

    if "unknown parameter" in text and "response_format" in text:
        return AppError(
            code="UPSTREAM_PARAM_UNSUPPORTED",
            title="上游参数不兼容",
            detail="服务商不支持 response_format 参数。",
            suggestion="请移除该服务商配置里的 response_format，或使用已支持自动降级的新版本。",
            status=400,
            retryable=True,
            diagnostics=diagnostics,
        )

    if status in (400, 415) and (
        "json" in text
        or "unsupported media type" in text
        or "bad request" in text
        or "content-type" in text
    ):
        return AppError(
            code="INVALID_REQUEST",
            title="请求格式不正确",
            detail=upstream_message or "请求体不是有效的 JSON，或 Content-Type 不符合接口要求。",
            suggestion="请刷新页面后重试；如果是直接调用 API，请使用 application/json 并提交合法 JSON。",
            status=400,
            retryable=False,
            diagnostics=diagnostics,
        )

    if status == 405 or "405 not allowed" in text or "method not allowed" in text:
        endpoint_text = f" {endpoint}" if endpoint else ""
        return AppError(
            code="ENDPOINT_METHOD_MISMATCH",
            title="接口路径或请求方法不匹配",
            detail=f"上游不接受当前请求{endpoint_text}，通常是 Base URL 或 endpoint_type 配置不对。",
            suggestion="请确认该服务商支持 OpenAI 兼容接口，并检查 Base URL、/v1 路径和 endpoint_type 是否匹配服务商文档。",
            status=400,
            retryable=False,
            diagnostics=diagnostics,
        )

    if status in (401, 403) or any(keyword in text for keyword in [
        "unauthorized",
        "unauthenticated",
        "forbidden",
        "invalid api key",
        "api key 认证失败",
        "权限被拒绝",
    ]):
        return AppError(
            code="AUTH_OR_PERMISSION",
            title="API Key 或权限不可用",
            detail=upstream_message or "服务商拒绝了当前请求。",
            suggestion="请检查 API Key、账户权限、模型访问权限和余额。",
            status=401 if status == 401 else 403,
            retryable=False,
            diagnostics=diagnostics,
        )

    if status == 429 or any(keyword in text for keyword in ["rate limit", "resource_exhausted", "quota", "配额", "限流"]):
        return AppError(
            code="RATE_LIMITED",
            title="上游限流或配额不足",
            detail=upstream_message or "服务商暂时拒绝了过多请求。",
            suggestion="请稍后重试，或降低并发/检查账户配额。",
            status=429,
            retryable=True,
            diagnostics=diagnostics,
        )

    if status == 404 or ("model" in text and ("not found" in text or "不存在" in raw)):
        return AppError(
            code="MODEL_NOT_FOUND",
            title="模型或接口不存在",
            detail=upstream_message or "当前模型名称或接口地址无法访问。",
            suggestion="请检查服务商 Base URL、endpoint_type 和模型名称。",
            status=404,
            retryable=False,
            diagnostics=diagnostics,
        )

    if status and status >= 500:
        return AppError(
            code="UPSTREAM_UNAVAILABLE",
            title="上游服务异常",
            detail=upstream_message or f"服务商返回 HTTP {status}。",
            suggestion="请稍后重试；如果持续失败，请切换服务商或查看服务商状态。",
            status=502,
            retryable=True,
            diagnostics=diagnostics,
        )

    if _looks_like_timeout(text):
        return AppError(
            code="NETWORK_TIMEOUT",
            title="网络请求超时",
            detail=f"连接 {host} 超时。" if host else "请求等待时间过长。",
            suggestion="请检查网络、代理和服务商状态后重试。",
            status=504,
            retryable=True,
            diagnostics=diagnostics,
        )

    if _looks_like_network(text):
        return AppError(
            code="NETWORK_ERROR",
            title="网络连接失败",
            detail=f"无法连接到 {host}。" if host else "无法连接到上游服务。",
            suggestion="请检查网络连接、代理设置和 Base URL。",
            status=502,
            retryable=True,
            diagnostics=diagnostics,
        )

    if "历史记录不存在" in raw or "任务不存在" in raw or "不存在" in raw:
        return AppError(
            code="RESOURCE_NOT_FOUND",
            title="资源不存在",
            detail=raw.split("\n", 1)[0],
            suggestion="请返回历史列表刷新后重试。",
            status=404,
            retryable=False,
            diagnostics=diagnostics,
        )

    return AppError(
        code="UNKNOWN_ERROR",
        title="操作失败",
        detail=_first_meaningful_line(raw) or "发生未知错误。",
        suggestion="请稍后重试；如果持续失败，请复制诊断信息反馈。",
        status=500,
        retryable=True,
        diagnostics=diagnostics,
    )


def _sanitize_diagnostics(data: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if "api_key" in key.lower() or "authorization" in key.lower():
            sanitized[key] = "***"
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = _truncate(str(value), 500) if isinstance(value, str) else value
        else:
            sanitized[key] = _truncate(str(value), 500)
    return sanitized


def _extract_status_and_message(raw: str) -> Tuple[Optional[int], Optional[str]]:
    status = None
    status_match = re.search(r"(?:HTTP|状态码[:：]?)\s*[:：]?\s*(\d{3})", raw, re.IGNORECASE)
    if status_match:
        status = int(status_match.group(1))
    else:
        leading_status_match = re.search(r"^\s*(\d{3})\s+[A-Za-z]", raw)
        if leading_status_match:
            status = int(leading_status_match.group(1))

    json_match = re.search(r"(\{.*\})", raw, re.DOTALL)
    if json_match:
        try:
            payload = json.loads(json_match.group(1))
            error = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error, dict):
                message = error.get("message") or error.get("detail")
                if message:
                    return status, str(message)
            if isinstance(error, str):
                return status, error
        except Exception:
            pass

    original_match = re.search(r"【原始错误】\s*([\s\S]+)", raw)
    if original_match:
        return status, _first_meaningful_line(original_match.group(1))

    if "<html" in raw.lower() or "<!doctype" in raw.lower():
        return status, _summarize_html(raw)

    return status, None


def _extract_host(raw: str) -> Optional[str]:
    match = re.search(r"host='([^']+)'", raw)
    if match:
        return match.group(1)
    match = re.search(r"https?://([^/\s)]+)", raw)
    if match:
        return match.group(1)
    return None


def _extract_endpoint(raw: str) -> Optional[str]:
    match = re.search(r"url:\s*(/[^\s)]+)", raw, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"with url:\s*(/[^\s)]+)", raw, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"https?://[^/]+(/[^\s)]+)", raw)
    if match:
        return match.group(1)
    return None


def _looks_like_proxy_refused(text: str) -> bool:
    return (
        "proxyerror" in text
        and ("connection refused" in text or "failed to establish a new connection" in text)
    ) or (
        "127.0.0.1" in text and "7890" in text and "connection refused" in text
    )


def _looks_like_fake_ip_tls(text: str) -> bool:
    return (
        "ssleoferror" in text
        or "unexpected_eof_while_reading" in text
        or "ssl_error_syscall" in text
        or ("eof occurred" in text and "ssl" in text)
        or ("198.18." in text and "ssl" in text)
    )


def _looks_like_timeout(text: str) -> bool:
    return "timeout" in text or "timed out" in text or "超时" in text


def _looks_like_network(text: str) -> bool:
    return any(keyword in text for keyword in [
        "connectionerror",
        "connection aborted",
        "connection reset",
        "failed to establish a new connection",
        "network",
        "网络",
        "连接失败",
        "连接错误",
    ])


def _first_meaningful_line(value: str) -> str:
    for line in value.splitlines():
        stripped = line.strip(" \t\r\n-")
        if stripped:
            return stripped
    return ""


def _summarize_raw(value: str, limit: int) -> str:
    if "<html" in value.lower() or "<!doctype" in value.lower():
        return _truncate(_summarize_html(value), limit)
    return _truncate(value, limit)


def _summarize_html(value: str) -> str:
    text = value.replace("\\r", " ").replace("\\n", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or _first_meaningful_line(value)


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."
