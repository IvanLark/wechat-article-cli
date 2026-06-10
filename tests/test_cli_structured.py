import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from wechat_article_cli.cli import cli
from wechat_article_cli.storage import (
    AccountProgress,
    Run,
    RunStatistics,
    TaskConfig,
    save_run,
)


def _invoke_json(
    runner: CliRunner,
    home: Path,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
) -> dict:
    command_env = {
        "WECHAT_ARTICLE_HOME": str(home),
        "WECHAT_PROXY_URL": "",
        "WECHAT_PROXY_TOKEN": "",
    }
    if env:
        command_env.update(env)
    result = runner.invoke(cli, args, env=command_env)
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

    library_path = tmp_path / "wechat-library.json"
    exported_library = _invoke_json(
        runner,
        tmp_path,
        ["library", "export", str(library_path), "--json", "--compact"],
    )
    assert exported_library["exported_accounts"] == 1
    assert exported_library["exported_groups"] == 1
    library_data = json.loads(library_path.read_text(encoding="utf-8"))
    assert library_data["schema_version"] == "1"
    assert library_data["accounts"][0]["name"] == "测试号"
    assert library_data["groups"] == [{"name": "测试分组", "accounts": ["测试号"]}]

    library_home = tmp_path / "library-home"
    imported_library = _invoke_json(
        runner,
        library_home,
        ["library", "import", str(library_path), "--json", "--compact"],
    )
    assert imported_library["accounts"]["imported"] == 1
    assert imported_library["groups"]["imported"] == 1
    assert imported_library["groups"]["missing_accounts"] == []

    library_accounts = _invoke_json(
        runner,
        library_home,
        ["account", "list", "--json", "--compact"],
    )
    assert library_accounts["accounts"][0]["fakeid"] == "fakeid-1"

    library_groups = _invoke_json(
        runner,
        library_home,
        ["group", "list", "--json", "--compact"],
    )
    assert library_groups["groups"][0]["accounts"] == ["测试号"]

    library_task = _invoke_json(
        runner,
        library_home,
        [
            "task",
            "create",
            "--group",
            "测试分组",
            "--name",
            "导入后任务",
            "--count",
            "1",
            "--no-content",
            "--json",
            "--compact",
        ],
    )
    assert library_task["task"]["config"]["group"] == "测试分组"

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

    library_import = _invoke_json(
        runner,
        tmp_path,
        ["schema", "library.import", "--json", "--compact"],
    )
    assert library_import["input_schema"]["title"] == "LibraryImportInput"
    assert library_import["output_schema"]["title"] == "LibraryImportOutput"

    library_export = _invoke_json(
        runner,
        tmp_path,
        ["schema", "library.export", "--json", "--compact"],
    )
    assert library_export["input_schema"]["title"] == "LibraryExportInput"
    assert library_export["output_schema"]["title"] == "LibraryExportOutput"


def test_config_commands_and_proxy_resolution(tmp_path: Path) -> None:
    runner = CliRunner()
    secret = "secret-token-value"

    config_path = _invoke_json(runner, tmp_path, ["config", "path", "--json", "--compact"])
    assert config_path["path"].endswith("config.yml")
    assert config_path["exists"] is False

    initial = _invoke_json(runner, tmp_path, ["config", "show", "--json", "--compact"])
    assert initial["exists"] is False
    assert initial["effective"]["proxy"]["url"] == []
    assert initial["effective"]["proxy"]["token"] == ""
    assert initial["sources"] == {"proxy.url": "missing", "proxy.token": "missing"}

    url_result = _invoke_json(
        runner,
        tmp_path,
        [
            "config",
            "set",
            "proxy.url",
            "https://a.example.com,https://b.example.com/",
            "--json",
            "--compact",
        ],
    )
    assert url_result["value"] == ["https://a.example.com", "https://b.example.com"]

    token_result = _invoke_json(
        runner,
        tmp_path,
        ["config", "set", "proxy.token", secret, "--json", "--compact"],
    )
    assert token_result["value"] == "sec...lue"
    assert secret not in json.dumps(token_result, ensure_ascii=False)

    file_data = yaml.safe_load((tmp_path / "config.yml").read_text(encoding="utf-8"))
    assert file_data == {
        "proxy": {
            "url": ["https://a.example.com", "https://b.example.com"],
            "token": secret,
        }
    }

    shown = _invoke_json(runner, tmp_path, ["config", "show", "--json", "--compact"])
    assert shown["exists"] is True
    assert shown["values"]["proxy"]["url"] == ["https://a.example.com", "https://b.example.com"]
    assert shown["values"]["proxy"]["token"] == "sec...lue"
    assert shown["effective"]["proxy"]["token"] == "sec...lue"
    assert secret not in json.dumps(shown, ensure_ascii=False)
    assert shown["sources"] == {"proxy.url": "config", "proxy.token": "config"}

    doctor = _invoke_json(runner, tmp_path, ["doctor", "--json", "--compact"])
    assert doctor["proxy_configured"] is True
    assert doctor["proxy_count"] == 2
    proxy_check = next(check for check in doctor["checks"] if check["name"] == "proxy_config")
    assert proxy_check["details"]["source"] == "config"
    assert proxy_check["details"]["proxy_count"] == 2

    env_shown = _invoke_json(
        runner,
        tmp_path,
        ["config", "show", "--json", "--compact"],
        env={
            "WECHAT_PROXY_URL": "https://env.example.com",
            "WECHAT_PROXY_TOKEN": "env-token-secret",
        },
    )
    assert env_shown["values"]["proxy"]["url"] == [
        "https://a.example.com",
        "https://b.example.com",
    ]
    assert env_shown["effective"]["proxy"]["url"] == ["https://env.example.com"]
    assert env_shown["effective"]["proxy"]["token"] == "env...ret"
    assert "env-token-secret" not in json.dumps(env_shown, ensure_ascii=False)
    assert env_shown["sources"] == {"proxy.url": "env", "proxy.token": "env"}

    unset = _invoke_json(
        runner,
        tmp_path,
        ["config", "unset", "proxy.token", "--json", "--compact"],
    )
    assert unset["action"] == "unset"
    assert unset["value"] is None
    file_data = yaml.safe_load((tmp_path / "config.yml").read_text(encoding="utf-8"))
    assert file_data == {"proxy": {"url": ["https://a.example.com", "https://b.example.com"]}}

    config_schema = _invoke_json(runner, tmp_path, ["schema", "config.set", "--json", "--compact"])
    assert config_schema["input_schema"]["title"] == "ConfigSetInput"
    assert config_schema["output_schema"]["title"] == "ConfigMutationOutput"

    show_schema = _invoke_json(runner, tmp_path, ["schema", "config.show", "--json", "--compact"])
    assert show_schema["input_schema"] is None
    assert show_schema["output_schema"]["title"] == "ConfigShowOutput"
