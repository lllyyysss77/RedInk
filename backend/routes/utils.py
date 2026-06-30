"""
API 路由工具函数

包含通用的日志记录、错误处理等辅助函数
"""

import logging
import traceback

from flask import jsonify

from backend.errors import AppError, ensure_app_error, error_payload

logger = logging.getLogger(__name__)


def log_request(endpoint: str, data: dict = None):
    """
    记录 API 请求日志

    Args:
        endpoint: API 端点路径
        data: 请求数据（会过滤敏感信息）
    """
    logger.info(f"📥 收到请求: {endpoint}")

    if data:
        # 过滤敏感信息和大数据（图片二进制）
        safe_data = {
            k: v for k, v in data.items()
            if k not in ['images', 'user_images'] and not isinstance(v, bytes)
        }

        # 对图片数据只显示数量
        if 'images' in data:
            safe_data['images'] = f"[{len(data['images'])} 张图片]"
        if 'user_images' in data:
            safe_data['user_images'] = f"[{len(data['user_images'])} 张图片]"

        logger.debug(f"  请求数据: {safe_data}")


def log_error(endpoint: str, error: Exception):
    """
    记录 API 错误日志

    Args:
        endpoint: API 端点路径
        error: 异常对象
    """
    logger.error(f"❌ 请求失败: {endpoint}")
    logger.error(f"  错误类型: {type(error).__name__}")
    logger.error(f"  错误信息: {str(error)}")
    logger.debug(f"  堆栈跟踪:\n{traceback.format_exc()}")


def api_error_response(error, status: int = None, context: dict = None):
    """返回统一结构化 API 错误响应。"""
    app_error = ensure_app_error(error, context=context)
    if status is not None:
        app_error.status = status
    status_code = app_error.status
    return jsonify(error_payload(app_error)), status_code


def validation_error(detail: str, suggestion: str = "请检查输入后重试") -> AppError:
    """构造参数校验错误。"""
    return AppError(
        code="INVALID_REQUEST",
        title="请求参数不完整",
        detail=detail,
        suggestion=suggestion,
        status=400,
        retryable=False,
    )


def normalize_error_result(result: dict, context: dict = None, fallback_status: int = 500) -> dict:
    """将 service 返回的旧格式错误转换为统一错误对象，同时保留兼容字段。"""
    if result.get("success", False):
        return result

    error = result.get("error") or result.get("error_message") or "操作失败"
    if isinstance(error, dict) and error.get("code"):
        error_obj = error
        error_message = result.get("error_message") or f"{error_obj.get('title', '操作失败')}：{error_obj.get('suggestion') or error_obj.get('detail', '')}"
    else:
        app_error = ensure_app_error(error, context=context)
        if app_error.status == 500 and fallback_status != 500:
            app_error.status = fallback_status
        error_obj = app_error.to_dict()
        error_message = app_error.to_message()

    next_result = dict(result)
    next_result["error"] = error_obj
    next_result["error_message"] = error_message
    return next_result


def mask_api_key(key: str) -> str:
    """
    遮盖 API Key，只显示前4位和后4位

    Args:
        key: 原始 API Key

    Returns:
        str: 遮盖后的 API Key
    """
    if not key:
        return ''
    if len(key) <= 8:
        return '*' * len(key)
    return key[:4] + '*' * (len(key) - 8) + key[-4:]


def prepare_providers_for_response(providers: dict) -> dict:
    """
    准备返回给前端的 providers 数据

    将 api_key 替换为脱敏版本，避免泄露

    Args:
        providers: 原始服务商配置字典

    Returns:
        dict: 处理后的服务商配置
    """
    result = {}
    for name, config in providers.items():
        provider_copy = config.copy()

        # 返回脱敏的 api_key
        if 'api_key' in provider_copy and provider_copy['api_key']:
            provider_copy['api_key_masked'] = mask_api_key(provider_copy['api_key'])
            # 不返回实际值，前端用空字符串表示"不修改"
            provider_copy['api_key'] = ''
        else:
            provider_copy['api_key_masked'] = ''
            provider_copy['api_key'] = ''

        result[name] = provider_copy

    return result
