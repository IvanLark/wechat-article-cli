"""wechat_article capability 元数据与 doctor 检查。"""

from __future__ import annotations

import os

from wechat_article_cli._toolkit.describe.doctor import BoundDoctorCheck
from wechat_article_cli._toolkit.describe.spec import (
    ArgumentSpec,
    CapabilitySpec,
    CommandSpec,
    DoctorCheckSpec,
    ExampleSpec,
    OutputSpec,
)
from wechat_article_cli._toolkit.runtime.env import EnvRequirement

CAPABILITY_NAME = "wechat_article"
CLI_NAME = "wechat-article"
INSPECTABLE_COMMANDS = (
    "auth",
    "auth.start",
    "auth.confirm",
    "auth.check",
    "account",
    "account.list",
    "account.search",
    "account.add",
    "account.remove",
    "account.import",
    "account.export",
    "group",
    "group.list",
    "group.create",
    "group.delete",
    "group.add",
    "group.remove",
    "article",
    "article.list",
    "article.content",
    "task",
    "task.create",
    "task.list",
    "task.info",
    "task.run",
    "run",
    "run.list",
    "run.status",
    "run.export",
    "doctor",
)

ENV_REQUIREMENTS = [
    EnvRequirement(
        name="WECHAT_PROXY_URL",
        description="文章内容抓取代理地址，多个代理可用逗号分隔",
        required=False,
        secret=False,
    ),
    EnvRequirement(
        name="WECHAT_PROXY_TOKEN",
        description="代理鉴权 token（如果代理服务需要）",
        required=False,
        secret=True,
    ),
]


AUTH_START_SPEC = CommandSpec(
    name="auth.start",
    path="wechat_article.auth.start",
    summary="生成公众号后台登录二维码",
    when_to_use="当当前机器尚未登录公众号后台，或旧凭证失效后需要重新登录时。",
    examples=[
        ExampleSpec(command=f"{CLI_NAME} auth start", description="生成登录二维码，等待用户扫码"),
    ],
    env=ENV_REQUIREMENTS,
    output=OutputSpec(supports_human=True, supports_json=True, supports_yaml=True),
    auth_mode="none",
    mutating=True,
)


