"""inspect 报告生成。"""

from __future__ import annotations

from pydantic import BaseModel

from wechat_article_cli._toolkit.describe.spec import CommandSpec
from wechat_article_cli._toolkit.protocol.models import InspectReport


def _schema_for(model: type[BaseModel] | None) -> dict | None:
    if model is None:
        return None
    return model.model_json_schema()


def build_inspect_report(
    spec: CommandSpec,
    *,
    input_model: type[BaseModel] | None = None,
    output_model: type[BaseModel] | None = None,
) -> InspectReport:
    return InspectReport(
        path=spec.path,
        summary=spec.summary,
        description=spec.description,
        when_to_use=spec.when_to_use,
        prerequisites=list(spec.prerequisites),
        next_steps=list(spec.next_steps),
        failure_recovery=list(spec.failure_recovery),
        env=[req.model_dump(mode="json", exclude_none=True) for req in spec.env],
        input_schema=_schema_for(input_model),
        output_schema=_schema_for(output_model),
        examples=[example.model_dump(mode="json", exclude_none=True) for example in spec.examples],
    )
