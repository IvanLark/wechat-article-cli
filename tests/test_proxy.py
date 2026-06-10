from wechat_article_cli.proxy import validate_html


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
