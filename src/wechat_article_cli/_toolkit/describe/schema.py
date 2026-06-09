"""schema 报告生成。"""

from __future__ import annotations

from pydantic import BaseModel

from wechat_article_cli._toolkit.describe.spec import CommandSpec
from wechat_article_cli._toolkit.protocol.models import SchemaReport


def _schema_for(model: type[BaseModel] | None) -> dict | None:
    if model is None:
        return None
    return model.model_json_schema()


def build_schema_report(
    spec: CommandSpec,
    *,
    input_model: type[BaseModel] | None = None,
    output_model: type[BaseModel] | None = None,
) -> SchemaReport:
    return SchemaReport(
        command=spec.path,
        input_schema=_schema_for(input_model),
        output_schema=_schema_for(output_model),
    )

