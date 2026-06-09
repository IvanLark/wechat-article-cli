"""运行时通用输出模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ConfigShowOutput(BaseModel):
    path: str
    values: dict[str, Any] = Field(default_factory=dict)


class ConfigMutationOutput(BaseModel):
    path: str
    key: str
    action: Literal["set", "unset"]
    value: Any | None = None


class SecretStatusItem(BaseModel):
    key: str
    configured: bool
    source: Literal["credentials", "env", "missing"]
    value_preview: str | None = None


class SecretListOutput(BaseModel):
    path: str
    items: list[SecretStatusItem] = Field(default_factory=list)


class SecretMutationOutput(BaseModel):
    path: str
    key: str
    action: Literal["set", "unset"]
