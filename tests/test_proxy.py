from wechat_article_cli.proxy import validate_html


def test_proxy_settings_read_config_file(tmp_path, monkeypatch) -> None:
    from wechat_article_cli.config import set_config_value
    from wechat_article_cli.proxy import get_proxy_token, get_proxy_urls

    monkeypatch.setenv("WECHAT_ARTICLE_HOME", str(tmp_path))
    monkeypatch.delenv("WECHAT_PROXY_URL", raising=False)
    monkeypatch.delenv("WECHAT_PROXY_TOKEN", raising=False)

    set_config_value("proxy.url", "https://a.example.com,https://b.example.com/")
    set_config_value("proxy.token", "secret-token-value")

    assert get_proxy_urls() == ["https://a.example.com", "https://b.example.com"]
    assert get_proxy_token() == "secret-token-value"


def test_proxy_settings_env_override_config_file(tmp_path, monkeypatch) -> None:
    from wechat_article_cli.config import set_config_value
    from wechat_article_cli.proxy import get_proxy_token, get_proxy_urls

    monkeypatch.setenv("WECHAT_ARTICLE_HOME", str(tmp_path))
    monkeypatch.delenv("WECHAT_PROXY_URL", raising=False)
    monkeypatch.delenv("WECHAT_PROXY_TOKEN", raising=False)

    set_config_value("proxy.url", "https://config.example.com")
    set_config_value("proxy.token", "config-token")
    monkeypatch.setenv("WECHAT_PROXY_URL", "https://env.example.com")
    monkeypatch.setenv("WECHAT_PROXY_TOKEN", "env-token")

    assert get_proxy_urls() == ["https://env.example.com"]
    assert get_proxy_token() == "env-token"


def test_proxy_settings_accept_urls_alias_in_config_file(tmp_path, monkeypatch) -> None:
    from wechat_article_cli.proxy import get_proxy_urls

    monkeypatch.setenv("WECHAT_ARTICLE_HOME", str(tmp_path))
    monkeypatch.delenv("WECHAT_PROXY_URL", raising=False)
    (tmp_path / "config.yml").write_text(
        "proxy:\n  urls:\n    - https://alias.example.com/\n",
        encoding="utf-8",
    )

    assert get_proxy_urls() == ["https://alias.example.com"]


def test_validate_html_success() -> None:
    status, message = validate_html('<html><div id="js_content">正文</div></html>')

    assert status == "success"
    assert message is None


def test_validate_html_deleted() -> None:
    html = """
    <div class="weui-msg">
      <h2 class="weui-msg__title">该内容已被发布者删除</h2>
    </div>
    """

    status, message = validate_html(html)

    assert status == "deleted"
    assert message is None


def test_validate_html_exception_uses_description_when_title_is_empty() -> None:
    html = """
    <div class="weui-msg">
      <h2 class="weui-msg__title"></h2>
      <p class="weui-msg__desc">参数错误</p>
    </div>
    """

    status, message = validate_html(html)

    assert status == "exception"
    assert message == "参数错误"
