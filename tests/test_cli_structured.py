import json
from pathlib import Path

from click.testing import CliRunner

from wechat_article_cli.cli import cli
from wechat_article_cli.storage import (
    AccountProgress,
    Run,
    RunStatistics,
    TaskConfig,
    save_run,
)


def _invoke_json(runner: CliRunner, home: Path, args: list[str]) -> dict:
    result = runner.invoke(cli, args, env={"WECHAT_ARTICLE_HOME": str(home)})
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    return payload["data"]


def _write_accounts(path: Path) -> Path:
    accounts_path = path / "accounts.json"
    accounts_path.write_text(
        json.dumps(
            [
                {
                    "fakeid": "fakeid-1",
                    "name": "测试号",
                    "avatar": "https://example.test/avatar.png",
                    "signature": "用于自动化测试",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return accounts_path


def test_account_group_and_task_structured_output(tmp_path: Path) -> None:
    runner = CliRunner()
    accounts_path = _write_accounts(tmp_path)

    imported = _invoke_json(
        runner,
        tmp_path,
        ["account", "import", str(accounts_path), "--json", "--compact"],
    )
    assert imported["imported"] == 1

    accounts = _invoke_json(runner, tmp_path, ["account", "list", "--json", "--compact"])
    assert accounts["total_accounts"] == 1
    assert accounts["accounts"][0]["name"] == "测试号"

    created = _invoke_json(runner, tmp_path, ["group", "create", "测试分组", "--json", "--compact"])
    assert created == {"name": "测试分组", "created": True}

    added = _invoke_json(
        runner,
        tmp_path,
        ["group", "add", "测试分组", "测试号", "--json", "--compact"],
    )
    assert added["added"] == ["测试号"]

    groups = _invoke_json(runner, tmp_path, ["group", "list", "--json", "--compact"])
    assert groups["groups"][0]["account_count"] == 1

    groups_export_path = tmp_path / "groups.json"
    exported_groups = _invoke_json(
        runner,
        tmp_path,
        ["group", "export", str(groups_export_path), "--json", "--compact"],
    )
    assert exported_groups["exported"] == 1
    assert groups_export_path.exists()
    exported_group_data = json.loads(groups_export_path.read_text(encoding="utf-8"))
    assert exported_group_data == [{"name": "测试分组", "accounts": ["测试号"]}]

    imported_home = tmp_path / "imported-home"
    imported_groups = _invoke_json(
        runner,
        imported_home,
        ["group", "import", str(groups_export_path), "--json", "--compact"],
    )
    assert imported_groups["imported"] == 1
    assert imported_groups["total_groups"] == 1

    listed_imported_groups = _invoke_json(
        runner,
        imported_home,
        ["group", "list", "--json", "--compact"],
    )
    assert listed_imported_groups["groups"][0]["accounts"] == ["测试号"]

    task = _invoke_json(
        runner,
        tmp_path,
        [
            "task",
            "create",
            "--group",
            "测试分组",
            "--name",
            "测试任务",
            "--count",
            "2",
            "--no-content",
            "--json",
            "--compact",
        ],
    )
    assert task["task"]["name"] == "测试任务"
    assert task["task"]["config"]["fetch_content"] is False

    tasks = _invoke_json(runner, tmp_path, ["task", "list", "--json", "--compact"])
    assert tasks["total_tasks"] == 1


def test_run_status_and_export_structured_output(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setenv("WECHAT_ARTICLE_HOME", str(tmp_path))
    run = Run(
        run_id="run-test",
        task_id="task-test",
        status="failed",
        created_at="2026-06-09T00:00:00+00:00",
        updated_at="2026-06-09T00:00:00+00:00",
        config=TaskConfig(accounts=["测试号"], article_count=1, fetch_content=False),
        progress=[
            AccountProgress(
                name="测试号",
                fakeid="fakeid-1",
                status="completed",
                articles_found=1,
                content_failed=1,
            )
        ],
        statistics=RunStatistics(
            total_accounts=1,
            completed_accounts=1,
            total_articles=1,
            content_failed=1,
        ),
        articles=[
            {
                "title": "失败样本",
                "account_name": "测试号",
                "author": "",
                "create_date": "2026-06-09",
                "link": "https://mp.weixin.qq.com/s/not-real",
                "digest": "",
                "content_status": "failed",
                "content_error": "文章状态异常：参数错误",
            }
        ],
    )

    runner.invoke(cli, ["doctor", "--json"], env={"WECHAT_ARTICLE_HOME": str(tmp_path)})
    save_run(run)

    status = _invoke_json(runner, tmp_path, ["run", "status", "run-test", "--json", "--compact"])
    assert status["run"]["statistics"]["content_failed"] == 1
    assert status["failed_articles"][0]["content_error"] == "文章状态异常：参数错误"

    exported = _invoke_json(
        runner,
        tmp_path,
        ["run", "export", "run-test", "--format", "json", "--json", "--compact"],
    )
    assert exported["article_count"] == 1
    export_path = Path(exported["path"])
    assert export_path.exists()
    export_data = json.loads(export_path.read_text(encoding="utf-8"))
    assert export_data["articles"][0]["content_status"] == "failed"


def test_schema_exposes_structured_contracts(tmp_path: Path) -> None:
    runner = CliRunner()
    data = _invoke_json(runner, tmp_path, ["schema", "run.status", "--json", "--compact"])

    assert data["input_schema"]["title"] == "RunIdInput"
    assert data["output_schema"]["title"] == "RunStatusOutput"

    group_import = _invoke_json(runner, tmp_path, ["schema", "group.import", "--json", "--compact"])
    assert group_import["input_schema"]["title"] == "GroupImportInput"
    assert group_import["output_schema"]["title"] == "GroupImportOutput"

    group_export = _invoke_json(runner, tmp_path, ["schema", "group.export", "--json", "--compact"])
    assert group_export["input_schema"]["title"] == "GroupExportInput"
    assert group_export["output_schema"]["title"] == "GroupExportOutput"
