"""doctor 框架。"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable

from wechat_article_cli._toolkit.describe.spec import DoctorCheckSpec
from wechat_article_cli._toolkit.protocol.models import DoctorCheckResult, DoctorReport


@dataclass(slots=True)
class BoundDoctorCheck:
    spec: DoctorCheckSpec
    runner: Callable[[], Any]


async def run_doctor(capability: str, checks: list[BoundDoctorCheck]) -> DoctorReport:
    results: list[DoctorCheckResult] = []

    for bound in checks:
        try:
            raw = bound.runner()
            if inspect.isawaitable(raw):
                raw = await raw

            if isinstance(raw, DoctorCheckResult):
                result = raw
            elif isinstance(raw, dict):
                result = DoctorCheckResult(name=bound.spec.name, **raw)
            elif isinstance(raw, bool):
                result = DoctorCheckResult(
                    name=bound.spec.name,
                    ok=raw,
                    message="ok" if raw else "failed",
                )
            else:
                result = DoctorCheckResult(
                    name=bound.spec.name,
                    ok=True,
                    message=str(raw),
                )
        except Exception as exc:
            result = DoctorCheckResult(
                name=bound.spec.name,
                ok=False,
                message=str(exc),
            )

        results.append(result)

    ok = all(item.ok for item in results)
    summary = "all checks passed" if ok else "some checks failed"
    return DoctorReport(ok=ok, capability=capability, checks=results, summary=summary)

