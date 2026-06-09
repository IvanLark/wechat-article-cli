"""微信公众号 HTTP 客户端

登录流程：start_login → get_qrcode → check_scan_status → execute_login
"""

from __future__ import annotations

import json as json_module
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from loguru import logger

from wechat_article_cli.storage import CN_TZ, Credentials

BASE_URL = "https://mp.weixin.qq.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/117.0.0.0 Safari/537.36"
    ),
    "Referer": "https://mp.weixin.qq.com/",
    "Origin": "https://mp.weixin.qq.com",
}

# 扫码状态码
SCAN_WAITING = 0        # 等待扫码
SCAN_CONFIRMED = 1      # 已确认，可以登录
SCAN_EXPIRED_1 = 2      # 二维码过期
SCAN_EXPIRED_2 = 3      # 二维码过期
SCAN_SCANNED = 4        # 已扫码，等待确认
SCAN_NO_EMAIL = 5       # 账号未绑定邮箱
SCAN_SCANNED_2 = 6      # 已扫码，等待确认


class WeChatClient:
    """微信公众号 API 客户端"""

    def __init__(self, credentials: Optional[Credentials] = None):
        self.credentials = credentials
        self._http = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._http.aclose()

    async def close(self):
        await self._http.aclose()

    def _get_headers(self, include_auth: bool = True) -> dict[str, str]:
        headers = HEADERS.copy()
        if include_auth and self.credentials:
            cookie_str = "; ".join(
                f"{k}={v}" for k, v in self.credentials.cookies.items()
            )
            headers["Cookie"] = cookie_str
        return headers

    # --- 登录流程 ---

    async def start_login(self) -> str:
        """步骤 1：创建登录会话，返回 uuid_cookie"""
        url = f"{BASE_URL}/cgi-bin/bizlogin?action=startlogin"
        sessionid = f"{int(time.time() * 1000)}{random.randint(100, 999)}"

        payload = {
            "userlang": "zh_CN",
            "redirect_url": "",
            "login_type": 3,
            "sessionid": sessionid,
            "token": "",
            "lang": "zh_CN",
            "f": "json",
            "ajax": 1,
        }

        logger.debug("正在创建登录会话...")
        resp = await self._http.post(
            url, data=payload, headers=self._get_headers(include_auth=False)
        )
        resp.raise_for_status()

        uuid_cookie = None
        for cookie in resp.cookies.jar:
            if cookie.name == "uuid":
                uuid_cookie = cookie.value
                break

        if not uuid_cookie:
            raise ValueError("未能获取 uuid cookie")

        logger.debug("登录会话创建成功，uuid={}", uuid_cookie[:8])
        return uuid_cookie

    async def get_qrcode(self, uuid_cookie: str) -> bytes:
        """步骤 2：获取二维码图片"""
        url = (
            f"{BASE_URL}/cgi-bin/scanloginqrcode"
            f"?action=getqrcode&random={int(time.time() * 1000)}"
        )
        headers = self._get_headers(include_auth=False)
        headers["Cookie"] = f"uuid={uuid_cookie}"

        logger.debug("正在获取二维码...")
        resp = await self._http.get(url, headers=headers)
        resp.raise_for_status()
        return resp.content

    async def check_scan_status(self, uuid_cookie: str) -> dict:
        """步骤 3：检查扫码状态（一次性检查，立即返回）"""
        url = (
            f"{BASE_URL}/cgi-bin/scanloginqrcode"
            "?action=ask&token=&lang=zh_CN&f=json&ajax=1"
        )
        headers = self._get_headers(include_auth=False)
        headers["Cookie"] = f"uuid={uuid_cookie}"

        resp = await self._http.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        if data.get("base_resp", {}).get("ret") != 0:
            raise ValueError(f"检查扫码状态失败: {data}")

        return {
            "status": data.get("status", 0),
            "user_category": data.get("user_category", 0),
            "acct_size": data.get("acct_size", 0),
        }

    async def execute_login(self, uuid_cookie: str) -> Credentials:
        """步骤 4：执行登录（扫码确认后调用），返回凭证"""
        url = f"{BASE_URL}/cgi-bin/bizlogin?action=login"
        headers = self._get_headers(include_auth=False)
        headers["Cookie"] = f"uuid={uuid_cookie}"

        payload = {
            "userlang": "zh_CN",
            "redirect_url": "",
            "cookie_forbidden": 0,
            "cookie_cleaned": 0,
            "plugin_used": 0,
            "login_type": 3,
            "token": "",
            "lang": "zh_CN",
            "f": "json",
            "ajax": 1,
        }

        logger.debug("正在执行登录...")
        resp = await self._http.post(url, data=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        if data.get("base_resp", {}).get("ret") != 0:
            raise ValueError(f"登录失败: {data}")

        redirect_url = data.get("redirect_url", "")
        if "token=" not in redirect_url:
            raise ValueError(f"未能从 redirect_url 提取 token: {redirect_url}")

        token = redirect_url.split("token=")[1].split("&")[0]

        cookies = {}
        for cookie in resp.cookies.jar:
            cookies[cookie.name] = cookie.value

        auth_key = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(days=4)

        return Credentials(
            auth_key=auth_key,
            token=token,
            cookies=cookies,
            created_at=created_at.isoformat(),
            expires_at=expires_at.isoformat(),
        )

    # --- 业务 API ---

    @staticmethod
    def _check_api_error(data: dict, action: str) -> None:
        """检查微信 API 返回的通用错误码"""
        ret = data.get("base_resp", {}).get("ret")
        if ret == 0:
            return
        if ret == 200013:
            raise ValueError(
                f"{action}失败：微信频率限制（错误码 200013），请等待约 60 秒后重试"
            )
        if ret in (-1, 200003):
            raise ValueError(
                f"{action}失败：登录凭证已失效（错误码 {ret}）。"
                "请执行 wechat-article auth start 重新生成二维码，需要用户使用微信扫码登录"
            )
        err_msg = data.get("base_resp", {}).get("err_msg", "未知错误")
        raise ValueError(f"{action}失败（错误码 {ret}）：{err_msg}")

    async def search_accounts(self, query: str) -> list[dict]:
        """搜索公众号，返回 fakeid、名称等信息"""
        if not self.credentials:
            raise ValueError("未登录")

        params = {
            "action": "search_biz",
            "query": query,
            "token": self.credentials.token,
            "lang": "zh_CN",
            "f": "json",
            "ajax": "1",
            "begin": 0,
            "count": 5,
        }

        logger.debug("搜索公众号：{}", query)
        resp = await self._http.get(
            f"{BASE_URL}/cgi-bin/searchbiz",
            params=params,
            headers=self._get_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        self._check_api_error(data, "搜索公众号")

        return [
            {
                "fakeid": item.get("fakeid", ""),
                "name": item.get("nickname", ""),
                "avatar": item.get("round_head_img", ""),
                "signature": item.get("signature", ""),
            }
            for item in data.get("list", [])
        ]

    async def get_articles(
        self, fakeid: str, count: int = 5, offset: int = 0
    ) -> list[dict]:
        """获取公众号文章列表"""
        if not self.credentials:
            raise ValueError("未登录")

        params = {
            "sub": "list",
            "search_field": "null",
            "begin": offset,
            "count": min(count, 20),
            "query": "",
            "fakeid": fakeid,
            "type": "101_1",
            "free_publish_type": "1",
            "sub_action": "list_ex",
            "token": self.credentials.token,
            "lang": "zh_CN",
            "f": "json",
            "ajax": "1",
        }

        logger.debug("获取文章列表：fakeid={}, count={}", fakeid, count)
        resp = await self._http.get(
            f"{BASE_URL}/cgi-bin/appmsgpublish",
            params=params,
            headers=self._get_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        self._check_api_error(data, "获取文章列表")

        # 解析嵌套 JSON
        publish_page = data.get("publish_page")
        if isinstance(publish_page, str):
            publish_page = json_module.loads(publish_page)

        publish_list = publish_page.get("publish_list", []) if publish_page else []
        publish_list = [item for item in publish_list if item.get("publish_info")]

        # 提取所有文章，用 aid 去重
        seen_aids: set[str] = set()
        results = []

        for item in publish_list:
            publish_info = item.get("publish_info")
            if isinstance(publish_info, str):
                try:
                    publish_info = json_module.loads(publish_info)
                except json_module.JSONDecodeError:
                    continue

            for article in (publish_info or {}).get("appmsgex", []):
                aid = article.get("aid", "")
                if not aid or aid in seen_aids:
                    continue
                seen_aids.add(aid)

                create_time = article.get("create_time", 0)
                create_date = (
                    datetime.fromtimestamp(create_time, tz=CN_TZ).strftime("%Y-%m-%d")
                    if create_time
                    else ""
                )

                results.append({
                    "aid": aid,
                    "title": article.get("title", ""),
                    "link": article.get("link", ""),
                    "digest": article.get("digest", ""),
                    "create_time": create_time,
                    "create_date": create_date,
                    "cover": article.get("cover", ""),
                    "author": article.get("author_name", article.get("author", "")),
                    "item_show_type": article.get("item_show_type", 0),
                })

        return results
