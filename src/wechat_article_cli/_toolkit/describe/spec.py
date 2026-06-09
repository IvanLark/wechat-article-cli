"""命令与 capability 元数据定义。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from wechat_article_cli._toolkit.runtime.env import EnvRequirement


class ExampleSpec(BaseModel):
    command: str
    description: str = ""


class ArgumentSpec(BaseModel):
    name: str
    description: str = ""
    required: bool = True
    positional: bool = True
    value_type: str = "string"


class OptionSpec(BaseModel):
    name: str
    description: str = ""
    required: bool = False
    value_type: str = "string"
    choices: list[str] = Field(default_factory=list)


class OutputSpec(BaseModel):
    supports_human: bool = True
    supports_json: bool = True
    supports_yaml: bool = False
    supports_stream: bool = False


class DoctorCheckSpec(BaseModel):
    name: str
    description: str = ""


class CommandSpec(BaseModel):
    name: str
    path: str
    summary: str
    description: str = ""
    when_to_use: str = ""
    prerequisites: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    failure_recovery: list[str] = Field(default_factory=list)
    arguments: list[ArgumentSpec] = Field(default_factory=list)
    options: list[OptionSpec] = Field(default_factory=list)
    examples: list[ExampleSpec] = Field(default_factory=list)
    env: list[EnvRequirement] = Field(default_factory=list)
    output: OutputSpec = Field(default_factory=OutputSpec)
    supports_dry_run: bool = False
    auth_mode: Literal["none", "optional", "required", "write"] = "optional"
    mutating: bool = False


class CapabilitySpec(BaseModel):
    name: str
    kind: Literal["source", "transform", "store"]
    summary: str
    description: str = ""
    cli_name: str | None = None
    background: str = ""
    when_to_use: str = ""
    quick_start: list[ExampleSpec] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    commands: list[CommandSpec] = Field(default_factory=list)
    env: list[EnvRequirement] = Field(default_factory=list)
    doctor_checks: list[DoctorCheckSpec] = Field(default_factory=list)


@dataclass(slots=True)
class BoundCommand:
    spec: CommandSpec
    input_model: type[BaseModel] | None
    output_model: type[BaseModel] | None
    handler: Callable[..., Any]
    render_human: Callable[..., None] | None = None
