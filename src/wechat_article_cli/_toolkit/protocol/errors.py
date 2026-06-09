"""通用错误类型。"""

from __future__ import annotations

from typing import Any

from wechat_article_cli._toolkit.protocol.exit_codes import (
    AUTH_ERROR,
    GENERAL_ERROR,
    INVALID_ARGUMENT,
    UPSTREAM_ERROR,
)
from wechat_article_cli._toolkit.protocol.models import ErrorEnvelope, ErrorInfo


class ToolError(Exception):
    code = "tool_error"
    exit_code = GENERAL_ERROR

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_envelope(self) -> ErrorEnvelope:
        return ErrorEnvelope(error=ErrorInfo(code=self.code, message=self.message, details=self.details))


class ValidationError(ToolError):
    code = "validation_error"
    exit_code = INVALID_ARGUMENT


class AuthError(ToolError):
    code = "auth_error"
    exit_code = AUTH_ERROR


class ProviderError(ToolError):
    code = "provider_error"
    exit_code = UPSTREAM_ERROR


class NotFoundError(ToolError):
    code = "not_found"
    exit_code = GENERAL_ERROR


class ConflictError(ToolError):
    code = "conflict"
    exit_code = GENERAL_ERROR


class ExternalAPIError(ToolError):
    code = "external_api_error"
    exit_code = UPSTREAM_ERROR
