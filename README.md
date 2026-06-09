# wechat-article-cli

非官方微信公众号文章抓取和本地整理 CLI。

它可以完成这些事：

- 扫码登录公众号后台
- 搜索公众号并保存到本地库
- 维护公众号分组
- 拉取公众号文章列表
- 抓取文章正文并导出为 Markdown、HTML 或纯文本
- 创建批量抓取任务，查看执行记录并导出结果
- 输出 JSON / YAML，方便脚本和 Agent 调用

## 安装

本项目使用 Python 3.11+。

```bash
pipx install git+https://github.com/IvanLark/wechat-article-cli.git
```

本地开发：

```bash
git clone https://github.com/IvanLark/wechat-article-cli.git
cd wechat-article-cli
uv sync --python 3.11
uv run wechat-article --help
```

## 快速开始

生成登录二维码：

```bash
wechat-article auth start
```

扫码后确认登录：

```bash
wechat-article auth confirm
```

检查状态：

```bash
wechat-article doctor
wechat-article doctor --json
```

搜索公众号：

```bash
wechat-article account search AI新榜
```

把最近一次搜索结果中的公众号加入本地库：

```bash
wechat-article account add AI新榜
```

拉取文章列表：

```bash
wechat-article article list AI新榜 --count 5
```

`--count` 表示向公众号后台请求的图文消息条数。公众号一次推送里可能包含多篇图文，所以最终展示的文章数可能大于 `--count`。

抓取正文为 Markdown：

```bash
wechat-article article content "https://mp.weixin.qq.com/s/..." --format md
```

## 数据目录

默认数据目录：

```text
~/.wechat-article
```

可以通过环境变量修改：

```bash
export WECHAT_ARTICLE_HOME="$HOME/.wechat-article"
```

目录里会保存登录凭证、二维码、公众号本地库、分组、任务、执行记录和导出文件。凭证文件包含 Cookie 和 token，请妥善保管。

## 代理配置

文章正文会先尝试直连。遇到微信风控拦截时，可以配置代理服务：

```bash
export WECHAT_PROXY_URL="https://your-worker.example.com"
export WECHAT_PROXY_TOKEN="your-token"
```

多个代理用英文逗号分隔：

```bash
export WECHAT_PROXY_URL="https://a.example.com,https://b.example.com"
```

代理接口约定：

```text
GET <proxy>?url=<encoded_article_url>&authorization=<token>
```

登录、搜索公众号、拉取文章列表走公众号后台接口，一般无需代理。代理只用于文章正文页面抓取。

## 结构化输出

支持 JSON / YAML：

```bash
wechat-article auth check --json
wechat-article article list AI新榜 --json
wechat-article inspect article.content --json
wechat-article schema article.content --json
```

输出会带统一 envelope：

```json
{
  "ok": true,
  "schema_version": "1",
  "data": {}
}
```

## 批量任务

创建分组：

```bash
wechat-article group create Agent资讯
wechat-article group add Agent资讯 AI新榜
```

创建任务：

```bash
wechat-article task create --group Agent资讯 --name 每日Agent资讯 --count 5
```

执行任务：

```bash
wechat-article task run <task_id>
```

查看和导出执行记录：

```bash
wechat-article run list
wechat-article run status <run_id>
wechat-article run export <run_id> --format json
wechat-article run export <run_id> --format csv
wechat-article run export <run_id> --format excel
```

导出的 JSON/CSV/Excel 会包含正文状态和正文错误：

- `cached`：正文来自本地缓存
- `fetched`：本次执行新抓取成功
- `failed`：正文抓取失败，错误原因会写入导出文件

## 命令自描述

这个工具内置了面向脚本和 Agent 的自描述命令：

```bash
wechat-article inspect article.content
wechat-article schema article.content --json
wechat-article doctor --json
```

## 注意事项

这是非官方工具，依赖微信公众号后台网页流程。请遵守微信公众平台规则、目标内容授权、版权要求和当地法律法规。

建议控制访问频率，用于个人备份、研究和整理自己有权访问的内容。工具不会内置代理服务，也不会替你判断内容使用权限。

## 开发

```bash
uv sync --python 3.11
uv run ruff check src/wechat_article_cli
uv run wechat-article --help
```
