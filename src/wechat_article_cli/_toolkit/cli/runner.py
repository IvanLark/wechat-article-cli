"""统一执行流程。"""

from __future__ import annotations

import inspect
from typing import Any

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from wechat_article_cli._toolkit.describe.spec import BoundCommand
from wechat_article_cli._toolkit.protocol.errors import ValidationError


async def execute_bound_command(command: BoundCommand, raw_input: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    validated_input: Any = raw_input
    if command.input_model is not None:
        try:
            validated_input = command.input_model.model_validate(raw_input)
        except PydanticValidationError as exc:
            raise ValidationError(str(exc)) from exc

    result = command.handler(validated_input, *args, **kwargs)
    if inspect.isawaitable(result):
        result = await result

    if command.output_model is not None:
        try:
            if isinstance(result, BaseModel):
                result = command.output_model.model_validate(result.model_dump(mode="json"))
            else:
                result = command.output_model.model_validate(result)
        except PydanticValidationError as exc:
            raise ValidationError(str(exc)) from exc

    return result
