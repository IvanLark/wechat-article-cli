"""结构化响应模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1"


class ErrorInfo(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class SuccessEnvelope(BaseModel):
    ok: Literal[True] = True
    schema_version: str = SCHEMA_VERSION
    data: Any
    meta: dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    ok: Literal[False] = False
    schema_version: str = SCHEMA_VERSION
    error: ErrorInfo


class ListMeta(BaseModel):
    count: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None
    message: str | None = None


class PageMeta(BaseModel):
    page: int | None = None
    pages: int | None = None
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None


class DoctorCheckResult(BaseModel):
    name: str
    ok: bool
    message: str
    hint: str | None = None
    details: dict[str, Any] | None = None


class DoctorReport(BaseModel):
    ok: bool
    capability: str
    checks: list[DoctorCheckResult] = Field(default_factory=list)
    summary: str | None = None


class InspectReport(BaseModel):
    path: str
    summary: str
    description: str = ""
    when_to_use: str = ""
    prerequisites: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    failure_recovery: list[str] = Field(default_factory=list)
    env: list[dict[str, Any]] = Field(default_factory=list)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    examples: list[dict[str, str]] = Field(default_factory=list)


class SchemaReport(BaseModel):
    command: str
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