AUTH_SPEC = CommandSpec(
    name="auth",
    path="wechat_article.auth",
    summary="管理公众号后台登录态",
    description="负责生成登录二维码、确认扫码状态以及检查当前凭证是否仍然有效。",
    when_to_use="当公众号后台尚未登录、凭证已过期，或执行抓取前想先确认登录状态时。",
    next_steps=[
        f"首次使用时，先执行 `{CLI_NAME} auth start`",
        f"用户扫码后，再执行 `{CLI_NAME} auth confirm`",
        f"日常健康检查可执行 `{CLI_NAME} auth check --json`",
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=True,
)


AUTH_CONFIRM_SPEC = CommandSpec(
    name="auth.confirm",
    path="wechat_article.auth.confirm",
    summary="检查扫码状态并在确认后完成登录",
    when_to_use="用户扫码后，用它来轮询确认状态并保存凭证。",
    examples=[
        ExampleSpec(command=f"{CLI_NAME} auth confirm", description="用户扫码后确认登录"),
    ],
    env=ENV_REQUIREMENTS,
    output=OutputSpec(supports_human=True, supports_json=True, supports_yaml=True),
    auth_mode="none",
    mutating=True,
)


AUTH_CHECK_SPEC = CommandSpec(
    name="auth.check",
    path="wechat_article.auth.check",
    summary="检查当前公众号后台凭证状态",
    when_to_use="当你不确定当前是否已登录，或希望在执行抓取前先做健康检查时。",
    examples=[
        ExampleSpec(command=f"{CLI_NAME} auth check --json", description="结构化输出凭证状态"),
    ],
    env=ENV_REQUIREMENTS,
    output=OutputSpec(supports_human=True, supports_json=True, supports_yaml=True),
    auth_mode="none",
    mutating=False,
)


ACCOUNT_SPEC = CommandSpec(
    name="account",
    path="wechat_article.account",
    summary="搜索、添加、删除和列出公众号",
    when_to_use="当你需要维护公众号本地库，为分组、文章抓取和任务执行准备目标集合时。",
    examples=[
        ExampleSpec(command=f"{CLI_NAME} account list", description="查看本地库中的公众号"),
    ],
    env=ENV_REQUIREMENTS,
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="required",
    mutating=True,
    next_steps=[
        f"先用 `{CLI_NAME} account search <关键词>` 找到公众号",
        f"再用 `{CLI_NAME} account add <名称>` 加入本地库",
        f"如果你已经有公众号清单 JSON，可直接执行 `{CLI_NAME} account import <json路径>` 批量导入",
    ],
)


ACCOUNT_LIST_SPEC = CommandSpec(
    name="account.list",
    path="wechat_article.account.list",
    summary="列出本地库中的公众号",
    when_to_use="当你需要确认当前已经保存了哪些公众号，或核对某个分组的成员时。",
    examples=[
        ExampleSpec(command=f"{CLI_NAME} account list", description="查看全部公众号"),
        ExampleSpec(command=f"{CLI_NAME} account list --group Agent资讯", description="查看某个分组内的公众号"),
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=False,
)


ACCOUNT_SEARCH_SPEC = CommandSpec(
    name="account.search",
    path="wechat_article.account.search",
    summary="搜索公众号",
    when_to_use="当你准备把公众号加入本地库之前，先搜索确认目标公众号时。",
    arguments=[
        ArgumentSpec(name="query", description="搜索关键词", required=True, positional=True, value_type="string"),
    ],
    examples=[
        ExampleSpec(command=f"{CLI_NAME} account search AI新榜", description="搜索公众号"),
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="required",
    mutating=False,
)


ACCOUNT_ADD_SPEC = CommandSpec(
    name="account.add",
    path="wechat_article.account.add",
    summary="把公众号加入本地库",
    when_to_use="当你已经搜索到目标公众号，想把它沉淀到本地库并用于后续分组、任务和抓取时。",
    arguments=[
        ArgumentSpec(name="names", description="公众号名称，多个用逗号分隔", required=True, positional=True, value_type="string"),
    ],
    examples=[
        ExampleSpec(command=f"{CLI_NAME} account add AI新榜", description="添加一个公众号"),
    ],
    next_steps=[
        f"添加后可执行 `{CLI_NAME} group add <分组名> <名称>`",
        f"也可以直接执行 `{CLI_NAME} article list <名称>`",
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="required",
    mutating=True,
)


ACCOUNT_REMOVE_SPEC = CommandSpec(
    name="account.remove",
    path="wechat_article.account.remove",
    summary="从本地库删除公众号",
    when_to_use="当某个公众号不再需要跟踪，或需要从所有工作流中移除时。",
    arguments=[
        ArgumentSpec(name="name", description="公众号名称", required=True, positional=True, value_type="string"),
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=True,
)


ACCOUNT_IMPORT_SPEC = CommandSpec(
    name="account.import",
    path="wechat_article.account.import",
    summary="从 JSON 文件批量导入公众号到本地库",
    when_to_use="当你已经有一份公众号清单 JSON，不想再逐个 search/add，以避免频繁搜索触发风控时。",
    arguments=[
        ArgumentSpec(name="json_path", description="公众号 JSON 文件路径", required=True, positional=True, value_type="path"),
    ],
    examples=[
        ExampleSpec(command=f"{CLI_NAME} account import ./公众号列表.json", description="批量导入公众号"),
    ],
    next_steps=[
        f"导入后可执行 `{CLI_NAME} account list` 检查结果",
        f"如需分组，可执行 `{CLI_NAME} group add <分组名> <名称>`",
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=True,
)


ACCOUNT_EXPORT_SPEC = CommandSpec(
    name="account.export",
    path="wechat_article.account.export",
    summary="把本地库中的公众号导出为 JSON",
    when_to_use="当你希望备份公众号本地库，或把现有公众号列表迁移到别的工作区时。",
    arguments=[
        ArgumentSpec(name="json_path", description="导出的 JSON 文件路径", required=True, positional=True, value_type="path"),
    ],
    examples=[
        ExampleSpec(command=f"{CLI_NAME} account export ./公众号列表.json", description="导出本地库"),
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=False,
)


GROUP_SPEC = CommandSpec(
    name="group",
    path="wechat_article.group",
    summary="管理公众号分组",
    when_to_use="当你希望把公众号按主题或工作流场景组织起来，供后续 task 批量执行时。",
    examples=[
        ExampleSpec(command=f"{CLI_NAME} group list", description="查看所有分组"),
    ],
    env=ENV_REQUIREMENTS,
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=True,
    next_steps=[
        f"创建分组后，可执行 `{CLI_NAME} group add <分组名> <名称>`",
        f"准备批量抓取时，可执行 `{CLI_NAME} task create --group <分组名>`",
    ],
)


GROUP_LIST_SPEC = CommandSpec(
    name="group.list",
    path="wechat_article.group.list",
    summary="列出所有分组",
    when_to_use="当你需要查看当前有哪些分组，以及每个分组的公众号成员时。",
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=False,
)


GROUP_CREATE_SPEC = CommandSpec(
    name="group.create",
    path="wechat_article.group.create",
    summary="创建一个新分组",
    arguments=[
        ArgumentSpec(name="name", description="分组名", required=True, positional=True, value_type="string"),
    ],
    next_steps=[
        f"创建后可执行 `{CLI_NAME} group add <分组名> <名称>`",
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=True,
)


GROUP_DELETE_SPEC = CommandSpec(
    name="group.delete",
    path="wechat_article.group.delete",
    summary="删除分组",
    arguments=[
        ArgumentSpec(name="name", description="分组名", required=True, positional=True, value_type="string"),
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=True,
)


GROUP_ADD_SPEC = CommandSpec(
    name="group.add",
    path="wechat_article.group.add",
    summary="把公众号加入分组",
    arguments=[
        ArgumentSpec(name="group_name", description="分组名", required=True, positional=True, value_type="string"),
        ArgumentSpec(name="names", description="公众号名称，多个用逗号分隔", required=True, positional=True, value_type="string"),
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=True,
)


GROUP_REMOVE_SPEC = CommandSpec(
    name="group.remove",
    path="wechat_article.group.remove",
    summary="从分组中移除公众号",
    arguments=[
        ArgumentSpec(name="group_name", description="分组名", required=True, positional=True, value_type="string"),
        ArgumentSpec(name="name", description="公众号名称", required=True, positional=True, value_type="string"),
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=True,
)


ARTICLE_LIST_SPEC = CommandSpec(
    name="article.list",
    path="wechat_article.article.list",
    summary="列出指定公众号或分组的文章列表",
    when_to_use="当你已经配置好公众号库或分组，想先拿到文章目录再决定后续抓取动作时。",
    arguments=[
        ArgumentSpec(name="name", description="公众号名称", required=False, positional=True, value_type="string"),
    ],
    examples=[
        ExampleSpec(command=f"{CLI_NAME} article list AI新榜", description="列出指定公众号文章"),
        ExampleSpec(command=f"{CLI_NAME} article list --group Agent资讯 --json", description="列出分组文章并输出 JSON"),
    ],
    env=ENV_REQUIREMENTS,
    output=OutputSpec(supports_human=True, supports_json=True, supports_yaml=True),
    auth_mode="required",
    mutating=False,
    prerequisites=[
        "已登录公众号后台",
        "已添加目标公众号，或已创建目标分组",
    ],
    next_steps=[
        "拿到文章链接后，可执行 `wechat-article article content <链接>` 抓取正文",
        "也可以通过 task/create/run 把批量抓取工作流固化下来",
    ],
)


ARTICLE_SPEC = CommandSpec(
    name="article",
    path="wechat_article.article",
    summary="查看文章列表并抓取文章正文",
    description="包含两个主要动作：先列文章列表，再按链接抓取正文内容。",
    when_to_use="当你已经有公众号或分组，希望开始真正获取文章信息与正文时。",
    next_steps=[
        f"先执行 `{CLI_NAME} article list <名称>` 或 `--group <分组>`",
        f"拿到链接后，再执行 `{CLI_NAME} article content <链接>`",
    ],
    failure_recovery=[
        "如果正文抓取失败，优先检查代理配置是否齐全",
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=False,
)


ARTICLE_CONTENT_SPEC = CommandSpec(
    name="article.content",
    path="wechat_article.article.content",
    summary="获取指定公众号文章内容",
    when_to_use="当你已经拿到文章链接，准备抓取正文、沉淀 Markdown，或交给 AI 继续处理时。",
    arguments=[
        ArgumentSpec(name="link", description="文章链接", required=True, positional=True, value_type="string"),
    ],
    examples=[
        ExampleSpec(command=f"{CLI_NAME} article content <链接> --format md", description="抓取文章内容为 Markdown"),
    ],
    env=ENV_REQUIREMENTS,
    output=OutputSpec(supports_human=True, supports_json=True, supports_yaml=True),
    auth_mode="none",
    mutating=False,
    next_steps=[
        "抓取正文后，可交给 Obsidian/飞书等后续能力继续处理",
    ],
    failure_recovery=[
        "如果直连失败，优先检查 `WECHAT_PROXY_URL` 是否配置",
    ],
)


TASK_SPEC = CommandSpec(
    name="task",
    path="wechat_article.task",
    summary="管理公众号批量抓取任务",
    description="任务是可复用的抓取模板，执行后会生成 run。",
    when_to_use="当你不想每次手工指定公众号和抓取参数，而是希望把批量工作固化成可重复执行的任务时。",
    examples=[
        ExampleSpec(command=f"{CLI_NAME} task list", description="查看任务列表"),
    ],
    env=ENV_REQUIREMENTS,
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=True,
    next_steps=[
        f"创建任务后，可执行 `{CLI_NAME} task run <task_id>`",
        f"执行后可用 `{CLI_NAME} run status <run_id>` 查看结果",
    ],
)


TASK_CREATE_SPEC = CommandSpec(
    name="task.create",
    path="wechat_article.task.create",
    summary="创建批量抓取任务",
    when_to_use="当你已经整理好公众号或分组，准备把抓取动作固化成可重复执行的任务时。",
    examples=[
        ExampleSpec(command=f"{CLI_NAME} task create --group Agent资讯 --name 每日Agent资讯", description="按分组创建任务"),
    ],
    next_steps=[
        f"创建后可执行 `{CLI_NAME} task run <task_id>` 直接跑一次",
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=True,
)


TASK_LIST_SPEC = CommandSpec(
    name="task.list",
    path="wechat_article.task.list",
    summary="列出所有任务",
    when_to_use="当你需要查看已经定义了哪些任务模板，并决定下一步要运行哪个任务时。",
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=False,
)


TASK_INFO_SPEC = CommandSpec(
    name="task.info",
    path="wechat_article.task.info",
    summary="查看某个任务的详情",
    when_to_use="当你拿到 task_id，需要确认任务配置、目标公众号和抓取参数时。",
    arguments=[
        ArgumentSpec(name="task_id", description="任务 ID", required=True, positional=True, value_type="string"),
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=False,
)


TASK_RUN_SPEC = CommandSpec(
    name="task.run",
    path="wechat_article.task.run",
    summary="执行一次任务并生成 run",
    when_to_use="当任务定义已经准备好，准备实际拉取文章并生成执行记录时。",
    arguments=[
        ArgumentSpec(name="task_id", description="任务 ID", required=True, positional=True, value_type="string"),
    ],
    next_steps=[
        f"执行后可用 `{CLI_NAME} run status <run_id>` 查看详情",
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=True,
)


RUN_SPEC = CommandSpec(
    name="run",
    path="wechat_article.run",
    summary="查看和导出任务执行记录",
    when_to_use="当任务已经执行过，你想查看执行情况、失败原因或导出结果时。",
    examples=[
        ExampleSpec(command=f"{CLI_NAME} run list", description="查看执行记录"),
    ],
    env=ENV_REQUIREMENTS,
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=False,
    next_steps=[
        f"先执行 `{CLI_NAME} run list` 找到 run_id",
        f"再执行 `{CLI_NAME} run status <run_id>` 或 `run export <run_id>`",
    ],
)


RUN_LIST_SPEC = CommandSpec(
    name="run.list",
    path="wechat_article.run.list",
    summary="列出执行记录",
    when_to_use="当你需要浏览历史执行记录，并决定查看哪个 run 的详情时。",
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=False,
)


RUN_STATUS_SPEC = CommandSpec(
    name="run.status",
    path="wechat_article.run.status",
    summary="查看某次执行记录的详情",
    when_to_use="当你要查看某次执行的进度、统计和每个公众号的结果时。",
    arguments=[
        ArgumentSpec(name="run_id", description="运行记录 ID", required=True, positional=True, value_type="string"),
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=False,
)


RUN_EXPORT_SPEC = CommandSpec(
    name="run.export",
    path="wechat_article.run.export",
    summary="导出某次执行记录的结果",
    when_to_use="当你已经确认某次 run 有价值，准备把结果落成 JSON/CSV/Excel 做后续分析或分享时。",
    arguments=[
        ArgumentSpec(name="run_id", description="运行记录 ID", required=True, positional=True, value_type="string"),
    ],
    examples=[
        ExampleSpec(command=f"{CLI_NAME} run export <run_id> --format json", description="导出为 JSON"),
    ],
    next_steps=[
        "导出后可把结果进一步沉淀到 Obsidian、飞书或别的后续能力",
    ],
    output=OutputSpec(supports_human=True, supports_json=False, supports_yaml=False),
    auth_mode="none",
    mutating=False,
)


DOCTOR_SPEC = CommandSpec(
    name="doctor",
    path="wechat_article.doctor",
    summary="检查 wechat_article 的凭证、代理和状态文件",
    when_to_use="当文章抓取失败、任务跑不动，或你不确定当前凭证和代理状态时。",
    examples=[
        ExampleSpec(command=f"{CLI_NAME} doctor --json", description="结构化诊断输出"),
    ],
    env=ENV_REQUIREMENTS,
    output=OutputSpec(supports_human=True, supports_json=True, supports_yaml=True),
    auth_mode="none",
    mutating=False,
)


INSPECT_SPEC = CommandSpec(
    name="inspect",
    path="wechat_article.inspect",
    summary="查看 wechat_article 命令的自描述信息",
    when_to_use="当你不确定某个命令适合什么场景，或希望 Agent 自学这个 capability 时。",
    arguments=[
        ArgumentSpec(name="command_name", description="要查看的命令名", required=True, positional=True, value_type="string")
    ],
    examples=[
        ExampleSpec(command=f"{CLI_NAME} inspect article.list --json", description="查看 article.list 的命令描述"),
    ],
    output=OutputSpec(supports_human=True, supports_json=True, supports_yaml=True),
    auth_mode="none",
    mutating=False,
)


SCHEMA_SPEC = CommandSpec(
    name="schema",
    path="wechat_article.schema",
    summary="查看 wechat_article 命令的输入/输出 schema",
    when_to_use="当你需要程序化理解某个命令的输入输出结构时。",
    arguments=[
        ArgumentSpec(name="command_name", description="要查看 schema 的命令名", required=True, positional=True, value_type="string")
    ],
    examples=[
        ExampleSpec(command=f"{CLI_NAME} schema article.list --json", description="查看 article.list 的 schema"),
    ],
    output=OutputSpec(supports_human=True, supports_json=True, supports_yaml=True),
    auth_mode="none",
    mutating=False,
)


CAPABILITY_SPEC = CapabilitySpec(
    name=CAPABILITY_NAME,
    kind="source",
    summary="微信公众号能力：登录、账号管理、分组、文章抓取、任务与执行记录",
    description="当前优先收编 auth/article/task/run 四块核心流程，account/group 暂时保留旧逻辑外壳包裹。",
    cli_name=CLI_NAME,
    background="微信公众号能力不是个人微信聊天能力，它依赖公众号后台登录态、公众号库、分组、任务和执行记录这些状态层。",
    when_to_use="当你希望批量跟踪某些公众号、拉取文章、沉淀正文并形成后续知识处理 workflow 时。",
    quick_start=[
        ExampleSpec(command="wechat-article auth start", description="先生成二维码登录公众号后台"),
        ExampleSpec(command="wechat-article doctor --json", description="检查当前凭证、代理和状态"),
    ],
    next_steps=[
        "登录后先用 account/group 维护公众号与分组",
        "需要正文时，用 article list/content；需要批量化时，用 task/run",
    ],
    commands=[
        AUTH_START_SPEC,
        AUTH_CONFIRM_SPEC,
        AUTH_CHECK_SPEC,
        AUTH_SPEC,
        ACCOUNT_SPEC,
        ACCOUNT_LIST_SPEC,
        ACCOUNT_SEARCH_SPEC,
        ACCOUNT_ADD_SPEC,
        ACCOUNT_REMOVE_SPEC,
        ACCOUNT_IMPORT_SPEC,
        ACCOUNT_EXPORT_SPEC,
        GROUP_SPEC,
        GROUP_LIST_SPEC,
        GROUP_CREATE_SPEC,
        GROUP_DELETE_SPEC,
        GROUP_ADD_SPEC,
        GROUP_REMOVE_SPEC,
        ARTICLE_SPEC,
        ARTICLE_LIST_SPEC,
        ARTICLE_CONTENT_SPEC,
        TASK_SPEC,
        TASK_CREATE_SPEC,
        TASK_LIST_SPEC,
        TASK_INFO_SPEC,
        TASK_RUN_SPEC,
        RUN_SPEC,
        RUN_LIST_SPEC,
        RUN_STATUS_SPEC,
        RUN_EXPORT_SPEC,
        DOCTOR_SPEC,
        INSPECT_SPEC,
        SCHEMA_SPEC,
    ],
    env=ENV_REQUIREMENTS,
    doctor_checks=[
        DoctorCheckSpec(name="auth_status", description="凭证是否存在且有效"),
        DoctorCheckSpec(name="proxy_config", description="代理配置是否存在"),
        DoctorCheckSpec(name="saved_accounts", description="本地公众号库是否可读取"),
        DoctorCheckSpec(name="tasks_store", description="任务定义是否可读取"),
        DoctorCheckSpec(name="runs_store", description="执行记录目录是否可读取"),
    ],
)


COMMAND_SPECS = {
    "auth.start": AUTH_START_SPEC,
    "auth.confirm": AUTH_CONFIRM_SPEC,
    "auth.check": AUTH_CHECK_SPEC,
    "auth": AUTH_SPEC,
    "account": ACCOUNT_SPEC,
    "account.list": ACCOUNT_LIST_SPEC,
    "account.search": ACCOUNT_SEARCH_SPEC,
    "account.add": ACCOUNT_ADD_SPEC,
    "account.remove": ACCOUNT_REMOVE_SPEC,
    "account.import": ACCOUNT_IMPORT_SPEC,
    "account.export": ACCOUNT_EXPORT_SPEC,
    "group": GROUP_SPEC,
    "group.list": GROUP_LIST_SPEC,
    "group.create": GROUP_CREATE_SPEC,
    "group.delete": GROUP_DELETE_SPEC,
    "group.add": GROUP_ADD_SPEC,
    "group.remove": GROUP_REMOVE_SPEC,
    "article": ARTICLE_SPEC,
    "article.list": ARTICLE_LIST_SPEC,
    "article.content": ARTICLE_CONTENT_SPEC,
    "task": TASK_SPEC,
    "task.create": TASK_CREATE_SPEC,
    "task.list": TASK_LIST_SPEC,
    "task.info": TASK_INFO_SPEC,
    "task.run": TASK_RUN_SPEC,
    "run": RUN_SPEC,
    "run.list": RUN_LIST_SPEC,
    "run.status": RUN_STATUS_SPEC,
    "run.export": RUN_EXPORT_SPEC,
    "doctor": DOCTOR_SPEC,
    "inspect": INSPECT_SPEC,
    "schema": SCHEMA_SPEC,
}


def get_capability_spec() -> CapabilitySpec:
    return CAPABILITY_SPEC


def get_command_spec(name: str) -> CommandSpec:
    try:
        return COMMAND_SPECS[name]
    except KeyError as exc:
        raise KeyError(f"未知 wechat_article 命令：{name}") from exc


def build_doctor_checks() -> list[BoundDoctorCheck]:
    return [
        BoundDoctorCheck(
            spec=DoctorCheckSpec(name="auth_status", description="凭证是否存在且有效"),
            runner=lambda: _check_auth_status(),
        ),
        BoundDoctorCheck(
            spec=DoctorCheckSpec(name="proxy_config", description="代理配置是否存在"),
            runner=lambda: {
                "ok": True,
                "message": "已配置 WECHAT_PROXY_URL" if os.environ.get("WECHAT_PROXY_URL") else "未配置 WECHAT_PROXY_URL，文章正文将先尝试直连",
                "hint": None if os.environ.get("WECHAT_PROXY_URL") else "直连遇到微信风控时，再配置文章代理",
            },
        ),
        BoundDoctorCheck(
            spec=DoctorCheckSpec(name="saved_accounts", description="本地公众号库是否可读取"),
            runner=lambda: _check_saved_accounts(),
        ),
        BoundDoctorCheck(
            spec=DoctorCheckSpec(name="tasks_store", description="任务定义是否可读取"),
            runner=lambda: _check_tasks_store(),
        ),
        BoundDoctorCheck(
            spec=DoctorCheckSpec(name="runs_store", description="执行记录目录是否可读取"),
            runner=lambda: _check_runs_store(),
        ),
    ]


def _check_auth_status():
    from wechat_article_cli.service import check_auth

    result = check_auth()
    status = result["status"]
    if status == "valid":
        return {"ok": True, "message": "公众号后台凭证有效"}
    if status == "expired":
        return {"ok": False, "message": "公众号后台凭证已过期", "hint": f"请执行 {CLI_NAME} auth start 重新生成二维码"}
    return {"ok": False, "message": "未登录公众号后台", "hint": f"请执行 {CLI_NAME} auth start 生成二维码"}


def _check_saved_accounts():
    from wechat_article_cli.storage import load_saved_accounts

    saved = load_saved_accounts()
    return {"ok": True, "message": f"本地公众号库可读取，当前 {len(saved.accounts)} 个公众号"}


def _check_tasks_store():
    from wechat_article_cli.storage import load_all_tasks

    tasks = load_all_tasks()
    return {"ok": True, "message": f"任务定义可读取，当前 {len(tasks)} 个任务"}


def _check_runs_store():
    from wechat_article_cli.storage import list_run_ids

    runs = list_run_ids()
    return {"ok": True, "message": f"执行记录可读取，当前 {len(runs)} 条 run"}
