"""自描述能力。"""

from wechat_article_cli._toolkit.describe.doctor import BoundDoctorCheck, run_doctor
from wechat_article_cli._toolkit.describe.inspect import build_inspect_report
from wechat_article_cli._toolkit.describe.schema import build_schema_report
from wechat_article_cli._toolkit.describe.spec import (
    ArgumentSpec,
    BoundCommand,
    CapabilitySpec,
    CommandSpec,
    DoctorCheckSpec,
    ExampleSpec,
    OptionSpec,
    OutputSpec,
)

__all__ = [
    "ArgumentSpec",
    "BoundCommand",
    "BoundDoctorCheck",
    "CapabilitySpec",
    "CommandSpec",
    "DoctorCheckSpec",
    "ExampleSpec",
    "OptionSpec",
    "OutputSpec",
    "build_inspect_report",
    "build_schema_report",
    "run_doctor",
]

