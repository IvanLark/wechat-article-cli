"""输出协议与错误模型。"""

from wechat_article_cli._toolkit.protocol.errors import (
    AuthError,
    ConflictError,
    ExternalAPIError,
    NotFoundError,
    ProviderError,
    ToolError,
    ValidationError,
)
from wechat_article_cli._toolkit.protocol.models import (
    DoctorCheckResult,
    DoctorReport,
    ErrorEnvelope,
    ErrorInfo,
    InspectReport,
    ListMeta,
    PageMeta,
    SchemaReport,
    SuccessEnvelope,
)
from wechat_article_cli._toolkit.protocol.output import (
    emit_ndjson,
    failure,
    print_error_json_and_exit,
    print_json,
    success,
)
from wechat_article_cli._toolkit.protocol.sanitize import (
    reject_dangerous_chars,
    sanitize_for_terminal,
)

__all__ = [
    "AuthError",
    "ConflictError",
    "DoctorCheckResult",
    "DoctorReport",
    "ErrorEnvelope",
    "ErrorInfo",
    "ExternalAPIError",
    "InspectReport",
    "ListMeta",
    "NotFoundError",
    "PageMeta",
    "ProviderError",
    "SchemaReport",
    "SuccessEnvelope",
    "ToolError",
    "ValidationError",
    "emit_ndjson",
    "failure",
    "print_error_json_and_exit",
    "print_json",
    "reject_dangerous_chars",
    "sanitize_for_terminal",
    "success",
]

