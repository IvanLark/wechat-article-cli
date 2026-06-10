# wechat-article-cli

非官方微信公众号文章抓取和本地整理 CLI。

这个工具优先面向 AI / Agent 使用：人负责提出目标，AI 通过结构化 CLI 命令维护公众号库、创建任务、拉文章、抓正文、导出结果。人也可以直接使用这些命令。

它可以完成这些事：

- 扫码登录公众号后台
- 搜索公众号并保存到本地库
- 维护公众号分组
- 导入、导出公众号库和分组配置
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

## 备份和迁移

公众号本地库支持导入、导出：

```bash
wechat-article account export ./accounts.json
wechat-article account import ./accounts.json
```

账号 JSON 可以是数组，也可以是带 `accounts` 字段的对象：

```json
[
  {
    "fakeid": "fakeid_xxx",
    "name": "AI新榜",
    "avatar": "https://...",
    "signature": "公众号简介"
  }
]
```

分组配置也支持导入、导出：

```bash
wechat-article group export ./groups.json
wechat-article group import ./groups.json
```

分组 JSON 可以是数组，也可以是带 `groups` 字段的对象：

```json
[
  {
    "name": "Agent资讯",
    "accounts": ["AI新榜"]
  }
]
```

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

### Cloudflare Worker 私有代理

可以参考 [wechat-article-exporter 私有代理文档](https://docs.mptext.top/get-started/private-proxy.html) 的思路，在 Cloudflare Workers 上部署一个只转发 `mp.weixin.qq.com` 的私有代理节点。

本仓库提供了带简单 token 鉴权的 Worker 示例：

```text
examples/cloudflare-worker.js
```

部署步骤：

1. 打开 Cloudflare 控制台，进入 `Workers 和 Pages`。
2. 创建一个 Worker，选择从 Hello World 开始。
3. 进入编辑代码页面，把 [examples/cloudflare-worker.js](examples/cloudflare-worker.js) 的内容复制进去。
4. 如需鉴权，在 Worker 的环境变量里设置：

```text
WECHAT_PROXY_TOKEN=一段随机字符串
```

5. 保存部署，访问 Worker 地址。如果返回 `缺少 url 参数`，说明 Worker 已经运行。
6. 在本地配置：

```bash
export WECHAT_PROXY_URL="https://your-worker.your-subdomain.workers.dev"
export WECHAT_PROXY_TOKEN="一段随机字符串"
```

如果你部署了多个 Worker，多个地址用英文逗号分隔：

```bash
export WECHAT_PROXY_URL="https://a.example.com,https://b.example.com"
```

安全建议：

- Worker 示例只允许代理 `mp.weixin.qq.com`，避免被当成开放代理滥用。
- 建议设置 `WECHAT_PROXY_TOKEN`，同时不要公开 Worker 地址。
- 发现流量异常时，直接改 token 或删除 Worker 后重新部署。
- 如果使用自定义域名，可以在 Cloudflare 里给 Worker 绑定自定义域名，访问稳定性通常会更好。

## 结构化输出

支持 JSON / YAML：

```bash
wechat-article auth check --json
wechat-article account list --json
wechat-article account export ./accounts.json --json
wechat-article group list --json
wechat-article group export ./groups.json --json
wechat-article task list --json
wechat-article run status <run_id> --json
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

AI 使用建议：

- 先执行 `wechat-article doctor --json` 检查登录、代理和本地状态。
- 用 `wechat-article inspect <command> --json` 判断命令适用场景。
- 用 `wechat-article schema <command> --json` 获取输入输出结构。
- 执行会改变本地状态的命令时，保存返回的 `task_id`、`run_id` 和导出路径。
- `task run --json` 的过程日志会输出到 stderr，stdout 只保留最终 JSON envelope。

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
uv run pytest
uv run wechat-article --help
```
