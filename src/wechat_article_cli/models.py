"""wechat_article capability 的边界模型。"""

from __future__ import annotations

from typing import Any, Literal

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


class AccountListInput(BaseModel):
    group_name: str | None = None


class AccountSearchInput(BaseModel):
    query: str

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query 不能为空")
        return normalized


class AccountAddInput(BaseModel):
    names: str

    @field_validator("names")
    @classmethod
    def validate_names(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("names 不能为空")
        return normalized


class AccountRemoveInput(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name 不能为空")
        return normalized


class AccountRecord(BaseModel):
    fakeid: str
    name: str
    avatar: str | None = None
    signature: str | None = None
    added_at: str | None = None


class AccountSearchOutput(BaseModel):
    query: str
    accounts: list[AccountRecord] = Field(default_factory=list)
    total_accounts: int = 0


class AccountListOutput(BaseModel):
    group_name: str | None = None
    accounts: list[AccountRecord] = Field(default_factory=list)
    total_accounts: int = 0


class AccountAddOutput(BaseModel):
    added: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    not_found: list[str] = Field(default_factory=list)
    added_count: int = 0
    skipped_count: int = 0
    not_found_count: int = 0


class AccountRemoveOutput(BaseModel):
    name: str
    removed: bool = True


class GroupRecord(BaseModel):
    name: str
    accounts: list[str] = Field(default_factory=list)
    account_count: int = 0


class GroupListOutput(BaseModel):
    groups: list[GroupRecord] = Field(default_factory=list)
    total_groups: int = 0


class GroupImportInput(BaseModel):
    json_path: str

    @field_validator("json_path")
    @classmethod
    def validate_json_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("json_path 不能为空")
        return normalized


class GroupImportOutput(BaseModel):
    json_path: str
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    invalid: int = 0
    invalid_accounts: int = 0
    total_groups: int = 0


class GroupExportInput(BaseModel):
    json_path: str

    @field_validator("json_path")
    @classmethod
    def validate_json_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("json_path 不能为空")
        return normalized


class GroupExportOutput(BaseModel):
    json_path: str
    exported: int = 0


class GroupCreateOutput(BaseModel):
    name: str
    created: bool = True


class GroupDeleteOutput(BaseModel):
    name: str
    deleted: bool = True
    removed_accounts: int = 0


class GroupAddOutput(BaseModel):
    group_name: str
    added: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    not_in_lib: list[str] = Field(default_factory=list)
    added_count: int = 0
    skipped_count: int = 0
    not_in_lib_count: int = 0


class GroupRemoveOutput(BaseModel):
    group_name: str
    name: str
    removed: bool = True


class GroupCreateInput(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name 不能为空")
        return normalized


class GroupDeleteInput(GroupCreateInput):
    pass


class GroupAddInput(BaseModel):
    group_name: str
    names: str


class GroupRemoveInput(BaseModel):
    group_name: str
    name: str


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


class TaskConfigPayload(BaseModel):
    accounts: list[str] = Field(default_factory=list)
    group: str | None = None
    article_count: int
    account_interval: float
    after_date: str | None = None
    fetch_content: bool
    content_concurrency: int


class TaskRecord(BaseModel):
    task_id: str
    name: str
    created_at: str
    config: TaskConfigPayload


class TaskCreateInput(BaseModel):
    group_name: str | None = None
    accounts: list[str] | None = None
    name: str = ""
    article_count: int = 5
    account_interval: float = 10.0
    after_date: str | None = None
    fetch_content: bool = True
    content_concurrency: int = 3


class TaskIdInput(BaseModel):
    task_id: str


class TaskCreateOutput(BaseModel):
    task: TaskRecord


class TaskListOutput(BaseModel):
    tasks: list[TaskRecord] = Field(default_factory=list)
    total_tasks: int = 0


class TaskInfoOutput(BaseModel):
    task: TaskRecord


class AccountProgressPayload(BaseModel):
    name: str
    fakeid: str
    status: str
    articles_found: int = 0
    articles_new: int = 0
    articles_cached: int = 0
    content_failed: int = 0
    error: str | None = None


class RunStatisticsPayload(BaseModel):
    total_accounts: int = 0
    completed_accounts: int = 0
    failed_accounts: int = 0
    total_articles: int = 0
    new_articles: int = 0
    cached_articles: int = 0
    content_failed: int = 0


class RunRecord(BaseModel):
    run_id: str
    task_id: str
    status: str
    created_at: str
    updated_at: str
    config: TaskConfigPayload
    progress: list[AccountProgressPayload] = Field(default_factory=list)
    statistics: RunStatisticsPayload
    articles: list[dict[str, Any]] = Field(default_factory=list)


class TaskRunOutput(BaseModel):
    run: RunRecord


class RunListOutput(BaseModel):
    runs: list[RunRecord] = Field(default_factory=list)
    total_runs: int = 0


class RunStatusOutput(BaseModel):
    run: RunRecord
    failed_articles: list[dict[str, Any]] = Field(default_factory=list)


class RunExportOutput(BaseModel):
    run_id: str
    format: Literal["json", "csv", "excel"]
    path: str
    article_count: int


class RunIdInput(BaseModel):
    run_id: str


class RunExportInput(BaseModel):
    run_id: str
    format: Literal["json", "csv", "excel"] = "json"


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
