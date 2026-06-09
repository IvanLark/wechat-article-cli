"""wechat_article capability 的边界模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from wechat_article_cli._toolkit.protocol.models import DoctorCheckResult


class AuthStartOutput(BaseModel):
    qrcode_path: str


class AuthConfirmOutput(BaseModel):
    status: str
    qrcode_path: str | None = None
    expires_at: str | None = None
    raw_status: str | int | None = None


class AuthCheckOutput(BaseModel):
    status: Literal["not_logged_in", "expired", "valid"]
    created_at: str | None = None
    expires_at: str | None = None
    remaining_seconds: int | None = None


class AccountImportInput(BaseModel):
    json_path: str

    @field_validator("json_path")
    @classmethod
    def validate_json_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("json_path 不能为空")
        return normalized


class AccountImportOutput(BaseModel):
    json_path: str
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    invalid: int = 0


class AccountExportInput(BaseModel):
    json_path: str

    @field_validator("json_path")
    @classmethod
    def validate_json_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("json_path 不能为空")
        return normalized


class AccountExportOutput(BaseModel):
    json_path: str
    exported: int = 0


class ArticleListInput(BaseModel):
    name: str | None = None
    group_name: str | None = None
    count: int = 5
    offset: int = 0

    @field_validator("name", "group_name")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_target(self) -> "ArticleListInput":
        if not self.name and not self.group_name:
            raise ValueError("请指定公众号名称或分组")
        return self


class ArticleSummary(BaseModel):
    title: str
    link: str
    create_date: str = ""
    author: str = ""
    digest: str = ""
    cover: str = ""
    item_show_type: int = 0


class ArticleBatch(BaseModel):
    account_name: str
    items: list[ArticleSummary] = Field(default_factory=list)


class ArticleListOutput(BaseModel):
    batches: list[ArticleBatch] = Field(default_factory=list)
    total_articles: int


class ArticleContentInput(BaseModel):
    link: str
    fmt: Literal["md", "markdown", "html", "text"] = "md"
    output: str | None = None

    @field_validator("link")
    @classmethod
    def validate_link(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("link 不能为空")
        return normalized

    @field_validator("output")
    @classmethod
    def normalize_output(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ArticleContentOutput(BaseModel):
    title: str
    author: str | None = None
    publish_date: str | None = None
    format: Literal["markdown", "html", "text"]
    content: str
    output_path: str
    cached: bool = False
    content_length: int


class DoctorPayload(BaseModel):
    ok: bool
    capability: str = "wechat_article"
    auth_status: str
    proxy_configured: bool
    proxy_count: int
    account_count: int
    group_count: int
    task_count: int
    run_count: int
    checks: list[DoctorCheckResult] = Field(default_factory=list)
    summary: str | None = None
