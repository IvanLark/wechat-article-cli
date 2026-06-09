"""环境变量读取、校验与脱敏展示。"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field


class EnvRequirement(BaseModel):
    name: str
    description: str | None = None
    required: bool = True
    secret: bool = False
    fallback_names: list[str] = Field(default_factory=list)


class EnvStatus(BaseModel):
    requested_name: str
    resolved_name: str | None = None
    present: bool
    secret: bool = False
    value_preview: str | None = None
    description: str | None = None


class EnvReport(BaseModel):
    ok: bool
    items: list[EnvStatus] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


def mask_secret(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}***{value[-2:]}"


def _preview_value(value: str, *, secret: bool) -> str:
    if secret:
        return mask_secret(value) or ""
    if len(value) <= 80:
        return value
    return f"{value[:77]}..."


def _resolve_candidates(requirement: EnvRequirement) -> tuple[str | None, str | None]:
    for candidate in [requirement.name, *requirement.fallback_names]:
        value = os.environ.get(candidate)
        if value:
            return value, candidate
    return None, None


def read_env(
    name: str,
    *fallback_names: str,
    required: bool = False,
    secret: bool = False,
) -> str | None:
    requirement = EnvRequirement(
        name=name,
        fallback_names=list(fallback_names),
        required=required,
        secret=secret,
    )
    value, resolved = _resolve_candidates(requirement)
    if required and value is None:
        raise ValueError(f"缺少环境变量：{name}")
    return value


def collect_env_report(requirements: list[EnvRequirement]) -> EnvReport:
    items: list[EnvStatus] = []
    missing: list[str] = []

    for requirement in requirements:
        value, resolved = _resolve_candidates(requirement)
        present = value is not None
        if requirement.required and not present:
            missing.append(requirement.name)
        items.append(
            EnvStatus(
                requested_name=requirement.name,
                resolved_name=resolved,
                present=present,
                secret=requirement.secret,
                value_preview=_preview_value(value, secret=requirement.secret) if value else None,
                description=requirement.description,
            )
        )

    return EnvReport(ok=not missing, items=items, missing=missing)
